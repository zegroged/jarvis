# Ransomware Olay Müdahalesi: Bir DFIR Lead'in Saha Defteri

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Ransomware olayları artık "bir sabah dosyalar şifrelenmiş" vakası değil. Modern ransomware bir **son perde**. Şifreleme tuşuna basıldığında saldırgan ağınızda genellikle **günlerdir, çoğu zaman haftalardır** oturuyor. Şifreleme; keşif, yatay hareket, kimlik bilgisi hırsızlığı ve veri sızdırma (exfiltration) tamamlandıktan sonra atılan son adımdır. Bu yüzden bir DFIR lead olarak benim işim "şifreyi kim çözecek" değildir; işim **saldırının tüm hikâyesini kronolojik olarak yeniden inşa etmektir**: nereden girdiler (initial access), ne zaman girdiler, hangi hesapları ele geçirdiler, hangi makinelere yayıldılar, **veri dışarı çıktı mı**, ve backup'lara dokundular mı.

Bu iş akışının IR sürecindeki (PICERL: Prepare, Identify, Contain, Eradicate, Recover, Lessons) yeri **Identify ve Containment'ın kesiştiği yer**. Ama ransomware'de sıra oynar: containment bazen identification'dan önce gelir, çünkü hâlâ aktif şifreleme varsa saniyeler önemlidir. Benim önceliğim şudur:

1. **Kanamayı durdur** (aktif şifreleme/yayılmayı izole et) — ama delil öldürmeden.
2. **Uçucu delili topla** (order of volatility).
3. **Hasta sıfırı ve giriş noktasını bul** (patient zero).
4. **Sızdırma oldu mu, olduysa ne çıktı** — bu artık en kritik hukuki/iş sorusudur.
5. **Kapsamı çıkar** (scope): hangi hesaplar, hangi makineler kirli.
6. **Temizle ve geri dön** — ama aynı delikten tekrar girilmeyeceğinden emin olarak.

En sık yapılan yönetsel hata şudur: yönetim "ne zaman iş başına döneriz" diye baskı yapar, ve ekip *scope* çıkmadan restore'a başlar. Scope bilinmeden yapılan restore, saldırganın hâlâ ağda olduğu bir ortama temiz makineleri geri koymaktır — yani ikinci şifrelemeye davetiye. Benim kırmızı çizgim: **kimlik hijyeni (parola sıfırlama + kirli hesapların tespiti) ve giriş noktasının kapatılması yapılmadan hiçbir restore yok.**

---

## 2. Adım-adım İŞ AKIŞI ve KARAR (asıl değer)

### Adım 0 — Triyaj ve "durdur ama öldürme" kararı (ilk 30 dakika)

Telefon çaldığında sorduğum ilk üç şey:
- **Şifreleme hâlâ aktif mi?** (Kullanıcılar canlı olarak dosyaların şifrelendiğini görüyor mu, disk I/O anormal mi?)
- **Etki alanı denetleyicisi (Domain Controller) etkilendi mi?** DC kirliyse oyun tamamen değişir — tüm domain kimlikleri yakılmış sayılır.
- **Backup'lar erişilebilir/sağlam mı?** (Ve backup sunucusu domain'e bağlı mı? Bağlıysa muhtemelen o da hedeflenmiştir.)

**Kritik containment kararı**: Etkilenen makineleri **kapatmam** — kapatmak RAM'i, dolayısıyla şifreleme anahtarlarını, çalışan zararlı process'leri ve ağ bağlantılarını yok eder. Bunun yerine **ağdan izole ederim**: switch port'unu kapatmak, EDR'ın "network containment/isolate host" özelliğini kullanmak, ya da fiziksel olarak kabloyu çekmek. Makine açık kalır, ama konuşamaz. EDR (CrowdStkrike, Defender for Endpoint, SentinelOne vb.) "isolate" yaptığında bile kendi konsoluyla konuşmaya devam eder — bu bize hâlâ görünürlük verir.

