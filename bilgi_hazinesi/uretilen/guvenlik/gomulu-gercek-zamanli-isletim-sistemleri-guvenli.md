# Gömülü Gerçek-Zamanlı İşletim Sistemleri Güvenliği

## RTOS, MPU Tabanlı İzolasyon ve Görev Zafiyetleri

Bu makale, gömülü sistemlerde yaygın kullanılan gerçek-zamanlı işletim sistemlerinin (RTOS - Real-Time Operating System) güvenlik mimarisini, özellikle bellek koruma birimi (MPU - Memory Protection Unit) tabanlı izolasyon mekanizmalarını ve bu mekanizmalardaki yapılandırma hatalarını eğitim amacıyla ele alır. Odak, mekanizmayı anlamak ve savunma/tespit kurmaktır; operasyonel saldırı talimatı değildir.

---

## 1. Tanım ve Bağlam

### RTOS nedir?

Bir **RTOS**, görevlerin (task/thread) öngörülebilir ve sınırlı gecikmeyle (deterministik) çalıştırılmasını hedefleyen küçük çekirdekli bir işletim sistemidir. **FreeRTOS** ve **Zephyr** bu alanın en yaygın açık kaynak temsilcileridir. Genel amaçlı bir işletim sistemi (Linux gibi) her işleme ayrı bir sanal adres alanı verirken, tipik bir RTOS uygulaması genellikle **tek bir fiziksel adres alanında** ve çoğu zaman **çekirdek ayrıcalık seviyesinde** çalışır. Bu, MMU (Memory Management Unit) yerine, çok daha basit olan **MPU** ile veya hiçbir donanımsal koruma olmadan çalışan mikrodenetleyicilerde (özellikle ARM Cortex-M ailesi) gerçekleşir.

### MMU ile MPU farkı

Bu ayrım güvenlik açısından kritiktir:

- **MMU**: Sanal adresi fiziksel adrese çevirir, sayfa (page) tablolarıyla her işleme izole adres alanı sağlar. Cortex-A gibi uygulama işlemcilerinde bulunur.
- **MPU**: Adres çevirisi **yapmaz**. Sadece fiziksel adres uzayını sınırlı sayıda **bölgeye (region)** ayırır ve her bölge için erişim izinlerini (okuma/yazma/çalıştırma, ayrıcalıklı/ayrıcalıksız) tanımlar. Bölge sayısı donanıma bağlıdır ve genellikle azdır (örneğin 8 veya 16 bölge). Cortex-M gibi mikrodenetleyicilerde bulunur.

MPU'nun az sayıda bölgeyle çalışması ve adres çevirisi yapmaması, izolasyonun tamamen **doğru yapılandırmaya** bağlı olması anlamına gelir. Yanlış yapılandırılmış bir MPU, izolasyon var sanılan bir sistemde gerçekte hiç koruma sağlamaz.

---

## 2. Kök Neden ve Çalışma Mantığı

### Ayrıcalık seviyeleri

ARM Cortex-M işlemciler iki yürütme modu sunar:

- **Privileged (ayrıcalıklı)**: Çekirdek, kesme işleyicileri (ISR) ve MPU yapılandırma kaydedicilerine erişim burada gerçekleşir.
- **Unprivileged (ayrıcalıksız)**: Uygulama görevlerinin çalıştırılması hedeflenen mod. Bu modda MPU kaydedicileri değiştirilemez, yani görev kendi kısıtlamalarını kaldıramaz.

Güvenli bir tasarımda kullanıcı görevleri **unprivileged** modda çalışmalı, yalnızca çekirdek **privileged** modda olmalıdır. Uygulamada ise birçok gömülü proje, kolaylık için tüm görevleri privileged modda çalıştırır. Bu durumda MPU teknik olarak etkin olsa bile, ayrıcalıklı bir görev MPU'yu yeniden yapılandırabilir veya kısıtlamaları hiç yaşamaz; izolasyon kâğıt üzerinde kalır.

### Görev izolasyonunun mantığı

FreeRTOS'un MPU destekli sürümü (genellikle "FreeRTOS-MPU" olarak anılır) ve Zephyr'in **userspace** özelliği, her göreve yalnızca kendi yığınına (stack) ve açıkça izin verilen bellek bölgelerine erişim tanır. Amaç, görevlerarası izolasyondur (task isolation):

- Bir görevin bir başka görevin yığınını okuyamaması/yazamaması,
- Bir görevin çekirdek veri yapılarını (kaynak yönetimi, kuyruklar, zamanlayıcı durumu) bozamaması,
- Bir bölgenin **W^X** (Write XOR Execute) ilkesine uyması: yazılabilir bir bölgenin çalıştırılabilir olmaması.

