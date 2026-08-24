# Threat Hunting (Pratisyen) — Bir DFIR Lead'in Saha Defteri

> Bu metin, "araç listesi" değildir. 15 yılda öğrendiğim şey şu: threat hunting araç meselesi değil, **hipotez ve yargı** meselesidir. Aşağıda anlatacağım şey, gerçek bir olayda kafamın içinde ne döndüğü, hangi artefaktı görünce nereye gittiğim, ve acemi analistin nerede tökezlediğidir.

---

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Threat hunting, alarm beklemeden **"burada zaten bir saldırgan var, kanıtını bulacağım"** varsayımıyla proaktif olarak iz sürmektir. Klasik alarm-tabanlı SOC ile arasındaki fark tam da burada: SOC, tetiklenen bir kuralı bekler; hunter ise tetiklenmemiş olanı arar. EDR'ın alarm üretmediği yerde saldırgan yaşar.

IR yaşam döngüsünde (Hazırlık → Tespit → Sınırlama → Kök Söküm → Kurtarma → Ders) hunting iki noktada devreye girer:

- **Proaktif kolda (breach yokken):** Hipotez kurar, telemetride ararsın. Amaç "dwell time"ı (saldırganın fark edilmeden geçirdiği süreyi) düşürmek. Sektör medyanı hâlâ haftalarla ölçülüyor; iyi bir hunting programı bunu günlere indirir.
- **Reaktif kolda (olay sırasında):** Bir uç noktada IOC bulunca, "bu tek makine mi, yoksa yatay yayılım var mı?" sorusuna cevap ararsın. Buna **scoping** (kapsam çıkarma) denir ve olayın gerçek maliyetini burada belirlersin.

Kritik ayrım: Hunting **doğrulanabilir bir hipotezle** başlar. "Kötü bir şey var mı bakalım" hunting değil, gezinti. Doğru hipotez şöyle kurulur: *"Eğer bir saldırgan T1003.001 ile LSASS dump aldıysa, `lsass.exe`'ye açılmış anormal PROCESS_VM_READ handle'ları veya `comsvcs.dll MiniDump` komut satırı izleri görürüm."* İşte bu aranabilir, ya bulunur ya bulunmaz.

---

## 2. Adım-adım İŞ AKIŞI ve KARAR (asıl değer)

Aşağıda tipik bir "kimlik bilgisi hırsızlığı şüphesi" hunt'ının benim kafamdaki akışını veriyorum. Sırayı ve **her adımdaki karar mantığını** önemseyin.

### Adım 0 — Hipotezi yaz, ATT&CK'e eşle

Hunt'a araç açarak değil, tek cümle yazarak başlarım. Örnek:

> "Domain'de bir hesap ele geçirildi; saldırgan LSASS'tan (T1003.001) veya SAM'dan (T1003.002) kimlik bilgisi çekip lateral movement (TA0008) yapıyor."

Bunu ATT&CK tekniklerine eşlerim çünkü **her tekniğin bıraktığı iz farklıdır** ve nereye bakacağımı bu belirler. LSASS dump ararken baktığım yer ile NTDS.dit (T1003.003) hırsızlığı ararken baktığım yer taban tabana farklı: biri uç nokta belleği/process telemetrisi, diğeri Domain Controller'daki `vssadmin`/`ntdsutil` ve VSS artefaktları.

### Adım 1 — Order of volatility'ye göre topla, ama önce dokunma sırasını planla

Klasik uçuculuk sırası (RFC 3227 ruhu): **RAM → ağ bağlantıları/ARP → çalışan process'ler → disk → loglar → arşiv**. Ama saha gerçeği şu: canlı bir makinede iş yaparken *ne toplayacağıma* değil, *hangi sırayla dokunacağıma* karar veririm, çünkü her komut kendi izini bırakır (Locard değişim ilkesi burada da geçerli — sisteme dokunan analist de iz bırakır).

