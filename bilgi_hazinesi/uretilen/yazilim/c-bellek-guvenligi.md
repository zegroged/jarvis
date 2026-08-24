# C Programlama ve Bellek Güvenliği

C dili, yazıldığı günden bu yana işletim sistemlerinin, gömülü sistemlerin, veritabanlarının ve neredeyse her performans-kritik altyapının temel taşı oldu. Bu gücün bedeli ise açık: C, belleği doğrudan sizin yönetmenize izin verir ve bu izni verirken sizi neredeyse hiç korumaz. Bir Python veya Java programcısı çöp toplayıcının (garbage collector) ve sınır denetimlerinin arkasına saklanabilirken, C programcısı çıplak bir donanım modelinin karşısında tek başınadır. Bu makale, C'de bellek güvenliğinin neden bu kadar kritik olduğunu, hataların kökeninde hangi mekanizmaların yattığını ve modern bir mühendisin bunlarla nasıl başa çıktığını derinlemesine ele alıyor.

## Belleğin C'deki Zihinsel Modeli

Bellek güvenliği hakkında konuşmadan önce, C'nin belleği nasıl gördüğünü doğru anlamak gerekir. C standardı, çalışan bir programın nesnelerini birbirinden farklı **depolama süreleri** (storage duration) olan bölgelere ayırır. Bu ayrım teoride soyuttur ama pratikte tipik bir sisteme şu şekilde yansır:

- **Static/global depolama**: Programın tüm ömrü boyunca yaşayan global ve `static` değişkenler.
- **Automatic depolama (stack)**: Fonksiyon çağrıldığında oluşan, fonksiyondan çıkınca yok olan yerel değişkenler.
- **Allocated depolama (heap)**: `malloc` ailesiyle sizin talebiniz üzerine ayrılan ve `free` ile yine sizin serbest bıraktığınız bellek.

Bu üçlü ayrım rastgele değildir. Stack, çağrı sırasına göre son giren ilk çıkar (LIFO) mantığıyla çalıştığı için son derece hızlıdır: bir fonksiyona girerken stack işaretçisi (stack pointer) birkaç bayt kaydırılır, çıkarken geri alınır. Heap ise böyle bir düzen garantisi vermez; nesneler herhangi bir sırada ayrılıp serbest bırakılabildiği için heap'i yöneten allocator karmaşık defter tutma işleri yapmak zorundadır. İşte bellek hatalarının büyük kısmı, programcının bu iki bölgenin ömür (lifetime) kurallarını karıştırmasından doğar.

### Pointer: Adres mi, Yoksa Fazlası mı?

Bir pointer'ı çoğu kaynak "bir adres tutan değişken" diye tanıtır. Bu tanım işlevsel olarak doğru ama tehlikeli derecede eksiktir. C standardı açısından bir pointer sadece sayısal bir adres değildir; belirli bir **tipe** ve o an geçerli olan bir **nesneye** bağlı, kendine ait kuralları olan bir değerdir. `int *p` ile `char *q` aynı ham adresi gösterse bile, `p` üzerinden okuma 4 bayt (tipik olarak), `q` üzerinden okuma 1 bayt anlamına gelir. Dahası, bir pointer sadece "geçerli bir nesneyi gösteriyor", "tam olarak o nesnenin bir eleman sonrasını gösteriyor" (dizilerde `arr + n` sınır işaretçisi olarak yasaldır) veya "null" olabilir. Bunların dışındaki her durum — serbest bırakılmış belleği gösteren, ömrü bitmiş yerel değişkeni gösteren, hiç ilklendirilmemiş çöp değer taşıyan pointer'lar — tanımsız davranış (undefined behavior) bölgesine girer.

Bu ayrımı vurgulamamın nedeni şu: bellek güvenliğini "adreslerle dikkatli oynamak" olarak düşünürseniz, derleyicinin neden beklemediğiniz optimizasyonlar yaptığını hiçbir zaman anlayamazsınız. Pointer'ları soyut, kurallı nesneler olarak düşünmek, sonraki her şeyin anahtarıdır.