**İstisna**: Aktif, yayılan şifreleme varsa ve izolasyon yeterince hızlı yapılamıyorsa, veri kaybını durdurmak için kapatma gerekebilir. Bu bir maliyet-fayda kararıdır: kaybedilecek RAM delili mi ağır basar, yoksa şifrelenecek yeni terabaytlar mı? Genelde birkaç makineyi kurtarmak için RAM'i feda etmem; ama **patient zero adayı makineyi mümkünse hep açık ve izole tutarım**, çünkü en değerli delil orada.

### Adım 1 — Uçucu delil toplama (Order of Volatility'ye göre)

Order of Volatility ilkesi: en hızlı kaybolan delili önce topla. Sıram:

1. **RAM imajı** — açık ve izole tuttuğum kritik makinelerden. Araç: `WinPmem`, `Magnet RAM Capture`, ya da EDR'ın memory acquisition özelliği. RAM'de aradığım: enjekte edilmiş process'ler, C2 bağlantıları, bazen şifreleme anahtarları, `lsass.exe`'den dump alınıp alınmadığının izleri, PowerShell komut geçmişi.
2. **Ağ bağlantıları ve process listesi** — canlı yanıt (live response) ile. `netstat`, çalışan process ağacı, açık handle'lar. EDR telemetrisi bunun çoğunu zaten pasif olarak topluyor olur.
3. **Disk / triyaj imajı** — burada **KAPE** (Kroll Artifact Parser and Extractor) benim baş silahım. Tam disk imajı almak saatler alır; KAPE ile "targeted collection" yaparak sadece adli değeri olan artefaktları (MFT, USN Journal, Event Log'lar, Registry hive'ları, Prefetch, SRUM, Amcache, ShimCache, tarayıcı geçmişi, PowerShell logları) dakikalar içinde toplarım. Yüzlerce makineyi tam imajlamak imkânsızdır; **triyaj imajı** ölçeklenebilir tek yoldur.
4. **Log'lar** — henüz döngüsel olarak (log rotation) silinmeden Windows Event Log'ları, EDR/SIEM export'ları, firewall ve VPN log'ları, DHCP log'ları (IP-makine eşlemesi için kritik).

Ölçek için: tek tek makinelere elle girmem. **Velociraptor** ile filo genelinde (fleet-wide) hunt yaparım. Velociraptor'un gücü şu: tek bir VQL sorgusuyla "tüm ağda şu IOC'yu, şu registry anahtarını, şu dosya hash'ini, şu scheduled task'ı taşıyan makineleri getir" diyebilirim. Ransomware'de scope çıkarmanın en hızlı yolu budur.

### Adım 2 — Zaman tünelini kur ve patient zero'yu bul

Şimdi asıl DFIR işi başlıyor: **timeline analizi**. Toplanan artefaktları **Eric Zimmerman araçlarıyla** ayrıştırırım:

- **MFTECmd** → `$MFT` ve `$UsnJrnl` ayrıştırma. Dosya oluşturma/değiştirme zamanları, şifrelenmiş dosyaların ve fidye notunun (ör. `readme.txt`, `RECOVER-FILES.hta`) ilk ne zaman ortaya çıktığı. USN Journal fidye notunun tam olarak hangi saniyede yazıldığını gösterir — bu şifreleme başlangıç anıdır (T-zero değil, ama son perde anı).
- **PECmd** → Prefetch analizi. Hangi çalıştırılabilirler ne zaman ilk kez koştu? Şifreleyici binary'nin (encryptor) ilk çalışma zamanı burada. `psexec.exe`, `rclone.exe`, `mimikatz` benzeri araçların Prefetch izleri altın değerindedir.
- **AmcacheParser / AppCompatCacheParser (ShimCache)** → Bir binary'nin sistemde *varlığının* kanıtı, çalışmasa bile. Saldırganın bıraktığı ama henüz koşmamış araçları yakalar.
- **SBECmd** → ShellBags: saldırganın hangi klasörlerde gezindiği (interaktif keşif).
- **SrumECmd** → SRUM: uygulama başına ağ trafiği baytları. **Exfiltration'ı ispatlamak için kritik** — hangi process ne kadar veri *dışarı* gönderdi. `rclone.exe` ya da tarayıcı 40 GB upload yaptıysa SRUM bunu söyler.
- **RECmd / Registry Explorer** → Registry hive analizi: persistence (Run anahtarları, Services), RDP kullanım izleri, çalıştırılan komutlar.