Pratik akış:
- Uç nokta hâlâ ağdaysa ve şüpheliyse: EDR üzerinden **network izolasyonu** düşünürüm ama önce **canlı RAM imajı** alırım (Magnet RAMCapture / WinPmem / Belkasoft). RAM'i almadan izole edip kapatırsam mimikatz'ın bellekteki izlerini, injeksiyon artefaktlarını, şifresiz clear-text credential'ları kaybederim.
- RAM alındıktan sonra **triage** için KAPE koşarım. KAPE'nin `!SANS_Triage` target'ı bana MFT, $J (USN journal), EVTX'ler, prefetch, amcache, SRUM, registry hive'ları ve daha fazlasını dakikalar içinde toplar. Bu, "her şeyi imajla" tuzağından kurtarır — 2 TB disk imajı almak yerine ~2 GB ile olayın %90'ını çözerim.
- Kurumsal ölçekte tek makineye gitmem; **Velociraptor** ile filoya sorgu atarım. Örneğin `Windows.System.Pslist` + custom VQL ile "hangi makinede `lsass.exe`'ye şüpheli handle var" sorusunu 10.000 uç noktada aynı anda sorarım. Hunting'in kurumsal kolu budur.

### Adım 2 — İlk temas noktası: process ve komut satırı telemetrisi

LSASS dump hipotezinde ilk baktığım yer **process oluşturma logları**:
- **Sysmon Event ID 1** (process create) → komut satırında `comsvcs.dll MiniDump`, `procdump -ma lsass`, `rundll32` + LSASS PID kombinasyonu ararım.
- **Sysmon Event ID 10** (process access) → bu benim altın madenim. `TargetImage: lsass.exe` ve `GrantedAccess: 0x1010` / `0x1410` / `0x1fffff` gibi PROCESS_VM_READ içeren erişimler. Meşru güvenlik yazılımı da LSASS'a bakar, bu yüzden **CallTrace**'e bakarım: çağrı `UNKNOWN` bir bellek bölgesinden mi geliyor (unbacked/injected kod işareti), yoksa imzalı bir DLL'den mi?
- **Windows Security 4688** (audit process creation, komut satırı loglama açıksa) → Sysmon yoksa yedeğim.

Karar mantığı: `GrantedAccess 0x1410`'u imzasız bir process'ten görürsem bu **çok kuvvetli** LSASS-dump sinyalidir, doğrudan credential theft koluna geçerim. `0x1000` (PROCESS_QUERY_LIMITED_INFORMATION) görürsem bu genellikle gürültüdür, es geçerim.

### Adım 3 — Disk artefaktları: "komutu göremediysem izini bulurum"

Saldırgan logları temizlemiş olabilir (T1070). Bu yüzden asla tek kaynağa güvenmem. Eric Zimmerman araç setiyle çapraz doğrulama yaparım:

- **Prefetch (PECmd):** `PROCDUMP.EXE`, `RUNDLL32.EXE` gibi çalıştırma kanıtı. Prefetch bana "kaç kez çalıştı, ilk/son çalışma zamanı, dosyanın diskteki yolu" verir. `PROCDUMP-*.pf` içindeki referanslı dosyalarda `lsass` geçiyorsa iş biter.
- **Amcache.hve (AmcacheParser):** Çalıştırılan binary'nin SHA1'i + ilk görülme zamanı. Silinmiş bir aracın bile parmak izi burada kalır. Hash'i VirusTotal/dahili TI ile eşlerim.
- **SRUM (SrumECmd):** Uygulama başına ağ byte'ı. Exfiltration şüphesinde "hangi process ne kadar veri gönderdi" sorusunun cevabı. NTDS.dit dışarı çıktıysa burada anormal upload görürüm.
- **$MFT + $J USN journal (MFTECmd):** Dosya oluşturma/silme kronolojisi. `lsass.dmp`, `sam`, `system` gibi dosyaların *oluşturulup silindiğini* USN journal'da yakalarım — dosya diskte yok ama izi journal'da duruyor.
- **ShellBags / LNK / Jump Lists:** İnsan operatörün hangi klasörlere göz attığı. Manuel keşif yapan bir saldırganı buradan koklarsınız.

### Adım 4 — Timeline: her şeyi zamana dizmek (asıl aydınlanma anı)

Bireysel artefaktlar "ne" olduğunu söyler; **timeline "hikâyeyi"** anlatır. İki yöntem kullanırım:

- Hızlı ve odaklı: Eric Zimmerman **Timeline Explorer** ile MFTECmd/EVTX çıktılarını yan yana koyar, dakika hassasiyetinde okurum.
- Büyük ve korelasyonlu: **Plaso (log2timeline)** ile süper-timeline üretir, **Timesketch**'e yüklerim. Timesketch'te tag'ler ve saved search'lerle ekip halinde çalışırız; "yıldızladığım" olaylar hikâyenin iskeletini çıkarır.

