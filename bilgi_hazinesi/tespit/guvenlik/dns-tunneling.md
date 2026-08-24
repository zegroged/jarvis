# DNS Tunneling / Exfiltration — Tespiti

## 1. Özet: saldırı + naif tespit

DNS tünellemesi, DNS protokolünü tasarlandığı iş (isim çözümleme) dışında bir taşıyıcı katman gibi kullanma sanatıdır. Fikir basittir: neredeyse hiçbir ağ DNS'i tamamen kapatamaz, çünkü kapatırsan kurum çöker. Güvenlik duvarı 443'ü, 22'yi, hatta ICMP'yi kısabilir ama 53/UDP (ve giderek DoH üzerinden 443) çoğu iç ağdan dışarıya bir şekilde akar. Saldırgan da bunu bilir. Sızdırılacak veriyi (dosya içeriği, komuta-kontrol trafiği, çalınan token'lar) base32/base64 ile kodlar, alt alan adı etiketlerine gömer ve kendi kontrolündeki otoritatif isim sunucusuna sorgu olarak yollar: `MFRGGZDF.exfil.saldirgan.com` gibi. Kurumun iç DNS resolver'ı bu sorguyu bilmediği için üst tarafa forward eder, sorgu internete çıkar, saldırganın otoritatif sunucusu veriyi decode eder ve TXT/CNAME/NULL yanıtıyla geri komut yollar. İki yönlü bir kanal kurulmuş olur. `iodine` klasik IP-over-DNS tünelidir; `dnscat2` ise doğrudan C2 için tasarlanmıştır ve şifreli, oturum tabanlı çalışır.

Naif tespit tam olarak yukarıdaki Sigma kuralının yaptığı şeydir: `process_creation` logsource'unda `Image|endswith: '\iodine.exe'` veya `Image|contains: '\dnscat2'`. Yani "bilinen tünelleme aracı diskte çalıştıysa yüksek seviye alarm ver". Bu kural doğrudur, yanlış değildir — `iodine.exe` adında bir process gerçek bir kurumsal Windows sunucusunda çalışıyorsa neredeyse kesin kötüdür, `falsepositives: Unlikely` yazması boşuna değil. Sysmon Event ID 1 (veya Windows 4688) üzerinden bu kural gayet iş görür ve düşük gürültülüdür.

Sorun, bu kuralın neyi yakaladığı değil, neyi yakalayamadığıdır. Bu kural yalnızca aptalın aptalını yakalar: aracı orijinal ismiyle, host üzerinde, process yaratımı loglanan bir makinede çalıştıran saldırganı. Gerçek dünyada tehdit aktörü ikili dosyayı `svchost_helper.exe` diye yeniden adlandırır, ya da hiç bilinen araç kullanmaz — kendi Python/PowerShell tüneli birkaç yüz satırdır. İşte değer buradan sonra başlıyor: naif kuralın kör noktalarını görmek, sinyalleri bağlamak ve yargı üretmek.

## 2. Naif tespit neden yetmez

İlk ve en büyük kör nokta: **isim tabanlı imza kırılgandır**. Kural `Image` alanına, yani çalıştırılabilir dosyanın adına bakıyor. Saldırgan `copy iodine.exe update.exe` yapar yapmaz kural tamamen kör olur. `dnscat2` için `contains` biraz daha dayanıklı ama o da yalnızca resmi Ruby istemcisinin process argümanlarında veya path'inde geçen ismi arıyor; `dnscat2` protokolünü konuşan bağımsız bir Go/C implementasyonu (bunlar mevcut ve public) bu kuralda hiçbir iz bırakmaz. Yani kural aracın *davranışını* değil, *dosya adını* yakalıyor — bu, imza tabanlı tespitin klasik zafiyetidir.

İkinci kör nokta: **logsource `process_creation`**. Yani bu tespit tamamen host telemetrisine bağımlı. Peki tünel ajanı process yaratımı loglanmayan bir yerden geliyorsa? Örneğin `regsvr32`/`rundll32` içine enjekte edilmiş bir modülden, ya da bir EDR'ın görmediği bir Linux/IoT/OT cihazından, ya da yönetilmeyen bir BYOD makineden çıkıyorsa, process_creation olayı hiç oluşmaz. DNS tünelinin *ağdaki* izi — anormal sorgu hacmi, uzun alt alan adları, yüksek entropi — bu kuralın penceresine hiç girmez. Yani tespiti tek bir telemetri katmanına (endpoint process) çakılamış durumda; ağ katmanı tamamen boş.

Üçüncüsü: **kural sadece bilinen iki araca demirlenmiş**. DNS exfiltration'ın gerçek repertuvarı çok geniş — `dns2tcp`, `OzymanDNS`, `DNSCat` türevleri, `Cobalt Strike`'ın DNS beacon'ı (ki bu enterprise kırmızı takım/gerçek APT'lerde en yaygın olanı), `Sliver`'ın DNS listener'ı, `Merlin`, veya sızıntı için basit `nslookup`/`Resolve-DnsName` döngüleri. Cobalt Strike DNS beacon'ı `iodine` gibi bir binary bırakmaz; genellikle enjekte edilmiş shellcode'dur ve trafiği `beacon.saldirgan.com`'a A/AAAA/TXT sorguları olarak gider. Bu kural onu görmez.