Tüm bunları **süper-zaman-tüneli (super timeline)** olarak birleştiririm. Plaso/log2timeline ham gücü verir ama gürültülüdür; ben genelde **Timesketch** ile çalışırım — birden fazla makinenin timeline'ını tek bir görselleştirilmiş sketch'te birleştirip, "şu 6 dakikalık pencerede ne oldu" diye pivot yaparım. Ekip halinde aynı sketch üzerinde etiketleme (tagging) yapmak scope'u hızla büyütür.

**Patient zero'ya nasıl varırım — "şu artefaktı görünce şu sonuca giderim" mantığı:**

- Şifreleme başlangıç zamanından **geriye doğru** sararım. Şifreleyici hangi hesapla, hangi makineden dağıtıldı?
- Şifreleyici genellikle **GPO**, **PsExec**, **WMI** ya da **PDQ/SCCM** gibi bir dağıtım mekanizmasıyla toplu itilir. WMI kullanımını görürsem (`wmic /node:... process call create` ya da `Win32_Process` üzerinden uzaktan execution), **Event ID 4688** (process creation) ve **WMI-Activity/Operational** log'una (`Microsoft-Windows-WMI-Activity/Operational`, Event ID 5857/5860/5861) bakarım. WMI ile lateral movement, ATT&CK **T1047**'nin klasik izidir ve genelde 135/5985 portları üzerinden gelir.
- Lateral movement zincirini takip ederim: her "sıçrama" makinesinde **kimlik doğrulama log'ları** (Security Event ID **4624** logon, özellikle **Type 3** ağ ve **Type 10** RDP; **4648** explicit credential) ve **4672** (özel ayrıcalık atanan logon = admin). Bir hesabın anormal makinelerde peş peşe Type 3 logon'ları = credential ile yayılma.
- Zinciri geriye sararak, **ilk anormal aktivitenin** olduğu makineye ve **ilk ele geçirilen hesaba** ulaşırım. İşte patient zero ve initial access vektörü orası.

**Initial access — ne ararım:**
- **Dışa açık RDP** → 4624 Type 10, kaynağı yabancı IP; öncesinde bir sürü 4625 (başarısız logon = brute force). En yaygın giriş.
- **VPN / firewall zafiyeti** → VPN log'unda anormal coğrafyadan başarılı giriş, MFA'nın atlandığı hesap.
- **Phishing** → Kullanıcı makinesinde e-posta ekinden çalışan bir loader; Prefetch'te Office → wscript/powershell zinciri, tarayıcı/Outlook geçmişi.
- **Zafiyet istismarı** (ör. dışa açık bir uygulama sunucusu) → web sunucusu log'unda anormal POST, ardından web shell.

### Adım 3 — Kimlik bilgisi hırsızlığını doğrula (bu, kapsamı belirler)

Saldırgan yayılmak için **mutlaka** kimlik çaldı. Bunu ispatlamak, "hangi hesaplar yakıldı"yı belirler — yani parola sıfırlama kapsamını. Aradıklarım (saldırgan prosedürleriyle eşlemeli):

