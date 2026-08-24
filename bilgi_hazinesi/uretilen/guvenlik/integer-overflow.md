# Integer Overflow Zafiyetleri: Boyut Hesabı, Küçük Tampon ve Off-by-One

## Tanım

Integer overflow (tam sayı taşması), bir aritmetik işlemin sonucunun kullanılan tam sayı tipinin temsil edebileceği aralığın dışına çıkması durumudur. Bilgisayarlar tam sayıları sabit sayıda bit ile tutar. Örneğin 32 bitlik işaretsiz (unsigned) bir tam sayı yalnızca `0` ile `4294967295` (yani `2^32 - 1`) arasındaki değerleri saklayabilir. Bu üst sınırı aşan bir işlem yapıldığında sonuç "sarar" (wrap-around); değer sıfıra veya beklenmedik küçük bir sayıya döner. İşaretli (signed) tam sayılarda ise taşma daha da tehlikelidir, çünkü büyük bir pozitif değer aniden negatif bir değere dönüşebilir.

Integer overflow'un kendisi teknik olarak yalnızca yanlış bir sayısal sonuçtur. Onu bir güvenlik zafiyetine çeviren şey, bu yanlış sayının genellikle bir **boyut hesabı** içinde kullanılmasıdır: bir bellek tamponunun (buffer) ne kadar büyük ayrılacağını, bir döngünün kaç kez döneceğini ya da bir kopyalama işleminin kaç bayt taşıyacağını belirleyen hesaplarda. Yanlış hesaplanan boyut, çoğu zaman **çok küçük bir tampon** ayrılmasına ve ardından bu tamponun sınırlarının dışına yazılmasına, yani klasik bir buffer overflow'a yol açar. Bu makale özellikle bu üçlüye odaklanıyor: boyut hesabındaki taşma, sonucunda oluşan küçük tampon ve bunların yakın akrabası olan off-by-one hataları.

## Kök Neden: Neden Böyle Oluyor

Integer overflow'un kökeninde donanımın ve düşük seviyeli dillerin çalışma biçimi yatar. Bir CPU, tam sayı toplama işlemini modüler aritmetik ile yapar. `n` bitlik bir kayıtta yapılan tüm işlemler aslında `mod 2^n` aritmetiğidir. Yani işlemci `4294967295 + 1` işlemini yaptığında, matematiksel sonuç olan `4294967296` sayısı 32 bite sığmadığı için en anlamlı bit atılır ve geriye `0` kalır. Donanım burada hiçbir hata sinyali üretmez; C ve C++ gibi diller de işaretsiz taşmayı iyi tanımlanmış (well-defined) "sarma" davranışı olarak kabul eder. Dolayısıyla program çökmeye ya da uyarı vermek yerine sessizce yanlış bir değerle çalışmaya devam eder. İşte bu sessizlik, zafiyetin temelidir: sistem "her şey yolunda" sanır.

Bu davranışın güvenlik açığına dönüşmesinin asıl nedeni, programcının zihnindeki model ile makinenin gerçekliği arasındaki uçurumdur. Programcı `boyut = eleman_sayisi * eleman_boyutu` yazdığında matematiksel çarpımı düşünür. Makine ise bu çarpımı sabit genişlikte bir tam sayıda yapar ve sonuç taşarsa küçük bir değer üretir. Programcı devamında `malloc(boyut)` çağırır ve beklediğinden çok daha küçük bir bellek bloğu alır; ama döngü hâlâ *gerçek* eleman sayısı kadar dönerek bu küçük bloğun dışına veri yazar. Kritik nokta şudur: taşma bir yerde olur (hesap), sonuçları başka bir yerde patlar (kopyalama). Bu mesafe, hatayı gözle görmeyi ve kod incelemesinde yakalamayı zorlaştırır.

İşaretli/işaretsiz karışıklığı da kök nedenlerin önemli bir parçasıdır. C dilinde bir işaretli ile bir işaretsiz değer aynı ifadede kullanıldığında, işaretli değer örtük olarak işaretsize dönüştürülür (usual arithmetic conversions). Bu yüzden negatif bir uzunluk değeri (`-1`) aniden çok büyük bir işaretsiz sayıya (`0xFFFFFFFF`) dönüşür. Bir uzunluk kontrolü `if (len > MAX)` şeklinde yazılmışsa ve `len` işaretsizse, saldırganın gönderdiği negatif görünümlü bir değer bu kontrolü atlatabilir ya da tam tersine kontrolü geçtikten sonra `memcpy`'de dev bir kopyalamaya yol açabilir.

