# Objective-C Bellek Güvenliği ve Legacy iOS Kod Tabanı Analizi

## Giriş ve Bağlam

Modern iOS geliştirme Swift ile anılsa da, büyük kurumsal iOS kod tabanlarının çekirdeği hâlâ önemli ölçüde **Objective-C** ile yazılmıştır. Bankacılık uygulamaları, uzun ömürlü SDK'lar, medya oynatıcılar ve on yıldan eski ürünler; içlerinde manuel bellek yönetimi, dinamik mesajlaşma (message passing) ve C ile iç içe geçmiş kod barındırır. Bu kod tabanları güvenlik denetimi ve bakım açısından kendine özgü bir sınıf oluşturur: Swift'in derleyici-garantili güvenlik ağının çoğu burada geçerli değildir.

Bu makale, Objective-C'nin bellek modelini **mekanizma düzeyinde** anlamayı, legacy kodda karşılaşılan tipik güvenlik açığı sınıflarını tanımayı ve bunlara karşı **tespit ile savunma** kurmayı amaçlar. Amaç istismar reçetesi değil; kök nedeni kavramak ve denetim/hardening yeteneği kazanmaktır.

## Objective-C Bellek Modelinin Temelleri

### Nesne yerleşimi ve `isa` işaretçisi

Objective-C nesneleri, C `struct`'larının üzerine kurulu heap tahsisleridir. Her nesnenin ilk alanı, sınıfını gösteren **`isa`** işaretçisidir. Mesaj gönderimi (`[obj method]`), derleme zamanında `objc_msgSend(obj, @selector(method))` çağrısına dönüşür. `objc_msgSend`, `obj`'nin `isa`'sından sınıfı bulur, o sınıfın metot tablosunda (dispatch table) selector'ü arar ve bulunan IMP (implementation) işaretçisine dallanır.

Bu tasarımın güvenlik açısından iki kritik sonucu vardır:

1. **Metot çözümü çalışma zamanında (runtime) yapılır.** Bir nesnenin hangi kodu çalıştıracağı statik olarak sabit değildir; `isa`'ya ve sınıf hiyerarşisine bağlıdır.
2. **`nil`'e mesaj göndermek güvenlidir ve sessizdir.** `objc_msgSend`, alıcı `nil` ise hiçbir şey yapmadan sıfır/`nil` döndürür. Bu, birçok hatayı gizler; bir zincirin ortasında beklenmedik `nil`, çökme yerine "sessiz yanlış davranış" üretir.

### Referans sayımı: retain / release / autorelease

Objective-C'nin bellek yönetimi **referans sayımına (reference counting)** dayanır. Her nesnenin bir retain count'u vardır:

- `retain` → sayacı bir artırır (sahiplik talep etme).
- `release` → sayacı bir azaltır. Sayaç sıfıra düşünce `dealloc` çağrılır ve bellek serbest bırakılır.
- `autorelease` → nesneyi mevcut **autorelease pool**'a ekler; havuz boşaltılınca (genellikle run loop turunun sonunda) bir `release` uygulanır.

Bu modelin temel kuralı **sahiplik (ownership)** ilkesidir: `alloc`, `new`, `copy`, `mutableCopy` ile veya `retain` ile bir nesnenin sahibi olursun ve dengeleyecek bir `release`/`autorelease` borçlusun olursun. Sahibi olmadığın (örneğin bir "convenience constructor"dan aldığın) nesneyi elde tutmak istiyorsan onu `retain` etmen gerekir.

## MRC ve ARC: İki Dünya

### MRR (Manual Retain-Release / MRC)

ARC öncesi kodda geliştirici her `retain`/`release`'i elle yazar. Kök hata kaynağı burada matematikseldir: retain ve release çağrılarının **her yolda dengelenmesi** gerekir. Erken `return`'ler, exception'lar, döngüler ve iç içe koşullar dengesizlik üretir.

### ARC (Automatic Reference Counting)

ARC bir garbage collector değildir; **derleyicinin** kaynak kodun sahiplik semantiğini analiz edip `retain`/`release`/`autorelease` çağrılarını derleme zamanında otomatik enjekte etmesidir. Runtime davranışı MRC ile aynıdır, ama denge çağrılarını insan değil derleyici yazar.

Kritik nokta: **Legacy kod tabanları karışıktır.** `-fno-objc-arc` bayrağıyla dosya-dosya MRC'ye düşürülmüş modüller, ARC ile derlenen modüllerle bir arada bulunur. Ayrıca `CoreFoundation` (CF) nesneleri (`CFStringRef`, `CGImageRef` vb.) ARC kapsamına **girmez**; onlar `CFRetain`/`CFRelease` ile elle yönetilir. Bu iki dünya arasındaki köprü (`__bridge`, `__bridge_transfer`, `__bridge_retained`) yanlış kullanıldığında sızıntı veya çift-serbest bırakma üretir.