Timeline'da aradığım imza şudur: `4624 (logon, type 3)` → hemen ardından `Sysmon 1 (rundll32 comsvcs)` → `MFT: lsass.dmp oluşma` → `4634 (logoff)`. Bu dört olayın saniyeler içinde art arda gelmesi, otomatik bir credential-dump script'inin parmak izidir.

### Adım 5 — Bellek analizi (RAM aldıysam)

**Volatility 3** ile:
- `windows.pslist` / `windows.psscan` farkını alırım — `psscan`'de görünüp `pslist`'te olmayan process = gizlenmiş/unlinked process (DKOM şüphesi).
- `windows.malfind` → RWX izinli, imajı olmayan (unbacked) bellek bölgeleri = kod injeksiyonu (T1055). Mimikatz veya Cobalt Strike beacon burada yakalanır.
- `windows.cmdline` → RAM'de yakalanmış komut satırları; diskteki log silinmiş olsa bile bellekte durabilir.
- `windows.netscan` → o an açık/kapanmış C2 bağlantıları, dinleyen portlar.
- LSASS'a handle açan process'leri `windows.handles` ile teyit ederim.

### Adım 6 — YARA ile içerik taraması

İsim/hash değil, **davranış/içerik** ararken YARA kullanırım. Bellek dökümünde veya disk triage'ında mimikatz'ın karakteristik string'leri, Cobalt Strike beacon config'i, ya da bilinen shellcode pattern'leri için tarama koşarım. Velociraptor'un içine YARA gömüp **10.000 makinede aynı kuralı** koşturmak, kurumsal scoping'in en güçlü hamlesidir.

### Adım 7 — Scoping ve pivot: "tek makine yalanı"

Bir IOC bulduğumda asla "tek makine, temizle geç" demem. Pivot ederim:
- Bulduğum SHA1/dosya adını **tüm filoda** Velociraptor ile ararım.
- Ele geçen hesabın `4624/4625/4768/4769` (Kerberos) loglarını DC'de tararım — o hesap başka nerelere logon olmuş?
- **Lateral movement izleri:** `7045` (yeni servis — PsExec imzası), `4697`, WMI için `Sysmon 19/20/21`, RDP için `4624 type 10` + `TerminalServices-RemoteConnectionManager` logları.

Bir makinede LSASS dump görüp scoping yapmazsam, iki hafta sonra domain admin ele geçmiş halde geri gelirim. Scoping, hunting'in olmazsa olmazıdır.

### Karar özeti (hızlı referans)

| Gördüğüm artefakt | Vardığım sonuç / sonraki hamle |
|---|---|
| Sysmon 10, LSASS, GrantedAccess 0x1410, imzasız kaynak | Kuvvetli LSASS dump → RAM al, malfind koş |
| Amcache'de `procdump` + prefetch teyidi, disk temiz | Araç çalışmış ama silinmiş → USN journal'da dmp ara |
| DC'de `vssadmin create shadow` + `ntdsutil` | NTDS.dit hırsızlığı (T1003.003) → SRUM'da exfil ara |
| `reg save HKLM\sam` komutu | SAM dump (T1003.002) → offline hash cracking riski |
| psscan'de var, pslist'te yok | Gizlenmiş process → tam bellek analizi |
| 4624 type 3 zinciri farklı makinelere | Yatay yayılım → filo geneli scoping |

---

## 3. Kritik dikkat noktaları

**Delil bütünlüğü (integrity).** Topladığın her artefaktın **SHA-256 hash'ini** anında al ve ayrı bir manifest'e yaz. Analiz kopyası üzerinde çalış, orijinali (write-blocker arkasında veya read-only) elleme. Bir imajı yanlışlıkla mount edip "modified" zaman damgasını değiştirirsen o delilin mahkeme değeri düşer. Kural: **orijinale asla iki kez dokunma.**

**Order of volatility.** RAM'i diskten önce al. Bir makineyi "temiz olsun" diye reboot eden bir sistem yöneticisi, farkında olmadan olayın en değerli delilini (bellekteki clear-text credential, injected kod, C2 bağlantısı) yok eder. İlk müdahale kuralın: *önce fotoğrafını çek, sonra dokun.* Reboot/shutdown, canlı RAM alınmadan önce yasaktır.

