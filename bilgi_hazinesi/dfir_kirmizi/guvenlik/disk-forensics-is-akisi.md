# Disk Forensics İş Akışı — Pratisyen Notları

> Bu metin sahadan gelen bir DFIR lead'inin defterinden. Amaç, "hangi butona basılır" değil, **hangi artefaktı görünce hangi sonuca gidilir ve neye göre karar verilir** mantığını aktarmak. Araçlar değişir; yargı kalıcıdır.

---

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Disk forensics, bir olayın **zaman çizelgesini** ve **failin diskte bıraktığı izleri** kalıcı depolamadan (HDD/SSD, sanal disk imajı, snapshot) yeniden kurmayı hedefler. Olay müdahalesinin klasik döngüsü (NIST 800-61 mantığında) hazırlık → tespit/analiz → sınırlama (containment) → temizleme (eradication) → toparlanma (recovery) → çıkarılan dersler şeklindedir. Disk forensics ağırlıklı olarak **analiz** fazının belkemiğidir ama tek başına oturmaz.

Sahadaki gerçek şu: bir olayda üç veri kaynağı vardır ve üçü birbirini doğrular — **uçucu bellek (RAM)**, **disk artefaktları** ve **ağ/telemetri (EDR, proxy, firewall, DNS logları)**. Disk forensics, EDR'ın "gördüğü ama sakladığı" ya da hiç görmediği şeyleri açar. EDR bir process'i öldürmüş olabilir ama diskte o process'in prefetch kaydı, çalıştırıldığı klasör, indirdiği ikinci aşama dropper hâlâ durur. Disk, EDR'ın kör olduğu anları (ajan yüklenmeden önce, ajanın devre dışı bırakıldığı pencere) doldurur.

Ne zaman disk forensics'e ağırlık verilir? İki durumda kritik olur:
- **EDR yoksa veya güvenilmezse**: Fail EDR'ı sonlandırdıysa, ajan olaydan sonra kurulduysa, ya da ortam hiç izlenmiyorsa disk tek gerçek kaynaktır.
- **"Ne aldılar, ne kadar süre içerdeydiler, ilk giriş nereden" sorularına** kesin cevap gerektiğinde. Bu sorular yasal, sigorta ve düzenleyici bildirim (KVKK/GDPR ihlal bildirimi) açısından hayati.

Kilit ayrım: **triage (hızlı üçlem)** ve **derin adli inceleme (deep-dive)**. Aktif bir olayda önce triage yaparsın — dakikalar/saatler içinde "bu makine gerçekten tehlikede mi, ilk giriş yaklaşık ne zaman, yayılım var mı" sorusuna cevap. Derin inceleme günler sürer ve genelde soruşturmanın omurgasını kurmak için birkaç seçili "anchor" (çıpa) makinede yapılır. Acemi hatası: 200 makinenin hepsinin tam imajını almaya çalışıp boğulmak.

---

## 2. Adım-adım iş akışı ve karar mantığı (asıl değer)

### 2.0 Karar sıfır: canlı sistem mi, kapalı mı? Order of volatility.

Elindeki makine **açık ve çalışıyorsa**, en uçucu veriden başlarsın çünkü onu bir daha asla göremezsin. Sıralama:

1. **RAM** (bellek dökümü) — process listesi, açık ağ bağlantıları, çözülmüş komut satırları, injeksiyon, şifre çözülmüş payload'lar, bazen transient malware yalnızca bellekte yaşar.
2. **Ağ durumu ve oturumlar** — `netstat`/EDR anlık bağlantılar, ARP, oturum açan kullanıcılar.
3. **Disk** — kalıcı ama en az uçucu olan.

Pratikte modern olayda **önce bellek dökümü alınır, sonra disk imajı**. Bellek dökümü için WinPmem veya EDR'ın kendi memory acquisition özelliği kullanılır. Makine kapalı geldiyse (ele geçirilmiş, çoktan kapatılmış), RAM gitmiştir; hiberfil.sys ve pagefile.sys üzerinden kısmi bellek kurtarmayı denersin ama umut azdır.

