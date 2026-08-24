# Production Incident / SRE Müdahalesi: Sahadan Yargı Notları

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Bir incident, "sistem beklenen davranıştan sapmış ve bunun kullanıcıya ya da işe bedeli var" demektir. Kritik nokta şu: incident yönetimi bir hata ayıklama (debugging) faaliyeti değildir. Debugging "neden bozuldu?" sorusunu sorar; incident müdahalesi ise önce "kanamayı nasıl durdururum?" sorusunu sorar. Acemi mühendisin en pahalı hatası bu ikisini karıştırmasıdır: alarm çalar çalmaz koda dalar, kök nedeni bulmaya çalışır, bu sırada müşteri 40 dakika daha hizmet alamaz. Kıdemli mühendis ise önce etkiyi keser, sonra teşhis eder. Teşhis, servis ayağa kalktıktan sonra yapılan bir lükstür.

Devreye girme anı genellikle üç kanaldan gelir: (1) otomatik alarm (SLO ihlali, hata oranı, gecikme), (2) müşteri şikâyeti / destek ekibi, (3) bir mühendisin "bir şeyler tuhaf" sezgisi. Bu üçünün güvenilirlik sırası da tam tersinedir aslında: en kötü incident'lar, alarmların hiç çalmadığı, önce Twitter'dan ya da bir büyük müşterinin CEO'sundan duyduğunuz olaylardır. Çünkü alarmınız yoksa, o failure mode'u hiç düşünmemişsiniz demektir.

İşin özü: incident müdahalesi baskı altında, eksik bilgiyle, geri alınması zor kararların hızlı verildiği bir karar verme disiplinidir. Değer, komut ezberinde değil, bu baskı altında doğru sırayla düşünebilmektedir.

## 2. Metodoloji ve karar ağacı — asıl değer burada

### 2.1 İlk 5 dakika: yönetmek, çözmek değil

İlk refleks teknik değil, organizasyonel olmalı. Kıdemli biri incident'a düştüğünde şu üç rolü zihninde ayırır: **Incident Commander (IC)**, **operasyoncu (eli klavyede olan)**, **iletişimci (scribe/comms)**. Tek kişilik olsa bile bu rolleri zihinsel olarak ayırmak gerekir, çünkü IC klavyeye dokunmaya başladığı an genel resmi kaybeder — tünel görüşüne girer. Sahada gördüğüm en yaygın çöküş şudur: en kıdemli mühendis "en hızlı ben çözerim" diye klavyeye geçer, IC boşta kalır, kimse büyük resmi tutmaz, üç kişi aynı anda birbirinden habersiz production'a müdahale eder ve durumu daha da bozar.

IC'nin ilk kararı önceliktir: **azaltma (mitigation) mı, kök neden mi?** Cevap neredeyse her zaman azaltmadır. "Neden oldu?" sorusunu şimdilik ertele.

### 2.2 Belirti → yön haritası (pratisyenin sezgisi)

Pro, panele bakınca şu tarz eşlemeleri saniyeler içinde yapar:

- **"Ne değişti?" her şeyden önce gelir.** Incident'ların ezici çoğunluğu bir değişiklikten doğar: deploy, config değişikliği, feature flag açılışı, altyapı upgrade'i, sertifika yenileme/expire, trafik artışı (kampanya, cron), bir bağımlılığın (upstream) bozulması. İlk sorduğum soru: "Son 1 saatte production'a ne girdi?" Deploy zaman çizelgesiyle alarmın başlangıç zamanını üst üste koyarım. Eğer alarm 14:32'de başladıysa ve 14:31'de bir deploy tamamlandıysa, kök nedeni %80 buldum demektir. Bu tek yargı, ortalama teşhis süresini yarıya indirir.

- **Hata oranı mı yükseldi, gecikme mi?** Hata oranı (5xx) genelde "bir bileşen tamamen düştü/reddediyor" der: crash loop, bağımlılık erişilemez, deploy'da bozuk imaj. Gecikme (latency) artışı ise "bir yerde kaynak tükeniyor ama henüz reddetmiyor" der: veritabanı bağlantı havuzu dolmuş, thread pool tıkanmış, GC baskısı, yavaş sorgu, downstream yavaşlamış. Gecikme artışı genellikle bir çığın habercisidir çünkü yavaşlayan servis, önündeki servisin bağlantı havuzunu tüketir ve failure yukarı doğru yayılır (cascading failure).

