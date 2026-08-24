# Lock-Free ve Wait-Free Programlama, Bellek Sıralama Modelleri (Memory Ordering / Atomics)

## Giriş: Neden Bu Konu Kritik

Çok çekirdekli işlemcilerin ve yüksek eşzamanlılık gerektiren sistemlerin (veritabanları, işletim sistemi çekirdekleri, ağ sunucuları, oyun motorları) kalbinde iki temel gerçeklik yatar: kilitler (mutex, semaphore) doğru kullanıldığında güvenlidir ama pahalıdır ve bazı senaryolarda ölümcül tuzaklar (deadlock, priority inversion, convoy effect) barındırır. Bu yüzden mühendisler, paylaşılan veriyi kilit kullanmadan, doğrudan atomic CPU talimatlarıyla senkronize eden "lock-free" ve "wait-free" teknikler geliştirmiştir.

Ancak bu tekniklerin doğru çalışması, "memory ordering" (bellek sıralama modeli) denen, çoğu yazılımcının yüzeysel bildiği ama derinlemesine anlamadığı bir konuya dayanır. Yanlış anlaşılan bir `memory_order`, yanlış kullanılan bir CAS (compare-and-swap) döngüsü, ya da fark edilmeyen bir ABA problemi; klasik bir "race condition" gibi görünmeyen ama üretimde ayda bir kez, sadece belirli bir CPU mimarisinde, sadece yüksek yük altında ortaya çıkan, hata ayıklaması kabusa dönüşen zafiyetler doğurur. Güvenlik açısından da önemlidir: bozulmuş atomic senkronizasyon; use-after-free, double-free, tutarsız durum (inconsistent state) gibi bellek güvenliği ve mantık hatası sınıflarına yol açabilir ki bunlar exploit edilebilir zafiyetlerdir. Bu makale, mekanizmayı doğru anlamanızı ve savunma/tespit refleksini kazanmanızı hedefler.

## Temel Kavramlar: Lock-Free, Wait-Free, Obstruction-Free

Bu üç terim genellikle birbirine karıştırılır ama kesin, matematiksel tanımları vardır. Bir algoritmanın "non-blocking" (bloklamayan) olması, hiçbir thread'in bir başka thread'in kilidini tutarken sonsuza kadar askıda kalamayacağı anlamına gelir. Bunun üç seviyesi vardır:

- **Obstruction-free**: Bir thread, izole çalıştırıldığında (diğer tüm thread'ler duraklatılırsa) sonlu adımda ilerleme kaydeder. Ama gerçek çekişme (contention) altında hiçbir ilerleme garantisi yoktur; iki thread birbirini sürekli "iptal ettirebilir" (livelock).
- **Lock-free**: Sistemdeki thread'lerin **en az biri**, her zaman ilerleme kaydeder. Bireysel bir thread aç kalabilir (starvation), yani sürekli başka thread'ler tarafından "geçilebilir", ama bütün sistem asla durmaz. CAS tabanlı retry-loop'lar tipik lock-free örneğidir.
- **Wait-free**: **Her** thread, kaç adımda tamamlayacağı önceden sınırlı (bounded) olacak şekilde ilerleme kaydeder. Starvation imkânsızdır. Bu en güçlü garantidir ama tasarımı ve pratikte performansı çoğu zaman çok daha karmaşık ve maliyetlidir; wait-free algoritmalar literatürde çoğunlukla akademik veya çok özel gerçek zamanlı (hard real-time) sistemlerde kullanılır.

Kök neden ayrımı şudur: kilit tabanlı senkronizasyonda bir thread kilidi tutarken önceliksiz zamanlanır (preempt edilir) veya çökerse, kilidi bekleyen **tüm** diğer thread'ler bloke kalır — bu "priority inversion" ve "convoy effect" kaynağıdır. Lock-free tasarımda ise hiçbir thread diğerinin "kilidi serbest bırakmasını" beklemez; bunun yerine "iyimser eşzamanlılık" (optimistic concurrency) mantığıyla, veriyi okur, yerel bir kopya üzerinde hesaplama yapar, sonra tek bir atomic işlemle (genellikle CAS) değişikliği "hep ya da hiç" şeklinde uygulamaya çalışır. Başarısız olursa (başka bir thread araya girdiyse) baştan dener.

## Atomic İşlemler ve CAS (Compare-And-Swap)

Donanım düzeyinde CPU'lar, "read-modify-write" işlemlerini bölünmez (atomic, yani ara sonuç asla gözlemlenemeyen) şekilde yapabilen özel talimatlar sunar: `LOCK CMPXCHG` (x86), `LDXR/STXR` (ARM, load-exclusive/store-exclusive) gibi. Bunların üzerine inşa edilen en temel yapı taşı **compare-and-swap**'tir:

```
bool CAS(T* adres, T beklenen, T yeni_deger) {
    atomic olarak:
        eğer *adres == beklenen ise:
            *adres = yeni_deger; return true;
        değilse:
            beklenen = *adres; return false;  // bazı API'lerde beklenen güncellenir
}
```

Tipik kullanım deseni, "oku-değiştir-CAS-ile-yaz" döngüsüdür:

```
do {
    eski = atomic_load(&sayac);
    yeni = eski + 1;
} while (!CAS(&sayac, eski, yeni));
```

Buradaki mantık şudur: eğer CAS başarısız olursa (aradan başka bir thread girip değeri değiştirdiyse), döngü baştan başlar; hiçbir thread kilit tutmadığı için hiçbir zaman "askıda" kalınmaz. Bu, lock-free'nin en yaygın inşa bloğudur — atomic sayaçlar, lock-free stack/queue, lock-free hash tablosu gibi yapıların hemen hepsi CAS döngüsü üzerine kuruludur.

Diğer önemli atomic ilkeller: `fetch_add` (atomic artırma), `exchange` (koşulsuz değiştir-ve-eskisini-döndür), ve daha güçlü ama donanım desteği daha sınırlı `compare_exchange_weak/strong` varyantları (weak sürüm, bazı mimarilerde "spurious failure" — beklenen değer eşleşse bile bazen başarısız dönebilme — özelliğine sahiptir, bu yüzden weak genelde döngü içinde, strong tek seferlik kontrol için tercih edilir).

## Bellek Sıralama Modelleri (Memory Ordering)

Bu, konunun en çok yanlış anlaşılan ve en kritik kısmıdır. "Atomic bir işlem yaptım" demek, "diğer thread'ler bu işlemin etkilerini doğru sırada görecek" anlamına **gelmez**. Modern CPU'lar ve derleyiciler performans için talimatları yeniden sıralayabilir (instruction reordering), hem derleme zamanında (compiler reordering) hem çalışma zamanında (CPU out-of-order execution, store buffer'lar, cache coherency gecikmeleri). Tek bir thread içinde bu yeniden sıralama gözlemlenemez ("as-if-serial" kuralı), ama **başka bir thread'in gözünden**, işlemlerin hangi sırayla "göründüğü" garanti değildir — bu tam olarak eşzamanlı programlamayı zorlaştıran şeydir.