**Chain of custody (delil zinciri).** Her delil için: kim topladı, ne zaman (UTC — lokal saat dilimiyle karıştırma), hangi araçla, hash'i ne, nerede saklanıyor, kimden kime devredildi. Bu zincir kopuksa, teknik olarak mükemmel analizin hukuken çöp olur. Excel bile olsa tut, ama tut.

**Anti-forensics'e karşı.** Olgun saldırgan iz bırakmamaya çalışır. Bilinen numaralar ve karşı hamlem:
- **Log temizleme (T1070.001):** `1102` (Security log cleared) ve `104` (System) event'lerini ilk aradıklarımdan. Log siliniyorsa merkezi SIEM/forwarded log senin sigortandır — bu yüzden logları uç noktada tutma, dışarı akıt.
- **Timestomp (T1070.006):** $MFT'de **$STANDARD_INFORMATION vs $FILE_NAME** zaman damgası tutarsızlığı = timestomping kanıtı. Zimmerman'ın MFTECmt'i her ikisini de verir; SI zamanı FN'den eskiyse alarm.
- **Prefetch/journal devre dışı bırakma:** Bunlar bile bir iz — "neden kapatıldı?" sorusu hipotez üretir.
- **Bellekte-yaşayan (fileless) saldırılar:** Diskte hiçbir şey yoksa RAM ve Sysmon telemetrisi tek şansın. Diske bakıp "temiz" demek en büyük hata.

**Tek kaynağa güvenme.** Her sonucu en az iki bağımsız artefaktla doğrula. Prefetch der ki "çalıştı", Amcache teyit eder "bu hash'le çalıştı", USN journal ekler "sonra silindi". Üç kaynak aynı hikâyeyi anlatıyorsa güvenirim.

---

## 4. Gerçek dünya senaryosu (kısa vaka)

**Tetik:** Pazartesi 09:00, EDR "orta önem" bir alarm attı — `WEB-APP-03` sunucusunda `rundll32.exe` beklenmedik bir parent'tan (`w3wp.exe`, IIS worker) türemiş. SOC "false positive olabilir" diye kapatmak üzereydi. Ben hunt açtım.

**Hipotez:** IIS'e (T1003.005 komşuluğu, AppCmd ile servis hesabı) veya web shell üzerinden erişilmiş, oradan credential dump denenmiş.

**Adım adım ne yaptım:**

1. **Velociraptor** ile `WEB-APP-03`'e bağlanıp `Sysmon EID 1` çektim. `rundll32.exe C:\Windows\System32\comsvcs.dll MiniDump 712 C:\Windows\Temp\w.dmp full` komutunu buldum. PID 712 = `lsass.exe`. Hipotez doğrulandı: **T1003.001 LSASS dump.**

2. **MFTECmd** ile $J USN journal çektim. `w.dmp` dosyası 09:47'de oluşmuş, 09:49'da **silinmiş**. Diskte yoktu ama journal izini tutmuştu.

3. **SRUM (SrumECmd)** → `w3wp.exe` üzerinden 09:52'de ~48 MB dışarı gönderim. LSASS dump'ının dışarı sızdırıldığının kanıtı (dmp dosyası tipik olarak bu boyutta).

4. **Timeline (Timesketch):** Geriye doğru ördüm. 08:30'da `w3wp.exe`'nin şüpheli bir `.aspx` dosyasına eriştiğini gördüm — MFT'de bu dosya 08:12'de oluşmuş. **Web shell** buydu. İlk erişim (initial access) noktası bulundu.

5. **Scoping:** Dump edilen credential'lar arasında bir servis hesabı (`svc-backup`) vardı. DC loglarında `4624 type 3` ile bu hesabın 10:05'te `FILE-SRV-01`'e logon olduğunu gördüm. Saldırgan zaten yayılmaya başlamıştı. Velociraptor'la `svc-backup`'ın dokunduğu tüm makineleri işaretledim.

**Varılan sonuç:** "Orta önem, muhtemel FP" diye kapatılacak bir alarm, aslında **web shell → LSASS dump → credential theft → başlamış lateral movement** zinciriydi. Dwell time'ı ~2 saatte yakaladık; scoping olmasaydı `svc-backup` üzerinden domain'in tamamı gidebilirdi. Sınırlama: `WEB-APP-03` ve `FILE-SRV-01` izole edildi, `svc-backup` şifresi (ve KRBTGT iki kez) resetlendi, web shell'in geldiği zafiyet yamandı.