- **Grafik keskin bir uçurum mu, yavaş bir tırmanış mı?** Keskin uçurum (cliff) → anlık bir olay: deploy, config, bir şeyin kapanması, network partition. Yavaş tırmanış (ramp) → biriken bir şey: memory leak, disk dolması, bağlantı sızıntısı (connection leak), kuyruk birikmesi, cache hit oranının bozulması. Bu ayrım, hangi hipotezi ilk test edeceğimi belirler.

- **Etki tek bir bölgeye/AZ'ye mi lokalize, global mi?** Tek AZ → altyapı/kapasite sorunu, o bölgeyi trafikten çekerim (drain) ve incident biter. Global → uygulama/config kaynaklı, kod veya konfigürasyona bakarım.

- **"Herkes mi etkilendi, belirli bir segment mi?** Belirli bir müşteri, belirli bir tenant, belirli bir endpoint, belirli bir cihaz/sürüm mü? Segment daralması kök nedeni daraltır. Tek bir büyük tenant patlıyorsa, o tenant'a özel bir veri/quota/hot-partition sorunu olabilir.

### 2.3 Azaltma karar ağacı

Sıra önemlidir, en ucuz ve en geri-alınabilir olandan başlarım:

1. **Son değişiklik geri alınabilir mi? Rollback.** Bir deploy ya da flag ilişkisi net görünüyorsa, kök nedeni anlamaya çalışmadan geri al. Rollback, "anlamadan geri almak" olduğu için mühendislik gururuna ters gelir; oysa production'da doğru olan çoğu zaman budur. Rollback, forward-fix'ten neredeyse her zaman daha güvenlidir çünkü daha önce çalıştığını bildiğiniz bir duruma dönersiniz.
2. **Feature flag ile kapatılabilir mi?** Yeni bir özellik açılmışsa ve incident onunla korele ise, flag'i kapat. Deploy geri almaktan bile hızlıdır.
3. **Trafiği kaydırabilir/kısabilir mi?** Sorunlu bölgeyi drain et, load shedding uygula (en düşük öncelikli trafiği reddet), rate limit devreye al.
4. **Kapasite eklenebilir mi?** Scale-out (yatay ölçekleme) bir çözümmüş gibi görünür ama tuzaktır: eğer sorun bir bağımlılıkta (örn. veritabanı) darboğazsa, daha çok uygulama sunucusu eklemek veritabanına daha çok yük bindirir ve durumu kötüleştirir. Kapasite eklemek yalnızca darboğazın gerçekten uygulama katmanı kapasitesi olduğunda işe yarar.
5. **Hiçbiri değilse forward-fix.** Küçük, cerrahi, tek amaçlı bir düzeltme. Incident sırasında büyük refactor yapmak felakettir.

Kritik takas: **hız mı, kesinlik mi?** Rollback hızlıdır ama yanlış hipotezle yaparsan zaman kaybedersin ve hâlâ bozuksun. Kesin teşhis yavaştır ama isabetlidir. Pro, etkinin şiddetine göre bu ibreyi ayarlar: gelir kanaması / güvenlik / veri kaybı riski varsa hıza kayarım (önce durdur, sonra anla); etki sınırlıysa biraz daha teşhise zaman ayırırım.

### 2.4 Bir kural: veri bütünlüğü > erişilebilirlik

Baskı altında en tehlikeli reflekslerden biri, "servisi ayağa kaldırayım" diye retry, replay, ya da manuel veri müdahalesi yapıp veriyi kalıcı bozmaktır. Erişilemezlik geçicidir, bozuk/çift işlenmiş veri kalıcıdır. Bir ödeme sistemini yeniden başlatırken körlemesine "kuyruğu tekrar oynat" dersen, aynı ödemeyi iki kez alabilirsin. Kıdemli mühendisin durup düşündüğü an tam burasıdır: "Bu işlem idempotent mi? Tekrar edersem ne olur?"

