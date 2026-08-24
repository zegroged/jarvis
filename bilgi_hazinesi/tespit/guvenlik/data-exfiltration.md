# Veri Sızdırma (Data Exfiltration) — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin, veri sızdırma tekniğini önce saldırgan gözüyle anlar, sonra o davranışın geride bıraktığı izleri ve bunları alarma çeviren tespit mantığını kurar. Amaç savunma ve tespit mühendisliğidir; canlı operasyonel saldırı reçetesi değildir.

Veri sızdırma, bir saldırının çoğu zaman en son ama en yıkıcı halkasıdır. Bir saldırgan içeri girer, yatayda yayılır, ayrıcalık yükseltir, hedef veriyi toplar (collection) — ama tüm bu emeğin karşılığını ancak veriyi kurum sınırının dışına, kendi kontrolündeki bir yere taşıdığında alır. MITRE ATT&CK terminolojisinde bu, **Exfiltration (TA0010)** taktiğidir. Mavi takım için buradaki temel gerçek şudur: sızdırma anı, saldırganın kaçınılmaz olarak "gürültü" çıkarmak zorunda kaldığı andır. Veri bir yerden bir yere akmak zorundadır ve her akış bir iz bırakır.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Veri sızdırma tek bir teknik değil, bir teknik ailesidir. Saldırganın istismar ettiği ortak şey şudur: **kurumların çoğu, içeriden dışarıya giden trafiği, dışarıdan içeriye gelen trafik kadar sıkı denetlemez.** Perimeter savunması geleneksel olarak "gelene" odaklıdır; oysa sızdırma "gidene" ihtiyaç duyar. Saldırgan bu asimetriyi sömürür.

Kavramsal olarak saldırganın çözmesi gereken üç problem vardır:

**1. Kanal seçimi (channel).** Veriyi hangi yoldan çıkaracak? Burada temel strateji "meşru trafiğe karışmak"tır. En sevilen kanallar zaten kurumda normalde açık ve gürültülü olan protokollerdir:
- **C2 kanalı üzerinden sızdırma (T1041, "Exfiltration Over C2 Channel"):** Zaten kurulu olan komuta-kontrol bağlantısı, veriyi de taşır. Ekstra bağlantı açmaz, dolayısıyla daha az iz bırakır.
- **Alternatif protokol üzerinden sızdırma (T1048):** C2'den ayrı bir kanal — FTP, TFTP, DNS, ICMP, SMTP. Özellikle **DNS tünelleme** klasiktir çünkü DNS neredeyse hiçbir kurumda tamamen bloklanmaz.
- **Web servisi üzerinden sızdırma (T1567):** Veriyi meşru bulut servislerine yükler — GitHub, Dropbox, Google Drive, pastebin türevleri, hatta bir GitHub Pages sitesi. Trafiğin hedefi "güvenilir" bir alan adı olduğu için firewall/proxy nadiren durdurur. Alt teknik **T1567.001** özellikle "kod deposu / bulut koduna sızdırma"yı kapsar.
- **Fiziksel ortam üzerinden (T1052):** USB gibi çıkarılabilir medya. Ağ hiç görmez.
- **Planlı transfer (T1029) ve otomatik sızdırma (T1020):** Veri, tespit penceresini daraltmak için belirli saatlerde (örneğin gece) ya da bir olay tetiklendiğinde otomatik olarak dışarı akar.

**2. Boyut ve hız problemi.** Büyük veri kütlesi, ani bir trafik zirvesi (spike) yaratır ve bu spike bir alarmdır. Saldırgan bunu iki şekilde yönetir: (a) **sıkıştırma/şifreleme ile boyut küçültme** (T1030 ile birlikte "veriyi paketleme"), (b) **düşük-ve-yavaş (low-and-slow)** yaklaşımı — veriyi günlere yayarak küçük parçalar hâlinde göndermek, böylece istatistiksel eşiklerin altında kalmak.

**3. Gizleme.** Sızdırılan veri neredeyse her zaman şifrelenir ya da kodlanır (base64, hex). Bu, DLP (Data Loss Prevention) sistemlerinin içerik-tabanlı imzalarını (örneğin "kredi kartı numarası deseni") boşa çıkarır. Mavi takım açısından bunun kritik sonucu şudur: **içeriğe güvenemezsin, davranışa güvenmek zorundasın** — kim, nereye, ne kadar, ne zaman, hangi protokolle.