## Ana Bellek Güvenliği Açığı Sınıfları

### 1. Use-After-Free (UAF): Dangling Pointer

**Tanım:** Bir nesnenin retain count'u sıfıra düşüp `dealloc` edildikten sonra, hâlâ elde tutulan bir işaretçi üzerinden ona erişilmesi. Bellek serbest bırakılmıştır ama işaretçi hâlâ eski adresi gösterir (dangling pointer).

**Kök neden / çalışma mantığı:** Objective-C'de bu, çoğu zaman bir `weak` referans yerine `unsafe_unretained` (veya MRC'de `assign`) kullanılmasından doğar. `assign`/`unsafe_unretained` özellikleri sahiplik almaz ve nesne yok olduğunda **otomatik olarak `nil`'lenmez**. Nesne serbest bırakıldıktan sonra bu işaretçiye mesaj gönderilirse, ya eski (çöp) bellek okunur ya da o adres başka bir nesneye yeniden tahsis edilmişse **tip karışıklığı (type confusion)** oluşur.

Message-passing bağlamında UAF özellikle tehlikelidir: serbest bırakılmış belleğin `isa` alanı saldırgan kontrolündeki bir değerle üzerine yazılabilirse, `objc_msgSend` sahte bir sınıf/IMP'ye dallanabilir. Bu, tarihsel olarak birçok Objective-C UAF'ının kod yürütmeye yükseltilme yoludur.

```objc
// Tehlikeli: delegate assign ile tutuluyor (MRC dönemi kalıntısı)
@property (nonatomic, assign) id<MyDelegate> delegate;
// ...
self.delegate = someController;   // someController dealloc olursa
[self.delegate didFinish];        // dangling pointer -> UAF
```

**Doğru kullanım:** Delegate'ler ve geri-referanslar için `weak` kullanın. `weak`, runtime tarafından takip edilir; hedef nesne `dealloc` olduğunda işaretçi otomatik `nil` yapılır. `nil`'e mesaj güvenli olduğu için UAF, sessiz no-op'a dönüşür.

```objc
@property (nonatomic, weak) id<MyDelegate> delegate;
```

### 2. Retain Cycle (Bellek Sızıntısı)

**Tanım:** İki nesne birbirini `strong` referansla tutar; retain count'ları asla sıfıra düşmez, dolayısıyla ikisi de serbest bırakılmaz.

**En yaygın kaynak: block'lar.** Bir block, içinde referans verdiği değişkenleri (`self` dahil) `strong` olarak yakalar (capture). Bir nesne bir block'u property olarak tutar, block da `self`'i yakalarsa döngü kapanır.

```objc
// Retain cycle: self -> block -> self
self.completion = ^{
    [self doSomething];   // self güçlü yakalanır
};
```

**Doğru kullanım — weak/strong dansı:**

```objc
__weak typeof(self) weakSelf = self;
self.completion = ^{
    __strong typeof(weakSelf) strongSelf = weakSelf;   // block içinde nil'lenmeyi engelle
    if (strongSelf) { [strongSelf doSomething]; }
};
```

Buradaki `strongSelf` deseni önemlidir: block çalışırken `weakSelf` yarı yolda `nil` olabilir; onu bir kez `strong`'a yükseltmek, block gövdesi boyunca nesnenin canlı kalmasını garanti eder.

### 3. Over-release ve Double-Free

**Tanım:** Bir nesneye sahip olmadığın hâlde (veya bir kez fazla) `release` çağırmak. Sayaç zamanından önce sıfıra düşer, nesne `dealloc` olur ve sonraki her erişim UAF'a dönüşür. Aynı belleği iki kez serbest bırakmak (double-free) heap yapısını bozar.

**Kök neden:** MRC'de convenience constructor'dan alınan (sahibi olmadığın) bir nesneyi `release` etmek; veya bir `retain`/`release` çiftini erken `return` yolunda unutmak. Ayrıca CF köprülemesinde `__bridge_transfer` ile sahipliği ARC'ye devrettikten sonra ayrıca `CFRelease` çağırmak klasik double-free'dir.

### 4. Zombie'ler ve Serbest Bellek Yeniden Kullanımı

