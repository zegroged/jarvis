# Dinamik Analiz ve Sandboxing

## Tanım

Dinamik analiz, bir yazılımı (özellikle şüpheli veya zararlı bir dosyayı) **çalıştırarak**, çalışma anındaki davranışını gözlemleme yöntemidir. Statik analizin tersine — ki statik analiz dosyayı çalıştırmadan baytları, disassembly çıktısını, string'leri ve import tablosunu inceler — dinamik analiz kodu gerçekten işletir ve şu soruların cevabını arar: Hangi dosyaları açtı? Hangi registry anahtarlarını değiştirdi? Ağda kime bağlandı? Belleğe ne enjekte etti? Hangi API çağrılarını yaptı?

Sandboxing ise bu gözlemin **güvenli bir izolasyon içinde** yapılmasını sağlayan altyapıdır. Bir sandbox, zararlının gerçek sistemlere zarar veremeyeceği, ağa gerçekten sızamayacağı, ama kendini gerçek bir kurban makinede sanacak kadar ikna edici bir kapalı ortamdır. Dinamik analiz "ne gözlemliyorum" sorusudur; sandboxing "bunu nasıl güvenle gözlemliyorum" sorusudur. İkisi birlikte, modern zararlı yazılım analizi ve tehdit istihbaratının belkemiğini oluşturur.

Bu makale dört sütun üzerine kuruludur: **debugger** ile adım adım kontrol, **API izleme** ile davranış yakalama, **ağ analizi** ile dışa bağlantıların çözülmesi ve **izolasyon** ile bunların güvenle yapılması.

## Kök Neden: Neden Dinamik Analize İhtiyaç Var?

Statik analiz teoride yeterli olmalıydı — sonuçta kodun tamamı orada, diskte duruyor. Ama pratikte modern zararlılar statik analizi kasıtlı olarak işe yaramaz hale getirir. Bunun birkaç temel nedeni var ve her biri dinamik analizin neden zorunlu olduğunu açıklar.

**Packing ve şifreleme.** Zararlıların büyük çoğunluğu bir *packer* (UPX gibi meşrudan, özel yazılmış ticari korumalara kadar) ile sıkıştırılmış veya şifrelenmiştir. Diskteki dosyaya baktığınızda gördüğünüz şey, gerçek zararlı kod değil, çalışma anında kendini belleğe açan (unpack eden) bir yükleyicidir (loader). Gerçek payload yalnızca kod çalışırken, bellekte, çözülmüş halde belirir. İşte bu yüzden analiz kodu çalıştırmadan tamamlanamaz: gerçek niyet sadece runtime'da açığa çıkar.

**Kod karmaşıklığı ve dallanma patlaması.** Bir programın hangi yolu izleyeceği çalışma zamanı girdilerine bağlıdır. Statik olarak tüm olası yolları çıkarmak (path explosion problemi) hesaplama açısından pratikte imkânsıza yakındır. Dinamik analiz ise "bu spesifik girdiyle program *gerçekten* ne yaptı" sorusunu kesin biçimde cevaplar.

**Gizli davranış ve tetikleyiciler.** Bazı zararlılar belirli bir tarih, belirli bir kullanıcı adı veya belirli bir domain'e erişim gibi koşullar sağlanmadan zararlı davranışını göstermez (logic bomb / trigger-based behavior). Bunları statik olarak fark etmek zordur; dinamik ortamda doğru koşulları taklit ederek tetiklenmelerini sağlayabilirsiniz.

Özetle dinamik analiz, "kodun ne yaptığını iddia ettiği" değil, "kodun gerçekten ne yaptığı" ile ilgilenir. Zararlı yazılım yazarlarının en çok gizlemek istediği şey de tam olarak budur.

## Debugger: Kodun Kalp Atışını Kontrol Etmek

### Çalışma Mantığı

Bir debugger, işletim sisteminin ve donanımın sağladığı özel mekanizmalar sayesinde çalışan bir sürecin (process) tam kontrolünü ele geçirir. Temelde iki tür durdurma noktası (breakpoint) vardır ve bunların nasıl çalıştığını anlamak, hem analizi hem de anti-debugging tekniklerini kavramak için kritiktir.

