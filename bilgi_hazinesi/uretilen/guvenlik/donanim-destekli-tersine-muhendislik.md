# Donanım Destekli Tersine Mühendislik: JTAG/SWD Debug, Glitching ve Yan Kanal Saldırıları

## Giriş ve Kapsam

Yazılım tersine mühendisliğinin (software reverse engineering) sınırlarına gelindiğinde, saldırganın veya güvenlik araştırmacısının önündeki tek yol çoğu zaman **fiziksel erişimdir**. Bir cihazın firmware'i şifreliyse, harici flash okuma bloke edilmişse veya bir güvenli önyükleme (secure boot) zinciri anahtarları koruyorsa, klasik disassembly yeterli olmaz. İşte bu noktada **donanım destekli tersine mühendislik** (hardware-assisted reverse engineering) devreye girer.

Bu makale üç ana tekniği kavramsal düzeyde inceler: **debug arayüzleri üzerinden erişim** (JTAG/SWD), **fault injection / glitching** (voltaj ve saat manipülasyonuyla hata enjeksiyonu) ve **yan kanal saldırıları** (side-channel attacks, özellikle güç analizi). Amaç, bu mekanizmaların nasıl çalıştığını anlamak ve karşı önlemleri (savunma, tespit) doğru kurmaktır. Metin, operasyonel bir saldırı el kitabı değildir; her tekniğin fiziği, tehdit modeli ve savunma tarafı vurgulanır.

Bu yetenek, profesyonel donanım güvenliği ekiplerinde niş ama yüksek değerli bir uzmanlıktır. Chip üreticileri, IoT güvenlik denetçileri, ödeme sistemi değerlendiricileri (payment/EMV değerlendirmesi) ve savunma sanayii bu alanda çalışır.

## Bölüm 1: Debug Arayüzleri — JTAG ve SWD

### Tanım ve Çalışma Mantığı

**JTAG** (Joint Test Action Group, resmi adıyla IEEE 1149.1) aslında bir tersine mühendislik aracı olarak değil, üretim sonrası kart testleri (boundary scan) için tasarlanmış bir standarttır. Amacı, lehimleme hatalarını ve bağlantı kopukluklarını test problarına ihtiyaç duymadan tespit etmekti. Ancak zamanla çip içi debug (on-chip debug) yetenekleri de aynı arayüz üzerinden sunulmaya başlandı; işte tersine mühendislik değeri buradan gelir.

JTAG, bir **TAP** (Test Access Port) durum makinesi etrafında çalışır ve tipik olarak beş sinyal kullanır:

- **TCK** (Test Clock) — saat sinyali
- **TMS** (Test Mode Select) — durum makinesini yönlendirir
- **TDI** (Test Data In) — veri girişi
- **TDO** (Test Data Out) — veri çıkışı
- **TRST** (Test Reset) — opsiyonel reset

**SWD** (Serial Wire Debug) ise ARM'ın geliştirdiği, JTAG'in iki telli (SWDIO ve SWCLK) alternatifidir. Fiziksel pin sayısını azaltmak için özellikle Cortex-M ailesinde yaygındır. İşlevsel olarak benzer erişim sağlar: bellek okuma/yazma, register erişimi, breakpoint koyma, tek adım (single-step) çalıştırma.

Bir debug arayüzü aktif ve kilitsizse, saldırgan pratik olarak işlemcinin sahibi olur: RAM ve flash'ı okuyabilir, çalışan kodu durdurabilir, register'ları değiştirebilir ve firmware'i tam olarak dökebilir (dump).

### Kök Neden: Neden Açık Kalırlar?

Debug arayüzlerinin üretimde ve saha teşhisinde (field diagnostics) çok işe yaraması, onların üretim hattından sonra kapatılmasını sık sık unutturur. Kök nedenler şunlardır:

- **Üretim kolaylığı için bırakılan portlar:** Programlama ve test için gerekli olan arayüz, seri üretimde kalıcı olarak devre dışı bırakılmaz.
- **Fuse/lock bit'lerin programlanmaması:** Çoğu MCU'da debug'ı kalıcı kapatan bir "lock" veya "readout protection" mekanizması vardır (örneğin ST'nin RDP seviyeleri, bazı ailelerde debug disable fuse'ları). Bunlar set edilmezse arayüz açık kalır.
- **Gizlenmiş ama kaldırılmamış izler:** Bazı üreticiler PCB üzerindeki test pad'lerini silkscreen'den kaldırır ama bakır izleri (traces) yerinde bırakır. Tersine mühendis, PCB'yi inceleyerek veya continuity testiyle bu noktaları bulur.

