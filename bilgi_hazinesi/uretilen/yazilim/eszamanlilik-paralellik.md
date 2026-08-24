# Eşzamanlılık ve Paralellik

## Tanım: İki Kavram, İki Ayrı Problem

Eşzamanlılık (concurrency) ve paralellik (parallelism) sık sık aynı anlamdaymış gibi kullanılır, ama aslında farklı iki sorunu tarif ederler. Bu ayrımı netleştirmeden gerisi havada kalır.

**Eşzamanlılık**, birden fazla işi *aynı zaman diliminde ilerletebilme* becerisidir. Burada anahtar kelime "ilerletebilme"dir; işlerin fiziksel olarak *tam olarak aynı anda* çalışması şart değildir. Tek çekirdekli bir işlemci bile eşzamanlı olabilir: işletim sistemi işleri hızla değiştirerek (context switch) hepsini biraz biraz ilerletir. Eşzamanlılık bir *yapı* ve *tasarım* meselesidir; programınızı birbirinden bağımsız ilerleyebilen parçalara bölmekle ilgilidir.

**Paralellik** ise birden fazla işin *fiziksel olarak aynı anda* yürütülmesidir. Bu, ancak birden fazla hesaplama biriminiz (çok çekirdekli CPU, GPU, ayrı makineler) varsa mümkündür. Paralellik bir *yürütme* meselesidir.

Rob Pike'ın meşhur özdeyişi bu ayrımı iyi anlatır: "Eşzamanlılık aynı anda birçok şeyle *ilgilenmektir*; paralellik aynı anda birçok şeyi *yapmaktır*." Bir program eşzamanlı olarak tasarlanmış olabilir ama tek çekirdekte paralellik olmadan çalışabilir; ya da paralel donanımda çalışıp gerçek hız kazancı elde edebilir. Eşzamanlı tasarım, paralelliği *mümkün kılar* ama garanti etmez.

Bu ayrımın pratik sonucu şudur: I/O ağırlıklı işlerde (ağ istekleri, disk, veritabanı) genellikle paralelliğe değil eşzamanlılığa ihtiyacınız vardır, çünkü darboğaz CPU değil beklemedir. CPU ağırlıklı işlerde (görüntü işleme, sayısal hesap) ise gerçek paralellik gerekir, çünkü darboğaz hesaplamanın kendisidir.

## Kök Neden: Neden Bu Kadar Zor?

Eşzamanlı programlamanın zorluğu, insanın zihninde programı *sıralı* (sequential) düşünmesinden kaynaklanır. Kod yazarken satırların yukarıdan aşağıya, tahmin edilebilir bir sırayla çalışacağını varsayarız. Eşzamanlılık bu varsayımı yıkar: iki iş parçası birbirinin arasına girebilir (interleaving), ve olası araya-girme sıralamalarının sayısı işlem sayısıyla üstel olarak patlar.

Asıl kök neden **paylaşılan değiştirilebilir durumdur** (shared mutable state). İki bağımsız yürütme akışı aynı bellek bölgesini okuyup yazdığında, sonucun ne olacağı zamanlamaya (timing) bağlı hale gelir. Zamanlama ise işletim sistemi zamanlayıcısına, CPU yüküne, cache durumuna bağlıdır; yani deterministik değildir. Deterministik olmayan bir sistemde hata ayıklamak neredeyse imkânsızdır çünkü hata her seferinde tekrarlanmaz.

Bir başka derin neden **bellek görünürlüğüdür** (memory visibility). Modern CPU'lar ve derleyiciler performans için talimatları yeniden sıralar (reordering) ve her çekirdeğin kendi cache'i vardır. Bir çekirdekte yazdığınız bir değer, başka bir çekirdekte hemen görünmeyebilir. Yani "değişkeni güncelledim" demek, "diğer thread bu güncellemeyi görecek" demek değildir. Bu yüzden dilin sunduğu **memory model** ve senkronizasyon primitifleri kritiktir; onlar olmadan kodunuz tek makinede bile yanlış sonuç üretir.

## Üç Model: Thread, Async, Mesaj Geçişi

Eşzamanlılığı ifade etmenin üç temel yaklaşımı vardır. Her biri farklı bir zihinsel modele ve farklı maliyetlere dayanır.