Serbest bırakılmış bir nesnenin belleği heap allocator tarafından hemen başka bir tahsise verilebilir. Bu yeniden kullanım (reuse), UAF'ları determinsitik olmayan çökmelere ve tip karışıklığına çevirir. Debug için `NSZombieEnabled`, serbest bırakılan nesneleri gerçek `dealloc` yerine "zombie" bir sarmalayıcıyla değiştirir; zombie'ye gelen her mesaj, hangi selector'ün ölü nesneye gönderildiğini bildiren bir hata üretir.

## Message-Passing ve Selector Enjeksiyonu

### `performSelector:` ve dinamik selector'ler

Objective-C'nin dinamizmi, çalışma zamanında string'den selector üretmeye izin verir:

```objc
SEL sel = NSSelectorFromString(userControlledString);
[target performSelector:sel withObject:arg];
```

**Güvenlik riski:** Selector adı, doğrudan veya dolaylı olarak dış girdiden (URL scheme, deep link, IPC payload, sunucu yanıtı, JS bridge) türüyorsa, saldırgan **hedefte var olan istenmeyen bir metodu** tetikleyebilir. Bu bir "kod enjeksiyonu" değil (var olmayan kod yaratılamaz), ama bir **yetkisiz metot çağrımı**dır: normalde erişilemeyen dahili API'lere ulaşmanın yolu olabilir.

Klasik örnek yüzeyi, `openURL:` üzerinden gelen deep-link'lerin bir sözlükten metot adına eşlenip `performSelector:` ile çağrılmasıdır. Girdi kısıtlanmazsa, saldırgan uygulamanın niyet etmediği bir handler'ı çalıştırabilir.

Ek olarak, `performSelector:` ile çağrılan selector'ün dönüş ve argüman tipleri ARC tarafından tam bilinemez; derleyici "may cause a leak" uyarısı verir. Bu, hem bellek güvenliği hem doğruluk sorunudur.

### `NSInvocation` ve tip güvensizliği

`NSInvocation` ile argümanlar ham bellek olarak (`setArgument:atIndex:`) yerleştirilir. Metot imzasıyla (`NSMethodSignature`) uyuşmayan argüman boyutları/tipleri, stack/heap bozulmasına yol açabilir. Denetimde `NSInvocation` kullanımları, imza doğrulaması yapılıp yapılmadığı açısından incelenmelidir.

### Method Swizzling

`method_exchangeImplementations` ile çalışma zamanında iki metodun IMP'leri takas edilebilir (swizzling). Meşru kullanımları (analitik, instrumentasyon) vardır, ama:

- Kategorilerde (`category`) aynı metodun tanımlanması ve swizzling'in birleşimi, hangi IMP'nin kazandığını belirsizleştirir.
- Kötü amaçlı bir kütüphane, güvenlik kontrolü yapan bir metodu swizzle ederek atlayabilir.
- `+load` içindeki swizzling sırası kütüphane yükleme sırasına bağlı olduğundan kırılgandır.

Denetimde `method_exchangeImplementations`, `class_replaceMethod`, `class_addMethod` çağrıları haritalanmalı; güvenlik kararı veren metotların (kimlik doğrulama, jailbreak tespiti, sertifika kontrolü) swizzle'a açık olup olmadığı değerlendirilmelidir.

## C ile İç İçe Geçen Klasik Bellek Hataları

Objective-C, C'nin süperkümesidir; legacy kodda ham C rutinleri bolca bulunur. Bu yüzden klasik C açıkları geçerlidir:

- **Buffer overflow:** `strcpy`, `sprintf`, `memcpy` sınır kontrolü olmadan; sabit boyutlu C dizilerine `NSString`'den `getCString:` ile kopyalama.
- **Format string:** `NSLog(userInput)` veya `[NSString stringWithFormat:userInput]` — kullanıcı girdisi format string olarak kullanılırsa `%@`, `%n` gibi belirteçler bilgi sızdırma veya bozulma üretir. Doğrusu her zaman `NSLog(@"%@", userInput)`.
- **Integer overflow → undersized allocation:** Bir uzunluk hesabı taşarsa, `malloc`/`NSData` küçük tahsis eder ama kod büyük veri yazar.
- **`NSData`/`NSString` sınır varsayımları:** `bytes`/`length` üzerinden ofset okurken length doğrulamasının atlanması.

## Tespit: Denetim ve Araç Yaklaşımı

### Statik analiz