### Örnek Senaryo

Bir akıllı ev cihazının PCB'sinde etiketsiz dört adet test pad bulunur. Araştırmacı, bir lojik analizör ve JTAGulator benzeri bir pinout keşif aracıyla hangi pad'in TCK/TMS/TDI/TDO olduğunu tespit eder. Arayüz kilitli değilse, OpenOCD gibi bir araçla bağlanıp flash içeriğini bir dosyaya döker. Bu firmware dump'ı daha sonra Ghidra ile statik analiz edilir. Burada donanım erişimi, yazılım analizinin "kilidini açan" adımdır.

### Tespit ve Savunma

**Savunma:**
- **Debug'ı kalıcı devre dışı bırakın:** Üretim sonrası lock/RDP bit'lerini en yüksek koruma seviyesine ayarlayın. ARM tarafında debug authentication sinyalleri (DBGEN, SPIDEN gibi) uygun şekilde konfigüre edilmelidir.
- **Debug erişimini kimlik doğrulamaya bağlayın:** Modern SoC'lerde "authenticated debug" veya "debug unlock via challenge-response" mekanizmaları bulunur; erişim yalnızca kriptografik anahtara sahip olana açılır.
- **Fiziksel gizleme yeterli değildir:** Pad'leri kaldırmak (security by obscurity) tek başına savunma sayılmaz; asıl önlem lojik seviyede kilitlemedir.
- **Tamper mesh ve kabuk koruması:** Yüksek güvenlik gerektiren cihazlarda, kapağın açılması durumunda anahtarları silen tamper-detection devreleri kullanılır.

**Tespit:**
- Üretim test aşamasında, sevkiyata çıkacak birimlerde debug portunun gerçekten kilitli olduğunu doğrulayan otomatik bir test adımı ekleyin. En sık hata, "geliştirme kartında kapattık, üretimde kontrol etmedik" senaryosudur.
- Firmware içinde, boot sırasında RDP/lock durumunu okuyup beklenmedik bir seviye ise loglama veya güvenli moda geçme mantığı kurulabilir.

## Bölüm 2: Fault Injection ve Glitching

### Tanım

**Fault injection** (hata enjeksiyonu), bir işlemcinin normal çalışma koşullarını kısa süreliğine bozarak onu **yanlış ama saldırgana faydalı** bir davranışa zorlama tekniğidir. En yaygın alt türleri:

- **Voltage glitching:** Besleme voltajının çok kısa (nanosaniye–mikrosaniye) süreyle düşürülmesi veya bozulması.
- **Clock glitching:** Saat sinyaline anormal, çok hızlı bir darbe (glitch) eklenmesi.
- **Electromagnetic fault injection (EMFI):** Çip yüzeyine yakın bir bobinle üretilen ani manyetik darbe.
- **Optical/laser fault injection:** Delid edilmiş (kapağı açılmış) çipe lazer atarak belirli transistörlerin durumunu bozma — en hassas ama en pahalı yöntem.

### Kök Neden: Neden İşe Yarar?

Dijital devreler, sinyallerin belirli **setup ve hold time** kısıtlarına uymasıyla doğru çalışır. Voltaj düştüğünde transistörlerin anahtarlama süresi uzar; saat aynı hızda gelmeye devam ederse, bir flip-flop henüz kararlı hale gelmemiş bir değeri yakalayabilir. Sonuç: **bir komut atlanır, bir karşılaştırma yanlış sonuç verir veya bir döngü sayacı bozulur.**

Saldırganın hedeflediği tipik durumlar:

- **Karşılaştırma atlatma:** `if (girilen_pin == dogru_pin)` kontrolünün sonucunu tersine çevirmek veya kontrolü tümden atlamak.
- **Döngü bozma:** Bir güvenli silme (secure erase) veya doğrulama döngüsünü erken sonlandırmak.
- **Secure boot atlatma:** İmza doğrulaması başarısız olduğunda dallanması gereken kodu, glitch ile başarılı dalına yönlendirmek. Buna "authentication bypass" denir.