### Thread (İş Parçacığı) Modeli

Thread, işletim sisteminin zamanlayabildiği en küçük yürütme birimidir. Aynı process içindeki thread'ler bellek adres alanını *paylaşır*; bu paylaşım hem güçlü hem tehlikelidir. Güçlüdür çünkü thread'ler arası veri paylaşımı için ekstra bir mekanizma gerekmez, değişkene erişmek yeterlidir. Tehlikelidir çünkü tam da bu paylaşım race condition'ların kaynağıdır.

Thread'ler **preemptive** (kesintili) zamanlanır: işletim sistemi herhangi bir anda, hatta bir talimatın ortasında bile thread'i durdurup başkasına geçebilir. Bu, programcının kontrolünde olmadığı için, kritik bölgelerin (critical section) açıkça korunması gerekir.

Thread'lerin maliyeti önemlidir. Her OS thread'i genellikle megabayt mertebesinde bir stack ayırır ve context switch, kernel'e giriş çıkış gerektirdiği için ucuz değildir. Bu yüzden on binlerce eşzamanlı bağlantıyı OS thread başına bir thread ile karşılamak (thread-per-connection) ölçeklenmez; bu, C10K probleminin özüdür.

### Async / Olay Döngüsü Modeli

Async model, bekleme sürelerini verimli kullanmak için doğdu. Fikir şudur: bir iş I/O için beklerken (örneğin ağdan cevap gelmesini beklerken) o bekleme boşa harcanmasın, aynı thread başka işi ilerletsin. Bunun kalbinde bir **event loop** (olay döngüsü) vardır: hazır olan işleri sırayla çalıştırır, bir iş "beklemeye" girdiğinde onu askıya alır ve sıradaki hazır işe geçer.

Buradaki kritik fark, zamanlamanın **cooperative** (işbirlikçi) olmasıdır. İş parçası, ancak açık bir bekleme noktasında (`await`, `yield`) kontrolü geri verir. Yani thread'lerdeki gibi rastgele bir anda kesilmez. Bu, bazı senkronizasyon sorunlarını hafifletir ama yeni bir tuzak getirir: eğer bir async görev uzun süren CPU-yoğun bir iş yaparsa ve hiç `await` etmezse, tüm event loop'u bloke eder ve diğer her şey durur. Bu yüzden async dünyasında "event loop'u bloklamamak" temel kuraldır.

Async'in en büyük avantajı hafifliğidir. Bir async görev (coroutine/future/task) sadece birkaç kilobayt bellek tutar, OS thread'i tutmaz. Böylece tek bir thread üzerinde on binlerce eşzamanlı bağlantı ilerletilebilir. Bu, I/O ağırlıklı sunucular için idealdir. Ancak async paralellik değildir: tek event loop tek çekirdek kullanır. Gerçek paralellik için birden fazla event loop'u birden fazla çekirdekte çalıştırmanız gerekir.

Async'in gizli bir maliyeti de "function coloring" denen olgudur: bir fonksiyon async olduğunda, onu çağıran zincir de genellikle async olmak zorunda kalır. Bu, kod tabanına bulaşan yapısal bir kısıttır ve senkron ile asenkron dünyaları köprülemek çoğu zaman sancılıdır.

### Mesaj Geçişi Modeli

Üçüncü yol, paylaşılan durumdan tamamen kaçınmaktır. Mesaj geçişinde (message passing) bağımsız yürütme birimleri belleği paylaşmaz; birbirlerine **mesaj** göndererek haberleşir. Her birim kendi özel durumunu tutar ve bu duruma sadece kendisi dokunur. Dışarıdan gelen istekler mesaj olarak kuyruğa girer ve tek tek işlenir.

Bunun kök mantığı sağlamdır: race condition'ın kaynağı paylaşılan değiştirilebilir durumsa, o durumu paylaşmayı bırakırsanız o sınıf hataları kökten yok edersiniz. Erlang'ın "actor" modeli ve Go'nun "channel" ile CSP (Communicating Sequential Processes) yaklaşımı bu felsefeye dayanır. Go topluluğunun sözü bunu özetler: "Belleği paylaşarak iletişim kurmayın; iletişim kurarak belleği paylaşın."