Bu izolasyon, bir görevin belleğinde oluşan bir hatanın (örneğin bir buffer overflow) tüm sistemi ele geçirmesini engellemeyi hedefler. İzolasyon çalıştığında, hatalı görev bir MPU fault üretir ve sistem bunu güvenli biçimde yakalayabilir.

### MPU bölge kuralları ve tipik kısıtlar

MPU bölgeleri donanıma özgü hizalama (alignment) kurallarına tabidir. Klasik ARMv7-M MPU'sunda bölge boyutları ikinin kuvveti olmalı ve bölge başlangıç adresi kendi boyutuna hizalı olmalıdır. Bu kısıt, geliştiricileri bölgeleri "yeterince büyük" tanımlamaya iter; büyük tanımlanan bir bölge ise gereğinden fazla belleği erişilebilir kılarak izolasyonu zayıflatır. ARMv8-M MPU'su daha esnek (base/limit tabanlı) bir model sunar ancak hizalama ve bölge sayısı sınırları hâlâ tasarımı kısıtlar.

---

## 3. Yaygın Zafiyet Sınıfları

### 3.1 Tüm görevleri ayrıcalıklı çalıştırmak

En yaygın hata, kullanıcı görevlerinin privileged modda başlatılmasıdır. FreeRTOS'ta bir görev, oluşturma sırasında ayrıcalıklı olarak işaretlenebilir. Bu bayrak dikkatsizce tüm görevlere uygulandığında, MPU aktif olsa bile hiçbir görev unprivileged kısıtlarına tabi olmaz. Sonuç: derinlemesine savunma katmanı tamamen kaybolur.

### 3.2 Aşırı geniş veya örtüşen bölgeler

MPU bölgeleri örtüşebilir (overlap) ve genellikle daha yüksek numaralı bölgenin izinleri öncelik kazanır (donanıma göre değişir). Bir geliştirici, bir görevin bir tampona erişebilmesi için bölgeyi olması gerekenden geniş tanımlarsa, o görev komşu veri yapılarını da görür. Örtüşen bölgelerde öncelik mantığı yanlış kurulduğunda, kısıtlayıcı olması beklenen bir bölge, altındaki geniş bir "her şeye izin ver" bölgesi tarafından etkisiz kılınabilir.

### 3.3 W^X ihlali (RWX bölgeler)

Hem yazılabilir hem çalıştırılabilir bir bölge, klasik kod enjeksiyonuna kapı aralar. Bir buffer overflow ile yığına yazılan veri, aynı zamanda çalıştırılabilirse, saldırgan denetimi ele alabilir. Güvenli tasarımda kod bölgeleri **salt-okunur + çalıştırılabilir**, veri/yığın bölgeleri **okuma/yazma + çalıştırılamaz (XN - eXecute Never)** olmalıdır.

### 3.4 Yığın taşması ve MPU koruma boşluğu

MPU, bir görevin yığınının sonuna **koruma bölgesi (guard region)** yerleştirerek yığın taşmasını (stack overflow) donanımsal olarak yakalayabilir. Yapılandırma bu guard'ı içermiyorsa, taşan yığın sessizce komşu belleği bozar. Ayrıca kesme işleyicilerinin (ISR) kullandığı ayrı yığın, görev yığınından farklı bir korumaya sahiptir; bu ayrım gözden kaçırıldığında ISR bağlamında taşmalar korumasız kalır.

### 3.5 Paylaşımlı bölgeler ve syscall sınırı

Zephyr userspace'te ayrıcalıksız görev, çekirdek hizmetlerine **system call** ile geçer. Bu geçişte çekirdeğe iletilen işaretçiler (pointer) doğrulanmalıdır; aksi halde görev, çekirdeğe kendi erişim alanı dışındaki bir adresi işaretçi olarak verip çekirdeği "confused deputy" durumuna sokabilir. Yani ayrıcalıksız kod, ayrıcalıklı çekirdeği kendi yerine yasak bir belleğe erişmeye ikna etmeye çalışır. Bu nedenle syscall giriş noktalarında pointer/tampon doğrulaması izolasyonun ayrılmaz parçasıdır.

### 3.6 DMA ile MPU'nun atlanması

MPU yalnızca **CPU** erişimlerini denetler. **DMA (Direct Memory Access)** denetleyicisi belleğe CPU'dan bağımsız erişir ve klasik MPU bunu görmez. Ayrıcalıksız bir görev bir DMA transferini programlayabiliyorsa, MPU kısıtlarını dolaylı olarak aşıp yasak bölgelere yazabilir. Bu, MPU tabanlı izolasyonun sık gözden kaçan bir kör noktasıdır; DMA erişimleri ayrı bir mekanizmayla (varsa sistem düzeyi MPU/koruma) kısıtlanmalıdır.