Glitch'in kritik özelliği **zamanlamadır** (timing). Saldırgan, hedef işlem tam da o hassas komutu çalıştırırken darbeyi göndermek zorundadır. Bu yüzden pratikte saldırgan, bir tetikleme (trigger) sinyali (örneğin bir GPIO değişimi veya güç tüketimindeki karakteristik bir desen) yakalayıp ardından ayarlanabilir bir gecikmeyle glitch üretir. Doğru zamanlamayı bulmak genellikle binlerce deneme (parameter sweep) gerektiren istatistiksel bir süreçtir.

### Örnek Senaryo (Kavramsal)

Bir mikrodenetleyici, önyüklemede harici flash'tan gelen imzayı doğrular; imza geçersizse debug'ı kapalı tutar ve çalışmayı durdurur. Araştırmacı, doğrulama fonksiyonunun çalıştığı zaman penceresini güç izinden tespit eder. Ardından, o pencerede besleme voltajına kontrollü bir çökme uygulanır. Çok sayıda denemeden birinde, doğrulama sonucunu taşıyan register bozulur ve kod "geçerli imza" dalına girer. Böylece debug açılır veya korumasız kod çalışır. Burada tek bir bit'in yanlış okunması, tüm güvenlik zincirini çökertebilir.

### Tespit ve Savunma

Fault injection'a karşı savunma, "tek noktadan kırılmayı" (single point of failure) ortadan kaldırmaya dayanır:

- **Redundant kontrol:** Kritik karşılaştırmaları iki kez, farklı biçimlerde yapın. Örneğin hem `if (a == b)` hem de ayrı bir yerde `if (a != b) hata()` mantığıyla çift kontrol; tek bir glitch her ikisini birden atlatamaz.
- **Rastgele gecikmeler (random delays):** Kritik işlemlerin öncesine rastgele süreli beklemeler ekleyin. Bu, saldırganın zamanlama penceresini kilitlemesini zorlaştırır.
- **Sonuç doğrulama ve idempotent olmayan bayraklar:** Güvenlik kararlarını basit bir boolean yerine, kolayca bozulamayan sabitlerle (örneğin belirli bir "sihirli değer") temsil edin. `TRUE`/`FALSE` yerine `0xA5A5A5A5` gibi Hamming mesafesi yüksek değerler tercih etmek, tek bit flip'in geçerli bir "başarılı" değere dönüşmesini zorlaştırır.
- **Donanımsal glitch detektörleri:** Modern güvenlik çipleri; voltaj, saat frekansı ve sıcaklıktaki anormallikleri izleyen sensörler içerir. Bir anomali algılandığında çip reset atar veya anahtarları siler.
- **Sayaç tutarlılığı:** Döngü sonunda beklenen iterasyon sayısını doğrulayın; erken çıkışı tespit edin.

**Tespit tarafında** en güçlü yaklaşım, cihazın kendi içinde çalışan **environmental sensörlerdir**. Yazılım seviyesinde ise, güvenlik kritik kararların çift yollu (double-check) verilip verilmediğini denetleyen kod incelemeleri (code review) önemlidir.

## Bölüm 3: Yan Kanal Saldırıları (Side-Channel Attacks)

### Tanım

**Yan kanal saldırısı**, bir kriptografik işlemi doğrudan matematiksel olarak kırmak yerine, işlemin **fiziksel yan ürünlerini** gözlemleyerek gizli bilgiyi (genellikle anahtarı) sızdırma tekniğidir. Bu yan ürünler şunlar olabilir:

- **Güç tüketimi** (power analysis) — en yaygın ve en güçlü kanal
- **Elektromanyetik yayılım** (EM emanations)
- **İşlem süresi** (timing attacks)
- **Ses, ısı, hatta hata mesajları**

Temel içgörü şudur: **CMOS devrelerde harcanan enerji, işlenen veriye bağlıdır.** Bir bit'i 0'dan 1'e çevirmek (transition), sabit kalmasından farklı miktarda anlık akım çeker. Dolayısıyla güç tüketimi izi (power trace), o an işlenen verinin dolaylı bir "gölgesini" taşır.

### Güç Analizi Türleri

**SPA (Simple Power Analysis):** Tek bir güç izini görsel olarak inceleyerek algoritmanın yapısını çıkarmak. Örneğin klasik "square-and-multiply" tabanlı bir RSA üstel almasında, güç izinde "1" ve "0" bitleri farklı desenler oluşturabilir; saldırgan bu deseni okuyarak özel anahtarı doğrudan gözlemleyebilir.