Mesaj geçişi kilit (lock) ihtiyacını büyük ölçüde ortadan kaldırır ve sistemi dağıtık hale getirmeyi kolaylaştırır (mesajlar makine sınırlarını aşabilir). Bedeli ise şudur: veri kopyalanır veya sahiplik devredilir, bu da bazı senaryolarda ek maliyet getirir; ve tasarımı doğru kurmak, senkron bir zihinden farklı düşünmeyi gerektirir. Ayrıca kuyruklar sınırsız büyürse (unbounded), tüketici üreticiye yetişemediğinde bellek şişer; bu yüzden geri basınç (backpressure) mekanizması gerekir.

## Somut Örnek: Bir Race Condition Nasıl Doğar?

Kavramları somutlaştıralım. İki thread'in ortak bir sayaç değişkenini bin kez artırdığını düşünün. Sezgisel beklenti, sonucun iki bin olmasıdır. Gerçekte çoğu zaman iki binden küçük çıkar. Neden?

Çünkü `sayac = sayac + 1` gibi tek satırlık masum bir işlem, makine seviyesinde tek adım değildir; en az üç adımdır:

1. Belleğinden `sayac` değerini oku (örneğin 41),
2. Bu değere 1 ekle (42),
3. Sonucu belleğe geri yaz (42).

Şimdi iki thread'in araya girmesini düşünün. Thread A değeri 41 olarak okur. Tam bu anda zamanlayıcı A'yı durdurup B'yi çalıştırır. B de 41 okur, 42 yapar, 42 yazar. Sonra A kaldığı yerden devam eder: elinde hâlâ eski değer olan 41 vardır, ona 1 ekler, 42 yazar. İki artırma yapıldı ama sonuç 43 değil 42 oldu; bir artırma **kayboldu**. Buna "lost update" denir.

Bu hatanın sinsiliği, çoğu zaman *doğru* sonuç vermesidir. Araya-girme her seferinde tam o kötü anda olmaz. Test ortamında bin defa çalışır, üretimde yük altında bozulur. İşte eşzamanlılık hatalarını bu kadar korkutucu yapan şey budur: deterministik olmadıkları için üretilemez (non-reproducible) ve gözden kaçar.

Çözüm, üç adımın **atomik** (bölünemez) yapılmasıdır: ya bir kilit ile kritik bölgeyi koruyarak, ya donanımın sunduğu atomik komutlarla (compare-and-swap gibi), ya da bu değişkeni tek bir sahibe emanet edip diğerlerinin ona sadece mesajla erişmesini sağlayarak.

## Kilitler ve Deadlock

En yaygın senkronizasyon aracı **mutex**tir (mutual exclusion). Mutex bir bayrak gibidir: bir thread onu kilitler, kritik bölgeye girer, çıkınca serbest bırakır. Aynı anda yalnızca bir thread kilidi tutabildiği için kritik bölge korunur. Bu basit görünür ama iki ciddi tuzak barındırır.

Birincisi **performans**tır. Kilit, tanımı gereği paralelliği *engeller*. Kilit tuttuğunuz süre boyunca diğer thread'ler bekler. Kritik bölgeniz ne kadar büyükse, seri (serial) çalışan kısım o kadar büyür ve Amdahl Yasası'nın acımasız matematiği devreye girer: programın seri kısmı, elde edebileceğiniz maksimum hızlanmaya kesin bir tavan koyar. Yüzde onu seri olan bir program, sonsuz çekirdekle bile en fazla on kat hızlanabilir. Bu yüzden kilit tutulan süre mümkün olduğunca kısa tutulmalıdır.

İkincisi **deadlock**tır (kilitlenme). Deadlock, iki veya daha fazla thread'in birbirinin tuttuğu kilidi beklemesiyle oluşan ve sonsuza dek süren bir bekleme durumudur. Klasik senaryo: Thread A, X kilidini tutuyor ve Y'yi bekliyor; Thread B, Y kilidini tutuyor ve X'i bekliyor. İkisi de karşısındakinin bırakmasını bekler, hiçbiri bırakmaz; sistem donar.