C++11 ve sonrasında (ve benzer şekilde Rust, Java'nın kendi modeliyle, C11) tanımlanan `std::memory_order` numaralandırması, programcıya bu sıralamayı ne kadar sıkı ya da gevşek isteyeceğini seçme imkânı verir:

- **`memory_order_relaxed`**: Sadece o değişkenin kendi atomicliğini garanti eder (yarı-yamalı okuma/yazma olmaz), ama başka hiçbir sıralama garantisi yoktur. Sadece bağımsız sayaçlar (örneğin istatistik/metrik sayaçları) gibi, sırasının önemsiz olduğu durumlarda kullanılır. En hızlı ama en tehlikeli moddur — yanlış yerde kullanılırsa "görünürlük" hataları (bir thread'in yazdığını diğerinin geç veya hiç görmemesi gibi) ortaya çıkar.

- **`memory_order_acquire`** (okuma tarafında) ve **`memory_order_release`** (yazma tarafında): Bunlar birlikte "acquire-release" çiftini oluşturur ve lock-free programlamanın temel dilidir. Bir thread bir değişkene `release` ile yazarsa, o yazmadan **önce** yaptığı tüm bellek işlemleri (o değişkenle ilgisiz olsalar bile), aynı değişkeni `acquire` ile okuyan başka bir thread'e, o okumadan **sonra** yapılan tüm işlemlerinden önce görünür hale gelir. Kısacası: "release, kilidi bırakmak gibi; acquire, kilidi almak gibi" davranır — ama gerçek bir kilit olmadan, sadece o tek atomic değişken üzerinden "senkronizasyon noktası" (synchronizes-with ilişkisi) kurulur. Bu, "bir flag'i true yap, başka thread flag'i true görünce, flag'den önce yazılmış olan datayı da güvenle okuyabilir" mantığının temelidir.

- **`memory_order_seq_cst`** (sequentially consistent, varsayılan): En güçlü ve en sezgisel modeldir — tüm thread'ler, tüm seq_cst işlemlerinin **aynı global sırayla** gerçekleştiğini görür, sanki tek bir global saat varmış gibi. En kolay akıl yürütülen moddur ama ekstra donanım engelleri (memory fence/barrier) gerektirdiği için en maliyetlisidir.

- **`memory_order_consume`**: Acquire'ın daha zayıf, "veri bağımlılığı" (data-dependency) üzerinden sıralama yapan bir varyantıdır; pratikte derleyicilerin doğru implemente etmesi çok zor olduğundan çoğu standart kütüphane onu acquire'a yükseltir ve modern tavsiyeler genelde consume'dan kaçınmayı önerir.

### Kök Neden: Neden Bu Karmaşıklık Var?

Temel sebep donanım performansıdır. CPU'lar arasında "cache coherency protokolü" (örneğin MESI ailesi) vardır ama her yazmanın anında tüm çekirdeklere yayılması (full sequential consistency donanımda) muazzam performans kaybı demektir — store buffer'lar, speculative execution, out-of-order pipeline'lar bu maliyeti gizlemek için var. Eğer her atomic işlem varsayılan olarak "dünyanın her yerinde anında görünür ve sıralı" olsaydı, çok çekirdekli performansın büyük kısmı heba olurdu. Bu yüzden dil standartları, "en gevşek moddan en sıkı moda" bir yelpaze sunar: programcı, algoritmanın gerçekte neye ihtiyacı olduğunu düşünüp en ucuz doğru modeli seçmelidir. Bu aynı zamanda en büyük tuzak kaynağıdır: gevşek modu, sıkı sıralama gerektiren bir senaryoda kullanmak.

## Yaygın Hatalar ve Tuzaklar

**1. "Atomic = senkronize" yanılgısı.** Bir değişkeni atomic yapmak sadece o tek değişken üzerindeki okuma/yazmanın yırtılmadan (tearing olmadan) gerçekleşmesini garanti eder. Onunla ilişkili başka verilerin görünürlük sırasını garanti etmez — bunun için doğru `memory_order` seçimi (genelde acquire/release çifti) şarttır. Yeni başlayan geliştiriciler sıkça "değişkeni atomic yaptım, artık thread-safe" der ve etraftaki ilişkili state'i relaxed sıralamayla bırakır; bu, "publish" (yayınlama) deseninde klasik bir hatadır: bir nesneyi hazırlayıp bir pointer'ı atomic olarak "yayınlarken" release kullanılmazsa, başka bir thread pointer'ı görüp içini henüz tam yazılmamış (yarı-inşa edilmiş) haliyle okuyabilir.

**2. ABA Problemi.** CAS, sadece "değer hâlâ X mi" diye bakar, "değer X'ten hiç değişmedi mi" diye bakmaz. Senaryo: Thread A bir pointer'ın değerinin `X` olduğunu okur, CAS yapmadan önce kesintiye uğrar. Bu sırada Thread B, değeri `X`'ten `Y`'ye değiştirir, sonra bir şekilde (örneğin bir bellek havuzunda yeniden kullanım/reuse yoluyla) tekrar `X` değerine (aynı bit paternine, farklı mantıksal nesneye!) geri döndürür. Thread A geri döndüğünde CAS(`X`, yeni) başarılı olur çünkü değer hâlâ `X` görünüyor — ama aradan geçen B/Y/tekrar-X döngüsünü Thread A hiç bilmez ve mantıksal olarak yanlış bir durumu "başarılı" sanır. Bu özellikle lock-free stack/free-list gibi düğüm (node) geri dönüştürülen yapılarda, use-after-free benzeri bellek güvenliği hatalarına yol açabilir. **Savunmalar:** her pointer'a bir "sürüm sayacı" (generation/tag counter) ekleyip CAS'ı geniş (double-width, örn. 128-bit) yapmak (tagged pointer / ABA counter deseni), ya da hazard pointer / epoch-based reclamation gibi güvenli bellek geri kazanım (memory reclamation) şemaları kullanmak, ya da mümkünse garbage-collected dil/ortamda çalışmak.

**3. False Sharing.** Bu bir doğruluk hatası değil, sinsi bir **performans** hatasıdır ama sistem güvenilirliği açısından da önemlidir (SLA ihlali, kapasite planlamasını bozma). Modern CPU cache'leri veriyi "cache line" denen sabit boyutlu bloklar halinde taşır (çoğu mimaride 64 bayt). Eğer iki farklı thread'in kullandığı, mantıksal olarak **ilgisiz** iki değişken aynı cache line'a düşerse, biri değişkenini yazdığında donanım tutarlılık protokolü tüm cache line'ı "geçersiz" (invalidate) ilan eder ve diğer çekirdek, kendi ilgisiz değişkenini okumak için bile cache line'ı yeniden çekmek zorunda kalır. Sonuç: hiçbir gerçek veri paylaşımı olmadığı halde, sanki paylaşılıyormuş gibi ağır performans kaybı (bazı ölçümlerde onlarca kata varan yavaşlama). **Tespit:** profilleme araçlarıyla (donanım performans sayaçları, cache-miss oranları) çekirdekler arası beklenmedik cache invalidation trafiği görülür. **Savunma:** sık yazılan, farklı thread'lere ait atomic değişkenleri `alignas(64)` gibi hizalama/padding teknikleriyle ayrı cache line'lara yerleştirmek (cache line padding).

**4. Yanlış "gevşek" (relaxed) kullanım.** Sadece sayaç artırma gibi tamamen bağımsız durumlarda relaxed güvenlidir. Bir flag'i relaxed ile set edip başka bir thread'in bunu görüp ilişkili veriye erişmesini beklemek klasik bir hatadır; derleyici veya CPU, gerçek dünyada "mantıksal olarak sonra gelmesi gereken" bir yazmayı öne alabilir çünkü relaxed modda bunu yasaklayan hiçbir kural yoktur.

**5. Double-checked locking hatası (tarihsel örnek).** C++'ta uzun süre `if (ptr == nullptr) { lock(); if (ptr == nullptr) ptr = new T(); }` deseni, atomic olmayan ham pointer ile yazılınca, ikinci thread `ptr`'ın non-null olduğunu görüp içini yarım okuyabiliyordu (constructor tamamlanmadan). Doğru çözüm, `ptr`'ı atomic yapıp release/acquire ile senkronize etmek, ya da dilin garantili tembel başlatma (thread-safe static initialization, örn. C++11 "magic statics") mekanizmalarını kullanmaktır.

**6. Lock-free = daha hızlı** varsayımı. Düşük/orta çekişmede lock-free genelde kazanır, ama yüksek çekişmede CAS retry-loop'ları "livelock" benzeri davranışla sürekli başarısız olup CPU'yu boşa harcayabilir (özellikle exponential backoff gibi bir yumuşatma yoksa). Basit bir mutex, iyi optimize edilmiş çekirdek desteğiyle (futex gibi) bazen daha öngörülebilir olabilir. Karar, ölçüme dayanmalı; "lock-free her zaman üstündür" bir efsanedir.

## Doğru Kullanım ve En İyi Pratikler

- **Varsayılan olarak `seq_cst` ile başlayın.** Doğruluğu kanıtlamak kolaydır; ancak profilleme gösterirse ve gerçekten darboğazsa, bilinçli olarak acquire/release'e indirin ve gerekçesini kod içinde (yorum olarak) belgeleyin. "Neden bu memory_order yeterli" sorusuna cevap veremiyorsanız, o optimizasyonu yapmayın.
- **Yayınlama deseninde (publish pattern) her zaman release/acquire çifti kullanın:** Veriyi hazırlayan thread son adımda `release` ile "hazır" işaretini yazsın; tüketen thread aynı işareti `acquire` ile okusun. Bu çift olmadan (örn. sadece üretici release ama tüketici relaxed okursa) garanti bozulur — ikisi de doğru tarafta olmalı.
- **Hazır, gözden geçirilmiş kütüphaneleri tercih edin.** Kendi lock-free stack/queue'nuzu sıfırdan yazmak yerine (Boost.Lockfree, folly, moodycamel::ConcurrentQueue gibi test edilmiş, akademik olarak da incelenmiş uygulamalar) kullanmak, ABA ve bellek geri kazanım hatalarından kaçınmanın en güvenli yoludur. Bu alan "kendi kriptonu yazma" prensibiyle aynı mantığa sahiptir: çok az kişi ince detayları ilk seferde doğru yapar.
- **Bellek geri kazanımını (memory reclamation) baştan tasarlayın.** Lock-free bir yapıda düğüm silme, "başka bir thread hâlâ bu düğüme bakıyor olabilir" sorusunu çözmeden yapılamaz. Hazard pointers, epoch-based reclamation (EBR), veya RCU (read-copy-update, Linux çekirdeğinde yaygın) gibi kanıtlanmış teknikler kullanın.
- **Cache line hizalamasına dikkat edin.** Çok thread'li sayaçlar, spinlock'lar, sık güncellenen atomic'ler için padding uygulayın; birlikte çalışan (aynı thread'in eriştiği) veriyi aynı cache line'da tutup, farklı thread'lerin eriştiği veriyi ayrı cache line'lara ayırın (bu, "false sharing"in tersi olan bilinçli data layout tasarımıdır).
- **Statik analiz ve dinamik araçlardan yararlanın.** ThreadSanitizer (TSan) gibi araçlar, veri yarışlarını (data race) ve yanlış senkronizasyon örüntülerini çalışma zamanında tespit edebilir; lock-free kod için özellikle değerlidir çünkü bu hatalar deterministik değildir, testte tesadüfen hiç tetiklenmeyebilir.
- **Basit tutun, kanıtlayın.** Her yeni lock-free algoritma, formal olarak (en azından titiz elle) doğruluk kanıtı gerektirir: "linearizability" (her işlemin dışarıdan tek bir anlık noktada gerçekleşmiş gibi görünmesi) gibi kavramlarla algoritmanın doğruluğunu tarif edebilmelisiniz. Kanıtlayamıyorsanız muhtemelen kilit kullanmak daha güvenlidir.

## Tespit ve Savunma Perspektifi (Güvenlik Açısı)

Bu konunun güvenlik boyutu, doğrudan "saldırı tekniği" değil, **savunmasız tasarımların nasıl zafiyete dönüştüğünü anlamak**tır:

- **Race condition tabanlı mantık hataları** (TOCTOU — time-of-check to time-of-use — benzeri desenler), yetersiz senkronize edilmiş atomic kullanımıyla ortaya çıkabilir: bir yetki kontrolü ile asıl kullanım arasında, başka bir thread state'i değiştirirse, kontrolün geçersiz hale gelmesi. Savunma: kontrol ve kullanım arasındaki state'i tek bir atomic işlemle (CAS ile) birleştirmek, ya da kritik bölgeyi gerçek bir kilitle korumak.
- **Bellek güvenliği zincirlemesi:** ABA problemi ve yanlış bellek geri kazanımı, use-after-free'ye kadar gidebilir; bu C/C++ gibi bellek güvenli olmayan dillerde ciddi bir exploit yüzeyi oluşturur. Savunma, yukarıda anlatılan hazard pointer/epoch tabanlı reclamation ve mümkünse bellek güvenli dillerin (Rust'ın `Arc`/`Atomic` tipleri, derleme zamanında veri yarışlarını büyük ölçüde engeller) tercih edilmesidir.
- **Tespit stratejisi:** Kod incelemesinde her `memory_order_relaxed` kullanımını "neden yeterli olduğu" açıklanmadan geçirmeyin; her CAS döngüsünü ABA açısından sorgulayın ("bu pointer/değer geri dönüştürülebilir mi?"); yük testlerini gerçek çok çekirdekli donanımda, farklı mimarilerde (x86 nispeten "güçlü" bellek modeline sahiptir, ARM ve POWER daha "zayıf"/gevşek modellidir — x86'da çalışan hatalı kod ARM'da çok daha kolay ortaya çıkar) çalıştırın. TSan/Helgrind gibi dinamik analiz araçlarını CI'a entegre edin.
- **Sistem sertleştirme:** Kritik altyapı bileşenlerinde (örneğin kimlik doğrulama sayaçları, rate-limiter durumları, oturum durumları) lock-free optimizasyonuna sadece ölçülmüş, kanıtlanmış bir performans ihtiyacı varsa başvurun; varsayılan olarak basit ve doğrulanması kolay kilit tabanlı yaklaşımı tercih edin. Performans için doğruluğu feda etmek, güvenlik açısından her zaman kötü bir takastır.

## Sonuç

Lock-free ve wait-free programlama, doğru uygulandığında muazzam ölçeklenebilirlik kazandırır, ama bunun bedeli büyük bilişsel yüktür: atomic işlemler, CAS semantiği, ve özellikle memory ordering modelleri (relaxed, acquire/release, seq_cst) arasındaki farkı hakiki anlamda kavramadan bu alana girmek, görünüşte çalışan ama nadiren ve tahmin edilemez şekilde bozulan kod üretir. En iyi savunma disiplini: varsayılan olarak en güçlü/en basit modeli seçmek, her optimizasyonu ölçüme dayandırmak, ABA ve false sharing gibi bilinen tuzakları sistematik olarak kod incelemesinde aramak, ve mümkün olduğunda tekerleği yeniden icat etmek yerine denenmiş kütüphanelere güvenmektir.