**Software breakpoint.** Debugger, durdurmak istediği adresteki orijinal komut baytını geçici olarak özel bir "tuzak" komutuyla değiştirir. x86 mimarisinde bu, tek baytlık `INT3` (0xCC) komutudur. CPU bu bayta ulaşınca bir kesme (interrupt) üretir, işletim sistemi bunu debugger'a iletir, debugger orijinal baytı geri koyar ve size kontrolü verir. Bu mekanizmanın kritik yan etkisi şudur: debugger bellekteki kodu **fiziksel olarak değiştirir**. Zararlı, kendi kodunun ilk baytlarını okuyup 0xCC arayarak debugger'ın varlığını sezebilir (self-checksumming).

**Hardware breakpoint.** Modern CPU'larda belirli debug register'ları (x86'da DR0–DR3 adres register'ları, DR7 kontrol register'ı) vardır. Bunlar belirli bir adrese erişim veya yürütme olduğunda CPU'nun kendisinin durmasını sağlar — kodu değiştirmeden. Bu yüzden hardware breakpoint'ler INT3 taramasına yakalanmaz; ama sayıları sınırlıdır (tipik olarak dört tane) ve zararlı DR register'larını okuyarak yine de varlığınızı sezebilir.

Debugger ayrıca **single-stepping** yapabilir: CPU'nun bayrak register'ındaki trap flag (TF) set edilerek her tek komut yürütmesinden sonra kontrolün debugger'a dönmesi sağlanır. Bu, unpacking rutinini adım adım izlemenin klasik yoludur.

### Somut Kullanım

Diyelim ki packed bir örnekle karşılaştınız. Yaygın strateji şudur: unpacking kodu, çözdüğü payload'a en sonunda bir atlama (jump) yapar — buna genellikle "OEP" (Original Entry Point) denir. Debugger'da bellek yazma bölgesine bir hardware breakpoint koyup ("kod kendini şuraya açtığında dur"), ardından o bölgede yürütme başladığında yakalayarak çözülmüş kodu bellekten dump edebilirsiniz (memory dumping). Böylece packer'ı çalıştırarak kendi işini yaptırıp, tam da payload açığa çıktığı anda dondurursunuz.

Kullanıcı-modu debugger'lar (x64dbg gibi) uygulama sürecinin kendisini incelerken; çekirdek-modu (kernel-mode) debugger'lar (WinDbg'in kernel modu gibi) sürücüleri (driver) ve rootkit'leri, yani işletim sisteminin çekirdeğinde çalışan kodu incelemek için gereklidir. Rootkit'ler tam olarak kullanıcı-modu görünürlüğün altında saklandığı için, çekirdek görünürlüğü olmadan analiz edilemezler.

### İstismar Mantığı: Anti-Debugging

Zararlı yazılım yazarları, debugger varlığını tespit etmek için geniş bir teknik cephanesi kullanır. Bu tekniklerin çoğu, debugger'ın çalışma mantığındaki gözlemlenebilir izlerden faydalanır:

- **Bayrak sorgulama.** Windows'ta bir sürecin debug altında olup olmadığı, süreç ortam yapısındaki (PEB — Process Environment Block) `BeingDebugged` bayrağı gibi alanlardan okunabilir. `IsDebuggerPresent` API'si esasen bu bayrağı okur. Daha gelişmiş varyantlar, doğrudan bellekteki PEB alanlarını manuel okur ki API hook'lanmış olsa bile atlatabilsin.
- **Zamanlama kontrolü.** Debug altında adım adım yürütme, doğal yürütmeden çok daha yavaştır. Zararlı, iki nokta arasında geçen süreyi (örneğin `RDTSC` komutuyla CPU tick sayarak) ölçer; süre anormal büyükse debugger'da olduğunu anlar.
- **Kod bütünlüğü kontrolü.** Kendi kod baytlarının checksum'ını alıp INT3 (0xCC) enjeksiyonunu veya değişiklikleri tespit eder.
- **İstisna tabanlı hile.** Kasıtlı olarak bir istisna (exception) fırlatıp, bunu debugger'ın mı yoksa kendi handler'ının mı yakaladığını gözlemler. Debugger araya girerse akış farklılaşır.

### Savunma: Anti-Anti-Debugging

Analist tarafı bu tekniklere karşı sistematik olarak çalışır. Temel yaklaşım, zararlının okuduğu göstergeleri **yalan söyleyecek şekilde** kontrol altına almaktır:

- PEB'deki `BeingDebugged` bayrağını manuel olarak sıfırlamak veya bu bayrağı okuyan API'leri her zaman "debug yok" döndürecek şekilde yamalamak. Bu iş için topluluk tarafından geliştirilmiş gizleme eklentileri (ScyllaHide türü) yaygın olarak kullanılır.
- Zamanlama kontrollerini, ölçüm sonuçlarını normal görünecek değerlerle yamalamak veya breakpoint'i zamanlama ölçümünün *arasında* değil dışında konumlandırmak.
- Kritik dallanma noktalarında, tespit sonucu "true" dönmüş olsa bile programın akışını manuel olarak istenen dala zorlamak (bayrak register'ını elle değiştirerek jump'ı çevirmek).

Burada altını çizmek gereken kavramsal nokta şudur: anti-debugging ve savunması sonu gelmeyen bir kedi-fare oyunudur, çünkü ikisi de aynı gözlemlenebilir gerçeklikten beslenir. Her tespit tekniği, debugger'ın çalışması için bıraktığı zorunlu bir ize dayanır; her karşı-önlem de o izi gizler. Kusursuz gizlilik teorik olarak mümkün değildir; pratikte hedef, zararlının "yeterince ikna" olmasını sağlamaktır.

## API İzleme: Davranışın Dilbilgisi

### Neden API Çağrıları?

Bir program işletim sistemiyle ne kadar konuşursa konuşsun, sonunda somut bir eylem yapmak için işletim sisteminin sunduğu fonksiyonları — API'leri ve nihayetinde sistem çağrılarını (syscall) — kullanmak zorundadır. Dosya oluşturmak, ağ soketi açmak, başka bir sürece bellek yazmak, registry değiştirmek... hepsi belli API kapılarından geçer. Dolayısıyla bir sürecin yaptığı API çağrılarının dizisi, o sürecin **davranışının dilbilgisidir**. Kodun tamamını okumadan, bu çağrı dizisinden niyeti çıkarabilirsiniz.

Örneğin `VirtualAllocEx` (başka süreçte bellek ayır) → `WriteProcessMemory` (o belleğe kod yaz) → `CreateRemoteThread` (o bellekte thread başlat) üçlüsü, klasik bir **process injection** imzasıdır. Bu üç çağrıyı bu sırayla gören bir analist, kodun geri kalanını okumadan bile kod enjeksiyonu yapıldığını söyleyebilir. Benzer şekilde `RegSetValueEx` ile "Run" anahtarına yazma, kalıcılık (persistence); `CryptEncrypt` çağrılarının yoğun dosya erişimiyle birleşmesi, ransomware davranışını işaret eder.

### Çalışma Mantığı: Hooking

API izlemenin kalbinde **hooking** yatar: bir API çağrısı gerçek hedefine gitmeden önce araya girip çağrıyı (parametreleriyle birlikte) kaydetmek. Başlıca yaklaşımlar:

- **Inline hooking (kullanıcı modu).** Hedef API fonksiyonunun ilk komutları, izleme koduna atlayan bir jump ile değiştirilir. Çağrı geldiğinde önce sizin kodunuz çalışır, parametreleri loglar, sonra orijinali çağırır. Hızlıdır ama zararlı, fonksiyonun ilk baytlarını kontrol ederek hook'u tespit edebilir.
- **IAT hooking.** Süreç import adres tablosundaki (IAT) fonksiyon işaretçileri kendi izleyicinize yönlendirilir. Daha az saldırgan ama dinamik olarak çözülen fonksiyonları (`GetProcAddress` ile bulunanları) kaçırabilir.
- **Syscall / çekirdek düzeyi izleme.** Kullanıcı-modu hook'lar, zararlı doğrudan syscall yaparak atlanabilir. Bu yüzden en sağlam izleme, çekirdek seviyesinde veya sanallaştırma katmanının altında yapılır — zararlının ulaşamayacağı bir konumdan. Windows'ta ETW (Event Tracing for Windows) ve çekirdek callback'leri, hook'a göre daha zor atlatılan telemetri kaynaklarıdır.

### İstismar ve Savunma Dengesi

**İstismar tarafı (zararlının kaçış teknikleri):**

- **Doğrudan syscall.** Zararlı, kullanıcı-modu API katmanını (örneğin ntdll'deki wrapper'ları) tamamen atlayıp syscall numarasını doğrudan işler. Böylece kullanıcı-modundaki tüm inline hook'ları görünmez kılar. Bu, son yıllarda giderek yaygınlaşan bir kaçış tekniğidir.
- **API unhooking.** Zararlı, diskteki temiz DLL kopyasından fonksiyonun orijinal baytlarını okuyup, bellekteki hook'lanmış kopyanın üzerine yazarak izleyiciyi devre dışı bırakır.
- **Dolaylı çözümleme.** Fonksiyonları isimden değil, hash'lenmiş isimlerle veya elle PE yapılarını gezerek çözer (API hashing); bu, statik tespiti de zorlaştırır ve IAT hooking'i etkisiz kılar.

**Savunma tarafı (analistin karşı hamlesi):**

- İzlemeyi zararlının erişemeyeceği bir katmana taşımak. En güçlü yaklaşım, gözlemi **misafir işletim sisteminin dışında** — hypervisor katmanında — yapmaktır. Zararlı kendi işletim sisteminin içinde çalışırken, hypervisor onu dışarıdan izler ve zararlının bu izleyiciye dokunması mümkün değildir. Bu, "out-of-guest" veya VMI (Virtual Machine Introspection) yaklaşımıdır.
- Birden çok telemetri kaynağını birleştirmek: kullanıcı-modu hook, çekirdek callback'i, ETW ve bellek anlık görüntüsü. Zararlı bir kaynağı atlatsa bile diğerinde iz bırakır; boşlukların kesişimi zaten başlı başına bir şüphe işaretidir.
- Davranışı tek tek çağrılar yerine **desenler** hâlinde değerlendirmek. Zararlı, tek bir API çağrısını gizleyebilir ama tüm zincirin sonucunu (ör. yeni bir kalıcılık kaydı, yeni bir ağ bağlantısı) gizleyemez.

## Ağ Analizi: Zararlının Dış Dünyayla Konuşması

### Neden Ağ Trafiği Kritik?

Modern zararlıların çoğu tek başına anlamlı değildir; bir komuta-kontrol (C2 — Command and Control) sunucusuyla konuşarak talimat alır, çalınan veriyi dışarı sızdırır (exfiltration) veya ek payload indirir. Bu yüzden ağ trafiği, zararlının **amacını ve altyapısını** ele veren en zengin kaynaklardan biridir. Hangi domain'lere bağlanıyor? Trafik nasıl şifreleniyor? C2 protokolü neye benziyor? Bu bilgiler hem tek örneği anlamak hem de aynı aktörün diğer kampanyalarını tespit için IOC (Indicator of Compromise) çıkarmak açısından paha biçilmezdir.

### Çalışma Mantığı ve Somut Örnek

Sandbox içinde tipik olarak bütün ağ trafiği bir noktadan geçirilir ve kaydedilir (full packet capture). Analist, DNS sorgularını (zararlı hangi domain'i çözmeye çalışıyor?), TCP bağlantılarını ve uygulama katmanı protokollerini inceler. Ancak burada temel bir gerilim vardır: **trafiği görmek için zararlının konuşmasına izin vermek gerekir, ama gerçek internete izin vermek tehlikelidir.**

Bu gerilim iki yaklaşımla yönetilir:

- **Simülasyon (sahte internet).** İnternete hiç çıkılmaz; bunun yerine tüm DNS sorgularına ve bağlantı isteklerine cevap veren sahte bir servis katmanı (INetSim gibi araçlar bu rolü oynar) kurulur. Zararlı bir web sunucusuna bağlanmaya çalışır, sahte servis geçerli görünen bir HTTP cevabı döner; zararlı "başarıyla bağlandım" sanır ve davranışına devam eder. Böylece hem gerçek zarar önlenir hem de zararlının protokol akışı gözlemlenir.
- **Kontrollü gerçek erişim.** Bazı durumlarda gerçek C2 ile konuşmak gerekir (örneğin gerçek talimatları görmek için). Bu, ciddi risk taşır ve genellikle bir VPN/anonimleştirme katmanı, sıkı çıkış filtreleri ve dikkatli operasyonel güvenlik ile yapılır — çünkü saldırgan analiz altyapınızın IP'sini görebilir.

### Şifreli Trafik Sorunu

Günümüz zararlılarının büyük kısmı TLS kullanır, dolayısıyla paket yakalama yalnızca şifreli baytları gösterir. Bunu aşmanın birkaç yolu vardır ve her birinin bir bedeli vardır:

- **TLS araya girme (interception / MITM).** Sandbox, kendi sertifika otoritesini kurbanın güven deposuna ekleyip trafiği çözüp yeniden şifreleyen bir proxy kullanır. Bu, içeriği görünür kılar; ama zararlı sertifika sabitleme (certificate pinning) yapıyorsa bağlantıyı reddeder ve davranışını değiştirir — yani araya girme çabası, kendisi bir gözlemci etkisi (observer effect) yaratır.
- **Bellekten anahtar/veri çıkarma.** Şifreleme *öncesi* veya *sonrası* veriyi süreç belleğinde yakalamak. Zararlı ağa göndermeden hemen önce düz metin bellekte durur; API izleme ile şifreleme fonksiyonlarını hook'layarak veya bellek dump'ından anahtarları çıkararak trafik çözülebilir.

### Savunma Perspektifi

Ağ analizinden çıkan bilgi doğrudan savunmaya dönüşür. C2 domain'leri ve IP'leri engelleme listelerine eklenir; C2 protokolünün karakteristik desenleri (belirli User-Agent'lar, sabit paket boyutları, düzenli "beaconing" aralıkları) ağ tespit imzalarına dönüştürülür. Burada güçlü bir kavram, davranışsal ağ tespitidir: alan adı sürekli değişse bile (DGA — Domain Generation Algorithm), muntazam aralıklarla dışarı ulaşan, jitter'lı ama periyodik beacon deseni kendini ele verir. Yani içerik gizlense de trafiğin *ritmi* bir imzadır.

## İzolasyon: Güvenli Gözlemin Temeli

### Neden İzolasyon Zorunlu ve Neden Zor?

Zararlıyı çalıştırıyorsunuz — tanımı gereği zarar vermek isteyen bir kodu. İzolasyonun görevi iki yönlüdür: zararlı **dışarı kaçamamalı** (containment) ve aynı zamanda kendini **gerçek bir sistemde sanmalı** (deception). Bu iki gereksinim doğal olarak çelişir: ne kadar çok yalıtım katmanı ve izleme aparatı eklerseniz, o kadar çok "burası bir laboratuvar" izi bırakırsınız; zararlı da tam olarak bu izleri arar.

İzolasyon tipik olarak katmanlar hâlinde kurulur:

- **Sanallaştırma (VM).** En yaygın katman. Zararlı bir sanal makinede çalışır, gerçek donanıma erişimi hypervisor tarafından aracılanır. Analiz sonrası VM temiz bir anlık görüntüye (snapshot) geri döndürülür — bu, dinamik analizi tekrarlanabilir kılan kritik özelliktir: her örnek aynı temiz başlangıç noktasından incelenir.
- **Ağ izolasyonu.** Yukarıda anlatıldığı gibi simüle edilmiş veya sıkı filtrelenmiş ağ.
- **Host-guest sınırı.** Hypervisor'ın kendisi güvenlik sınırıdır; buradaki bir zafiyet, "VM escape" ile zararlının gerçek host'a kaçmasına yol açabilir.

### İstismar Mantığı: Sandbox / VM Kaçınma

Zararlıların önemli bir kısmı, bir analiz ortamında olduğunu düşündüğünde zararlı davranışını *hiç* göstermez — masumca çıkar veya uyur. Buna **sandbox evasion** denir ve tespit teknikleri şu kategorilere ayrılır:

- **Yapaylık (artifact) tespiti.** Sanallaştırma ve izleme araçlarının bıraktığı izleri arar: belirli sürücü isimleri, sanal cihaz üreticisi imzaları, ekstra yardımcı süreçler, karakteristik MAC adres önekleri, belirli registry anahtarları.
- **Zamanlama ve kaynak tespiti.** Gerçek kullanıcı makineleri tek çekirdekli ve 2 GB RAM'li nadiren olur; küçük disk, az çekirdek, az RAM bir laboratuvar işaretidir. Ayrıca sandbox'lar örneği genellikle birkaç dakika izler; zararlı uzun süre "uyuyarak" (sleep) analiz penceresini boşa harcatır.
- **İnsan varlığı tespiti.** Gerçek bir kullanıcıda fare hareketi, tıklama, açık pencereler, tarayıcı geçmişi, son açılan dosyalar olur. Bunların yokluğu, otomatik bir sandbox işaretidir. Bazı zararlılar kullanıcı bir belgeyi kaydırana (scroll) veya belirli bir etkileşim yapana kadar tetiklenmez.

### Savunma: İkna Edici İzolasyon

Analist tarafı, bu tespit sinyallerini nötrleştirmek için sandbox'ı "sertleştirir" (hardening) ve gerçekçi kılar:

- **Yapaylıkları gizlemek.** Sanallaştırma ve izleme izlerini maskelemek; sürücü/registry/cihaz isimlerini gerçek bir makineye benzetmek. Ancak bu asla eksiksiz olamaz — her gizlenen iz için zararlının bakabileceği başka bir yer kalır. Bu yüzden bazı gelişmiş analiz laboratuvarları, tespit edilecek yapay bir katman bırakmamak için **çıplak donanım (bare-metal)** üzerinde analiz yapar.
- **Sistemi yaşanmış göstermek.** Sahte kullanıcı dosyaları, gezinme geçmişi, otomatik fare/klavye simülasyonu, çok çekirdek ve gerçekçi RAM ile makineyi "kullanılıyor" göstermek.
- **Uyuma hilelerini yenmek.** Zararlının çağırdığı bekleme fonksiyonlarını hızlandırarak (sleep-patching / time acceleration) uzun uyku sürelerini anında geçirmek; böylece "10 dakika uyu sonra başla" diyen zararlı, analiz penceresi içinde tetiklenmeye zorlanır.
- **Katmanı derinleştirmek.** Out-of-guest introspection ile izlemeyi misafirin içinden çıkarıp hypervisor'a taşımak. Zararlı kendi işletim sistemi içinde hiçbir izleme aparatı göremez, çünkü izleme gerçekten orada değildir.

Yine aynı asimetriyle karşılaşıyoruz: zararlının davranışını görmek için onu kandırmanız gerekir; kandırma çabası ise iz bırakır. Bu, dinamik analizin kalbindeki değişmez gerilimdir.

## Yaygın Hatalar

Deneyimli analistlerin bile düştüğü, sonuçları geçersiz kılabilecek yaygın hatalar vardır:

- **Analiz ortamını izole etmemek.** Zararlıyı gerçek ağa bağlı, snapshot'ı olmayan, gerçek dosyalar barındıran bir makinede çalıştırmak felakete davetiyedir — solucan (worm) yanal yayılabilir, ransomware paylaşımları şifreleyebilir. İzolasyon opsiyonel değildir.
- **Tek bir çalıştırmaya güvenmek.** Zararlı, ortama, tarihe veya rastgeleliğe bağlı davranış gösterebilir. Tek gözlem yanıltıcıdır; farklı koşullarda (farklı tarih, sahte kullanıcı verisi, farklı ağ cevapları) tekrar çalıştırmak gerekir.
- **Kaçınmayı yorumlamamak.** Bir örnek sandbox'ta "hiçbir şey yapmadı" ise, bu "zararsız" demek değildir — çoğunlukla "kaçındı" demektir. Sessizlik, en güçlü zararlı işaretlerinden biridir ve daha derin (manuel, debugger'lı) analize yönlendirmelidir.
- **Sadece dinamik veya sadece statik analize güvenmek.** İkisi birbirini tamamlar. Dinamik analiz "ne yaptığını" gösterir ama tetiklenmeyen kod yollarını kaçırır; statik analiz "neler yapabileceğini" gösterir ama packing'e takılır. Doğru yaklaşım ikisini iç içe kullanmaktır.
- **Gözlemci etkisini görmezden gelmek.** TLS araya girme, hook'lama ve sandbox aparatlarının hepsi zararlının davranışını değiştirebilir. Gördüğünüz davranışın, aparatınıza bir tepki olup olmadığını her zaman sorgulamak gerekir.
- **Analiz makinesinin kimliğini sızdırmak.** Kontrollü gerçek internet erişimi sırasında kurumun gerçek IP'sinden C2'ye bağlanmak, saldırganı incelendiğinden haberdar eder ve altyapıyı değiştirmesine yol açar.

## En İyi Pratikler

- **Katmanlı gözlem uygulayın.** Tek bir izleme kaynağına güvenmeyin. Debugger, API/syscall izleme, ağ yakalama ve bellek anlık görüntülerini birleştirin. Bir zararlı bir katmanı atlatabilir ama hepsini birden atlatamaz; katmanlar arası tutarsızlık zaten değerli bir sinyaldir.
- **Snapshot temelli, tekrarlanabilir bir laboratuvar kurun.** Her analizi bilinen temiz bir başlangıç noktasından yapın ve bitince geri yükleyin. Bu, hem güvenlik hem de bilimsel tekrarlanabilirlik sağlar.
- **Ortamı gerçekçi kılın.** Sahte kullanıcı verisi, etkileşim simülasyonu, gerçekçi donanım profili ve sleep-patching ile kaçınmayı zorlaştırın. Amaç, zararlının "gerçek kurban" hissetmesidir.
- **Gözlemi zararlının erişemeyeceği katmana taşıyın.** Mümkün olduğunda out-of-guest / hypervisor seviyesi introspection tercih edin; misafir içindeki her aparat, zararlının bulup atlatabileceği bir yüzeydir.
- **Gözlemci etkisini bilinçli yönetin.** Ne zaman TLS'i araya girip ne zaman girmeyeceğinize, ne zaman gerçek C2'ye izin vereceğinize bilerek karar verin; her müdahalenin davranışı değiştirebileceğini kabul edin.
- **Çıktıyı savunmaya dönüştürün.** Dinamik analizin ürünü sadece bir rapor değil; IOC'ler, ağ ve host davranış imzaları, MITRE ATT&CK teknik eşlemeleri olmalıdır. Analiz, tek örneği anlamaktan aynı aktörü ölçekte tespit etmeye uzanmalıdır.
- **Operasyonel güvenliği koruyun.** Analiz altyapınızın kimliğini gizleyin; saldırganın incelendiğini fark etmesi hem istihbarat değerinizi hem de kendi güvenliğinizi tehlikeye atar.

Sonuç olarak dinamik analiz ve sandboxing, "kodu çalıştırıp izlemek" gibi basit görünen ama derinlerinde sürekli bir aldatma-tespit yarışı barındıran bir disiplindir. Her gözlem aracı bir iz bırakır, her iz bir kaçınma fırsatıdır ve her kaçınma yeni bir gözlem katmanı doğurur. İyi bir analist bu asimetriyi anlar, tek bir araca değil katmanlı ve şüpheci bir metodolojiye güvenir ve zararlının sessizliğini bile bir veri olarak okur.