Şimdi ters tarafa geçelim — eğer bu kör noktaları kapatmak için "ağ tabanlı DNS anomali tespiti" yazarsanız (uzun sorgu, yüksek entropi, çok sayıda benzersiz alt alan adı) o zaman da **false positive seli** başlar. Çünkü modern internet, meşru sebeplerle DNS'i bir taşıyıcı gibi kullanan servislerle doludur:

- **Antivirüs/EDR reputation lookup'ları**: McAfee, Sophos, Trend Micro, Cisco Umbrella/OpenDNS ajanları dosya ve URL itibarını uzun, kodlanmış, yüksek entropili alt alan adları üzerinden sorgular. `a1b2c3d4e5f6...avqs.net` tam da bir tünel gibi görünür ama tamamen meşrudur.
- **CDN ve bulut servisleri**: Akamai, CloudFront, Azure gibi servislerin FQDN'leri uzun ve rastgele görünen etiketler içerir.
- **Spam/RBL kontrolleri**: Mail sunucuları IP itibarı için `4.3.2.1.zen.spamhaus.org` tarzı yüzlerce sorgu üretir.
- **Telemetri ve analitik**: Bazı yazılımlar durum bilgisini gerçekten DNS TXT sorgularıyla gönderir.

Yani entropiye ya da uzunluğa göre alarm veren ham bir kural, bir kurumsal ağda saatte binlerce meşru olayı işaretler. Analist bu selde boğulur, alarmı mute eder ve gerçek tünel tam da o mute'un altından geçer. Naif tespitin iki ucu da bu: imzaya bağlarsan kolay atlatılır, davranışa bağlarsan gürültüde boğulursun. Değer, ikisinin arasını bağlamakta.

## 3. Korelasyon zinciri (asıl değer)

DNS tünelinin *tek başına* hiçbir sinyali güvenilir değildir. Uzun bir sorgu tek başına bir şey söylemez, yüksek entropi tek başına Umbrella olabilir, `iodine.exe` çalışması tek başına bir kırmızı takım testinin artığı olabilir. Yüksek güvenli tespit, birden fazla zayıf sinyali *zamanda ve bağlamda* birbirine bağlamaktan doğar. İşte pratikte kurduğumuz zincirler:

**Zincir A — Yeni domain + hacim + tek kaynak:**
1. Bir iç host, **daha önce hiç sorgulanmamış** bir üst alan adına (kurumun 90 günlük DNS geçmişinde yok) sorgu yapıyor. Tek başına önemsiz.
2. Aynı host, aynı üst alan adının **çok sayıda benzersiz alt alan adı** varyantını (10 dakikada 200+ farklı FQDN) sorguluyor. Tek başına belki bir CDN.
3. Bu üst alan adının otoritatif NS kaydı **son 30 gün içinde kaydedilmiş** genç bir domain (yeni kayıtlı domain / NRD zenginleştirmesi) veya bilinmeyen bir hosting'de.

A + B + C birleşince: tek host, genç domain'e, kısa sürede yüzlerce benzersiz yüksek-entropili alt alan adı — bu, CDN veya AV lookup'ıyla açıklanamaz. Çünkü meşru servisler *bilinen, yerleşik, whitelist'lenebilir* üst alan adları kullanır. İşte tünelin imzası "uzun sorgu" değil, "**tek kaynaktan, genç/bilinmeyen bir tek üst alan adına, yüksek kardinaliteli benzersiz alt sorgu akışı**"dır.