---

## 4. Örnek Senaryo (Kavramsal)

Bir IoT termostat firmware'ini düşünelim. İçinde iki görev var:

- **NetTask**: Ağdan gelen paketleri işler, tampona (buffer) kopyalar.
- **CtrlTask**: Isıtma rölesini yöneten kritik kontrol görevi.

Tasarım hedefi: NetTask'te oluşacak bir bellek hatasının CtrlTask'i etkilememesi.

**Doğru yapılandırma**: NetTask unprivileged çalışır; MPU bölgesi yalnızca kendi yığınını ve ağ tamponunu kapsar (XN, RW). CtrlTask'in belleği NetTask'in erişim alanı dışındadır. NetTask'teki bir taşma bir MPU fault üretir; sistem güvenli duruma geçer, röle güvenli konumda kalır.

**Yanlış yapılandırma**: Her iki görev de privileged; ya da NetTask'in bölgesi tüm RAM'i kapsayacak kadar geniş. Bu durumda NetTask'teki bir taşma, CtrlTask'in kontrol değişkenlerini bozabilir; röle beklenmedik davranır ve fiziksel bir güvenlik sorununa dönüşebilir. Buradaki asıl ders, MPU'nun varlığının değil, **bölge sınırlarının doğruluğunun** koruma sağladığıdır.

---

## 5. Tespit

Tespit, hem geliştirme aşamasında hem çalışma zamanında yapılmalıdır.

### 5.1 Statik ve yapılandırma denetimi

- **MPU bölge tablosunun gözden geçirilmesi**: Her bölge için başlangıç, boyut, izinler (RW/RO/XN) ve ayrıcalık düzeyi tek tek doğrulanmalıdır. Bölgelerin gereğinden geniş olmadığı, RWX bölge bulunmadığı ve örtüşme önceliklerinin bilinçli olduğu kontrol edilmelidir.
- **Görev ayrıcalık bayraklarının denetimi**: Hangi görevlerin privileged oluşturulduğu listelenmeli; kritik olmayan her görevin unprivileged olması hedeflenmelidir.
- **Yapı yapılandırmasının doğrulanması**: MPU desteğinin ve userspace özelliğinin derleme zamanı seçenekleriyle gerçekten etkin olduğu doğrulanmalıdır. Sık rastlanan bir yanılgı, MPU kodunun projede olması ama ilgili derleme seçeneğinin kapalı olması nedeniyle çalışma zamanında hiç devreye girmemesidir.

### 5.2 Çalışma zamanı tespiti

- **Fault işleyicilerinin izlenmesi**: Cortex-M'de MPU ihlalleri genellikle **MemManage Fault** üretir (mevcut değilse HardFault'a yükselir). Bu işleyicide fault durum kaydedicileri (örneğin MemManage Fault Status ve hatalı adres kaydedicileri) okunup kayıt altına alınmalıdır. Beklenmedik MemManage fault'ları, bir izolasyon ihlali veya bellek bozulması göstergesidir.
- **Guard bölge tetiklenmeleri**: Yığın guard bölgesinden gelen fault'lar, bir yığın taşması sinyalidir ve loglanmalıdır.
- **Telemetri ve watchdog**: Görevlerin beklenen periyotlarda çalışıp çalışmadığı bir watchdog ile izlenmeli; sapmalar bozulma işareti sayılmalıdır.

### 5.3 Test yoluyla tespit

- **Negatif testler**: Bir görevin, erişmemesi gereken bir adrese eriştiğinde gerçekten fault ürettiğini doğrulayan testler yazılmalıdır. İzolasyonun "sessizce başarısız olmadığını" ancak bu tür testler kanıtlar.
- **Fuzzing**: Ağ/parser giriş noktaları fuzz edilerek bellek hatalarının MPU tarafından yakalanıp yakalanmadığı gözlemlenmelidir.

---

## 6. Savunma

### 6.1 En az ayrıcalık ilkesi

Her görev yalnızca işini yapmaya yetecek belleğe ve moda sahip olmalıdır. Varsayılan privileged değil, varsayılan unprivileged olmalıdır. Yalnızca donanıma yakın, gerçekten ayrıcalık gerektiren görevler istisna tutulmalıdır.

### 6.2 Dar ve amaca özel bölgeler