## Somut Örnekler

### Örnek 1: Çarpımda taşan boyut hesabı

En yaygın kalıp, eleman sayısı ile eleman boyutunun çarpılmasıdır:

```c
void* dizi_olustur(uint32_t eleman_sayisi) {
    // Her eleman 16 bayt olsun
    uint32_t boyut = eleman_sayisi * 16;   // TAŞMA RISKI
    char* tampon = malloc(boyut);
    if (!tampon) return NULL;

    for (uint32_t i = 0; i < eleman_sayisi; i++) {
        memcpy(tampon + i * 16, kaynak(i), 16);  // TAMPON DIŞINA YAZMA
    }
    return tampon;
}
```

Saldırgan `eleman_sayisi` değerini `0x10000000` (268.435.456) gönderirse, `0x10000000 * 16 = 0x100000000` olur. Bu değer 32 bite sığmaz; en üst bit atılınca `boyut` sıfıra döner (ya da başka değerlerle küçük bir sayıya). `malloc(0)` çoğu implementasyonda çok küçük ama geçerli bir işaretçi döndürür. Ardından döngü tam `268 milyon` kez dönerek bu minicik tamponun çok ötesine veri yazar. Sonuç: heap tabanlı büyük bir bellek bozulması. Buradaki asıl mesele, ayrılan boyut ile kullanılan boyutun *farklı* hesaplardan gelmesidir; ayırma taştı, kullanım taşmadı.

### Örnek 2: Toplamada taşan boyut ve başlık payı

Ağ protokollerinde sık görülen bir kalıp, bir başlık boyutu ile veri boyutunun toplanmasıdır:

```c
uint16_t veri_uzunlugu = paketten_oku();       // saldırgan kontrolünde
uint16_t toplam = veri_uzunlugu + BASLIK_BOYUTU; // 16 bit toplam, TAŞMA RISKI
char* tampon = malloc(toplam);
memcpy(tampon, baslik, BASLIK_BOYUTU);
memcpy(tampon + BASLIK_BOYUTU, veri, veri_uzunlugu);
```

`veri_uzunlugu` değeri `65530` ve `BASLIK_BOYUTU` `16` ise, `65530 + 16 = 65546` olur; bu `2^16 = 65536` sınırını aşar ve `toplam` `10` değerine sarar. `malloc(10)` küçük bir tampon verir, ama ikinci `memcpy` `veri_uzunlugu` kadar (yani 65530 bayt) kopyalar ve tamponu kilometrelerce aşar. Bu kalıp özellikle ayrıştırıcılarda (parser) tehlikelidir; çünkü uzunluk alanı doğrudan ağdan, yani saldırgandan gelir.

### Örnek 3: Off-by-one — bir baytlık ölümcül fark

Off-by-one, döngü sınırlarında ya da boyut hesabında tam bir birimlik sapmadır. En klasik biçimi, sonlandırıcı null bayt (`\0`) için yer ayrılmamasıdır:

```c
char* kopyala(const char* girdi) {
    size_t uzunluk = strlen(girdi);
    char* tampon = malloc(uzunluk);      // HATA: +1 unutuldu
    strcpy(tampon, girdi);               // null bayt tamponun 1 dışına yazılır
    return tampon;
}
```

`strlen` sonlandırıcı null'ı saymaz. `strcpy` ise onu yazar. Dolayısıyla `uzunluk` bayt ayrılıp `uzunluk + 1` bayt yazılır; tam olarak bir bayt taşar. Bu tek baytlık taşma zararsız görünebilir, ama heap üzerinde bir sonraki bellek yığınının metadata'sının en düşük değerli baytını bozarak (null byte overflow) sofistike sömürülere kapı açabilir.

Off-by-one'ın döngü biçimi de aynı derecede yaygındır:

```c
char tampon[64];
for (size_t i = 0; i <= 64; i++) {   // HATA: <= yerine < olmalı
    tampon[i] = veri[i];             // i == 64'te dizi dışına yazma
}
```