Deadlock'un oluşması için dört koşulun (Coffman koşulları) aynı anda sağlanması gerekir: karşılıklı dışlama (mutual exclusion), tut-ve-bekle (hold and wait), kesintisizlik (no preemption; kilit zorla alınamaz) ve döngüsel bekleme (circular wait). Bu koşullardan herhangi *birini* kırmak deadlock'u imkânsız kılar.

Pratikte en etkili ve en çok kullanılan yöntem **döngüsel beklemeyi kırmaktır**: tüm kilitleri her yerde *aynı sıralamada* alın. Eğer her thread önce X'i sonra Y'yi almak zorundaysa, döngüsel bekleme oluşamaz, dolayısıyla deadlock da oluşamaz. Bu, disiplin gerektiren ama son derece güvenilir bir kuraldır. Bir başka yöntem, kilit almak için zaman aşımı (timeout) kullanmak ve alınamazsa geri çekilip yeniden denemektir; bu tut-ve-bekle koşulunu zayıflatır.

Deadlock'un daha az bilinen akrabaları da vardır. **Livelock**, thread'lerin kilitlenmemesi ama sürekli birbirine yol vermeye çalışıp hiçbirinin ilerleyememesidir (dar koridorda iki kişinin aynı yöne adım atıp durması gibi). **Starvation** (açlık), bir thread'in kilidi hep başkalarına kaptırıp asla sıra alamamasıdır; genellikle adil olmayan (unfair) zamanlama veya öncelik kaynaklıdır.

## Yaygın Hatalar

**Kilit almadan paylaşılan değişkene erişmek.** En temel hata. "Sadece okuyorum, yazmıyorum, sorun olmaz" düşüncesi yanlıştır; başka bir thread yazarken okumak yarım (torn) değer okumaya veya bellek görünürlüğü sorunlarına yol açar. Paylaşılan değiştirilebilir duruma her erişim senkronize olmalıdır.

**volatile ile atomikliği karıştırmak.** Birçok dilde `volatile` yalnızca *görünürlüğü* garanti eder (değeri her seferinde bellekten oku), *atomikliği* değil. `sayac++` volatile bir değişkende bile hâlâ üç adımdır ve hâlâ race condition'a açıktır. Görünürlük ayrı, atomiklik ayrı problemdir.

**Kilidi geniş tutmak.** Tüm fonksiyonu tek bir dev kilit altına almak "güvenli" hissettirir ama paralelliği öldürür ve deadlock riskini artırır. Kilit sadece gerçek kritik bölgeyi, mümkün olan en kısa süre kapsamalıdır.

**Event loop'u bloklamak.** Async kodda senkron ve uzun süren bir çağrı yapmak (bloklu dosya okuma, ağır CPU hesabı, `sleep`) tüm event loop'u dondurur ve binlerce bağlantıyı aynı anda felç eder. CPU-yoğun işler ayrı bir thread havuzuna veya process'e taşınmalıdır.

**Double-checked locking'i yanlış kurmak.** Performans için kilidi atlamaya çalışan bu meşhur desen, memory model doğru anlaşılmadan yazıldığında sessizce bozulur; yarım kurulmuş bir nesne başka thread'e görünebilir. Bu tür "akıllı" optimizasyonlar, dilin garantilerini tam bilmeden yapılmamalıdır.

**Kaynağı kilit altında beklemek.** Bir kilidi tutarken başka bir kilit beklemek, ağ çağrısı yapmak veya kullanıcı girdisi beklemek deadlock ve uzun bekleme için davetiyedir. Kilit altında yalnızca hızlı, yerel, deterministik iş yapılmalıdır.

## En İyi Pratikler

**Önce paylaşılan durumu ortadan kaldırmayı düşünün.** En güvenli kilit, hiç ihtiyaç duymadığınız kilittir. Değişmezlik (immutability) ve mesaj geçişi, bir sınıf hatayı tasarımla yok eder. Veri değiştirilemezse, onu paylaşmak tamamen güvenlidir çünkü kimse değiştiremez. Mümkün olan her yerde durumu tek bir sahibe kapatın.

**Doğru modeli işe göre seçin.** Bu, en kritik mühendislik kararıdır ve şu sezgiyle özetlenebilir:

- İş **I/O ağırlıklıysa** (çok sayıda ağ/disk bağlantısı, çoğu zaman beklemede) **async** modeli genellikle en verimlisidir; on binlerce bağlantıyı az kaynakla ilerletir.
- İş **CPU ağırlıklıysa** (yoğun hesap) gerçek **paralellik** gerekir; işi çekirdek sayısı kadar parçaya bölüp ayrı thread'lerde veya process'lerde çalıştırın. Global yorumlayıcı kilidi (GIL) olan dillerde CPU paralelliği için thread yerine ayrı process'lere yönelmek gerekebilir.
- Sistem **birçok bağımsız, durumlu aktörden** oluşuyorsa veya dağıtık olacaksa **mesaj geçişi / actor** modeli en temiz ölçeklenir.
- Basit, sınırlı sayıda arka plan işi için sade **thread + havuz (thread pool)** yeterlidir; her iş için yeni thread açmak yerine sabit boyutlu bir havuz kullanın.

**Yüksek seviye soyutlamaları tercih edin.** Ham thread ve ham mutex ile uğraşmak yerine, dilin sunduğu daha güvenli yapıları kullanın: thread-safe kuyruklar, atomik tipler, thread havuzları, yapılandırılmış eşzamanlılık (structured concurrency), immutable koleksiyonlar. Bu soyutlamalar hataların büyük kısmını sizin yerinize önler.

**Kilit sıralamasını bir kural haline getirin.** Birden fazla kilit almanız gerekiyorsa, tüm kod tabanında tek bir global sıralama tanımlayın ve buna istisnasız uyun. Bu, deadlock'a karşı en güvenilir korumadır.

**Yapılandırılmış eşzamanlılık uygulayın.** Başlattığınız her eşzamanlı işin yaşam süresini net bir kapsama (scope) bağlayın; kapsam bitmeden içindeki tüm işler bitsin veya iptal edilsin. Bu, "başıboş" (leaked) görevleri, unutulmuş hataları ve kaynak sızıntılarını önler. Bir işin başladığını ama kimsenin bitmesini beklemediği durumdan kaçının.

**Geri basıncı (backpressure) tasarıma dahil edin.** Üretici tüketiciden hızlıysa, sınırsız kuyruk belleği tüketip sistemi çökertir. Sınırlı (bounded) kuyruklar kullanın ve kuyruk dolduğunda üreticiyi yavaşlatın. Sağlıklı bir sistem, aşırı yükte çökmek yerine nazikçe yavaşlamalıdır.

**Test etmenin sınırlarını kabul edin.** Eşzamanlılık hataları deterministik olmadığı için normal testlerle güvenilir biçimde yakalanamaz. Yükü artırın, zamanlamayı stres altında test edin, mümkünse yarış-dedektörü (race detector) ve statik analiz araçları kullanın. Ama en güçlü savunma, hatayı imkânsız kılan tasarımdır; testle yakalanan hata, tasarımla önlenmiş hatadan her zaman daha pahalıdır.

**Ölçmeden optimize etmeyin.** Kilit çekişmesi (lock contention) gerçek bir darboğaz olmadan kilitsiz (lock-free) veriyapılarına atlamak, karmaşıklığı fırlatır ve yeni hatalar doğurur. Önce profilleyin, gerçek darboğazı bulun, sonra o noktaya odaklanın. Eşzamanlı kodda "erken optimizasyon" her yerdekinden daha tehlikelidir çünkü doğruluğu (correctness) riske atar.

## Kapanış

Eşzamanlılık, modern yazılımın kaçınılmaz bir gerçeğidir; çok çekirdekli işlemciler ve ağ üzerinden çalışan sistemler bunu zorunlu kılar. Ama karmaşıklığının kök nedeni tek bir yerde toplanır: paylaşılan değiştirilebilir durum ile deterministik olmayan zamanlamanın birleşimi. Thread, async ve mesaj geçişi, bu sorunla başa çıkmanın üç farklı stratejisidir ve hiçbiri her derde deva değildir. Usta mühendis, problemin şeklini (I/O mu, CPU mu, dağıtık mı) doğru okur, ona uygun modeli seçer, paylaşılan durumu mümkün olduğunca yok eder, ve kalan senkronizasyonu disiplinli kurallarla yönetir. En iyi eşzamanlı kod, en akıllı kilit hilelerini içeren değil, kilide en az ihtiyaç duyacak şekilde tasarlanmış olandır.