**Kritik karar noktası — kapatmak mı, canlı mı toplamak?**
- Ransomware aktif şifreleme yapıyorsa: **containment önce**. Ağdan izole et (kabloyu çek / EDR ile network isolation), ama makineyi hemen KAPATMA — RAM'de şifreleme anahtarı olabilir. Bazı ailelerde anahtar bellekte bulunmuştur.
- Fail hâlâ interaktif oturumda ("hands-on-keyboard") ise: acele kapatma failin izlerini silmesini tetikleyebilir; sessizce bellek al, izole et, sonra karar ver.

### 2.1 Delil toplama: imajlama

Karar: **tam disk imajı mı, hedefli triage koleksiyonu mu?**

Ölçekte (onlarca/yüzlerce host) tam imaj mümkün değil. Burada **KAPE** (Kroll Artifact Parser and Extractor) devreye girer. KAPE, sadece adli değeri yüksek artefaktları (kilitli dosyalar dâhil, VSS ve ham NTFS okuma ile) dakikalar içinde toplar: `$MFT`, `$J` (USN Journal), registry hive'ları, event log'lar, Prefetch, SRUM, Amcache, tarayıcı geçmişi, LNK, Jump List. Ölçekte dağıtım için **Velociraptor** — endpoint'lere sorgu gönderip artefakt toplayan, hunt yapabilen açık kaynak platform. "500 makinede şu IOC var mı" sorusuna Velociraptor VQL ile saatler içinde cevap verirsin.

Anchor makinelerde tam imaj: FTK Imager, `dd`/`dc3dd`, veya X-Ways ile bit-bit kopya. **Write-blocker** (donanımsal ya da yazılımsal) fiziksel diske dokunuyorsan zorunlu. Sanal ortamda snapshot / VMDK kopyası alırsın.

**Her toplamada hash al** (MD5 çakışmaya açık ama pratikte hâlâ ikincil olarak; asıl SHA-256). Toplama anında ve sonradan tekrar hash'le, eşleşmeyi belgele. Bu chain of custody'nin temelidir.

### 2.2 İnceleme mantığı: hangi artefakt hangi soruya cevap verir

DFIR analistinin kafasındaki harita, sorulara göre organize olur. "Şu artefaktı görünce şu sonuca giderim" örnekleri:

**Soru: Ne çalıştırıldı? (Execution)**
- **Prefetch** (`C:\Windows\Prefetch\*.pf`): Bir çalıştırılabilir çalıştıysa Prefetch dosyası oluşur. İçinde son 8 çalıştırma zamanı, çalıştırma sayısı, ilişkili dosya/DLL yolları. `PECmd` (Eric Zimmerman) ile parse. **Yorum**: `RUNDLL32.EXE` normal ama `C:\Users\Public\svchost.exe` için bir prefetch görürsem alarm — `svchost` asla oradan çalışmaz, bu bir maskeleme (masquerading).
- **Amcache.hve** ve **ShimCache (AppCompatCache)**: Çalıştırılmış (bazen sadece var olan) binary'lerin SHA-1'i, yolu, ilk görülme zamanı. **Yorum**: Prefetch silinmiş olsa bile Amcache faili yakalayabilir. İkisini çapraz kontrol ederim; biri boş biri dolu ise anti-forensics şüphesi.
- **SRUM** (`SRUDB.dat`): Uygulama başına ağ trafiği (bayt cinsinden) ve kaynak kullanımı. **Yorum**: Exfiltrasyon şüphesinde altın. "Hangi process gigabaytlarca veri gönderdi" sorusuna SRUM cevap verir. `SrumECmd` ile parse.