`<=` operatörü döngüyü `i = 64` değerinde bir kez fazla döndürür ve `tampon[64]`, geçerli son indeks olan `tampon[63]`'ün bir dışına yazar. Buradaki kök neden dizilerin sıfırdan indekslenmesi ile insan sezgisinin (1'den sayma) çarpışmasıdır.

## Sömürü/İstismar Mantığı

Saldırganın bakış açısından integer overflow, doğrudan kod çalıştırmaya değil, önce **bellek bozulmasına** giden bir yoldur. Saldırgan hedefi şudur: boyut hesabına giren bir girdiyi (uzunluk alanı, eleman sayısı, indeks) kontrol edip, ayrılan tampon ile yazılan veri arasında bir uyumsuzluk yaratmak.

Tipik bir istismar zinciri şöyle işler. Önce saldırgan, boyut hesabına giren değeri taşma sınırına yakın bir yere iter; amaç, `malloc`'a küçük bir değer, kopyalama döngüsüne ise büyük bir değer geçirmektir. Bu iki değer arasındaki fark, saldırganın komşu bellek üzerine yazabileceği alanın büyüklüğüdür. Heap üzerinde bu yazma, bitişik bir nesnenin işaretçilerini, uzunluk alanlarını ya da bellek yöneticisinin (allocator) tuttuğu metadata'yı hedef alır. Off-by-one durumunda ise saldırgan, tek baytlık kontrolü heap chunk başlığının anlamlı bir bitine (örneğin bir boyut alanının en düşük baytına) denk getirmeye çalışır; buna literatürde "poison null byte" ya da benzeri teknikler denir.

İstismarın gücü, saldırganın taşan yazma üzerindeki *kontrol derecesine* bağlıdır. Eğer hem yazılacak veri hem de taşma miktarı saldırgan kontrolündeyse, bir fonksiyon işaretçisini, bir C++ vtable girişini ya da bir dönüş adresini (stack tabanlı ise) hedefleyerek kontrol akışını ele geçirmek mümkün olabilir. Modern sistemlerde ASLR ve DEP/NX gibi korumalar bunu zorlaştırdığı için, saldırganlar genellikle önce bir bilgi sızıntısı (info leak) ile bellek düzenini öğrenip sonra taşmayı hedefli biçimde kullanır. Boyut taşmalarının cazip olmasının bir nedeni de, geçerli görünen küçük girdilerle tetiklenebilmeleri ve giriş doğrulama filtrelerini kolayca geçebilmeleridir; çünkü gönderilen değer aslında "makul" bir sayıdır, taşma iç hesapta gerçekleşir.

## Savunma Mantığı

Savunmanın temel ilkesi, taşmanın *sonucunu* değil *kendisini* engellemektir. Bir boyut hesabı yapmadan önce ya da yaparken taşma olup olmayacağını kontrol etmek gerekir.

**Kontrolleri işlemden önce yap.** `boyut = a * b` yazıp sonra `boyut`'u kontrol etmek işe yaramaz, çünkü kontrol ettiğiniz değer zaten taşmış olabilir. Doğru yaklaşım, çarpma yapmadan önce sınırı test etmektir:

```c
if (eleman_sayisi > SIZE_MAX / eleman_boyutu) {
    // taşma olurdu, reddet
    return HATA;
}
size_t boyut = eleman_sayisi * eleman_boyutu;  // artık güvenli
```

Burada bölme kullanılmasının nedeni önemlidir: `SIZE_MAX / eleman_boyutu`, çarpımın taşmadan tutabileceği en büyük `eleman_sayisi` değerini verir. Bunu aşan her giriş taşmaya yol açacağından baştan reddedilir. Bölme, taşma üretemez (sıfıra bölme dışında), bu yüzden güvenli bir ön kontrol aracıdır.