MPU bölgeleri mümkün olan en dar sınırlarla tanımlanmalı; her göreve yalnızca kendi yığını ve açıkça gerekli paylaşımlı tamponlar açılmalıdır. Hizalama kısıtları nedeniyle bölge büyütmek gerekiyorsa, bu genişlemenin neyi açığa çıkardığı bilinçli değerlendirilmelidir.

### 6.3 W^X uygulanması

Kod bölgeleri salt-okunur ve çalıştırılabilir; veri, yığın ve heap bölgeleri yazılabilir ve **XN** olmalıdır. Yazılabilir-çalıştırılabilir hiçbir bölge bırakılmamalıdır.

### 6.4 Yığın guard bölgeleri

Her görev yığını için guard bölgesi tanımlanmalı; taşma donanımsal olarak yakalanmalıdır. ISR yığını da ayrıca korunmalıdır.

### 6.5 Syscall sınırında doğrulama

Ayrıcalıksız görevlerden çekirdeğe geçen tüm işaretçi ve tampon uzunlukları, çekirdek tarafında, çağıran görevin erişim alanına göre doğrulanmalıdır. Çekirdek, ayrıcalıksız kodun verdiği ham adrese körü körüne güvenmemelidir.

### 6.6 DMA'nın ayrıca kısıtlanması

DMA erişimleri MPU dışında kaldığından, DMA tanımlayıcılarını programlayabilen kod güvenilir kabul edilmeli veya DMA hedef adresleri ayrıca kısıtlanmalıdır. Mümkünse ayrıcalıksız görevlere doğrudan DMA yapılandırma yetkisi verilmemelidir.

### 6.7 Derinlemesine savunma ve güncel çekirdek

MPU izolasyonu tek başına yeterli değildir; stack canary, güvenli önyükleme (secure boot), imzalı firmware güncellemesi ve güvenli iletişim ile birlikte katmanlı bir savunma oluşturulmalıdır. Kullanılan RTOS çekirdeği düzenli güncellenmeli; MPU ve userspace ile ilgili düzeltmeler (özellikle ARMv8-M ve TrustZone ile ilgili olanlar) takip edilmelidir.

### 6.8 TrustZone tamamlayıcılığı

ARMv8-M'te **TrustZone-M**, belleği ve çevre birimlerini "secure" ve "non-secure" dünyalara ayırır. Bu, MPU'nun yerini almaz; ikisi farklı katmanlardır. TrustZone dünyalar arası bir sınır çizerken, MPU her dünya içindeki görevlerarası izolasyonu sağlar. İkisi doğru birlikte kullanıldığında koruma güçlenir; ancak secure/non-secure geçiş fonksiyonlarının (veneer) girişlerindeki argüman doğrulaması, tıpkı syscall sınırında olduğu gibi kritik önemdedir.

---

## 7. Yaygın Hatalar (Özet Kontrol Listesi)

- MPU'nun kodda var olup derleme seçeneğiyle **etkinleştirilmemiş** olması; kimse fault görmediği için "çalışıyor" sanılması.
- Tüm görevlerin **privileged** çalıştırılması, izolasyonun etkisiz kalması.
- Bölgelerin hizalama kolaylığı için **aşırı geniş** tanımlanması.
- **RWX** (yazılabilir + çalıştırılabilir) bölge bırakılması.
- Yığın **guard** bölgelerinin unutulması; taşmaların sessizce belleği bozması.
- **Syscall/veneer** sınırında pointer doğrulamasının atlanması (confused deputy).
- **DMA**'nın MPU dışında olduğunun göz ardı edilmesi.
- Fault işleyicilerinin yalnızca sistemi resetlemesi, **teşhis bilgisi loglamaması**; olayların görünmez kalması.
- Negatif izolasyon testlerinin yazılmaması; korumanın gerçekte çalışıp çalışmadığının hiç doğrulanmaması.

---

## 8. Kapanış

MPU tabanlı izolasyon, gömülü RTOS güvenliğinde güçlü ama kırılgan bir araçtır: doğru yapılandırıldığında bir görevdeki hatanın tüm cihazı ele geçirmesini engeller, yanlış yapılandırıldığında ise var olmayan bir güven duygusu yaratır. Bu alanda uzmanlık, komut ezberlemekten çok **bölge sınırlarını, ayrıcalık düzeylerini ve donanımın gerçekten neyi denetleyip neyi denetlemediğini** (özellikle DMA gibi kör noktaları) anlamaktır. Savunmanın özü nettir: en az ayrıcalık, dar bölgeler, W^X, guard'lar, sınır doğrulaması ve korumanın gerçekten tetiklendiğini kanıtlayan testler.