## Tanımsız Davranış (Undefined Behavior): Kök Neden

Bellek güvenliği tartışmalarının kalbinde **undefined behavior** (UB) kavramı yatar. Yeni başlayanların en büyük yanılgısı UB'yi "program çöker" veya "yanlış sonuç verir" sanmaktır. Gerçek çok daha rahatsız edicidir: UB, C standardının o program için **hiçbir gereksinim koymadığı** durumdur. Derleyici o noktada istediğini yapabilir — çökme, sessizce yanlış çalışma, doğru görünme, hatta o kod yolunu tamamen silme.

### Neden UB Diye Bir Şey Var?

Buradaki "neden" sorusu kritiktir çünkü UB kasıtlı bir tasarım kararıdır, bir kaza değildir. C, 1970'lerin sonundan itibaren çok farklı donanım mimarilerinde (farklı bayt sıralamaları, farklı word boyutları, farklı hizalama kuralları olan makineler) taşınabilir olmayı hedefledi. Standart, her mimaride pahalıya mal olacak denetimleri zorunlu kılsaydı, C bu makinelerin çoğunda yavaşlar ve rekabet edemezdi. Bu yüzden standart, "programcı bu kuralı çiğnemeyecek" varsayımını yaptı ve karşılığında derleyiciye çok agresif optimizasyon özgürlüğü tanıdı.

Modern derleyiciler bu özgürlüğü sonuna kadar kullanır. Örneğin derleyici, "bu pointer dereference edildiğine göre null olamaz" diye akıl yürütüp, sonrasında yazdığınız `if (p == NULL)` kontrolünü tamamen kaldırabilir. Kodunuzda mantıken var olan bir güvenlik kontrolü, UB varsayımı yüzünden makine kodundan silinir. Bu yüzden UB sadece "bug" değildir; güvenlik açıklarının doğrudan kaynağıdır.

### Signed Integer Overflow Örneği

UB'nin sinsiliğini gösteren klasik bir örnek signed tamsayı taşmasıdır. `unsigned` taşma tanımlıdır (modulo 2^N sarmalanır) ama `signed` taşma UB'dir. Bir programcı şöyle bir sınır kontrolü yazabilir:

```c
// TEHLIKELI: len + offset signed taşarsa UB
if (len + offset < buffer_size) {
    // buffer'a yaz
}
```

`len + offset` signed tamsayı taşması yaparsa, matematiksel olarak beklediğiniz negatif/büyük sonuç yerine derleyicinin varsaydığı "taşma olmaz" mantığı devreye girer ve kontrol beklenmedik biçimde geçebilir. Doğru yaklaşım, taşmayı denklemin karşı tarafına almaktır: `offset < buffer_size - len` gibi taşamayacak bir forma sokmak veya en baştan unsigned tiplerle ve açık taşma denetimiyle çalışmaktır.

## malloc / free: Heap Yönetiminin İç Mantığı

Heap bölgesini yöneten `malloc`, `calloc`, `realloc` ve `free` fonksiyonları, bir **allocator** kütüphanesinin arayüzüdür. Bu fonksiyonların nasıl çalıştığını kavramak, ilgili hataların neden bu kadar tehlikeli olduğunu açıklar.

### Allocator Ne Yapar?

`malloc(n)` çağırdığınızda, allocator size en az `n` bayt bitişik bellek verir ve size sadece o bloğun başlangıç adresini döndürür. Ama allocator arka planda çok daha fazlasını tutar: her bloğun ne kadar büyük olduğunu, serbest mi kullanımda mı olduğunu, komşu bloklarla ilişkisini kaydeder. Tipik allocator'lar bu **metadata**'yı (defter kayıtlarını) bloğun hemen öncesindeki birkaç bayta yerleştirir. İşte bu tasarım, bir bug'ın neden geniş yıkıma yol açtığını açıklar: eğer bir blokta sınırın ötesine yazarsanız, çoğu zaman komşu bloğun metadata'sını bozarsınız ve çökme, yazma anında değil, çok sonra başka bir `malloc` veya `free` çağrısında ortaya çıkar. Hatanın belirtisiyle nedeni zaman ve mekan olarak birbirinden koptuğu için bu tür bug'lar meşhur biçimde zor izlenir.