**Dersin özü:** Alarmın "önem" etiketine değil, hipoteze güvendim. `rundll32` + IIS parent kombinasyonu benim için "orta" değil, "hemen bak" demekti.

---

## 5. Yaygın tuzaklar ve pro yargısı

**1. Hipotezsiz gezinmek.** Acemi araçları açar, log denizinde yüzer, 4 saat sonra "bir şey bulamadım" der. Bulamaz, çünkü ne aradığını bilmiyordu. Pro her hunt'ı yazılı, ATT&CK'e eşli, doğrulanabilir tek cümleyle başlatır.

**2. Reboot/shutdown ile delili yok etmek.** "Makineyi temizleyelim" refleksi. Canlı RAM alınmadan yapılan her kapatma, fileless saldırının tüm kanıtını siler. Pro önce imaj, sonra müdahale der.

**3. Tek makineye kilitlenmek (scoping yapmamak).** Bir IOC bulup "buldum, temizledim" demek en pahalı hata. Saldırgan zaten yayılmıştır. Pro her bulguyu filo geneline pivot eder.

**4. Zaman dilimi karmaşası.** Bir artefakt UTC, diğeri lokal, EDR bambaşka. Timeline'ı yanlış saat dilimiyle örersen sebep-sonuç ters döner. Pro her şeyi **UTC'ye normalize eder** ve her aracın hangi TZ'de yazdığını bilir.

**5. Meşru araç = temiz sanmak (living-off-the-land).** `rundll32`, `certutil`, `wmic`, `bitsadmin`, `powershell`, `vssadmin` — hepsi imzalı Windows aracı. Acemi "Microsoft imzalı, güvenli" der geçer. Pro **komut satırı bağlamına** bakar: `certutil -urlcache -f http://...` indirmedir, `rundll32 comsvcs.dll MiniDump` credential dump'tır. Binary'nin kim olduğu değil, **ne yaptığı** önemli.

**6. Alarm önem etiketine kölelik.** SIEM "low" dedi diye geçmek. Önem skoru bağlamı bilmez; sen bilirsin. IIS worker'dan türeyen `rundll32` etiketi "low" olabilir ama context'i "kritik"tir.

**7. Tek artefakta güvenip erken sonuç.** Sadece prefetch'e bakıp "çalışmış" demek yetmez — silinmiş mi, hash'i ne, dışarı veri gitmiş mi? Pro üçgenleme yapar: en az iki-üç bağımsız kaynak aynı hikâyeyi anlatmalı.

**8. Delil zincirini ihmal etmek.** "Nasılsa iç soruşturma" deyip hash almamak, kim-ne-zaman tutmamak. Olay adliyeye/hukuka giderse teknik olarak kusursuz işin çöpe gider. Pro ilk dakikadan chain of custody tutar.

**9. Anti-forensics'i görmezden gelmek.** "Log yok, demek ki temiz." Hayır — log'un *yokluğu* bir bulgudur. `1102` event'i, kapatılmış Sysmon, timestomp'lanmış dosya... yokluk da veridir. Pro "neden burada boşluk var?" diye sorar.

**10. Baseline bilmemek.** Neyin normal olduğunu bilmeden neyin anormal olduğunu göremezsin. `svchost.exe`'nin normalde hangi parent'tan, hangi komut satırıyla, kaç instance koştuğunu bilmiyorsan, sahte `svch0st.exe`'yi de yakalayamazsın. Pro hunting'den önce ortamın normalini öğrenir — hunting'in %50'si baseline bilgisidir.

---

### Kapanış notu

Threat hunting'in sırrı pahalı araçta değil, **disiplinli merakta**: her bulguya "peki ya başka nerede?" diye sormak, her temiz sonuca "gerçekten mi, yoksa saldırgan mı temizledi?" diye şüphe duymak, ve her hikâyeyi timeline'da baştan sona ördükten sonra imzalamak. Araçlar (KAPE, Velociraptor, Volatility, Zimmerman seti, Timesketch, YARA) yalnızca soruları hızlı sorma imkânı verir — doğru soruyu senin yargın kurar.