- **Clang Static Analyzer** (Xcode "Analyze"): retain/release dengesizliklerini, olası `nil` dereferance'larını, ARC köprüleme hatalarını ve bazı UAF kalıplarını yakalar. Legacy denetiminin ilk adımı olmalıdır.
- **Derleyici uyarıları maksimize edilmeli:** `-Wall -Wextra`, ARC uyarıları, `-Wformat-security`. "may cause a leak" ve "performSelector may cause a leak" uyarıları ciddiye alınmalıdır.
- **Grep tabanlı yüzey haritalama:** `performSelector`, `NSSelectorFromString`, `NSInvocation`, `method_exchangeImplementations`, `__bridge_transfer`, `assign`/`unsafe_unretained` property'leri, `strcpy`/`sprintf`/`memcpy`, `stringWithFormat:` çağrılarının envanterini çıkarmak denetim kapsamını netleştirir.

### Dinamik analiz

- **Address Sanitizer (ASan):** UAF, heap buffer overflow, double-free gibi bellek hatalarını çalışma zamanında yakalar ve hem tahsis hem serbest bırakma yığın izini verir. Objective-C/C karışık kodda en değerli araçlardan biridir.
- **NSZombieEnabled:** Serbest bırakılmış nesneye mesajı yakalar; UAF kaynağını selector düzeyinde işaret eder.
- **Instruments — Leaks & Allocations:** Retain cycle'ları ve büyüyen tahsisleri görselleştirir; block kaynaklı sızıntıları bulmakta etkilidir.
- **Malloc Scribble/Guard:** Serbest bırakılan belleği tanınabilir bir kalıpla doldurarak UAF'ı erken çökmeye çevirir.

## Savunma ve Hardening Prensipleri

1. **Yeni kodu ARC ile yaz; legacy MRC modülleri kademeli geçir.** Manuel retain/release'i insan matematiğinden çıkarmak, tüm bir hata sınıfını (over/under-release) büyük ölçüde eler.
2. **Sahiplik niteliklerini doğru seç.** Geri-referanslar ve delegate'ler `weak`; sahip olunan alt-nesneler `strong`; asla sahibi olmadan `assign`/`unsafe_unretained` ile nesne tutma.
3. **Block'larda weak/strong desenini standartlaştır.** Kod incelemesinde block içinde çıplak `self` bir kırmızı bayrak olmalı.
4. **Dinamik selector'lere allow-list uygula.** `performSelector:`/`NSSelectorFromString` hedeflerini, dış girdiden gelen değeri asla doğrudan selector'e çevirmeyecek şekilde kısıtla; izinli metotları sabit bir sözlükle eşle.
5. **Güvenli C API'leri kullan.** `strlcpy`/`snprintf`; boyut hesaplarında taşma kontrolü; format string'lerde sabit literal.
6. **CF ↔ ObjC köprülemesini standartlaştır ve gözden geçir.** `__bridge_transfer` sonrası `CFRelease` yok; `__bridge_retained` sonrası `CFRelease` var — bu eşleşmeyi denetle.
7. **CI'a sanitizer'lı ve statik-analiz'li build ekle.** ASan'lı test suite'i ve "Analyze" adımını pipeline'a koymak, regresyonları erken yakalar.

## Yaygın Hatalar (Özet)

- Delegate'i `weak` yerine `assign`/`strong` tutmak (UAF veya retain cycle).
- Block içinde `self`'i güçlü yakalayıp aynı block'u `self`'te saklamak (retain cycle).
- MRC'de convenience constructor sonucunu `release` etmek (over-release).
- `__bridge_transfer` sonrası ayrıca `CFRelease` çağırmak (double-free).
- `NSLog(kullaniciGirdisi)` — format string açığı.
- Dış girdiyi `NSSelectorFromString` ile doğrudan selector'e çevirmek (yetkisiz metot çağrımı).
- ARC uyarılarını ("may cause a leak") gürültü sayıp bastırmak.
- `nil` sessizliğine güvenip bir zincirin ortasındaki beklenmedik `nil`'i hata olarak fark etmemek.

## Sonuç

Objective-C'nin bellek güvenliği, dinamik mesajlaşma ve referans sayımının kesiştiği yerde yaşar. Legacy iOS kod tabanlarında en yüksek riskli yüzeyler; `weak` yerine `assign` kullanan geri-referanslar (UAF), block kaynaklı retain cycle'lar, MRC dengesizlikleri, CF köprüleme hataları ve dış girdiyle beslenen dinamik selector'lerdir. Savunma stratejisi tek bir araca değil, katmanlara dayanır: ARC'ye geçiş, doğru sahiplik nitelikleri, dinamik çağrılara allow-list, güvenli C kullanımı ve CI'da statik analiz ile sanitizer'lar. Bu katmanlar birlikte, on yıllık bir kod tabanını dahi denetlenebilir ve savunulabilir hâle getirir.
