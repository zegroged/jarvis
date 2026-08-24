# System Call ve Kernel/User Sınırı

## Tanım

Modern bir işletim sistemi, çalışan kodu iki temel ayrıcalık düzleminde işletir: **kernel mode** (çekirdek kipi) ve **user mode** (kullanıcı kipi). Bu ayrım, yazılım dünyasının en temel güvenlik ve kararlılık mekanizmalarından biridir. Kullanıcı programları -- tarayıcınız, metin editörünüz, oyununuz -- user mode'da koşar ve donanıma, belleğe, diğer proseslerin adres uzayına doğrudan erişemez. Donanımla konuşmak, dosya açmak, ağdan veri okumak, bellek ayırmak gibi ayrıcalıklı işlemler yalnızca kernel mode'da yürütülür.

İşte bu iki dünya arasındaki köprü **system call** (sistem çağrısı, kısaca "syscall")'dır. Bir syscall, user mode'daki bir programın "ben bu işlemi kendim yapamam, çekirdeğe rica ediyorum" demesinin yapısal, denetimli yoludur. Kullanıcı programı bir kapıyı çalar, çekirdek kapıyı açar, isteği doğrular, işi yapar ve sonucu geri döndürür. Bu kapı -- **kernel/user sınırı** -- rastgele geçilemeyen, donanım tarafından zorlanan bir güvenlik sınırıdır.

Bu makale, mode geçişinin donanım seviyesinde neden ve nasıl gerçekleştiğini, syscall mekanizmasının iç işleyişini, güvenlik sınırının hangi tehditlere karşı durduğunu ve pratikte yapılan hataları ele alıyor.

## Kök Neden: Neden İki Ayrı Kip Var?

Bu ayrımın var olma sebebini anlamak için tek bir kipin dünyasını düşünelim. Eğer her program donanıma ve tüm belleğe doğrudan erişebilseydi, hatalı yazılmış tek bir uygulama makinenin tamamını çökertebilir; kötü niyetli bir program başka programların şifrelerini bellekten okuyabilir, disk denetleyicisine keyfi komut gönderip diski silebilirdi. Erken dönem işletim sistemlerinin (örneğin klasik MS-DOS) kararsızlığının ve güvenliksizliğinin kök nedeni tam olarak buydu: koruma sınırı yoktu.

Çözüm, güvenilmez kodu güvenilir çekirdekten **donanım seviyesinde** izole etmektir. Neden donanım seviyesinde? Çünkü yazılımla uygulanan bir koruma, o yazılımın kendisi ele geçirildiğinde çöker. Donanım tarafından zorlanan bir sınır ise, CPU'nun kendi elektronik devreleri tarafından her komut çalıştırılırken kontrol edilir ve yazılımla atlatılamaz.

### Ayrıcalık Halkaları (Privilege Rings)

x86 mimarisi bu ayrımı **protection ring** (koruma halkaları) kavramıyla uygular. Donanım dört halka tanımlar: Ring 0'dan Ring 3'e. Ring 0 en ayrıcalıklı seviyedir ve çekirdek burada koşar; Ring 3 en az ayrıcalıklı seviyedir ve kullanıcı programları burada koşar. Aradaki Ring 1 ve Ring 2, pratikte neredeyse hiçbir yaygın işletim sistemi tarafından kullanılmaz -- Linux ve Windows sadece Ring 0 ve Ring 3'ü kullanır. Bunun sebebi taşınabilirliktir: birçok CPU mimarisi (örneğin ARM) yalnızca iki temel seviye sunar, dolayısıyla iki seviyeye dayanan bir tasarım her yerde çalışır.

CPU'nun o an hangi halkada olduğu, bir yazmaçtaki (register) durum bitleriyle takip edilir. Ayrıcalıklı bir komut -- örneğin doğrudan disk denetleyicisine erişen bir I/O komutu ya da sayfa tablosu tabanını değiştiren bir komut -- Ring 3'te çalıştırılmaya kalkışıldığında, CPU bunu donanımsal olarak reddeder ve bir **exception** (istisna, general protection fault türünden) fırlatır. İşte user mode programının "izin verilmeyen" bir şey yapmasını fiziksel olarak imkansız kılan mekanizma budur.