**Taşma güvenli fonksiyonlar ve dil desteği kullan.** Modern derleyiciler taşmayı yakalayan yerleşik fonksiyonlar sunar; örneğin GCC/Clang'de `__builtin_mul_overflow` ve `__builtin_add_overflow`, işlemin taşıp taşmadığını bir bayrakla döndürür ve sonucu da güvenli biçimde verir. Bu tür fonksiyonlar hem daha okunaklıdır hem de derleyicinin donanım taşma bayraklarını kullanmasına izin verir. Bellek ayırırken `malloc(a * b)` yerine, çarpımı içeride güvenli yapan `calloc(a, b)` tercih edilmelidir; `calloc` standarda göre çarpım taşarsa `NULL` döndürmekle yükümlüdür.

**Tip seçimini bilinçli yap.** Boyutlar için daima işaretsiz ve platform genişliğinde olan `size_t` tipini kullanmak, 32/64 bit karışıklığını azaltır. Uzunlukları asla işaretli `int` içinde taşımayın; ağdan gelen negatif görünümlü değerlerin işaretsize dönüşüp dev sayılar üretmesi böyle engellenir. İşaretli/işaretsiz karşılaştırmalarında derleyici uyarılarını (`-Wsign-compare` gibi) açık tutmak, gözden kaçan dönüşümleri erkenden yakalar.

**Sonlandırıcı bayt ve sınır için daima pay bırak.** String kopyalarında `+1`'i ritüel hâline getirin ve `strcpy`/`strcat` yerine hedef boyutu bilen `snprintf` ya da açıkça sınır alan fonksiyonları kullanın. Döngü sınırlarında `<=` yerine `<` kullanımını bir alışkanlık olarak benimseyin ve dizi boyutunu sabit kodlamak yerine `sizeof(dizi)/sizeof(dizi[0])` gibi türetilmiş ifadelerle hesaplayın.

**Katmanlı savunma ekle.** Derleyici tabanlı sanitizer'lar (örneğin UndefinedBehaviorSanitizer'ın integer overflow kontrolü ve AddressSanitizer'ın bellek sınırı kontrolü) test ve fuzzing aşamasında bu hataları çalışma anında yakalar. Stack canary, ASLR ve DEP/NX gibi işletim sistemi ve derleyici korumaları, bir taşma yine de oluşursa istismarı zorlaştıran ikincil bariyerlerdir; ama bunlar kök nedeni çözmez, yalnızca sömürüyü pahalılaştırır.

## Yaygın Hatalar

**Taşmayı sonradan kontrol etmek.** En sık görülen yanılgı, `boyut = a * b; if (boyut < a) ...` gibi taşma sonrası kontrollerdir. İşaretsiz taşma için bu bazen işe yarar ama işaretli taşma C/C++'ta tanımsız davranıştır (undefined behavior); derleyici "taşma olamaz" varsayımıyla kontrolü tamamen silebilir. Yani işaretli taşmayı taşma-sonrası test ederek yakalamaya çalışmak, derleyicinin ortadan kaldırdığı bir kontrol yazmaktır.

**İki farklı hesaptan gelen boyutlara güvenmek.** Bir yerde `malloc` için hesaplanan boyut ile başka bir yerde döngü ya da `memcpy` için kullanılan boyutun aynı olduğunu varsaymak tehlikelidir. Bu iki değer bağımsız olarak taşabilir. Ayrılan boyut ile kullanılan boyut mümkün olduğunca *tek bir kaynaktan* türetilmeli ve o kaynak doğrulanmalıdır.

**Küçük tip aralıklarını unutmak.** `uint16_t` ya da `uint8_t` gibi dar tiplerde toplama ve çarpma çok daha erken taşar. Programcı 32 bit düşünürken hesap aslında 16 bitte yapılıyor olabilir; özellikle protokol alanları dar tipler kullandığında bu tuzak sık kurulur. Ara hesapları geniş bir tipe (`size_t`) yükseltmeden yapılan aritmetik, sessiz taşmanın klasik zeminidir.

**Sonlandırıcı null'ı hesaba katmamak.** `strlen` bazlı boyut hesaplarında `+1`'in unutulması, tekrar tekrar ortaya çıkan bir off-by-one kaynağıdır. Aynı şekilde, sabit boyutlu tampona veri kopyalarken null bayt için yer ayırmayı unutmak, "kopyalanan veri tam sığıyor ama sonlandırıcı taşıyor" durumunu yaratır.