`free(p)` çağırdığınızda, o bloğu tekrar kullanılabilir listeye geri verirsiniz — ama bellekteki baytlar hemen silinmez ve `p`'nin taşıdığı adres hâlâ aynıdır. Bu ayrıntı, birazdan göreceğimiz use-after-free ve double-free hatalarının temelidir.

### Doğru Kullanım İskeleti

```c
size_t n = count * sizeof(*arr);   // taşma riski: aşağıya bakın
int *arr = malloc(n);
if (arr == NULL) {
    // Ayırma başarısız oldu. ASLA atlanmamalı.
    return -1;
}
// ... arr kullanılır ...
free(arr);
arr = NULL;   // dangling pointer'ı etkisiz hale getir
```

Bu kısacık örnekte üç kritik davranış var. Birincisi, `malloc`'un dönüş değeri **her zaman** kontrol edilir; bellek dolu bir sistemde `NULL` dönebilir ve bunu görmezden gelmek doğrudan null pointer dereference'e yol açar. İkincisi, boyut hesabında `count * sizeof(*arr)` çarpımı taşabilir; büyük `count` değerlerinde bu çarpım sarmalanıp beklenenden küçük bir blok ayrılmasına, ardından buffer overflow'a yol açar. Güvenli kod bu çarpımı taşmaya karşı denetler (`calloc` bu denetimi sizin için yapmayı hedefler, bu yüzden dizi ayırmada tercih edilir). Üçüncüsü, `free`'den sonra pointer `NULL`'a çekilir; bu, aynı pointer'ın yanlışlıkla tekrar kullanılmasını veya tekrar serbest bırakılmasını görece zararsız hale getirir çünkü `free(NULL)` tanımlı ve güvenlidir.

## Yaygın Bellek Hataları ve Kök Nedenleri

Şimdi C'de en sık görülen ve en yıkıcı olan bellek hatası sınıflarını, her birinin neden ortaya çıktığına odaklanarak inceleyelim.

### Buffer Overflow (Tampon Taşması)