Bir başka boyut, verilen Sigma kurallarının işaret ettiği **SaaS/DevOps platformları üzerinden sızdırma**dır. Burada saldırgan tek bir paket bile göndermez; bunun yerine platformun kendi meşru özelliklerini kötüye kullanır: özel bir repoyu public yapar, bir organizasyonu/repoyu kendi hesabına transfer eder, özel repoların fork'lanmasına izin veren ayarı açar, ya da bir GitHub Pages sitesini public'e çevirerek iç kaynağı internete açar. Bu, "veriyi çalmak" yerine "veriyi zaten bulunduğu yerde herkese açmak" biçiminde bir sızdırmadır ve ağ katmanında hiç görünmez — yalnızca **audit log** katmanında görünür.

---

## 2. Bıraktığı izler / artefaktlar

Sızdırma davranışı, kanaldan bağımsız olarak birkaç katmanda iz bırakır. Bunları bilmek, doğru log kaynağını doğru tespite bağlamak için şarttır.

**Ağ katmanı (network / proxy / firewall / NetFlow):**
- **Yön asimetrisi:** Normalde çoğu istemci için `bytes_out << bytes_in` (indirilen, gönderilenden çok fazladır). Sızdırmada bu ters döner — bir iş istasyonundan dışarıya olağandışı büyüklükte `bytes_out`.
- **DNS anomalileri (T1048 / DNS tünelleme):** Anormal uzun subdomain'ler, yüksek entropili (rastgele görünen) etiketler, tek bir domain'e olağandışı yüksek sayıda TXT/NULL/CNAME sorgusu, olağandışı yüksek NXDOMAIN oranı.
- **Beaconing:** Sabit aralıklı, düzenli dış bağlantılar — C2 kanalı üzerinden sızdırmanın (T1041) parmak izi.
- **Alışılmadık hedefler:** Kurumun normalde konuşmadığı bulut depolama, pastebin, kişisel Dropbox/Drive endpoint'leri, yeni kayıtlı (newly registered) domain'ler.
- **Alışılmadık protokol/port:** İş istasyonundan giden ham FTP, TFTP (UDP/69), SMTP, ICMP payload'ları.

**Canary / honeypot katmanı (verilen OpenCanary kuralları):**
Bu, en yüksek sinyal-gürültü oranına sahip artefakt kaynağıdır. Bir OpenCanary düğümü sahte servisler (FTP, TFTP vb.) sunar. Bu servislere hiçbir meşru kullanıcının erişmesi için sebep yoktur; dolayısıyla oradaki her etkileşim tanımı gereği şüphelidir. Loglar `logtype` alanıyla ayrışır: FTP giriş denemesi `logtype: 2000`, TFTP isteği `logtype: 10001`. Bir saldırgan ağı tararken ya da veri taşıyacağı bir kanal ararken bu sahte servislere dokunduğunda kendini ele verir.

**SaaS / DevOps audit log katmanı (verilen GitHub kuralları):**
- `repo.pages_public` — bir repo'nun GitHub Pages sitesinin public'e çevrilmesi.
- Özel/dahili repoların fork'lanmasına izin veren ayarın açılması/temizlenmesi (`private_repository_forking`).
- Repository veya organizasyon transferi (`repo.transfer`, ilgili migration olayları).
- Bu olaylar yalnızca **audit log streaming** etkinse toplanabilir — bu, kuralların `definition` alanında açıkça belirtilen bir ön koşuldur ve mavi takımın öncelikle bu logging'i açmış olması gerekir.

**Uç nokta (endpoint / Windows Event Log / Sysmon):**
- **Sysmon Event ID 11 (FileCreate):** Sızdırma öncesi "staging" (evreleme) — verinin tek bir arşiv dosyasında toplanması. `.zip`, `.rar`, `.7z`, `.cab` dosyalarının olağandışı konumlarda (`C:\Users\Public`, `%TEMP%`, `C:\Windows\Temp`) oluşması.
- **Sysmon Event ID 3 (NetworkConnection):** Bir arşivleme/betik sürecinin (örn. `powershell.exe`, `rundll32.exe`, `curl.exe`) dış bir IP'ye bağlantı kurması.
- **Sysmon Event ID 1 / Windows Security 4688 (ProcessCreate):** Sıkıştırma ve transfer komut satırı desenleri — örneğin `rar.exe a -hp<parola>`, `Compress-Archive`, `certutil -encode`, `curl -T`, `Invoke-WebRequest ... -Method Put`, `bitsadmin /transfer`.
- **Çıkarılabilir medya (T1052):** Windows Security **Event ID 6416** (yeni harici cihaz tanındı) ve büyük dosya kopyalama olayları.
- **DLP / e-posta ağ geçidi olayları:** İzin verilenler dışı alıcıya büyük ek, dış adrese otomatik yönlendirme kuralı oluşturma.