**Girdi doğrulamasını yalnızca üst sınırla yapmak.** Bir uzunluğu yalnızca `if (len > MAX)` ile kontrol etmek, `len` işaretliyse ve negatif gelebiliyorsa yetersizdir. Hem alt sınır (negatif olmama) hem üst sınır kontrol edilmelidir; ya da baştan işaretsiz tip kullanılmalıdır.

**Bellek yöneticisinin `malloc(0)` davranışına güvenmek.** Boyut sıfıra taştığında `malloc(0)` bazı platformlarda `NULL`, bazılarında geçerli ama sıfır kullanılabilir baytlık bir işaretçi döndürür. İkinci durum, `NULL` kontrolünü geçip yine de yazmaya izin verdiği için özellikle sinsidir.

## En İyi Pratikler

İyi bir savunma, integer overflow'u bir "istisna" değil, ele alınması gereken normal bir durum olarak görmekten geçer. Aşağıdaki ilkeler bir bütün olarak uygulandığında bu zafiyet sınıfının büyük kısmı ortadan kalkar.

Her boyut hesabını, girdiyi işleyen sınırın (trust boundary) hemen içinde doğrulayın. Ağdan, dosyadan ya da kullanıcıdan gelen her uzunluk ve sayaç değeri, kullanılmadan önce hem alt hem üst sınırıyla test edilmelidir. Doğrulama, hesap yapılmadan önce ve taşma güvenli yöntemlerle yapılmalı; asla "önce hesapla, sonra bak" sırasıyla değil.

Boyut aritmetiği için standart, denenmiş yardımcı fonksiyonlar kullanın: `calloc`, derleyicinin `__builtin_*_overflow` ailesi, ya da projeye özel "checked arithmetic" sarmalayıcıları. Bu fonksiyonların dönüş değerini her zaman kontrol edin; taşma bayrağını görmezden gelmek, kontrolü hiç yazmamakla aynıdır. Ayırma başarısızlığında (`NULL` dönüşünde) işlemi güvenli biçimde sonlandırın.

Bellek işlemlerinde açıkça sınır alan API'leri tercih edin. `strcpy`/`strcat`/`sprintf` gibi sınırsız fonksiyonları kod tabanından kademeli olarak çıkarıp yerlerine hedef tampon boyutunu bilen alternatiflerini koyun. String'lerde sonlandırıcı null için daima bir bayt fazla ayırın ve kopyalama sonrası sonlandırmayı garanti edin.

Diziler ve döngülerde sınır ifadelerini tek bir güvenilir kaynaktan türetin. Tampon boyutunu bir yere, döngü sınırını başka bir yere sabit kodlamak yerine, boyutu `sizeof` ile hesaplayıp döngüde de aynı değeri kullanın; böylece biri değişince diğeri otomatik uyumlu kalır. `<` ve `<=` seçimini her yazışta bilinçli yapın.

Mümkün olan yerde bellek güvenli dilleri ya da soyutlamaları değerlendirin. Rust gibi diller, taşmayı hata ayıklama modunda panik ile yakalar ve dizi erişimlerinde çalışma anında sınır kontrolü yapar; C++ tarafında `std::vector` ve `std::span` gibi tipler ham işaretçi aritmetiğine kıyasla çok daha az taşma yüzeyi sunar. Yeni yazılan kritik bileşenlerde ham `char*` ve manuel boyut hesabı yerine bu soyutlamalar öncelikli olmalıdır.

Son olarak, süreç düzeyinde savunmayı otomatikleştirin. Sürekli entegrasyon (CI) hattında UBSan ve ASan ile derlenmiş testler çalıştırın, protokol ayrıştırıcıları ve girdi işleyen tüm bileşenleri fuzzing'e tabi tutun. Fuzzing, tam olarak bu tür "belirli bir uç değerle taşan" hataları bulmakta insan incelemesinden çok daha etkilidir; çünkü otomatik olarak sınır değerlerini ve devasa sayıları deneyerek gizli taşmaları tetikler. Kod incelemesinde ise her `malloc`, `memcpy` ve sabit boyutlu tampon kullanımını, "buraya giren boyut nereden geliyor ve taşabilir mi?" sorusuyla okuyun. Bu tek soru, integer overflow zafiyetlerinin çoğunu gün ışığına çıkarır.