## 3. Gerçek senaryo üzerinden yürüyüş: bağlantı havuzu tükenmesi

Somut bir vaka anlatayım — sahada defalarca gördüğüm bir desen. Kod dilinden bağımsız açıklıyorum ama olay gerçektir.

### Belirti
Saat 20:15, akşam trafik zirvesi. Alarm: API'nin p99 gecikmesi 200 ms'den 8 saniyeye fırladı. Hata oranı da yükseliyor: istekler 30 saniyede timeout'a düşüyor. CPU kullanımı ise düşük — sunucular boşta gibi görünüyor. Bu kombinasyon çok öğretici: **yüksek gecikme + düşük CPU = bir yerde bekleniyor, işlem yapılmıyor.** Bir şey için sırada bekleniyor demektir. Neyi bekliyor? Genellikle bir kilit, bir I/O, ya da bir kaynak havuzu.

### İlk hamle (azaltma refleksi)
"Ne değişti?" Deploy geçmişine bakıyorum: 20:05'te bir sürüm çıkmış. Alarm 20:12'de başlıyor. Korelasyon güçlü ama tam oturmuyor (7 dakikalık gecikme). Yine de en güvenli hamle rollback. Rollback'i tetikliyorum. 20:20'de eski sürüm ayakta — ve gecikme düşmüyor. Demek ki kök neden deploy değil, deploy sadece tetikleyici olabilir ya da tamamen ilgisiz. Rollback yanlış çıktı ama yanlış olduğunu öğrenmek de bilgidir ve maliyeti düşüktü.

### Teşhise geçiş
Gecikme + düşük CPU beni kaynak havuzuna yönlendiriyor. Uygulamanın veritabanı bağlantı havuzu metriklerine bakıyorum: **aktif bağlantı sayısı havuz üst sınırında (örn. 20/20), bekleyen istek kuyruğu şişmiş.** İşte darboğaz. Her istek boş bir DB bağlantısı bekliyor, bulamayınca kuyrukta bekliyor, sonunda timeout oluyor. CPU düşük çünkü thread'ler iş yapmıyor, bekliyor.

Peki bağlantılar neden serbest kalmıyor? Veritabanına gidiyorum: yavaş sorgu logunda yeni bir sorgu görüyorum — 20:05 deploy'uyla gelen bir endpoint, `WHERE` şartında yeni bir alan kullanıyor ve o alanda **index yok**. Tablo küçükken (test/staging'de) sorun yok; ama production'da milyonlarca satırda full table scan yapıyor, her sorgu 3-4 saniye sürüyor. Trafik zirvesinde bu sorgular bağlantıları uzun süre tutuyor, havuz doluyor, tüm API donuyor. Deploy gerçekten suçluymuş — ama rollback işe yaramadı çünkü **rollback sonrası bekleyen kuyruk ve zaten açık kalmış yavaş sorgular temizlenmedi; ayrıca sürüm izleyen istemcilerin bir kısmı hâlâ eski bağlantıları tutuyordu.** (Sahada rollback'in "hemen" düzeltmemesinin sık bir sebebi budur: durum, kod değil, birikmiş durumdur.)

### Doğrulama ve düzeltme
Hipotezi doğruluyorum: o endpoint'i feature flag ile kapatıyorum. 90 saniye içinde bağlantı havuzu boşalıyor, kuyruk eriyor, p99 normale dönüyor. Incident azaltıldı (20:31). Kök neden net: eksik index.