**Soru: Kalıcılık nasıl sağlandı? (Persistence)**
- **Registry Run/RunOnce anahtarları**, `Services`, `Scheduled Tasks` (`C:\Windows\System32\Tasks\`), WMI event subscription, Startup klasörleri. RECmd / Registry Explorer (Eric Zimmerman) ile hive'ları tarar, Autoruns mantığıyla bakarsın. **Yorum**: Görünürde meşru isimli ama son 48 saatte oluşmuş bir scheduled task, ilk şüphelim.

**Soru: Fail dosyalarla ne yaptı? (Anti-forensics ve dosya faaliyeti)**
- **`$MFT`**: NTFS'in kalbi. Her dosyanın oluşturma/değiştirme/erişim/MFT-değişim (MACB) zamanları hem `$STANDARD_INFORMATION` hem `$FILE_NAME` özniteliklerinde. **Yorum — timestomping tespiti**: `$SI` zamanı 2019'u, `$FN` zamanı 2026'yı gösteriyorsa fail zaman damgasını geri kaydırmış (timestomping). `MFTECmd` çıktısında bu ikisini yan yana koyup tutarsızlık ararım. Ayrıca `$SI` zaman damgasının saniye altı (sub-second) kısmı sıfırlanmışsa, bu birçok timestomping aracının imzasıdır.
- **`$J` USN Journal**: Dosya oluşturma/silme/yeniden adlandırma olay akışı. **Yorum**: Fail dosyayı silmiş olsa bile USN Journal "şu dosya şu anda silindi" kaydını tutar. Silinen dropper'ın adını ve zamanını buradan çıkarırım.

**Soru: Kim, ne zaman, nereden erişti? (Kullanıcı faaliyeti ve lateral movement)**
- **LNK dosyaları** ve **Jump Lists**: Açılan dosyaların (silinmiş olsa, hatta harici USB'de olsa bile) yolunu, boyutunu, zaman damgalarını, volume seri numarasını tutar. **Yorum**: `E:\` üzerinde bir LNK görürsem harici medya kullanımı; volume seri no ile USB'yi eşleştiririm.
- **ShellBags**: Gezinilen klasörler (silinmiş olanlar dâhil). Fail hangi klasörleri gezdi?
- **Event Logs** (`Security.evtx`, `System`, `RDP` ile ilgili `TerminalServices-*`): 4624 (başarılı logon, Logon Type ile — Type 3 ağ, Type 10 RDP), 4625 (başarısız — brute-force), 4672 (özel yetki atanması), 7045 (yeni servis kurulumu — çoğu zaman malware/PsExec izi), 4688 (process oluşturma, komut satırıyla — açıksa altın). **Yorum**: Ard arda 4625'ler ardından tek 4624 → başarılı brute-force. Kaynak IP'yi çekerim.

Analiz platformu olarak **Autopsy** (açık kaynak, keyword search + dosya kurtarma + carving için iyi bir all-in-one) ya da ticari X-Ways / EnCase kullanılır. Kilit teknik: **timeline**. Tüm bu artefaktları tek bir zaman ekseninde birleştirmek. **Plaso/log2timeline** ile "süper timeline" üretir, sonucu **Timesketch**'e yükler; binlerce olayı görsel olarak tarar, filtrelersin. Karar mantığı burada somutlaşır: bir "anchor" olayı (örn. şüpheli 7045 servis kurulumu) bulursun, o zaman damgasının **±5 dakikasına** zoom yaparsın — o pencerede ne çalıştı, hangi dosya oluştu, hangi ağ bağlantısı açıldı, hepsi tek ekranda dizilir. Bu, olayın "hikâye"sini kurmanın yoludur.

**YARA**: Bilinen malware imzaları ya da kendi yazdığın kuralla imaj/bellek içinde tarama. Şüpheli bir binary bulduğunda YARA kuralıyla diğer host'larda ("bu var mı") hunt yaparsın (Velociraptor + YARA kombinasyonu güçlü).

**Volume Shadow Copy (VSS) — çoğunun atladığı hazine.** Windows, System Restore/Shadow Copy ile diskin geçmiş "gölge" hâllerini tutabilir. Fail bugünkü dosyayı sildiyse bile, dünkü gölge kopyada duruyor olabilir. `vshadow` / `vssadmin list shadows` ile mevcut gölgeleri sıralar, her birini ayrı bir "geçmiş disk" gibi mount edip aynı artefaktları (registry, $MFT, dosyalar) **zaman içinde** karşılaştırırsın. Bir registry anahtarının dün var olup bugün silindiğini görmek, kalıcılığın ne zaman kurulup temizlendiğini tam olarak verir. Fail `vssadmin delete shadows` çalıştırdıysa (ransomware'de standart), bu komutun kendisi event log ve prefetch'te iz bırakır — silme girişimi de bir bulgudur.

**Bellek analizi — Volatility.** Disk yanında bellek dökümünü **Volatility** ile işlersin: `pslist`/`pstree` (process hiyerarşisi — WINWORD'ün altında POWERSHELL doğal değildir, alarm), `malfind` (injekte edilmiş/çalıştırılabilir bellek bölgeleri), `netscan` (dökümandaki anlık ağ bağlantıları — hangi C2 IP'sine bağlıydı), `cmdline` (process'lerin tam komut satırı — diskte silinmiş olsa bile), `handles`/`dlllist`. **Yorum**: Diskte hiçbir binary bulamadığın "fileless" bir saldırıda, malfind + netscan çoğu zaman kayıp halkayı verir.

### 2.3 Zamanı sabitle: saat dilimi ve saat sapması

Her şeyi UTC'ye normalize et. Sistemin RegistryTimeZoneInformation'ından yerel dilimi ve saat sapmasını (clock skew) belirle. Farklı kaynakların (event log yerel, `$MFT` UTC, tarayıcı geçmişi epoch) zamanlarını hizalamazsan sahte "sıralama" çıkarır, yanlış nedensellik kurarsın. Bu, timeline'ın en sinsi tuzağıdır.

---

## 3. Kritik dikkat noktaları

**Delil bütünlüğü ve order of volatility.** Kural basit: en uçucudan en kalıcıya doğru topla, ve **hiçbir toplama işleminde kanıtı değiştirme**. Canlı sistemde araç çalıştırmak diski değiştirir (yeni prefetch, yeni MFT kaydı) — bunu bilerek kabul edersin ve **ne yaptığını belgelersin**. Prensip: müdahalenin ayak izi minimum ve **dokümante** olsun. Toplama araçlarını mümkünse harici medyadan çalıştır, çıktıyı incelenen diske yazma.

**Hash ve doğrulama.** İmaj alırken kaynak diskin hash'ini al, imajın hash'ini al, eşitliği kanıtla. Analizi **daima kopya üzerinde** yap, orijinale bir daha dokunma. Write-blocker fiziksel disklerde şart. Hash zinciri koparsa mahkemede/denetimde tüm delil çöker.

**Chain of custody (delil zinciri).** Kim, ne zaman, neyi, nereden aldı; nerede saklandı; kime devredildi — her transfer imzalı ve zaman damgalı. Delil deposu erişimi kısıtlı. Bu bürokrasi değil; delilin "kurcalanmamış" olduğunu ispatın tek yolu. Kurumsal bir olayda mahkemeye gitmese bile sigorta ve düzenleyici için aynı titizlik gerekir.

**Anti-forensics'e karşı bilinç.** Failler iz siler: log temizleme (Event 1102 — "audit log cleared" — bu bile bir delildir!), timestomping, `sdelete` ile güvenli silme, VSS (Volume Shadow Copy) silme (`vssadmin delete shadows`), dosyaları alternate data stream'lere (ADS) saklama, LOLBin (living-off-the-land) kullanımı — meşru Windows araçlarıyla (certutil, bitsadmin, mshta, regsvr32) iş görme. Pro refleksi: **bir artefaktın yokluğu da bir bulgudur.** Prefetch kapalıysa neden kapalı? Loglar boşsa kim boşalttı? VSS'ler silinmişse, silinmeden önceki gölge kopyalardan (varsa) veri kurtarmayı denerim. Silme her zaman tam değildir — MFT'de "silinmiş ama üzerine yazılmamış" kayıtlar, unallocated space'te **file carving** ile kurtarılabilen dosya parçaları çıkar.

**SSD gerçeği.** SSD'lerde TRIM, silinen blokları donanım seviyesinde sıfırlayabilir; HDD'deki gibi "silinmiş dosyayı kurtarma" garantisi yoktur. Bunu baştan bilerek beklentini ayarla — SSD'de unallocated space carving ile mucize bekleme, ama MFT kayıtları, journal ve VSS hâlâ değerli.

**Şifreli disk.** BitLocker/LUKS açık makinede canlı toplama yapmazsan, kapalı diskte kurtarma anahtarı (recovery key) olmadan hiçbir şeye ulaşamazsın. Karar: şifreli ve açık bir makineyle karşılaşırsan, kapatmadan önce canlı imaj almayı ya da recovery key'i kurumsal AD/Intune escrow'undan almayı planla. Kapatıp sonra "açamıyorum" demek, geri dönüşü olmayan bir hata.

**Araç doğrulama ve tekrar edilebilirlik.** Kullandığın parser'ın (özellikle tek başına açık kaynak araçların) çıktısına körü körüne güvenme; kritik bir bulguyu ikinci bir araçla ya da ham veriye (hex'te MFT kaydı) bakarak teyit et. Adli sonuç, bağımsız bir analistin aynı imajdan aynı sonuca ulaşabilmesi (reproducibility) ile güç kazanır. Her adımını, hangi aracı hangi parametreyle çalıştırdığını not al.

---

## 4. Gerçek dünya senaryosu

**Vaka:** Orta ölçekli bir şirketin finans departmanından bir kullanıcı, "bilgisayarım tuhaf davranıyor, sabah bir Office belgesi açtım" diye bildirimde bulunuyor. EDR bir uyarı üretmiş ama düşük öncelikli işaretlenmiş. Görev: ne oldu, yayıldı mı, ne alındı?

**Adım 1 — Triage toplama.** Makine açık. Önce WinPmem ile bellek dökümü, ardından KAPE ile hedefli artefakt koleksiyonu (`!SANS_Triage` hedefi) alıyoruz. Hash'ler kaydediliyor, makine EDR ile ağdan izole ediliyor. RAM'i acele kapatmıyoruz.

**Adım 2 — İlk giriş.** Kullanıcı "Office belgesi" dedi. `$MFT` ve tarayıcı/e-posta artefaktlarına bakıyoruz. `%Temp%` altında `Fatura_Ekim.docm` (makrolu belge) buluyoruz, oluşturma zamanı 08:14. Outlook'un ekler klasöründe aynı dosya var — **phishing eki**.

**Adım 3 — Execution zinciri.** Prefetch (`PECmd`) ve Amcache'e bakıyoruz. 08:15'te `WINWORD.EXE`, hemen ardından **08:15'te `POWERSHELL.EXE`** çalışmış. Makrolar tipik olarak PowerShell doğurur. Event log 4688 açıkmış (şanslıyız) — komut satırı: base64 kodlu, `-enc` bayraklı, encoded komut çözüldüğünde bir dış IP'den ikinci aşama indirme. Bu **dropper** davranışı.

**Adım 4 — Persistence.** Registry Explorer ile Run anahtarlarını ve `Tasks` klasörünü tarıyoruz. 08:16'da oluşturulmuş `\Microsoft\Windows\UpdateSync` adlı bir scheduled task — meşru görünmek için "Update" ismi almış ama Microsoft'un böyle bir görevi yok ve zamanı olayla çakışıyor. Çalıştırdığı: `%AppData%\svchost.exe`. **Masquerading + persistence** doğrulandı.

**Adım 5 — Exfiltrasyon kontrolü.** SRUM (`SrumECmd`) parse ediliyor. `svchost.exe` (sahte olan, AppData'daki) öğleden sonra ~120 MB giden trafik üretmiş. Kullanıcının "Finans_Raporlari" klasöründeki ShellBags ve son LNK'ler, o klasörün 14:30 civarı gezildiğini gösteriyor. USN Journal'da bir `.zip` dosyasının oluşturulup 14:45'te silindiği kaydı var. **Sonuç: veri toplandı, arşivlendi, dışarı gönderildi.**

**Adım 6 — Yayılım (lateral movement) kontrolü.** Security log'da Logon Type 3 ile başka bir sunucuya bağlantı denemesi var mı? 4648 (explicit credential) ve 4624 Type 3 kayıtlarını tarıyoruz. Bu makineden bir dosya sunucusuna Type 3 logon görülüyor, 15:10. Velociraptor ile o dosya sunucusunda ve aynı subnet'teki host'larda `svchost.exe` (aynı SHA-256) için YARA/hash hunt başlatıyoruz — **ikinci bir makinede eşleşme** çıkıyor.

**Varılan sonuç:** İlk giriş 08:14'te makrolu phishing ekiyle; PowerShell dropper ikinci aşamayı çekmiş; sahte scheduled task ile kalıcılık; finans verisi arşivlenip ~120 MB dışarı sızmış; en az bir başka makineye yayılım olmuş. Bu bulgular containment kapsamını (iki host + dosya sunucusu izolasyonu, şifre resetleri) ve KVKK ihlal bildirimi değerlendirmesini tetikliyor. Timeline Timesketch'te tek eksende sunuluyor — 08:14 phishing'den 15:10 lateral movement'a kadar kesintisiz hikâye.

---

## 5. Yaygın tuzaklar ve pro yargısı

**1. Canlı sistemi refleksle kapatmak (ya da tam tersi refleksle açık bırakmak).** Acemi ya "fişi çeker" (RAM'i ve belki şifreleme anahtarını yok eder) ya da saatlerce dokunmaz (fail iz siler). Pro, containment ile delil koruma arasındaki dengeyi olayın türüne göre kurar: aktif ransomware'de önce bellek + izolasyon, hands-on-keyboard'da sessiz gözlem, sonra hamle.

**2. Tek artefakta güvenmek.** "Prefetch'te yok, demek çalışmadı." Yanlış. Prefetch kapalı olabilir, silinmiş olabilir, ya da 64-bit'te farklı davranabilir. Pro **her sonucu en az iki bağımsız artefaktla doğrular** (Prefetch + Amcache + $MFT + Event log çaprazı). Tek kaynak = zayıf iddia.

**3. Zaman dilimini normalize etmemek.** Farklı kaynakların zamanlarını hizalamadan timeline kurmak, olmayan bir nedensellik uydurur. "A, B'den önce oldu" derken A yerel saat, B UTC ise koca bir yanılgı. Her şey UTC, saat sapması hesaba katılmış olmalı.

**4. Timestomping'i gözden kaçırmak.** Sadece `$SI` zaman damgalarına bakıp "bu dosya 2019'dan kalma, alakasız" demek. Pro, `$SI` ve `$FN` zaman damgalarını yan yana koyar, sub-second alanlarına bakar; USN Journal'ın "değişmeyen" olay zamanına güvenir.

**5. Bir artefaktın yokluğunu "temiz" saymak.** Boş event log masumiyet değil, **silme** işaretidir (1102'yi ara). Kapalı prefetch, silinmiş VSS, eksik loglar — hepsi anti-forensics sinyali. Pro için "yokluk" da veridir.

**6. Ölçekte boğulmak.** 200 makinenin hepsine tam imaj çıkarmaya çalışmak haftalar yer, olay soğur. Pro önce triage + hunt (KAPE/Velociraptor) ile kapsamı daraltır, sadece 2-3 anchor makinede derin inceleme yapar.

**7. IOC avına saplanıp TTP'yi kaçırmak.** Sadece hash/IP eşleştirmek. Fail bir sonraki saldırıda hash'i değiştirir. Pro davranışa (TTP — masquerading, LOLBin kullanımı, scheduled task persistence) odaklanır; MITRE ATT&CK diliyle etiketler, böylece varyantları da yakalar.

**8. Delil zincirini gevşetmek.** "Nasılsa mahkemeye gitmez" diye hash almamak, kopya yerine orijinalde çalışmak. Sonra iş yasal boyuta taşınınca tüm delil kullanılamaz hâle gelir. Pro, başından **her delili mahkemelik varsayar** ve titizliği gevşetmez.

**9. RAM'i unutmak.** Sadece diske bakmak. Fileless (dosyasız) malware, injekte edilmiş kod, çözülmüş komut satırları, ağ bağlantıları çoğu zaman **yalnızca bellekte** yaşar. Volatility ile bellek analizi (pslist, malfind, netscan, cmdline) disk bulgularını tamamlar ve çoğu zaman "kayıp halkayı" verir.

**10. Hikâyeyi kurmadan rapor yazmak.** Bulguları liste hâlinde dökmek ("şu prefetch var, şu task var") ama bunları neden-sonuç zincirine oturtmamak. Pro'nun çıktısı, karar vericinin okuyup **kapsam ve aksiyon** çıkarabileceği bir zaman çizelgesi ve anlatıdır — teknik bulgu yığını değil.

---

**Özet zihinsel model:** Disk forensics, artefaktları toplama işi değil; **doğru soruyu sorup, o soruya cevap veren artefaktları çapraz doğrulayarak zamanla dizip, olayın hikâyesini kurma** işidir. Araçlar (KAPE, Velociraptor, Volatility, Plaso, Timesketch, Zimmerman seti, YARA, Autopsy) bu yargının hizmetkârıdır. Değer, "svchost'u yanlış yerde görünce alarma geçen" ve "boş logu masumiyet değil silme sayan" refleksin kendisindedir.