**DPA (Differential Power Analysis):** Bu, çok daha güçlü ve istatistiksel bir tekniktir. Saldırgan binlerce/milyonlarca güç izi toplar. Ardından, anahtarın küçük bir parçası (örneğin bir bayt) hakkında hipotezler kurar; her hipotez için ara değerin (intermediate value) belirli bir bit'ini hesaplar ve izleri bu bit'e göre gruplar. Doğru anahtar hipotezinde, gruplar arasındaki ortalama güç farkı istatistiksel olarak anlamlı bir tepe (peak) oluşturur; yanlış hipotezlerde ise gürültüde kaybolur. Bu şekilde anahtar bayt bayt kurtarılabilir.

**CPA (Correlation Power Analysis):** DPA'nın gelişmiş bir varyantıdır; ölçülen güç ile bir güç modeli (genellikle **Hamming weight** veya **Hamming distance** modeli) arasındaki **korelasyon** hesaplanır. Doğru anahtar hipotezi en yüksek korelasyonu verir. Pratikte CPA, düşük gürültüde daha az iz ile sonuca ulaşabildiği için sıkça tercih edilir.

### Kök Neden

Kök neden, **veri bağımlı güç tüketimi**dir. AES gibi bir şifrede, S-box çıkışı gibi ara değerler hem anahtara hem de bilinen veriye (plaintext/ciphertext) bağlıdır. Saldırgan bilinen veriyi kontrol ettiği için, anahtarın küçük parçaları hakkındaki hipotezleri fiziksel ölçümle sınayabilir. Bu, tüm anahtarı bir kerede tahmin etmek (2^128 zorluk) yerine, her baytı ayrı ayrı kurtararak problemi katlanır zorluktan doğrusal zorluğa indirger — yan kanal saldırılarının yıkıcı gücü buradan gelir.

### Örnek Senaryo (Kavramsal)

Bir akıllı kart, AES ile bir kimlik doğrulama yapıyor. Araştırmacı, kartın güç hattına bir shunt direnç koyup bir osiloskopla ilk AES turundaki güç tüketimini kaydeder. Bilinen plaintext'lerle binlerce ölçüm alır. Her ölçüm için, ilk turun S-box çıkışının Hamming weight'ini her olası anahtar baytı için modeller ve gerçek ölçümle korelasyona bakar. En yüksek korelasyonu veren hipotez, o anahtar baytıdır. 16 bayt için işlem tekrarlanır ve tam AES anahtarı, şifreyi hiç "kırmadan" elde edilir.

### Tespit ve Savunma

Yan kanal savunması iki ana felsefeye dayanır: **gizleme (hiding)** ve **maskeleme (masking)**.

- **Masking (maskeleme):** Ara değerleri, her çalıştırmada rastgele bir maske ile karıştırmak. Böylece ölçülen güç, gerçek ara değerle değil, rastgele maskelenmiş bir değerle korele olur; saldırganın istatistiği bozulur. Bu, matematiksel olarak sağlam ama uygulaması zor bir yöntemdir (higher-order DPA saldırıları daha yüksek dereceli maskeleme gerektirir).
- **Hiding (gizleme):** Güç tüketimini veriden bağımsız hale getirmeye çalışmak. Yöntemler: sabit ağırlıklı kodlama (dual-rail logic), gürültü enjeksiyonu, işlemlerin sırasını rastgeleleştirme (shuffling) ve rastgele dummy operasyonlar eklemek.
- **Sabit zamanlı kod (constant-time):** Timing saldırılarına karşı, kodun çalışma süresi gizli veriye bağlı olmamalıdır. Dallanmaları (branch) ve veri bağımlı bellek erişimlerini gizli veriden ayırın.
- **Protokol seviyesi savunma:** Anahtarları sık döndürmek (key rotation) ve çalıştırma sayısını sınırlamak, DPA'nın ihtiyaç duyduğu büyük iz kümesini toplamayı engeller. Bir anahtarla yalnızca sınırlı sayıda işlem yapılmasına izin veren "leakage-resilient" protokoller bu mantığı kullanır.