- **LSASS dump (T1003.001)**: `lsass.exe`'ye erişen anormal process (EDR'da görülür), ya da diskte `lsass.dmp`. `comsvcs.dll MiniDump`, `procdump -ma lsass`, ya da doğrudan Mimikatz izleri.
- **SAM hive hırsızlığı (T1003.002)**: Bu yazının referansındaki prosedür. Diskte/komut geçmişinde `reg save HKLM\SAM sam` ve `reg save HKLM\SYSTEM system` görürsem, saldırgan yerel hesap hash'lerini almış demektir. Prefetch'te `reg.exe`, ya da 4688'de bu komut satırı. Yerel admin parolası paylaşımlıysa (LAPS yoksa) bu tek başına tüm filoyu açar.
- **NTDS.dit hırsızlığı (T1003.003)** — **domain'in kıyameti**: Saldırgan `ntds.dit`'e ulaştıysa **tüm domain'in tüm parola hash'lerini** aldı. İzler: DC'de **`vssadmin create shadow`** (Volume Shadow Copy oluşturma — ATT&CK **T1003.003 / T1006**), ardından gölge kopyadan `ntds.dit` kopyalama; ya da `ntdsutil` ile `ifm` (Install From Media) dump; ya da `secretsdump.py`; ya da `Invoke-NinjaCopy`. DC'de **Event ID 8222** (shadow copy), vssadmin komut satırı (4688), ve NTDS klasörüne erişim. **Bunu görürsem kararım nettir: krbtgt hesabının parolası iki kez sıfırlanmalı** (Kerberos Golden Ticket riskini kapatmak için), ve pratikte tüm domain kimlikleri gözden geçirilmelidir.
- **Direct Volume Access / Shadow Copy kötüye kullanımı (T1006)**: `vssadmin`, `wbadmin`, `esentutl` ile disk/dosya erişimi — hem NTDS hırsızlığı hem de dosya erişim kontrollerini atlatma için. Aynı `vssadmin` aracı saldırganın iki farklı amacı için kullanılır: (a) shadow copy *oluşturup* NTDS çalmak, (b) shadow copy'leri *silip* kurtarmayı engellemek. Hangisi olduğunu komut satırı söyler: `create` vs `delete`.

**Shadow copy silme (T1490 — Inhibit System Recovery)**: Ransomware imzası niteliğindedir. `vssadmin delete shadows /all`, `wbadmin delete catalog`, `bcdedit /set recoveryenabled no`. Bunu 4688/PowerShell log'unda görmek zaten "ransomware çalıştı" teyididir ve genelde şifrelemeden hemen önce gelir.

### Adım 4 — Exfiltration (veri sızdırma) tespiti — artık en kritik soru

Modern ransomware **çifte gasp** (double extortion): önce çalarlar, sonra şifrelerler. "Ödemezsen verini yayınlarız." Bir veri ihlali (breach) olup olmadığı **hukuki bildirim yükümlülüğünü** (KVKK, GDPR) tetikler. Bu yüzden exfiltration'ı ispatlamak veya ekarte etmek işin en hassas parçasıdır.

Ne ararım:
- **rclone / MEGAsync / FileZilla / WinSCP** izleri (Prefetch, Amcache). `rclone.exe` neredeyse her modern ransomware vakasında var. rclone config dosyası (`rclone.conf`) hangi buluta gittiğini söyler.
- **SRUM** ile process başına giden bayt miktarı — büyük outbound = kanıt.
- **Firewall / proxy / NetFlow** log'larında büyük ve sürekli outbound bağlantılar; anormal hedeflere (MEGA, anonim bulut, saldırgan C2) yüklemeler.
- **Anormal arşivleme**: `7z`, `rar` ile büyük arşiv oluşturma (staging). Genelde exfil öncesi veri `C:\temp`, `C:\PerfLogs` gibi yerlerde stage edilir.

Karar: SRUM ve firewall net bir şekilde büyük outbound gösteriyorsa, veriyi "çıktı" kabul eder ve hukuk/yönetime bildiririm. Hiçbir kanıt yoksa "kanıt bulunamadı" derim ama **"olmadı" diye garanti vermem** — log rotation nedeniyle kanıt kaybolmuş olabilir; bunu dürüstçe raporlarım.

### Adım 5 — Zararlı analizi ve IOC türetme (YARA)