**Kimlik/erişim katmanı:**
- Bir servis hesabının ya da kullanıcının normalde erişmediği veri depolarına, dosya paylaşımlarına toplu erişimi — sızdırma öncesi collection'ın izi.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Verilen gerçek Sigma kuralları iki farklı tespit felsefesini temsil eder: **(A) canary/tuzak temelli** ve **(B) SaaS audit-log temelli**. İkisinin de ortak gücü, düşük yanlış-pozitif oranıdır çünkü izledikleri olaylar meşru iş akışında ya hiç görülmez ya da nadiren görülür. Aşağıda her birinin mantığını açıp somutlaştırıyorum.

### 3.1 Canary temelli tespit — OpenCanary FTP/TFTP

**Mantık:** OpenCanary bir aldatma (deception) aracıdır. Ürettiği loglar `category: application`, `product: opencanary` altında toplanır ve her servis tipi bir sayısal `logtype` ile ayrışır. Kural, tek bir alana bakar ve o alan eşleşirse **koşulsuz** alarm verir — çünkü bir tuzak servise dokunmanın masum açıklaması pratikte yoktur. İşte tam da bu yüzden "OpenCanary - FTP Login Attempt" kuralının `falsepositives` alanı "Unlikely" ve `level` değeri `high`'tır.

FTP giriş denemesi için tespit mantığı, gerçek kuraldaki gibi:

```yaml
# OpenCanary - FTP Login Attempt (id: 6991bc2b-ae2e-447f-bc55-3a1ba04c14e5) mantığına dayalı
logsource:
    category: application
    product: opencanary
detection:
    selection:
        logtype: 2000        # OpenCanary'de FTP giriş denemesini işaret eder
    condition: selection
level: high
```

TFTP isteği için mantık aynıdır, yalnızca `logtype` değişir — gerçek "OpenCanary - TFTP Request" kuralı `logtype: 10001` kullanır ve `attack.exfiltration` / `attack.t1041` ile etiketlidir. TFTP'nin özellikle önemli olmasının sebebi, hafif ve kimlik doğrulamasız bir dosya transfer protokolü olması, dolayısıyla sızdırma için basit bir alternatif kanal (T1048) sunmasıdır. Bir iş istasyonu ya da tarayan bir aktör bu tuzak TFTP servisine bir istek yollarsa, bu neredeyse kesin bir düşmanca keşif/sızdırma sinyalidir.

Bu iki kuralın mavi takım için asıl değeri: **eşik ayarı, baseline, makine öğrenmesi gerektirmezler.** "Bir olay geldi mi? Alarm ver." Bu yüzden bir SOC için erken uyarı sistemi olarak paha biçilmezdir — özellikle iç ağa yerleştirilmiş canary'ler, yatay hareket sonrası sızdırma kanalı arayan saldırganı, gerçek veriye ulaşmadan yakalar.

### 3.2 SaaS audit temelli tespit — GitHub sızdırma sinyalleri

Bu grup, ağ katmanında görünmeyen "platform içi" sızdırmayı yakalar. Ortak `logsource` şudur:

```yaml
logsource:
    product: github
    service: audit
```

Ve mutlak ön koşul, kuralların `definition` alanında yazdığı gibi, **audit log streaming**'in etkin olmasıdır. Bu açık değilse bu olaylar hiç toplanmaz — tespit mühendisliğinin ilk adımı bu logging'i sağlamaktır.

**GitHub Pages'in public yapılması** (gerçek kural id: `0c46d4f4-a2bf-4104-9597-8d653fc2bb55`, `attack.t1567.001`) tam olarak "web servisi üzerinden sızdırma" alt tekniğidir — iç bir repo'nun içeriği, Pages özelliği kötüye kullanılarak internete servis edilir. Tespit mantığı sade ve tek alanlıdır:

```yaml
# GitHub Repository Pages Site Changed to Public mantığı
logsource:
    product: github
    service: audit
detection:
    selection:
        action: 'repo.pages_public'
    condition: selection
falsepositives:
    - Yetkili kullanıcıların meşru repo yayınlaması
level: low
```

Buradaki `level: low` bilinçli bir seçimdir: bu eylemin meşru bir yayınlama süreci olma ihtimali yüksektir, dolayısıyla tek başına yüksek öncelikli bir olay değildir. Değeri, **korelasyonda** ortaya çıkar (bkz. bölüm 4).