**Tespit:** Yan kanal saldırıları pasif ve gizlidir; cihaz "saldırıya uğradığını" doğrudan anlayamaz. Bu yüzden savunma büyük ölçüde önleyicidir. Değerlendirme tarafında ise, ürünün üretim öncesi bir **yan kanal değerlendirmesinden** (leakage assessment, örneğin TVLA — Test Vector Leakage Assessment metodolojisi) geçirilmesi standart pratiktir. Bu testte, cihazın istatistiksel olarak veri sızdırıp sızdırmadığı ölçülür.

## Bu Tekniklerin Birlikte Kullanımı

Gerçek dünyada bu üç yöntem çoğu zaman **zincir** halinde kullanılır. Tipik bir değerlendirme akışı şöyledir:

1. **Keşif:** PCB incelenir, çip tanımlanır (datasheet bulunur), debug pad'leri aranır.
2. **Kolay yol denemesi:** JTAG/SWD açık mı? Açıksa iş biter, firmware dökülür.
3. **Kilitliyse glitching:** Debug kilitliyse, readout protection'ı atlatmak için voltage glitching denenir — çünkü kilit kontrolü de yazılımsal bir dallanmadır ve glitch ile atlatılabilir.
4. **Anahtar gerekiyorsa yan kanal:** Firmware şifreliyse veya bir kriptografik anahtar gerekiyorsa, güç analizi devreye girer.

Bu katmanlı yapı, savunmanın da katmanlı olması gerektiğini gösterir: tek bir önlem (örneğin sadece debug kapatmak) yeterli değildir.

## Yaygın Hatalar

**Savunma tarafında sık yapılan hatalar:**

- **Debug'ı üretimde kapatmayı unutmak.** En yaygın ve en kolay istismar edilen hata budur. Geliştirme kartıyla üretim biriminin konfigürasyonu ayrı doğrulanmalıdır.
- **Security by obscurity'e güvenmek.** Pad'leri silkscreen'den kaldırmak, çip markasını kazımak (decapping'i biraz zorlaştırır ama engellemez) gerçek koruma değildir.
- **Güvenlik kararını tek bir boolean'a bağlamak.** Glitch'e karşı, kritik kararlar redundant ve yüksek Hamming mesafeli değerlerle korunmalıdır.
- **"Yazılımda güvenli, o halde donanımda da güvenli" varsayımı.** Kriptografik olarak sağlam bir AES uygulaması bile, maskeleme olmadan güç analizine karşı savunmasızdır. Algoritmanın matematiksel gücü, fiziksel sızıntıyı önlemez.
- **Tehdit modelini yanlış çizmek.** Fiziksel erişimi olmayan bir cihaz için glitch koruması gereksiz olabilirken, elden ele dolaşan bir akıllı kart için zorunludur. Savunma yatırımı tehdit modeliyle orantılı olmalıdır.

**Araştırma/analiz tarafında sık yapılan hatalar:**

- **Zamanlama penceresini yeterince taramamak.** Glitch parametreleri (voltaj derinliği, süre, gecikme) çok geniş bir uzaydır; sistematik bir sweep olmadan başarı şansı düşüktür.
- **Yetersiz veya gürültülü ölçüm.** Yan kanal analizinde kötü prob yerleşimi, düşük örnekleme hızı veya senkronizasyon (trace alignment) sorunları, gerçek sızıntıyı gürültüde boğar.
- **Çipe zarar vermek.** Decapping veya aşırı glitch, hedefi kalıcı bozabilir; değerlendirmelerde genellikle birden fazla numune gerekir.

## Sonuç

Donanım destekli tersine mühendislik, yazılım analizinin bittiği yerde başlar ve fiziksel dünyanın kaçınılmaz gerçeklerinden — zamanlama toleransları, veri bağımlı güç tüketimi, unutulmuş debug portları — beslenir. Bir güvenlik mühendisi için buradaki en önemli ders, **savunmanın katmanlı ve fizik-farkında olması gerektiğidir**. Matematiksel olarak sağlam bir şifre, glitch'e açık bir dallanma veya maskelenmemiş bir S-box yüzünden pratikte kırılabilir.

Savunma tarafının önceliği nettir: debug'ı kalıcı kilitleyin, kritik kararları redundant kurun, kriptoyu maskeleyin ve — tehdit modeli fiziksel erişimi içeriyorsa — donanımsal tamper ve glitch detektörlerine yatırım yapın. Tespit bu alanda büyük ölçüde önleyicidir; bu yüzden ürün, sahaya çıkmadan önce yetkin bir yan kanal ve fault injection değerlendirmesinden geçmelidir.