Şifreleyici binary'yi ve bırakılan araçları izole ortamda analiz ederim. Hash'lerini alır, **YARA** kuralları yazar ya da bilinen aile kurallarını kullanırım, sonra **Velociraptor/EDR ile tüm filoda YARA hunt** yaparak aynı binary'nin/backdoor'un başka nerede olduğunu bulurum. Fidye notundaki ID ve aile ismini VirusTotal/açık kaynakla eşleyip, bilinen TTP'lerle karşılaştırırım (bilinen bir aileyse persistence ve exfil yöntemleri tahmin edilebilir). **Uydurma yapmam**: aile kesin değilse "tespit edilen aile belirsiz" derim, ödeme/decryptor konusunda spekülasyon yapmam.

### Adım 6 — Eradication ve Recovery (kararlı geri dönüş)

- **Kapatılacak delik**: initial access vektörü (RDP'yi kapat/MFA zorla, VPN yamala, phishing'e maruz hesabı sıfırla). Bu yapılmadan restore yok.
- **Kimlik hijyeni**: Kirli tüm hesapların parolaları sıfırlanır; DC etkilendiyse krbtgt iki kez sıfırlanır; servis hesapları gözden geçirilir; olası backdoor hesaplar (saldırganın açtığı yeni admin) silinir.
- **Persistence temizliği**: Scheduled task'lar, yeni servisler, Run anahtarları, WMI event subscription'lar, GPO değişiklikleri — hepsi Velociraptor hunt'la temizlenir.
- **Restore**: Sağlamlığı doğrulanmış, izole edilmiş backup'tan; ya da temiz kurulum. Backup'ı geri koymadan önce **backup'ın da kirlenmediğinden** emin olurum (saldırgan haftalardır içerdeyse backup'a da persistence bulaşmış olabilir).
- **İzleme**: Geri dönüşten sonra en az birkaç hafta yükseltilmiş izleme — saldırgan geri dönmeyi dener.

---

## 3. Kritik dikkat noktaları

**Delil bütünlüğü (evidence integrity)**: Her imajın **hash'ini** (SHA-256) alırım, toplama anında ve saklama sırasında; hash'ler eşleşiyorsa delil değişmemiştir. Delil üzerinde asla doğrudan çalışmam — **çalışma kopyası** üzerinde analiz yaparım, orijinal (master) yazma-korumalı saklanır. Mümkünse **write blocker** (donanımsal yazma engelleyici) kullanırım.

**Order of volatility**: Yukarıda anlatıldı ama tekrar vurgu: RAM ve ağ durumu saniyeler içinde kaybolur, disk kalıcıdır. Yanlış sıra = geri dönülemez delil kaybı. En yaygın acemi hatası: panikle makineyi yeniden başlatmak/kapatmak ve RAM'deki her şeyi (şifreleme anahtarı dahil!) yok etmek.

**Chain of custody (delil zinciri)**: Her delilin kim tarafından, ne zaman, nereden toplandığı ve elden ele nasıl geçtiği belgelenir. Vaka mahkemeye/sigortaya/hukuka giderse bu zincir olmadan delil geçersizdir. Zaman damgaları **UTC** ve senkronize olmalı; makinelerin saat kayması (clock skew) not edilmeli, yoksa timeline'lar yanlış hizalanır.

**Anti-forensics'e karşı**: Saldırgan iz siler. Aradığım kaçış izleri:
- **Event log temizleme** → **Event ID 1102** (Security log cleared) ve **104** (System log cleared). Log'un silinmiş olması bile bir delildir. Boşluk gördüğüm yerde şüphelenirim.
- **Timestomping (T1070.006)**: Dosya zaman damgalarını değiştirme. `$STANDARD_INFORMATION` ve `$FILE_NAME` zaman damgalarını MFT'de karşılaştırırım — tutarsızsa (ör. SI zamanı FN'den eski, ya da milisaniye alanı sıfırlanmış) timestomp var demektir. Zimmerman'ın MFTECmd'i bu iki zaman setini de verir.
- **USN Journal / $LogFile** silinmiş dosyaların ve yeniden adlandırmaların izini tutar; saldırgan MFT'yi manipüle etse bile USN'de iz kalabilir.
- **Log rotation vs kasıtlı silme** ayrımı: kanıt yoksa "yoktu" diye atlamam; "toplama anında mevcut değildi, silinmiş/döngüye girmiş olabilir" derim.