**Zincir B — Endpoint + ağ birleşimi (en güçlüsü):**
1. `process_creation`: bir kullanıcı iş istasyonunda `powershell.exe` veya `python.exe` **anormal parent** altında (örn. Office makrosu, `wscript`) doğuyor. (Sysmon EID 1)
2. Kısa süre sonra **aynı host** DNS proxy/resolver loglarında yukarıdaki Zincir A davranışını gösteriyor.
3. Aynı hostta **DNS istekleri iç resolver'ı atlıyor** — yani doğrudan 53/UDP ile dış bir IP'ye ya da 443 üzerinden bir DoH sağlayıcısına gidiyor (Sysmon EID 3 network connection, DestinationPort 53 veya bilinen DoH IP'leri).

Burada kritik nüans şu: sağlıklı bir kurumda iç istemciler **asla** doğrudan dışarıya 53 konuşmaz; hepsi iç DNS sunucusuna gider, o forward eder. Bir endpoint'in doğrudan dış 53 veya bilinen bir public DoH endpoint'ine (`1.1.1.1`, `dns.google`, `mozilla.cloudflare-dns.com`) bağlanması **başlı başına yüksek değerli bir sinyaldir** — çünkü meşru trafik iç resolver'dan geçer, DNS logunda görünür; tüneli iç resolver'dan kaçırmak isteyen saldırgan bunu bypass eder. Process anomalisi (adım 1) + tünel benzeri davranış (adım 2) + resolver bypass (adım 3) birleşince alarm artık "belki" değil, "büyük ihtimalle" olur.

**Zincir C — Beaconing zamanlaması + veri asimetrisi:**
1. Bir host, bir domaine **düzenli aralıklarla** (jitter'lı ama istatistiksel olarak periyodik — örn. her 60±5 sn) sorgu atıyor. Bu C2 beacon imzasıdır; exfiltration'dan çok komuta-kontroldür.
2. **Sorgu/yanıt veri asimetrisi**: giden sorgu isimlerinin toplam byte'ı, dönen A kaydı yanıtlarının çok üstünde. Yani makine "konuşuyor" ama karşılık "az dinliyor" — normal isim çözümlemede tam tersi olur (kısa soru, uzun cevap değil; ama exfil'de giden yük büyük). TXT/NULL kayıt tipi oranının anormal yüksekliği de buraya girer, çünkü normal istemci trafiği ezici çoğunlukla A/AAAA'dır.

Bu üç zincirin ortak dersi: DNS tüneli tespitinde **"ne" sorgulandığından çok "kim, ne sıklıkla, hangi kardinalitede, hangi bağlamda" sorguladığı** önemlidir. Google'da "DNS tunneling detection" arayınca çıkan "uzun alt alan adı ve yüksek entropi ara" tavsiyesi tek başına gürültü üretir; onu bir C2/exfil olayına çeviren şey, bu davranışı process kökeni, resolver bypass'ı, domain yaşı ve zamanlama periyodikliğiyle birleştirmektir.

## 4. False positive gerçeği ve triage yargısı

Sahada bu alarmı meşru üreten şeylerin gerçek listesi (ve bunları neden karıştırdığımız):

- **Cisco Umbrella / OpenDNS ajanı**: itibar sorgularını `xxxxxxxx.opendns.com` benzeri kodlanmış, yüksek entropili, çok sayıda benzersiz alt alan adı olarak yollar. Zincir A'nın "benzersiz alt alan hacmi" kriterini birebir tetikler. Ayrımı: üst alan adı *yerleşik ve whitelist'lenebilir*, domain yaşı yıllarca.
- **Antivirüs bulut lookup'ları**: `*.avqs.net` (McAfee), `*.avts.mcafee.com`, Sophos `*.sophosxl.net`, ESET, Kaspersky — hepsi benzer desen. Bunlar kurumun her makinesinde vardır ve **yaygın oldukları için** ayırt edilebilir: tünel tek/az sayıda hosttan çıkar, AV lookup'ı *tüm* filodan çıkar.
- **SCCM / yönetim ajanları, yedekleme yazılımı, vuln scanner**: Bunlar aslında DNS tüneli üretmez ama `process_creation` naif kuralının komşusu olan "anormal ağ aracı çalıştı" alarmlarında görünür; ayrıca Qualys/Nessus/Tenable tarama sırasında hedef isimleri toplu çözümlerken hacimli DNS üretir.
- **Kırmızı takım / pentest artıkları**: Gerçekten `dnscat2` veya `iodine` bir yetkili testte çalışmış olabilir. Naif kural bunu doğru yakalar ama analist "gerçek ihlal mi, planlı test mi" ayrımını yapmalı.
- **Malware olmayan telemetri**: bazı IoT/akıllı cihaz ve oyun yazılımları durum bilgisini DNS TXT ile taşır.

Kıdemli analistin gerçek/gürültü ayrımında izlediği yargı sırası:

**Önce yaygınlık (prevalence) sorusu.** İlk baktığım şey alarmın kaç hosttan geldiğidir. Aynı domaine 4.000 iş istasyonunun hepsi sorguluyorsa bu bir kurumsal servis, tünel değil. Tünel dar bir tabana sahiptir — bir, iki, birkaç host. "Nadir + tek kaynak" her zaman "yaygın + çok kaynak"tan daha şüphelidir.

**Sonra domain itibarı ve yaşı.** Üst alan adını WHOIS/passive DNS ile bakarım: kayıt tarihi dün mü, NS'i bilinen bir hosting mi yoksa "bulletproof" bir yerde mi, sertifika/pasif DNS geçmişi var mı. Yerleşik bir AV vendor domaini ile 3 günlük bir `.top`/`.xyz` domaini arasındaki fark, alarmın kaderini belirler.

**Sonra kaynağın bağlamı.** O hostta o process ne yapıyor? `MsMpEng.exe` veya `umbrella_agent` mi bu sorguları yapıyor, yoksa bir Office belgesinden doğmuş `powershell.exe` mi? İşte burada endpoint telemetrisi ağ alarmını ya öldürür ya da doğrular. Process kökeni meşruysa (imzalı, bilinen ajan) alarm düşer; kökeni anormal parent'sa alarm yükselir.

**Çoklu alarmda önce neye bakarım?** Aynı hostta hem "resolver bypass (doğrudan dış 53/DoH)" hem "DNS tünel davranışı" hem de "anormal process" alarmı varsa, **önce resolver bypass'a** bakarım. Çünkü o, en az false positive üreten ve en yüksek niyet gösteren sinyaldir: sağlıklı bir istemcinin iç DNS'i atlaması için neredeyse hiçbir meşru sebep yoktur. Onu doğrularsam diğer iki alarm zaten anlam kazanır. Entropi/uzunluk alarmına en son bakarım, çünkü en gürültülü olan odur.

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Saldırgan tespiti atlatmak için kural dokümanında yazmayan şunları yapar; her birine ikinci-derece tespit:

**Kaçınma 1 — Aracı yeniden adlandırma / özel implementasyon.** `iodine.exe`'yi `chrome_helper.exe` yapar ya da 300 satırlık kendi Python tünelini yazar. → **Karşı-tespit:** İsimden vazgeç, davranışa geç. Process adı yerine "iç DNS resolver'ı atlayarak doğrudan dış 53/DoH'a giden herhangi bir process" (Sysmon EID 3 + parent/image korelasyonu) ve ağ tarafında Zincir A davranışı. İmza değil, davranış imzası.

**Kaçınma 2 — Hız kısma (low and slow).** Saatte binlerce sorgu yerine dakikada bir sorgu atarak hacim/entropi eşiklerinin altında kalır. Exfiltration'ı günlere yayar. → **Karşı-tespit:** Hacim eşiğine değil, **kardinalite birikimine uzun pencerede** bak. Bir host 24 saatte tek bir genç domaine 500 benzersiz alt alan adı sorgusu yaptıysa, dakikada bir bile olsa bu anormaldir. Ayrıca beaconing periyodikliği (Zincir C) hız kısmadan bağımsız olarak periyodik desenle yakalanır — yavaş beacon da beacondur.

**Kaçınma 3 — Entropiyi düşürme.** Base32 yerine kelime-listesi tabanlı kodlama (dictionary encoding) kullanarak alt alan adlarını `apple-river-blue.domain.com` gibi "insansı" ve düşük entropili yapar. → **Karşı-tespit:** Entropiden vazgeç, **benzersizlik ve NXDOMAIN oranına** bak. Kodlama insansı görünse de her sorgu farklıdır ve karşı taraf her varyantı çözemediğinde ya da alt alan mevcut olmadığında yüksek NXDOMAIN üretir. Yüksek benzersiz-FQDN + yüksek NXDOMAIN + tek kaynak, entropiden bağımsız güçlü sinyaldir.

**Kaçınma 4 — DoH/DoT ile şifreleme.** DNS'i 443 üzerinden şifreli DoH'a taşıyarak DNS loglarını ve resolver görünürlüğünü tamamen kör eder. Artık iç DNS sunucusu sorguları hiç görmez. → **Karşı-tespit:** İki katman. Birincisi, **bilinen public DoH endpoint IP/SNI listesine** giden istemci trafiğini işaretle — kurumsal politikada istemcilerin doğrudan DoH kullanması zaten yasak olmalı, dolayısıyla `dns.google`/`cloudflare-dns.com`'a giden istemci TLS bağlantısı başlı başına policy ihlali alarmıdır. İkincisi, tanınmayan bir IP'ye giden, **SNI'si olmayan ya da sürekli sabit boyutlu paketlerle beacon eden** TLS oturumlarını JA3/JA4 ve akış boyutu analiziyle yakala. DoH tüneli DNS logunu öldürür ama ağ akış metadata'sını öldüremez.

**Kaçınma 5 — Meşru domain üzerinden geçme (domain fronting benzeri / servis kötüye kullanımı).** Saldırgan kendi domainini kaydetmek yerine, alt alan adı kaydetmene izin veren bir servis (bazı dynamic DNS ya da wildcard destekleyen servisler) üzerinden geçer, böylece "genç domain" ve "kötü itibar" sinyallerini atlar. → **Karşı-tespit:** Domain itibarı yerine **davranışsal kardinalite** ön plana çıkar; ayrıca dynamic DNS ve wildcard-friendly TLD'leri (`.duckdns.org`, bazı `.xyz`/`.top` kümeleri) ayrı bir risk kategorisi olarak izle ve o kategoride kardinalite eşiğini düşür.

**Kaçınma 6 — Sysmon/EDR'ı görmeyen yerden çıkma.** OT/IoT, yönetilmeyen Linux, yazıcı, kamera üzerinden tünel kurar; endpoint telemetrisi hiç yoktur. → **Karşı-tespit:** Bu tam da neden **ağ katmanı (DNS resolver logları / pasif DNS / NetFlow) endpoint'ten vazgeçilemez olduğunu** gösterir. Endpoint kör olduğunda tek görünürlüğün DNS sunucusunun kendi query logudur. Bu yüzden kritik kural: her iç host'un DNS'i mutlaka merkezi resolver'dan geçmeli ve o resolver query logging açık olmalı — böylece "cihazda ajan yok" senaryosunda bile davranış görünür.

Kedi-fare oyununun özü şu: saldırgan hangi katmanı kör ederse (isim, hacim, entropi, DNS logu), tespit bir üst-değişmez özelliğe kayar. İsmi değiştirebilir ama resolver bypass davranışını gizleyemez; hacmi düşürebilir ama uzun pencerede kardinalite birikimini gizleyemez; entropiyi düşürebilir ama benzersizliği ve NXDOMAIN'i gizleyemez; DNS logunu DoH ile öldürebilir ama TLS akış metadata'sını öldüremez. Katmanlı savunmanın anlamı budur.

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** Sigma kuralı `process_creation` / `Image` diyor ama bu alan her telemetride aynı isimde değil. Sysmon EID 1'de `Image` var; Windows Security 4688'de karşılığı `NewProcessName`'dir ve **komut satırı (`CommandLine`) 4688'de varsayılan kapalıdır** — "Include command line in process creation events" GPO'sunu açmadıysan `iodine -f -P sifre domain` gibi tünel argümanlarını hiç göremezsin, sadece exe adını görürsün. Bu, yeniden adlandırma kaçınmasını daha da öldürücü yapar. Elastic ECS'te alan `process.executable`, Splunk Sysmon TA'da `Image` korunur ama CIM normalizasyonunda `process` olur; Sentinel'de `DeviceProcessEvents` tablosunda `FolderPath`/`ProcessCommandLine`'dır. Kuralı taşırken bu eşlemeleri birebir kontrol etmezsen kural sessizce hiçbir şey yakalamaz — en tehlikeli hata budur, çünkü alarm vermeyen kural "temiz" sanılır.

**Varsayılan loglanmayan şeyler (en kritik gerçek).** DNS tüneli tespiti çoğu kurumda çuvallar çünkü **DNS query logging kapalıdır**. Windows DNS Server'da analitik/denetim logları (`Microsoft-Windows-DNS-Server/Analytical` veya DNS Analytic ETW) varsayılan olarak KAPALIDIR ve açıldığında ciddi performans/hacim getirir. Sysmon ile host tarafında DNS görmek istiyorsan **Sysmon EID 22 (DnsQuery)** şarttır ve iyi bir Sysmon config'de bu event yaygın gürültüyü (Windows update, telemetri) hariç tutacak şekilde tune edilmelidir; aksi halde EID 22 tek başına SIEM'i şişirir. Yani "DNS tünelini yakalarım" demeden önce sorulacak soru: query loglarım gerçekten toplanıyor mu, yoksa sadece firewall'un allow/deny özetini mi görüyorum? Çoğu ekip ikincisini görür ve alt alan adı detayını hiç göremez — bu durumda Zincir A/B'nin hiçbiri çalışmaz.

**Audit policy / Sysmon gereksinimleri özeti:** process argümanları için 4688 + CommandLine GPO ya da Sysmon EID 1; resolver bypass için Sysmon EID 3 (network connection, `DestinationPort=53` ve dış IP); host DNS görünürlüğü için Sysmon EID 22; ağ tarafı için merkezi DNS resolver query logging (Windows DNS analytic, BIND query log, ya da Umbrella/Infoblox export) veya pasif DNS. Bunların hiçbiri "varsayılan açık" değildir; hepsini bilinçli açman gerekir.

**Splunk vs Sentinel vs Elastic farkları.** 
- **Splunk**: kardinalite tabanlı tünel tespiti Splunk'ın güçlü olduğu yerdir — `stats dc(query) by src` ile "host başına benzersiz alt alan sayısı", `| eventstats` ile beacon periyodikliği, `URL Toolbox` app'i ile Shannon entropisi (`ut_shannon`) hesaplanır. Ancak entropiyi ham eşikle kullanmak yukarıdaki FP selini getirir; mutlaka domain whitelist lookup'ı ve prevalence ile birleştir.
- **Sentinel (KQL)**: `DnsEvents` tablosu (MMA/AMA ile DNS analytic gerektirir) veya `DeviceNetworkEvents`. Entropi için yerleşik fonksiyon yoktur, hesaplaması hantaldır; pratikte `strlen`, benzersiz sayım (`dcount`) ve `make_set` ile kardinaliteye yaslanılır. Genç domain zenginleştirmesi için ThreatIntelligenceIndicator/watchlist join'i şarttır.
- **Elastic**: `packetbeat` DNS modülü ya da `Network Packet Capture` DNS'i güzel parse eder, `dns.question.name`, `dns.question.type` alanları hazır gelir; ECS sayesinde entropi/uzunluk için `runtime field` veya bir ingest pipeline scriptiyle registered_domain ve subdomain ayrımı yapılır. Elastic'in `registered_domain` processor'ı üst alan adı ile alt alanı ayırmada işi kolaylaştırır — kardinaliteyi *registered domain başına* saymak, tünel tespitinin doğru granülaritesidir.

**Tuning gerçeği.** Bu tespitte "kur ve unut" yoktur. Whitelist canlı bir varlıktır: her yeni AV/telemetri servisi, her yeni SaaS entegrasyonu yeni bir yüksek-entropili meşru domain getirir ve onu allow-list'e eklemezsen analist yeni bir FP dalgasında boğulur. Pratik yaklaşım: entropi/kardinalite kuralını **düşük şiddetli, biriktirici** (risk-based alerting / Sentinel'de entity behavior) olarak çalıştır, tek başına ticket açtırma; onu ancak "resolver bypass" veya "anormal process kökeni" gibi ikinci bir yüksek-niyet sinyaliyle korele olduğunda yüksek şiddete çıkar. Yani mimari: gürültülü sinyaller arka planda risk puanı biriktirir, temiz sinyaller (isim imzası, resolver bypass) doğrudan alarm verir, ikisi bir hostta buluştuğunda olay olur. `iodine.exe` naif kuralını da silme — o hâlâ değerli, çünkü aptal saldırganı bedava yakalar; sadece ona *tek savunman* olarak güvenme.

Son saha notu: DNS tüneli en çok, ekiplerin "DNS zaten iç iş, kimse oradan veri kaçırmaz" varsayımı yüzünden başarılı olur. O varsayımı kır. En sık gördüğüm gerçek ihlal deseni, endpoint EDR'ının gördüğü bir ilk erişimden sonra C2'nin sessizce DNS'e (çoğu zaman Cobalt Strike DNS beacon'a) düşmesi ve haftalarca fark edilmemesidir — çünkü DNS query logging kapalıydı. Tespit mühendisliğinin buradaki asıl işi, süslü bir entropi formülü yazmak değil; önce görünürlüğü (query logging + resolver merkezileştirme) sağlamak, sonra zayıf sinyalleri bağlamaktır.