### Bellek İzolasyonu ve Sanal Bellek

Ayrıcalık halkaları hikayenin yarısıdır; diğer yarısı **bellek izolasyonu**dur. CPU'nun **MMU** (Memory Management Unit) adlı birimi, her prosesin gördüğü sanal adresleri fiziksel adreslere çevirir. Her sanal bellek sayfasının, o sayfaya hangi ayrıcalık seviyesinden erişilebileceğini belirten koruma bitleri vardır. Çekirdek belleğine ait sayfalar "yalnızca supervisor" olarak işaretlenir; user mode'daki bir program bu adreslere dokunmaya çalıştığında MMU bir **page fault** üretir.

Bunun neden kritik olduğunu görmek için şu senaryoyu düşünün: iki farklı kullanıcının programı aynı makinede koşuyor. Sanal bellek sayesinde her biri, sanki tüm adres uzayı kendisinindir gibi görür; birinin `0x400000` adresi diğerininkinden tamamen farklı bir fiziksel bölgeye eşlenir. Bu yüzden bir program başkasının belleğini ne okuyabilir ne de bozabilir. Kernel/user sınırının güvenlik değeri, işte bu ayrıcalık halkaları ile bellek izolasyonunun birleşiminden doğar.

## Mode Geçişi Nasıl Çalışır?

Şimdi işin kalbine gelelim: user mode'dan kernel mode'a geçiş tam olarak nasıl olur? Anahtar nokta şudur -- kullanıcı programı çekirdeğin herhangi bir adresine keyfi olarak "atlayamaz". Eğer atlayabilseydi, sınır anlamsız olurdu; kötü niyetli kod doğrudan çekirdeğin ortasındaki bir noktaya sıçrayıp güvenlik kontrollerini baypas ederdi.

Bunun yerine geçiş, yalnızca **önceden tanımlı, denetimli giriş noktaları** üzerinden yapılabilir. Program özel bir CPU komutu çalıştırır; bu komut CPU'yu atomik olarak hem Ring 0'a yükseltir hem de kontrolü çekirdeğin önceden kaydettiği sabit bir giriş adresine aktarır. Kullanıcı, bu giriş adresini değiştiremez ve nereye atlanacağını seçemez. Kapının nerede olduğuna çekirdek karar verir; kullanıcı yalnızca kapıyı çalabilir.

### Trap, Syscall Komutu ve Giriş Noktası

Tarihsel olarak x86'da bu geçiş bir **software interrupt** (yazılım kesmesi) ile yapılırdı -- klasik yöntem `int 0x80` komutuydu. CPU bir kesme numarası görür, **IDT** (Interrupt Descriptor Table) adlı tabloya bakar, o numaraya karşılık gelen çekirdek handler adresini bulur ve oraya kontrolü aktarır. Ancak kesme mekanizması görece yavaştı çünkü çok sayıda tabloya erişip durum kaydetmesi gerekiyordu.

Bu yüzden modern x86-64 işlemciler, syscall'a özel hızlı komutlar sunar: `syscall`/`sysret` (AMD kökenli, 64-bit standart) ve `sysenter`/`sysexit` (Intel kökenli). Bu komutlar, giriş adresini önceden özel yazmaçlara yazılmış değerlerden okur ve kesme tablosuna gitmeden doğrudan çekirdek giriş noktasına dalış yapar. Sonuç, geçişin çok daha az saat çevrimi harcamasıdır.

Geçiş anında donanım ve çekirdek şunları yapmak zorundadır:

1. **Ayrıcalık yükseltme:** CPU Ring 3'ten Ring 0'a geçer.
2. **Yığın değişimi:** User mode yığını (stack) güvenilmezdir; çekirdek kendi güvenli kernel stack'ine geçer. Aksi halde kullanıcı, çekirdeğin yığın verisini manipüle edebilirdi.
3. **Durum kaydı:** Kullanıcı programının yazmaç durumu ve dönüş adresi saklanır ki işlem bitince tam olarak kaldığı yerden devam edebilsin.