---

## 4. Gerçek dünya senaryosu

**Vaka**: Cuma 03:10, orta ölçekli bir üretim firması. Sabah çalışanlar dosya sunucusundaki dosyaların `.locked` uzantısıyla açılmadığını, her klasörde `RECOVER-YOUR-FILES.txt` olduğunu bildiriyor. Panik. Yönetim "hemen backup'tan dönün" diyor.

**Benim akışım:**

1. **Triyaj**: Şifreleme durmuş görünüyor (gece bitmiş). DC etkilenmiş mi? İki DC'den birinde de fidye notu var — kötü işaret. Backup sunucusu domain'e bağlı ve o da şifrelenmiş. Yönetime: "Restore *henüz* yok, önce ne olduğunu anlamalıyız, yoksa aynı deliğe geri koyarız."

2. **Uçucu delil**: DC'lerden ve dosya sunucusundan EDR ile RAM yakalama; KAPE ile hepsinden targeted collection. Velociraptor ile filo genelinde `.locked` dosyaları ve fidye notunu barındıran makineleri listeliyorum → 14 sunucu, 60+ istemci kirli.

3. **Timeline**: USN Journal (MFTECmd) fidye notunun ilk olarak Perşembe 02:47'de bir dosya sunucusunda yazıldığını gösteriyor. Prefetch'te (PECmd) şifreleyici binary `svchost32.exe` (sahte isim) o makinede 02:45'te ilk kez koşmuş. Geriye sarıyorum.