**Özel repo fork ayarının açılması/temizlenmesi** (id: `69b3bd1e-...`, `attack.t1020` + `attack.t1537`) ve **repo/organizasyon transferi** (id: `04ad83ef-...`, aynı etiketler) ise kalıcılık (persistence) ve sızdırma niyetini birlikte işaret eder. Bir saldırgan özel repoların fork'lanmasına izin vererek kod tabanının kopyalarının çıkarılmasının önünü açar; bir repoyu/organizasyonu kontrol ettiği bir hedefe transfer ederek tüm veriyi tek hamlede taşır. Bu iki kuralın tespit mantığı da audit `action` alanındaki ilgili değere (fork ayarının enable/clear edilmesi, transfer olayı) demirlenir ve `condition: selection` ile tetiklenir.

Bu kuralların ortak dersi: **SaaS sızdırmasında tespitin birincil kaynağı ağ değil, uygulamanın kendi audit `action` alanıdır.** Mavi takım, önce doğru olayları streaming ile toplamalı, sonra "yüksek riskli yapılandırma değişikliği" olan `action` değerlerini bir izleme listesine bağlamalıdır.

### 3.3 İki basit tespit mantığı örneği (sentez)

Yukarıdaki gerçek kuralların mantığını genelleyerek, kendi ortamınızda kullanabileceğiniz iki basit tespit fikri — mevcut kuralların alan/felsefesine sadık kalarak:

**Örnek A — Herhangi bir canary etkileşimi = yüksek öncelik.** OpenCanary'nin FTP (`logtype: 2000`) ve TFTP (`logtype: 10001`) kurallarının mantığını tek bir "meta" kural altında birleştir: `product: opencanary` altındaki *herhangi bir* `logtype` eşleşmesi, kaynak IP ile birlikte SOC'a `high` seviye çıksın. Bu, sızdırma kanalı arayan aktörü kanal kurulmadan yakalar.

**Örnek B — SaaS "veriyi açığa çıkarma" olaylarının kümelenmesi.** `product: github, service: audit` altında, `repo.pages_public`, özel-repo fork ayarının açılması ve repo/org transferi `action` değerlerini tek bir izleme listesine koy. Tek bir olay düşük öncelikli olabilir; ama aynı aktör ya da kısa zaman penceresinde birden fazlası görülürse öncelik yükselt. Bu, bölüm 4'te anlatılan korelasyon yaklaşımının somut hâlidir.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan tespiti nasıl atlatmaya çalışır

**1. Meşru trafiğe karışma.** En temel kaçınma, gürültülü ve güvenilir kanalları kullanmaktır: DNS, HTTPS, GitHub/Drive/Dropbox gibi allow-list'te olan bulut servisleri. Verilen GitHub kurallarının varlık sebebi tam da budur — saldırgan "güvenilir platform" içinde kaldığı için ağ savunması onu görmez.
- **Savunma:** Ağ katmanının kör kaldığı yerde uygulama audit log'una geç. `repo.pages_public`, fork ayarı, transfer gibi `action` değerlerini izle. Ağ tarafında ise "güvenilir" domain'lere bile giden `bytes_out` hacmini davranışsal olarak baseline'la.

**2. Düşük-ve-yavaş (low-and-slow).** Veriyi günlere yayarak hacim eşiklerinin altında kalmak. Tek seferlik büyük transfer alarmını tetiklemez.
- **Savunma:** Anlık eşik yerine **kümülatif** pencere kullan (bir kaynaktan 24 saatte toplam giden bayt). Ayrıca beaconing'in düzenliliğini (jitter analizi) izle — low-and-slow bile bir ritim bırakır.

**3. Şifreleme ve kodlama.** İçeriği şifreleyerek/base64'leyerek DLP imza motorlarını boşa çıkarma.
- **Savunma:** İçerik yerine metadata ve davranış. Şifreli olsa da yön asimetrisi, hedef itibarı, DNS entropisi, bağlantı ritmi hâlâ görünür. Canary'ler burada özellikle güçlüdür çünkü içeriğe hiç bakmazlar — bir tuzağa dokunmak, ne taşındığından bağımsız olarak alarmdır.