Kalıcı düzeltme (incident sonrası, aceleyle değil):
- İlgili sütuna index eklenir (production'da büyük tabloda index oluşturma da dikkatli yapılır — kilitleme yaratmayan, çevrimiçi/CONCURRENT bir index oluşturma yöntemiyle, aksi hâlde index oluştururken tabloyu kilitleyip ikinci bir incident yaratırsınız).
- Sorguya bir zaman aşımı (statement timeout) konur ki tek bir yavaş sorgu bir daha tüm havuzu esir almasın.
- Bağlantı havuzuna daha agresif bir "bağlantı edinme zaman aşımı" eklenir: bağlantı 500 ms'de gelmezse isteği hızlı reddet (fail fast), böylece kuyruk sonsuz büyümez ve geri basınç (backpressure) oluşur.

### Buradaki yargı özeti
Zafiyet: geliştirici sorguyu yazdı, staging'de hızlı çalıştı, "çalışıyor" dedi. Teşhis: gecikme+düşük CPU → havuz → yavaş sorgu → eksik index. Düzeltme: önce flag ile durdur, sonra index + timeout + fail-fast. Acemi burada ya kör rollback'e takılıp kalırdı ya da "sunucu ekleyelim" diyip veritabanını büsbütün öldürürdü.

## 4. Acemi vs pro: tuzaklar ve gözden kaçanlar

**"Grafik düzeldi, incident bitti" yanılgısı.** Acemi, metrik normale dönünce rahatlar. Pro sorar: gerçekten düzeldi mi, yoksa trafik mi düştü? Gece yarısı yükün azalması sorunu maskeleyebilir; yarın aynı saatte geri gelir. Ayrıca birikmiş işler (kuyruktaki mesajlar, işlenmemiş job'lar) hâlâ orada olabilir. "Yeşil" panel, "sağlıklı sistem" demek değildir.

**Korelasyonu nedensellik sanmak.** İki grafik aynı anda hareket ediyor diye biri diğerinin sebebi değildir. İkisi de üçüncü bir ortak nedene bağlı olabilir. Pro, "bu değişikliği geri alırsam belirti kaybolur mu?" diye test edilebilir bir hipotez kurar, gözlemle doğrular.

**Aynı anda birden çok şeyi değiştirmek.** Baskı altında acemi panikle üç şeyi birden yapar: rollback + config değişikliği + restart. Sonra düzelirse hangisinin işe yaradığını bilemez; bozulursa hangisinin bozduğunu bilemez. Kural: **her seferinde tek değişiklik, sonucu gözle, sonra devam.** İncident sırasında bilimsel yöntem, hızdan daha değerlidir.

**Retry ve timeout'un ters tepmesi.** "Hata alıyoruz, retry ekleyelim" en tehlikeli iyi-niyetli reflekstir. Zaten boğulmakta olan bir bağımlılığa retry eklemek, ona 3 kat yük bindirir ve retry fırtınası (retry storm) yaratır — sistemi kendi kendine DDoS'lar. Downstream yavaşken retry, benzin döker. Pro retry'ı jitter'lı exponential backoff ve bir bütçe (retry budget) ile sınırlar, ve devre kesici (circuit breaker) kullanır.

**Yeniden başlatmayı çözüm sanmak.** Restart, memory leak veya bozuk durumu geçici temizler, incident "biter", herkes yatmaya gider — ve leak devam eder, ertesi gün geri gelir. Restart bir azaltmadır, teşhis değil. Restart etmeden önce, mümkünse leak eden process'in bir bellek dökümünü (heap dump) al; yeniden başlatınca kanıt yok olur. Acemi kanıtı yok eder, pro önce kanıtı toplar.

**"Cascading failure"i tek bir servisin suçu sanmak.** Panelde A servisi kırmızı diye suçlu A değildir. A, B'ye bağlı, B yavaşladı, A'nın thread'leri B'yi beklerken tükendi, A da kırmızıya döndü. Gerçek kaynak B, hatta B'nin bağlı olduğu C. Pro bağımlılık zincirini aşağı doğru izler, en dipteki değişikliği arar. "Kırmızının en derinine in."

**Thundering herd / cache çökmesi.** Cache aniden boşalırsa (deploy, flush, TTL'lerin aynı anda dolması) tüm istekler aynı anda veritabanına yığılır ve onu ezer. Acemi "cache'i temizleyelim, temiz başlasın" der ve incident'ı büyütür. Pro cache'i kademeli ısıtır, TTL'lere jitter ekler.

**İletişimi ihmal etmek.** Acemi teknik olarak doğru çalışır ama 45 dakika kimseye bir şey söylemez. Bu sırada 6 yönetici panik içinde birbirini arar, destek ekibi ne diyeceğini bilmez, aynı incident için üç ayrı savaş odası açılır. Pro düzenli aralıklarla (etki, ne yapıldığı, tahmini süre) durum yayınlar — çözemese bile. İletişim, incident yönetiminin yarısıdır.

**Suçlu arama kültürü.** Acemi (ve olgunlaşmamış organizasyon) "kim deploy etti?" diye sorar. Bu, incident'lardan ders çıkarmayı öldürür çünkü insanlar hatalarını saklamaya başlar. Pro ve sağlıklı ekip **blameless postmortem** yapar: soru "kim" değil, "sistemimiz nasıl oldu da tek bir kişinin hatasının production'ı bu kadar kolay bozmasına izin verdi?" Insan hata yapar; sistem hatayı yakalamalıydı. Eksik olan test, review, canary, guardrail'dir.

**SLO'yu ve hata bütçesini unutmak.** Her dalgalanma incident değildir. %100 uptime hedefi tuzaktır — imkânsızdır ve peşinden koşmak inovasyonu durdurur. Pro, hata bütçesi (error budget) düşünür: SLO %99.9 ise, bütçe içinde kaldıkça küçük dalgalanmalar için gece 3'te kimseyi uyandırmaya gerek yoktur. Bütçe tükendiğinde ise deploy'ları durdurup istikrara odaklanılır. Bu, alarm yorgunluğunu (alert fatigue) önleyen yargıdır.

## 5. Araçlar ve saha notları

**Gözlemlenebilirlik (observability) üç ayak.** Metrikler (metrics) "bir şey bozuk mu?" sorusuna hızlı cevap verir — ucuz, toplu, ama düşük çözünürlük. Loglar "tam olarak ne oldu?" için — pahalı ama ayrıntılı. İzler (distributed tracing) "bu tek isteğin zamanı nerede harcandı?" için — mikroservis dünyasında olmazsa olmaz, çünkü bir isteğin 12 servis arasında hangi adımda yavaşladığını başka türlü göremezsiniz. Pratik tüyo: incident'ta önce metriklerle **daralt** (hangi servis, hangi endpoint, hangi zaman), sonra trace ile **derinleş** (o istek nerede takıldı), en son log'a **in** (o adımda tam hata neydi). Baştan log'a dalmak, samanlıkta iğne aramaktır.

**"USE" ve "RED" metodları.** Kaynaklar için USE: Utilization (doluluk), Saturation (kuyruk/bekleme), Errors. Servisler için RED: Rate (istek hızı), Errors (hata oranı), Duration (gecikme). Bir panele baktığımda bu çerçeveyle bakarım; hangi metriğin eksik olduğunu da fark ederim — çoğu incident'ta "saturation" (kuyruk derinliği, havuz doluluğu) metriği eksiktir ve tam da o gösterge en kritik olandır.

**Dashboards vs. exploration.** Önceden hazırlanmış panolar bilinen failure mode'lar içindir; bilinmeyen bir incident'ta onlar yetmez, ad hoc sorgu (yüksek kardinaliteli, "hangi müşteri", "hangi sürüm", "hangi host" kırılımı yapabilen) gerekir. Bu yüzden yüksek kardinaliteyi destekleyen observability araçları kritiktir. "Sadece dashboard'a bakan" ekip, dashboard'da olmayan sorunu asla göremez.

**Debugger vs. production.** Production'da genelde klasik breakpoint debugger kullanamazsınız (canlı trafiği durduramazsınız). Onun yerine: heap dump / thread dump (Java/JVM dünyasında bir sürecin o anki tüm thread'lerinin ne yaptığını gösterir — "tüm thread'ler aynı kilidi bekliyor" görüntüsü altın değerindedir), profiler (CPU/allocation profili, özellikle sürekli profil toplayan continuous profiling), ve strace/tcpdump gibi sistem düzeyi araçlar. Bir process "asılı" ve neden belli değilse, ilk hamlem thread dump almaktır: çoğu kilitlenme (deadlock) ve havuz tükenmesi orada apaçık görünür.

**Feature flag sistemi bir güvenlik ağıdır.** Yeni riskli her davranışı flag arkasına koymak, incident süresini dakikalardan saniyelere indirir çünkü deploy beklemeden kapatabilirsiniz. Sahada en çok pişman olunan şey: riskli bir değişikliği flag'siz çıkarmak. Flag ayrıca kademeli açılış (canary: önce %1, sonra %10, sonra %100) sağlar — sorun %1'deyken yakalanır, tüm kullanıcıyı vurmadan.

**Runbook'lar.** İyi bir runbook, gece 3'te uykulu bir nöbetçinin (on-call) düşünmeden izleyebileceği somut adımlardır: "şu alarm çalarsa, şu paneli aç, şu metriğe bak, şuysa şunu yap." Kötü runbook ise "sistemin sağlığını kontrol edin" gibi işe yaramaz genellemelerdir. Pratik kural: her alarmın bir runbook linki olmalı; runbook'u olmayan alarm ya gürültüdür (silinmeli) ya da eksik iştir (yazılmalı).

**Postmortem ve zaman çizelgesi.** Incident biter bitmez (hafıza tazeyken) bir zaman çizelgesi çıkarın: ne zaman başladı, ne zaman fark edildi (detection), ne zaman azaltıldı (mitigation), ne zaman tamamen çözüldü. İki kritik metrik: **TTD (time to detect)** ve **TTM/TTR (time to mitigate/resolve)**. Çoğu organizasyonun asıl sorunu çözüm süresi değil, tespit süresidir — saatlerce bozuk kalıp kimsenin fark etmemesi. TTD'yi kısaltmak (doğru alarmlar) genellikle en yüksek getirili yatırımdır.

**Alarm tasarımı — belirtiye alarm koy, nedene değil.** Pratik tüyo: "CPU %80" gibi neden-alarmları çok gürültü üretir (CPU %80 olabilir ve her şey yolunda olabilir). Bunun yerine kullanıcının hissettiği belirtiye alarm koy: hata oranı, gecikme, başarı oranı — yani SLO'ya. "Kullanıcı acı çekiyor mu?" alarmı, "bir makinede bir metrik yüksek mi?" alarmından çok daha az yanlış-pozitif üretir. Sayfa (page) yalnızca insan müdahalesi gereken, aciliyeti olan durumlar için olmalı; gerisi ticket ya da gösterge olarak kalmalı. Alarm yorgunluğu, gerçek incident'ı kaçırmanın bir numaralı sebebidir.

**Chaos engineering ve oyun günleri (game days).** Failure mode'ları incident anında değil, kontrollü ortamda öğrenmenin yolu, kasıtlı olarak bir şeyleri bozup ekibin müdahalesini prova etmektir. Bir bağımlılığı kapatın, gecikme enjekte edin, bir AZ'yi düşürün. Böylece hem runbook'lar test edilir hem de nöbetçiler baskı altında düşünmeyi öğrenir. Sahada gördüğüm en dayanıklı ekipler, incident'ı bir sürpriz değil, prova edilmiş bir senaryo olarak yaşayanlardır.

**Son bir saha notu — "iki adamlı yetki" ve geri alınamaz eylemler.** Baskı altında en pahalı hatalar geri alınamaz olanlardır: yanlış tabloda `DELETE`, production veritabanını silme, yanlış cluster'a `apply`. Kıdemli bir refleks: geri alınamaz bir komuttan önce dur, komutu bir başkasına yüksek sesle oku, hedefin (host, ortam, namespace) doğruluğunu teyit ettir. "İki dakikanı alır ama kariyerini kurtarır." Production terminaline farklı bir renk/uyarı koymak, `--dry-run` alışkanlığı, ve tehlikeli komutlarda onay istemek acemiye yavaşlık gibi gelir; pro bunları can simidi bilir.

---

Özetle: incident müdahalesinin asıl becerisi teknik bilgi değil, baskı altında doğru sırayla düşünme disiplinidir. Önce durdur, sonra anla. Tek değişiklik yap, gözle. Kanıtı yok etmeden topla. Korelasyonu nedensellikle karıştırma. Ve en önemlisi: sistem, tek bir insanın hatasıyla çökebiliyorsa, suçlanacak olan o insan değil, o kırılganlığa izin veren sistemdir. Sağlıklı SRE kültürü bu yargının üzerine kurulur.