4. **Lateral movement**: Şifreleyici, Çarşamba gecesi oluşturulan bir **GPO** ve **PsExec** ile toplu itilmiş (bir sunucuda `PSEXESVC` servisi ve Prefetch'te `psexec.exe`). Şifreleyiciyi iten hesap: `svc_backup` (bir servis hesabı, domain admin yetkili — yanlış yapılandırma). 4624 Type 3 log'ları bu hesabın onlarca makinede peş peşe logon'unu gösteriyor.

5. **Credential theft**: `svc_backup` nasıl ele geçirildi? Bir istemci makinede (patient zero adayı) Salı günü `lsass` dump izi (EDR alarmı, `comsvcs.dll` MiniDump) ve ardından DC'de **`vssadmin create shadow`** + `ntds.dit` kopyalama (Event 8222 + 4688). Yani saldırgan **NTDS.dit'i çalmış — tüm domain hash'leri gitti.**

6. **Initial access**: Patient zero istemcisinde geriye gidince, Pazartesi bir kullanıcının Outlook'undan çalışan makro'lu bir Office belgesi → PowerShell loader zinciri (Prefetch + PowerShell Operational log Event 4104). Phishing. İlk giriş anı: Pazartesi 14:20.

7. **Exfiltration**: SRUM (SrumECmd) dosya sunucusunda `rclone.exe`'nin Çarşamba gecesi ~48 GB outbound gönderdiğini gösteriyor; firewall log'u MEGA IP aralığına yüklemeyi doğruluyor. `rclone.conf` bulundu. **Veri sızdırıldı → KVKK bildirim yükümlülüğü tetiklendi.** Hukuka haber verilir.

8. **Anti-forensics**: DC'de Event ID 1102 (Security log temizlendi) Perşembe 03:05'te — saldırgan çıkışta iz sildi. Boşluk, sildikleri pencereyi işaretliyor.

**Varılan sonuç ve aksiyon**: Giriş = phishing (Pazartesi). Tam kompromi = 3 gün sessiz keşif + NTDS hırsızlığı + 48 GB exfil, sonra Perşembe gece şifreleme. Aksiyon: phishing'e maruz hesap ve `svc_backup` dahil tüm ayrıcalıklı hesaplar sıfırlandı, **krbtgt iki kez** döndürüldü, GPO/PsExec persistence temizlendi, initial access için e-posta filtreleme + makro engelleme sıkılaştırıldı, MFA zorlandı. Restore ancak **temiz** (offline, domain-dışı) yedekten ve kimlik hijyeni tamamlandıktan sonra yapıldı. Sızdırma nedeniyle yasal bildirim süreci başlatıldı.

---

## 5. Yaygın tuzaklar ve pro yargısı (acemi neyi yanlış yapar)

**1. Panikle makineyi kapatmak/yeniden başlatmak.** Acemi refleksi. RAM'i, şifreleme anahtarını, canlı C2'yi ve process'leri yok eder. Pro: izole et, açık tut, RAM'i al.

**2. Scope çıkmadan restore etmek.** En pahalı hata. Saldırgan hâlâ içerdeyken temiz makine geri koymak = birkaç gün sonra ikinci şifreleme (ve bunu birçok kez gerçek vakada gördüm). Pro: giriş kapatılmadan, kimlik hijyeni yapılmadan restore yok.

**3. Fidye notuna kilitlenip "şifreyi nasıl çözerim" derdine düşmek.** Asıl soru bu değil. Asıl sorular: nasıl girdiler, ne çaldılar, hangi hesaplar yakıldı. Şifre çözme genelde ya backup'tan ya (nadiren) açık decryptor'dan çözülür; senin katma değerin hikâyeyi çıkarmakta.

**4. Exfiltration'ı atlamak.** Acemi şifrelemeye odaklanır, veri hırsızlığını görmez. Halbuki hukuki/mali sonucun en ağırı sızdırmadır. SRUM ve firewall log'una bakmamak = ihlali kaçırmak.

**5. NTDS/krbtgt'yi anlamamak.** DC kirliyse ve NTDS çalındıysa, sadece parola sıfırlamak yetmez — krbtgt döndürülmezse saldırgan Golden Ticket ile istediği zaman geri döner. Acemi sadece kirli makineleri temizler, kimlik altyapısının yakıldığını göremez.

**6. Delil zinciri ve hash almayı boş vermek.** "Nasılsa mahkemeye gitmez" diye düşünmek. Sigorta ekspertizi, KVKK, dava — hepsi delil ister. Hash'siz, chain-of-custody'siz delil çöptür.

**7. Log boşluğunu "bir şey yok" sanmak.** Event ID 1102 gördüğünde ya da timeline'da sessizlik gördüğünde, "temizmiş" değil "silinmiş" diye düşün. Yokluk çoğu zaman kasıtlıdır.

**8. Tek makineye odaklanıp filo görüşünü kaybetmek.** Elle tek tek makine incelemek ölçeklenmez ve scope'u kaçırır. Pro: Velociraptor/EDR ile fleet-wide hunt, Timesketch ile birleşik timeline. Ransomware bir *filo* olayıdır, tek makine olayı değil.

**9. Saldırganın anti-forensic timestomp'una kanmak.** Dosya tarihine körü körüne güvenmek. Pro: `$SI` vs `$FN` zaman damgalarını karşılaştır, USN Journal'a güven, tek bir artefakta değil çapraz doğrulamaya (Prefetch + Amcache + Event Log + USN) dayan.

**10. "Kesin şu aile / kesin ödeme çözer" diye spekülasyon.** Belirsizken kesinlik satmak güven kaybettirir ve yanlış karar verdirir. Pro yargısı: bildiğini bildiğin kadar söyle, bilmediğini dürüstçe "kanıt yetersiz" diye raporla. DFIR'da güvenilirliğin, kesin konuşmandan değil, kalibreli konuşmandan gelir.

**Son söz — pro sezgisi**: Ransomware'de en değerli beceri araç kullanmak değil, **"bu artefaktı görünce bir sonraki adımda nereye bakacağını bilmek"**. Fidye notunun zamanı → geriye sar. GPO/PsExec → dağıtım hesabını bul. O hesabın logon'ları → lateral zinciri çöz. Zincirin başı → lsass/SAM/NTDS izi → credential theft'i doğrula. SRUM'da büyük outbound → exfil. Event 1102 → sildikleri pencere. Bu pivot zinciri, hangi aracı kullandığından çok daha önemlidir. Araçlar değişir, bu düşünme biçimi değişmez.