**4. Canary'lerden kaçınma.** Deneyimli bir saldırgan tuzak servislerin varlığından şüphelenip onlardan kaçınmaya çalışabilir.
- **Savunma:** Canary'leri gerçek varlıklardan ayırt edilemez kıl, ağa inandırıcı biçimde serp (dosya paylaşımlarında, kimlik depolarında canary token'lar). OpenCanary'nin `logtype` temelli, koşulsuz-alarm modeli tam da bu yüzden değerli: kaçınmak için saldırganın önce tuzağı bulması gerekir, bulma denemesi de çoğu zaman iz bırakır.

**5. Audit logging'i kör etme.** SaaS sızdırmasında gelişmiş aktör, mümkünse audit streaming'i kapatmaya ya da log'ları temizlemeye çalışabilir.
- **Savunma:** Streaming yapılandırmasındaki değişikliklerin kendisini izle (logging'in kapatılması bir alarm olmalı). Log'ları merkezî ve değiştirilemez (immutable/WORM) bir SIEM'e akıt, böylece kaynaktaki silme geriye dönük olamaz.

### Tipik false positive kaynakları ve ayıklama

Tespit mühendisliğinde asıl zorluk, alarmın "gerçek mi" olduğunu ayırmaktır. Sızdırma tespitlerinde tipik yanlış-pozitif kaynakları:

**Meşru bulut yedekleme ve senkronizasyon.** OneDrive/Drive/Dropbox istemcileri, yedek yazılımları büyük `bytes_out` üretir.
- **Ayıklama:** Bilinen yedek/sync process'lerini ve hedef domain'leri allow-list'e al; sızdırma şüphesini yalnızca *beklenmedik* process → *beklenmedik* hedef kombinasyonuna daralt.

**Meşru yayınlama ve DevOps akışı.** GitHub Pages kuralının `falsepositives` alanında açıkça yazdığı gibi, bir Pages sitesinin public yapılması çoğu zaman normal yayınlama sürecidir. Repo transferi de meşru bir yeniden yapılanma olabilir.
- **Ayıklama:** Eylemi gerçekleştiren aktörü ve bağlamı kontrol et — yetkili bir maintainer mı, olağan çalışma saatinde mi, değişiklik yönetimi kaydı var mı? Bu yüzden Pages kuralı `low` seviyededir: tek başına aksiyon değil, korelasyon girdisidir.

**Yönetim ve izleme araçları.** Ağ tarama, envanter ve monitoring araçları alışılmadık protokollerde bağlantı kurabilir. Canary tarafında ise dahili zafiyet tarayıcıları (vulnerability scanner) tuzak servislere dokunabilir.
- **Ayıklama:** Onaylı tarayıcıların IP'lerini canary alarmlarında istisna yap — ama dikkatle, çünkü bu istisna saldırganın da saklanabileceği bir boşluk yaratır. Tarayıcı IP'sinden gelen etkileşimi tamamen susturmak yerine düşük önceliğe çek.

**DNS'in doğal gürültüsü.** CDN, antivirüs telemetrisi ve bazı meşru servisler uzun, yüksek-entropili subdomain'ler üretir; bunlar DNS-tünelleme tespitini yanıltır.
- **Ayıklama:** Bilinen CDN/güvenlik domain'lerini baseline'la; entropi eşiğini tek başına kullanma, sorgu hacmi + NXDOMAIN oranı + hedef itibarı ile birleştir.

### Bütünsel yaklaşım: korelasyon

Sızdırma tespitinin en güçlü hâli tek bir kural değil, **zincirin korelasyonudur.** Verilen kuralların her biri zincirin bir halkasını görür: canary etkileşimi (kanal arayışı), staging (Sysmon 11 arşiv oluşumu), collection (olağandışı erişim), ve nihai çıkış (GitHub Pages public / transfer / DNS spike). Tek başına `low` olan bir GitHub Pages olayı, aynı aktörden gelen bir canary tetiklenmesi ya da bir arşivleme process'i ile aynı zaman penceresinde görüldüğünde önceliği patlar. Mavi takımın işi, bu düşük-sinyalleri bir zaman ekseninde ve aktör kimliği etrafında birleştirip "izole olay"dan "sızdırma zinciri"ne yükseltmektir.

Özetle: sızdırma, saldırganın gizlenmek zorunda olduğu ama akışın kendisini gizleyemediği andır. İçeriğe değil davranışa bak; tuzakları (canary) erken uyarı olarak kullan; SaaS audit log'unu ağ kadar ciddiye al; ve tekil düşük-seviye sinyalleri korelasyonla birleştir. Hırsızı bu şekilde tanırsan, mücevheri kapıdan çıkmadan yakalarsın.