En bilinen bellek hatasıdır: bir tamponun (dizi, `malloc`'lu blok) sınırlarının ötesine okuma veya yazma. Kök neden, C'nin diziler için sınır denetimi yapmamasıdır — bu bilinçli bir performans kararıdır. `arr[i]` ifadesi aslında `*(arr + i)` demektir ve derleyici `i`'nin geçerli aralıkta olup olmadığını kontrol etmez; sadece adres aritmetiği yapıp o adrese erişir.

Stack üzerinde bir yerel diziyi taşırsanız, komşudaki dönüş adresini (return address) veya kaydedilmiş register değerlerini ezersiniz. Klasik "stack smashing" saldırıları tam olarak bunu sömürür: saldırgan girdisiyle dönüş adresini kendi kontrol ettiği bir adresle değiştirip programın akışını ele geçirir. Modern sistemler bu saldırıyı zorlaştırmak için **stack canary** (dönüş adresinin önüne konan ve fonksiyon dönerken doğrulanan gizli değer), **ASLR** (Address Space Layout Randomization, bellek düzenini rastgeleleştirme) ve **NX/DEP** (yazılabilir sayfaların çalıştırılamaz olması) gibi savunmalar kullanır. Ama bunlar hafifletmedir, çözüm değildir; kök nedeni ortadan kaldırmazlar.

Klasik tuzak, standart kütüphanenin sınır-farkında olmayan fonksiyonlarıdır. `gets` fonksiyonu girdiyi hiçbir sınır bilgisi olmadan okuduğu için o kadar tehlikelidir ki modern standartlardan tamamen çıkarılmıştır. `strcpy`, `strcat`, `sprintf` gibi fonksiyonlar da hedef tamponun boyutunu bilmedikleri için dikkatsiz kullanımda taşmaya davetiye çıkarır. Bunların yerine boyut alan `snprintf` gibi muadilleri tercih edilmelidir — ve bu muadillerde bile dönüş değerini ve sonlandırıcı null bayt davranışını doğru yorumlamak gerekir.

### Use-After-Free (Serbest Bırakma Sonrası Kullanım)

`free(p)` çağırdıktan sonra `p` üzerinden erişmeye devam etmek use-after-free'dir. Kök neden yukarıda anlattığımız gerçektir: `free`, pointer'ın değerini değiştirmez, sadece bloğu allocator'a iade eder. `p` hâlâ eski adresi taşır ama o adres artık başka bir amaç için yeniden ayrılmış olabilir.

Bunun neden bir güvenlik felaketi olduğu şudur: serbest bırakılan blok başka bir `malloc` tarafından tekrar kullanıldığında, artık iki farklı kod yolu aynı belleği farklı amaçlarla kullanıyordur. Saldırgan bu durumu, serbest bırakılan bloğun yerine kendi kontrol ettiği veriyi yerleştirecek şekilde manipüle edebilirse (heap grooming/spraying teknikleriyle), eski `p` üzerinden yapılan bir yazma saldırganın verisini bozmaya veya bir fonksiyon işaretçisini ele geçirmeye dönüşebilir. Use-after-free, günümüzde tarayıcı ve çekirdek istismarlarının en verimli sınıflarından biridir.

En sinsi varyantı, birden fazla pointer'ın aynı bloğu göstermesidir: bir kopya üzerinden `free` çağrılır, diğer kopya kullanılmaya devam eder. Sahiplik (ownership) modelinin belirsiz olduğu kodlarda bu çok kolay olur.

### Double-Free (Çift Serbest Bırakma)

Aynı bloğu iki kez `free` etmek de UB'dir ve use-after-free ile akrabadır. Neden tehlikelidir? Çünkü ilk `free`, bloğu allocator'ın serbest listesine ekler; ikinci `free` aynı bloğu tekrar eklemeye çalışınca allocator'ın iç veri yapıları (çoğunlukla bağlı listeler) tutarsız hale gelir. Saldırgan, bozulan bu serbest liste yapısını istismar ederek allocator'ı kandırıp keyfi bir adrese yazma yeteneği elde edebilir. Çözüm basit bir alışkanlıktır: `free`'den sonra pointer'ı `NULL`'a çekmek, çünkü `free(NULL)` güvenlidir ve ikinci çağrı zararsızlaşır.

### Uninitialized Memory (İlklendirilmemiş Bellek)

`malloc` ayrılan belleği sıfırlamaz; içinde önceki kullanımdan kalan çöp baytlar bulunur (`calloc` ise sıfırlar, farkı budur). İlklendirilmemiş bir yerel değişkeni veya `malloc`'lu bloğu okumak UB'dir. Görünürde sonuç bazen "rastgele değer" gibi durur, ama tehlike ikilidir. Birincisi, çöp değerin bir pointer olarak yorumlanıp dereference edilmesi çökmeye yol açar. İkincisi, bir güvenlik açısı vardır: eski verinin (belki başka bir kullanıcının parolası, kriptografik anahtarı) sıfırlanmadan dışarıya sızması, klasik **information disclosure** açıklarının kaynağıdır. Bu yüzden hassas veriyi tutan tamponlar kullanımdan sonra açıkça sıfırlanmalıdır — ve derleyicinin "nasıl olsa kullanılmıyor" diye bu sıfırlamayı optimize edip silmemesine dikkat edilmelidir.

### Memory Leak (Bellek Sızıntısı)

Ayrılan ama hiç serbest bırakılmayan bellek sızıntıdır. Doğrudan bir güvenlik açığı gibi görünmese de, uzun ömürlü süreçlerde (sunucular, gömülü sistemler) sızıntı belleği yavaşça tüketip sonunda ayırmaların başarısız olmasına ve hizmet reddine (denial of service) yol açar. Kök neden neredeyse her zaman belirsiz sahipliktir: bir bloğu kimin serbest bırakacağı kodun tasarımında net değildir. Hata yollarında (error path) sızıntı özellikle yaygındır; bir fonksiyonun ortasında hata dönerken, o ana kadar ayrılmış blokların temizlenmesi unutulur.

### Type Confusion ve Strict Aliasing İhlalleri

Daha ileri bir hata sınıfı, aynı belleği uyumsuz tipler üzerinden yorumlamaktır. C'nin **strict aliasing** kuralı, kabaca, birbiriyle uyumsuz tiplere ait pointer'ların aynı nesneyi göstermeyeceğini varsayar (`char*` ve `unsigned char*` bu kuralın istisnalarıdır). Bu varsayım derleyiciye değerleri register'da tutup yeniden okumamak gibi optimizasyonlar yapma izni verir. Bir `float`'ı `int*` üzerinden okuma gibi kestirmelere başvurursanız, kod bazı derleyicilerde çalışır, optimizasyon açılınca bozulur. Tipler arası bit-düzeyi dönüşüm gerektiğinde doğru araç `memcpy` ile baytları kopyalamaktır; derleyiciler bu deyimi tanır ve genellikle sıfır maliyetli koda çevirir.

## En İyi Pratikler: Savunma Katmanları

Bellek güvenliği tek bir hamleyle değil, üst üste binen savunma katmanlarıyla sağlanır. Aşağıdakiler, deneyimli C ekiplerinin fiilen uyguladığı disiplinlerdir.

### 1. Sahiplik (Ownership) Modelini Açıkça Belirle

Her `malloc`'lu blok için "bunu kim serbest bırakacak?" sorusunun tek ve net bir cevabı olmalıdır. Bu, C'de olmayan bir dil özelliğini disiplinle taklit etmektir. Bir fonksiyon bellek döndürüyorsa, dokümantasyonu çağıranın onu serbest bırakması gerektiğini açıkça söylemeli; bir yapı (struct) bir pointer'a sahipse, o yapıyı yok eden fonksiyon o pointer'ı da serbest bırakmalıdır. Sahiplik belirsizse, double-free ve leak kaçınılmazdır. Modern C++ akıllı pointer'ları (`unique_ptr`, `shared_ptr`) tam da bu problemi çözmek için vardır; saf C'de bu sözleşmeyi kod düzeni ve isimlendirme kuralıyla kendiniz taşımak zorundasınız.

### 2. Her Ayırmanın Dönüşünü ve Her Boyut Hesabını Denetle

`malloc`/`realloc` dönüşünü kontrol etmek pazarlık konusu değildir. Özellikle `realloc` bir tuzak barındırır: başarısız olduğunda `NULL` döner ama **eski blok hâlâ geçerlidir**. `p = realloc(p, n);` yazarsanız ve `realloc` başarısız olursa, `p`'yi `NULL` ile ezerek eski bloğa erişimi kaybedersiniz — bu bir leak'tir. Doğru desen, dönüşü geçici bir değişkende tutup başarıdan sonra atamaktır. Boyut hesaplarındaki çarpma ve toplama taşmaları da bilinçli olarak denetlenmelidir.

### 3. Derleyici ve Statik Analiz Uyarılarını Ciddiye Al

Derleyicileri yüksek uyarı seviyesinde çalıştırmak (yaygın olarak `-Wall -Wextra` bayrakları ve uyarıları hataya çeviren seçenekler) neredeyse ücretsiz bir savunma katmanıdır. Derleyici, ilklendirilmemiş değişken kullanımı, tip uyumsuzlukları ve şüpheli işaretçi dönüşümleri gibi birçok sorunu daha derleme aşamasında yakalar. Bunun üstüne statik analizörler, kod hiç çalışmadan olası null dereference ve leak yollarını izleyebilir. Bu araçların spesifik bayrak isimleri derleyici sürümüne göre değişebildiği için, projenizin derleyicisinin kendi dokümantasyonuna bakmanızı öneririm.

### 4. Çalışma Zamanı Dedektörleriyle Test Et

Statik analiz her şeyi yakalayamaz; bazı hatalar ancak belirli girdilerle çalışırken ortaya çıkar. Burada **sanitizer** araçları devreye girer. AddressSanitizer (ASan), programı buffer overflow, use-after-free ve double-free anında yakalayacak biçimde enstrümante eder ve hatayı belirtinin çok sonrasında değil, tam gerçekleştiği noktada bildirir. MemorySanitizer ilklendirilmemiş okumaları, UndefinedBehaviorSanitizer çeşitli UB türlerini avlar. Bunları **fuzzing** (rastgele/mutasyona uğramış girdilerle programı otomatik bombardımana tutma) ile birleştirmek, insan gözünün asla düşünmeyeceği kenar durumlarını ortaya çıkaran son derece etkili bir kombinasyondur. Ayrıca Valgrind gibi araçlar, programı yeniden derlemeye gerek kalmadan bellek hatalarını ve sızıntıları izleyebilir; enstrümantasyona dayalı sanitizer'lara göre daha yavaş ama bazı senaryolarda daha pratiktir.

### 5. Güvenli Deyimleri Varsayılan Yap

Kod tabanınızda tehlikeli fonksiyonları güvenli muadilleriyle değiştirmek bir alışkanlık haline gelmelidir. Sınır-farkında string ve bellek fonksiyonlarını (boyut parametresi alan varyantları) tercih edin; sabit boyutlu tampon yerine dinamik büyüyen yapılar kullanın; hassas veriyi kullanımdan sonra temizleyin. Bir tampon boyutunu her zaman `sizeof` ile türetin, sabit sayı olarak elle yazmayın — çünkü tampon boyutu değişince elle yazılmış sabit güncellenmeyi unutulur ve taşma açığı doğar.

### 6. Karmaşıklığı Azalt, Yüzey Alanını Küçült

Belki de en derin ilke budur: bellek güvenliği bir kod kalitesi ve tasarım meselesidir. İç içe geçmiş manuel bellek yönetimi, karmaşık pointer aritmetiği ve dağınık sahiplik ne kadar çoksa, hata olasılığı o kadar yüksektir. İyi C mühendisleri belleği tek bir yerde ayırıp tek bir yerde serbest bırakan, ham işaretçi aritmetiğini soyutlayan, girdi doğrulamayı sınırlarda toplayan yapılar kurar. Bazen en doğru karar, kritik bir bileşeni bellek-güvenli bir dilde (örneğin Rust) yeniden yazmak veya en riskli parçaları izole etmektir. C'nin gücünü kullanmak, onun tehlikelerini de sorumlulukla taşımak demektir.

## Sonuç

C'de bellek güvenliği, tek tek kuralları ezberlemekle değil, altta yatan modeli — depolama süreleri, pointer'ların kurallı doğası ve tanımsız davranışın derleyiciye tanıdığı özgürlük — gerçekten kavramakla başlar. Buffer overflow, use-after-free, double-free, uninitialized read ve leak gibi hataların hepsi, aslında aynı temel gerçekliğin farklı yüzleridir: C size belleği çıplak biçimde emanet eder ve o emaneti korumak tümüyle sizin sorumluluğunuzdadır. Modern bir mühendis bu sorumluluğu, açık sahiplik modelleri, disiplinli hata denetimi, derleyici uyarıları, statik analiz, sanitizer'lar ve fuzzing'den oluşan üst üste binen katmanlarla taşır. Hiçbir tek araç tam güvenlik vermez; ama bu katmanlar birlikte, C'nin ödün vermeyen performansını makul bir güvenlikle birleştirmeyi mümkün kılar.