### İşin Anlaşması: Syscall Numaraları ve Argümanlar

Peki program hangi işlemi istediğini nasıl söyler? Çekirdek her sistem çağrısına bir **numara** atar (örneğin dosya okuma, yazma, prosess oluşturma her biri ayrı bir tam sayıdır). Program, istediği çağrının numarasını belirli bir yazmaca (x86-64 Linux'ta genellikle `rax`), argümanları da diğer yazmaçlara (`rdi`, `rsi`, `rdx` ...) yerleştirir, sonra `syscall` komutunu çalıştırır. Bu "hangi yazmaç neyi taşır" düzenine **calling convention** (çağrı sözleşmesi) denir ve mimariye özgüdür.

Çekirdek giriş noktasında bu numarayı okur, bir **syscall tablosunda** karşılık gelen çekirdek fonksiyonunu bulur, argümanları doğrular ve işi yapar. Dönüş değeri yine bir yazmaç üzerinden kullanıcıya geri verilir. Bu yüzden syscall arayüzü, çekirdek ile kullanıcı arasındaki değişmez bir sözleşmedir -- Linux çekirdeğinin "user space'i asla bozma" ilkesinin temelinde de bu numaraların ve davranışların sürümler arası sabit kalması yatar.

### libc Katmanı: Neden Doğrudan Syscall Yazmazsınız

Uygulama geliştiricisi olarak neredeyse hiçbir zaman `syscall` komutunu elle yazmazsınız. Bunun yerine C standart kütüphanesi (glibc, musl gibi) size `read()`, `write()`, `open()` gibi normal fonksiyonlar sunar. Bu **wrapper** fonksiyonlar, argümanları doğru yazmaçlara yerleştirir, syscall komutunu çalıştırır, dönen değeri kontrol eder ve hata durumunda `errno` gibi bir mekanizmayla size anlaşılır bir hata bildirir.

Bu katman neden var? Çünkü ham syscall arayüzü mimariye ve işletim sistemine göre değişir; libc bu farklılıkları soyutlayarak taşınabilir kod yazmanızı sağlar. Ayrıca `printf` gibi üst seviye fonksiyonlar, performans için verinizi bir **buffer**'da biriktirip tek bir `write` syscall'ında toplar -- her karakter için ayrı syscall yapmak feci yavaş olurdu.

## Somut Örnek: Bir `read()` Çağrısının Yolculuğu

Diyelim ki programınız bir dosyadan veri okuyor ve `read(fd, buf, 100)` çağırıyor. Perde arkasında olanlar şunlardır:

1. Programınız user mode'da, Ring 3'te koşuyor. libc'nin `read` wrapper'ı çağrılıyor.
2. Wrapper, `read` syscall numarasını `rax`'e; dosya tanıtıcısı `fd`'yi, tampon adresi `buf`'ı ve okunacak bayt sayısı `100`'ü ilgili argüman yazmaçlarına yerleştiriyor.
3. `syscall` komutu çalışıyor. CPU atomik olarak Ring 0'a yükseliyor, kernel stack'ine geçiyor ve çekirdeğin syscall giriş noktasına dalıyor.
4. Çekirdek `rax`'teki numaraya bakıp syscall tablosundan `sys_read` fonksiyonunu buluyor. **Kritik adım:** Çekirdek, `buf` adresinin gerçekten bu prosese ait geçerli, yazılabilir bir user-space adresi olduğunu doğruluyor. Bu doğrulama olmazsa, kötü niyetli bir program `buf` olarak bir çekirdek adresi geçirip çekirdeğin verisini üzerine yazdırabilirdi.
5. Çekirdek diskten (ya da dosya sistemi önbelleğinden) veriyi okuyup kullanıcının tamponuna kopyalıyor.
6. `sysret` komutu çalışıyor; CPU Ring 3'e iniyor, kullanıcı yığınına dönüyor ve okunan bayt sayısı dönüş değeri olarak `read`'in çağrıldığı yere teslim ediliyor.

Bu yolculukta dikkat edilmesi gereken şey, her adımda güvenin **tek yönlü** olmasıdır: çekirdek kullanıcıya güvenmez, kullanıcının verdiği her adresi, her uzunluğu, her tanıtıcıyı yeniden doğrular. Kullanıcı ise çekirdeğe güvenmek zorundadır çünkü başka seçeneği yoktur.

## Güvenlik Sınırının Anlamı ve Saldırı Yüzeyi

Kernel/user sınırı bir **güvenlik sınırı** (security boundary / trust boundary)'dır. Bu, sınırın iki tarafının farklı güven seviyelerinde olduğu anlamına gelir. Çekirdeğin bakış açısından, user space'ten gelen her şey potansiyel olarak düşmancadır. Bu tavsiye değil, tasarım ilkesidir.

### Neden Syscall Arayüzü Değerli Bir Saldırı Hedefidir

İronik olarak, güvenliği sağlayan syscall arayüzü aynı zamanda en tehlikeli saldırı yüzeyidir. Sebebi mantıksal: user mode'daki kod izole edilmiştir ve tek başına makineyi ele geçiremez; ele geçirmek için Ring 0'a, yani çekirdeğe ulaşmak gerekir. Çekirdeğe user space'ten ulaşmanın yasal tek yolu ise syscall arayüzüdür. Dolayısıyla ayrıcalık yükseltme (**privilege escalation**) saldırıları neredeyse her zaman bir syscall içindeki bir hatayı istismar eder.

Klasik hata sınıfları şunlardır:

- **Yetersiz argüman doğrulaması:** Çekirdek, kullanıcının verdiği bir işaretçiyi ya da uzunluğu doğru doğrulamazsa, kullanıcı çekirdek belleğini okutabilir veya yazdırabilir. Kullanıcı işaretçilerine güvenli erişim için çekirdekler özel yardımcı fonksiyonlar (Linux'ta `copy_from_user`/`copy_to_user` ailesi) kullanır; bir syscall bu fonksiyonları atlayıp ham işaretçiye dokunursa açık doğar.

- **TOCTOU (time-of-check to time-of-use) / race condition:** Çekirdek bir argümanı doğruladıktan sonra ama kullanmadan önce, başka bir thread o argümanı değiştirirse, doğrulama geçersiz kalır. Örneğin çekirdek bir kullanıcı işaretçisini doğrular, sonra ikinci kez okur; kötü niyetli bir thread arada değeri değiştirmiş olabilir. Bu yüzden değerler genellikle bir kez çekirdek belleğine kopyalanıp orada kullanılır.

- **Integer overflow ve boyut hesabı hataları:** Kullanıcının verdiği bir uzunluk değeri, çekirdekte bir toplama ya da çarpma sırasında taşarsa, çekirdek beklediğinden çok daha küçük bir tampon ayırıp ardından üzerine taşacak şekilde yazabilir -- bu bir kernel-space **buffer overflow**'a dönüşür.

### Sınırı Güçlendiren Ek Katmanlar

Zamanla sadece "sınır var" demek yetmediği anlaşıldı; sınırın her iki yanı da sertleştirildi. Örneğin modern CPU'lar **SMEP** (Supervisor Mode Execution Prevention) ve **SMAP** (Supervisor Mode Access Prevention) gibi özellikler sunar. SMEP, çekirdeğin yanlışlıkla kullanıcı belleğindeki kodu çalıştırmasını donanımsal olarak engeller; klasik bir istismar tekniği, çekirdeği kandırıp kullanıcı belleğine yerleştirilmiş kötü koda atlatmaktı, SMEP bunu kırar. SMAP ise çekirdeğin kullanıcı belleğine bilinçsizce erişmesini engelleyerek belirli açık sınıflarını zorlaştırır.

Ayrıca **seccomp** gibi mekanizmalar, bir prosesin yapabileceği syscall'ların kümesini daraltır. Fikir şudur: bir web sunucusu prosesinin diske keyfi yazma ya da yeni prosess oluşturma yeteneğine ihtiyacı yoksa, bu syscall'ları o prosese kapatırsanız, proses ele geçirilse bile saldırganın elindeki koz küçülür. Bu, **saldırı yüzeyini azaltma** (attack surface reduction) ilkesinin somut uygulamasıdır. Konteyner teknolojileri (Docker gibi) bu tür kısıtlamaları yoğun kullanır.

## Doğru Kullanım ve Tuzaklar

### Syscall'lar Pahalıdır: Sıklığı Yönetin

Bir mode geçişi bedavaya gelmez. CPU ayrıcalık değiştirir, yığın değiştirir, durum kaydeder; ayrıca modern işlemcilerde geçiş, dallanma tahmini ve önbellek durumu üzerinde dolaylı maliyetler yaratır. Bu maliyet, Spectre/Meltdown sınıfı donanım açıklarına karşı eklenen yazılım azaltmalarıyla (mitigation) bazı sistemlerde daha da arttı, çünkü geçişte ek güvenlik işlemleri yapılması gerekti.

Pratik sonuç: **syscall sayısını azaltmak performansın temel kaldıracıdır.** Bir dosyayı bayt bayt okumak yerine büyük bloklar halinde okuyun. Çok sayıda soket işlemini `epoll`/`io_uring` gibi toplu mekanizmalarla birleştirin. `printf` gibi tamponlanmış fonksiyonların neden var olduğunu hatırlayın -- iş yükünüzü tek bir syscall'a toplarlar. Bir programı profillerken beklenmedik yavaşlık görüyorsanız, ilk bakılacak yerlerden biri gereksiz sık yapılan syscall'lardır; `strace` gibi bir araç, bir prosesin yaptığı syscall'ları listeleyerek bu israfı ortaya çıkarır.

### Hata Kodlarını Her Zaman Kontrol Edin

Syscall'lar başarısız olabilir -- dosya yoktur, izin reddedilir, disk dolar. libc wrapper'ları hatayı genellikle negatif ya da `-1` dönüş değeriyle ve `errno` üzerinden bildirir. Yaygın ve tehlikeli bir tuzak, dönüş değerini kontrol etmeden devam etmektir. Örneğin `write`'ın döndürdüğü değer, istediğinizden **az** olabilir (kısmi yazma); bunu görmezden gelirseniz sessizce veri kaybedersiniz. Doğru yaklaşım, kısa okuma/yazmalara karşı döngü kurmak ve `errno` değerine göre anlamlı davranmaktır.

### EINTR ve Kesilen Syscall'lar

Bloklayan bir syscall (örneğin uzun bir `read`), proses bir sinyal aldığında yarıda kesilebilir ve `EINTR` hatasıyla döner. Bu bir "gerçek" hata değildir; syscall'ı yeniden denemeniz gerektiğinin işaretidir. Bu davranıştan habersiz yazılan kod, sinyal geldiğinde açıklanamaz şekilde başarısız olur. Deneyimli geliştiriciler bloklayan çağrıları `EINTR` durumunda tekrar deneyen bir sarmalayıcı içine alır.

## Yaygın Hatalar

Geliştiricilerin bu konuda en sık düştüğü yanlışlar şunlardır:

- **Syscall'ı "sıradan bir fonksiyon çağrısı" sanmak.** Bir syscall, normal fonksiyon çağrısından çok daha pahalıdır ve bloklayabilir. Bir syscall'ı sıkı bir döngünün içine gömerek programı yavaşlatmak çok yaygın bir hatadır.

- **Dönüş değerini ve `errno`'yu görmezden gelmek.** Özellikle kısmi okuma/yazma ve `EINTR` durumları göz ardı edilince nadir ama ciddi hatalar doğar -- bu tür hatalar test ortamında görünmeyip üretimde patlar.

- **Kernel/user sınırını "kod içi güvenlik kontrolü" ile karıştırmak.** User mode'da yaptığınız bir yetki kontrolünün güvenlik değeri, çekirdeğin uyguladığı sınırınkiyle aynı değildir. Kullanıcı, kendi user-space kodunu değiştirebilir; gerçek yaptırım çekirdekte veya güvenilir bir sunucuda olmalıdır. Bu, "istemci tarafı doğrulamaya güvenme" ilkesinin sistem seviyesindeki karşılığıdır.

- **Çekirdeğe geçen verinin çekirdek tarafından yeniden doğrulandığını unutmak** ve kendi tarafında hiç doğrulama yapmayan çekirdek/sürücü kodu yazmak. Sürücü ya da çekirdek modülü geliştiriyorsanız, aksi ispat edilene kadar kullanıcıdan gelen her işaretçi ve boyut düşmancadır.

- **Konteyner ya da sandbox içinde çalışırken kapalı bir syscall'a takılmak.** seccomp profili belirli syscall'ları engellediğinde, program anlaşılması güç şekilde çöker. Bu tür ortamlarda hata ayıklarken, kapatılmış bir syscall'ın engellenmiş olup olmadığını akla getirmek zaman kazandırır.

## En İyi Pratikler

En sağlıklı zihinsel model şudur: kernel/user sınırı, kod ile donanım arasındaki bir **güven duvarı**dır ve tüm tasarımınız bu duvarın maliyetli ama güvenli bir kapıyla geçildiği varsayımına dayanmalıdır.

- **Syscall'ları toplu yapın.** I/O'yu büyük bloklar halinde gerçekleştirin, tamponlama kullanın, mümkünse `epoll`/`io_uring` gibi çok sayıda işlemi tek geçişte toplayan modern arayüzleri tercih edin. Amaç, aynı işi daha az mode geçişiyle yapmaktır.

- **Her syscall'ın başarısız olabileceğini varsayın.** Dönüş değerini her zaman kontrol edin, `errno`'yu doğru yorumlayın, kısmi işlemlere ve `EINTR`'ye karşı döngü kurun. Bu, sağlam sistem yazılımının pazarlık kabul etmez kuralıdır.

- **Güvenliği doğru katmana yerleştirin.** Gerçek yaptırım her zaman güvenilir tarafta -- çekirdekte ya da sunucuda -- olmalıdır. User-space kontrolleri kolaylık içindir, güvenlik için değil.

- **Ayrıcalığı en aza indirin.** Prosesinizin gerçekten ihtiyaç duyduğu syscall'ların ötesindeki yetenekleri seccomp ile kısıtlayın; en az ayrıcalık (least privilege) ilkesini uygulayın. Bir proses ne kadar az şey yapabiliyorsa, ele geçirildiğinde o kadar az zarar verir.

- **Çekirdek tarafında kod yazıyorsanız, kullanıcı verisine asla doğrudan dokunmayın.** Güvenli kopyalama fonksiyonlarını kullanın, boyut hesaplarında taşmaya (integer overflow) karşı dikkatli olun ve TOCTOU race condition'larından kaçınmak için doğrulanan değeri bir kez kopyalayıp öyle kullanın.

- **Davranışı gözlemleyin.** `strace` gibi araçlarla bir programın hangi syscall'ları, hangi sıklıkta yaptığını görmek; hem performans israfını hem de beklenmedik davranışları ortaya çıkarır. Sınırın öbür tarafında ne olduğunu görebilmek, hem hata ayıklamanın hem de optimizasyonun anahtarıdır.

Özetle: kernel/user sınırı, modern bilgisayarların hem kararlı hem güvenli olmasının temelidir. Donanımın zorladığı bu ayrım sayesinde hatalı bir program tüm makineyi çökertemez, kötü niyetli bir program komşusunun sırlarını çalamaz. System call ise bu sınırı geçmenin tek meşru, denetimli yoludur -- pahalı ama güvenli bir kapı. İyi sistem yazılımı yazmak, bu kapının hem maliyetini saygıyla karşılamak hem de güven modelini asla ihlal etmemek demektir.
