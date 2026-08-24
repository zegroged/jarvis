# Rust Ownership ve Güvenlik: Ownership, Borrow, Lifetime, Fearless Concurrency ve Unsafe

## Giriş: Rust Neyi Çözmeye Çalışıyor?

Sistem programlama tarihi, iki kötü seçenek arasında sıkışıp kalmıştı. Bir tarafta C ve C++ gibi diller vardı: hızlı, donanıma yakın, belleği elle yöneten ama karşılığında `use-after-free`, `double free`, `dangling pointer`, `buffer overflow` ve `data race` gibi bir sürü bellek güvenliği (memory safety) hatasına açık diller. Diğer tarafta Java, Go, C# gibi bir `garbage collector` (çöp toplayıcı) ile gelen diller vardı: güvenli ama çalışma zamanında (runtime) belleği takip eden bir mekanizmanın getirdiği öngörülemeyen duraklamalar (pause) ve ek yük (overhead) ile.

Rust'ın temel iddiası şudur: bellek güvenliğini **çalışma zamanında değil, derleme zamanında (compile time)** garanti edebiliriz. Yani bir `garbage collector` olmadan, sıfır çalışma zamanı maliyetiyle. Microsoft ve Google'ın kendi güvenlik analizlerinde tekrar tekrar dile getirdiği bir gerçek var: ciddi güvenlik açıklarının çok büyük bir kısmı (bu şirketlerin yayımladığı rakamlarda tipik olarak yaklaşık üçte iki civarı) bellek güvenliği ihlallerinden kaynaklanıyor. Rust bu sınıf hataları büyük ölçüde **dilin kendisi tarafından imkansız kılınacak** biçimde tasarladı.

Bunu mümkün kılan çekirdek mekanizma **ownership** (sahiplik) sistemidir. Bu makale ownership'ten başlayıp `borrowing`, `lifetime`, `fearless concurrency` ve `unsafe`'e kadar bu sistemin nasıl çalıştığını, neden böyle tasarlandığını ve pratikte nasıl doğru kullanılacağını anlatıyor.

## Ownership: Belleğin Tek Bir Sahibi Vardır

### Tanım ve Üç Kural

Ownership, Rust'ın belleği kimin yönettiğini belirleyen kural setidir. Üç temel kuralı vardır:

1. Her değerin bir **sahibi (owner)** vardır.
2. Aynı anda **yalnızca bir sahip** olabilir.
3. Sahip kapsam (scope) dışına çıktığında, değer **otomatik olarak serbest bırakılır (drop edilir)**.

Buradaki dahiyane kısım üçüncü kuraldır. Rust, bir değişkenin kapsamının nerede bittiğini derleme zamanında zaten bilir. Dolayısıyla belleği ne zaman serbest bırakacağını da bilir. Bunun için çalışma zamanında bir izleyiciye, referans sayacına (reference counter) veya çöp toplayıcıya ihtiyaç yoktur. Derleyici, kapsamın kapanış parantezinde otomatik olarak `drop` çağrısını yerleştirir. Buna **RAII** (Resource Acquisition Is Initialization) denir; C++ dünyasından gelen bu fikir Rust'ta dilin merkezine yerleştirilmiştir.

### Kök Neden: Neden "Move" Semantiği?

Ownership'in en çok kafa karıştıran ama en kritik davranışı **move** (taşıma) semantiğidir. Şu koda bakalım:

```rust
let s1 = String::from("merhaba");
let s2 = s1;
println!("{}", s1); // DERLEME HATASI
```

Çoğu dilde bu kod sorunsuz çalışır; `s1` ve `s2` aynı stringi gösterir. Rust'ta ise `let s2 = s1;` satırı sahipliği `s1`'den `s2`'ye **taşır**. Artık `s1` geçersizdir ve onu kullanmak derleme hatası verir.

Peki neden? Kök nedene inelim. `String` tipi heap üzerinde tutulan bir veriye işaret eden bir yapıdır: bir pointer, bir uzunluk (length) ve bir kapasite (capacity) barındırır. Eğer Rust `s1 = s2` atamasını basit bir kopyalama olarak bıraksaydı, iki değişken de aynı heap adresini gösterirdi. Kapsam bittiğinde her ikisi de kendi `drop`'unu çağıracak ve **aynı bellek iki kez serbest bırakılacaktı**. İşte bu, C/C++ dünyasının klasik `double free` hatasıdır ve ciddi güvenlik açıklarının kaynağıdır.

Rust bu ikilemi move ile çözer: kaynak değişkeni geçersizleştirerek "tek sahip" kuralını korur. Böylece `double free` **kavramsal olarak** imkansız hale gelir; çünkü drop çağrısını yalnızca güncel sahip yapabilir.

Buradaki maliyet analizi de önemlidir: `let s2 = s1` bir move olduğunda, heap'teki asıl veri kopyalanmaz; yalnızca pointer/length/capacity üçlüsü (yani stack üzerindeki küçük yapı) kopyalanır. Bu yüzden move ucuzdur.

### Copy ve Clone Ayrımı

Basit, sabit boyutlu ve tamamen stack üzerinde yaşayan tipler (`i32`, `bool`, `char`, bunlardan oluşan tuple'lar gibi) `Copy` trait'ini uygular. Bunlarda `let y = x;` bir move değil, gerçek bir bit kopyasıdır ve `x` hâlâ geçerlidir. Sebep basittir: bu tipler heap kaynağı tutmadığı için `double free` riski yoktur, dolayısıyla kopyalamak güvenlidir ve ucuzdur.

Heap kaynağı tutan bir tipin gerçek kopyasını istiyorsanız, bunu **açıkça** `.clone()` çağırarak yaparsınız. Bu tasarım tercihi de bilinçlidir: derin kopyalama (deep copy) pahalı bir işlemdir ve Rust bunun kod içinde görünür olmasını, yani sizi "ben bilerek bu maliyeti kabul ediyorum" demeye zorlamayı ister.

## Borrowing: Sahipliği Devretmeden Erişim

### Neden Borrowing'e İhtiyaç Var?

Her fonksiyona değeri taşıyarak (move) geçmek zorunda olsaydık, sürekli değerleri geri döndürmek zorunda kalırdık; bu da son derece hantal olurdu. Çözüm **borrowing** (ödünç alma), yani referanslardır. Bir referans (`&T`), sahipliği devralmadan bir değere erişmenizi sağlar. Fonksiyon değeri "ödünç alır", işini yapar ve sahiplik hiç el değiştirmediği için orijinal sahip geçerliliğini korur.

### Borrow Checker'ın Altın Kuralı

Rust'ın en meşhur bileşeni **borrow checker**'dır ve tek bir merkezi kuralı zorunlu kılar. Herhangi bir anda, belirli bir veri için ya:

- **istediğiniz kadar sabit (immutable) referans** (`&T`) olabilir,
- **ya da tam olarak bir tane değiştirilebilir (mutable) referans** (`&mut T`) olabilir.

İkisi aynı anda olamaz. Yani birileri veriyi okurken başka biri onu değiştiremez.

Bu kural neden var? Kök neden **aliasing + mutation** ikilisidir. Bir veriye aynı anda hem erişilip hem değiştirilmesi, yazılım tarihindeki en sinsi hataların anasıdır. Klasik örnek `iterator invalidation`'dır: bir koleksiyon üzerinde döngüde gezerken (bu bir immutable borrow'dur) aynı koleksiyona eleman eklerseniz (bu bir mutable borrow gerektirir), koleksiyon içindeki bellek yeniden konumlandırılabilir (reallocation) ve elinizdeki iterator artık serbest bırakılmış belleği gösterir; bu bir `use-after-free`'dir. Rust bunu derleme zamanında yakalar:

```rust
let mut v = vec![1, 2, 3];
for x in &v {          // v ödünç alındı (immutable)
    v.push(*x);        // DERLEME HATASI: v'yi mutable ödünç alamazsın
}
```

C++'ta bu kod derlenir ve çalışma zamanında çökebilir veya sessizce yanlış davranabilir. Rust'ta ise derleyici "hayır" der. İşte "fearless" (korkusuz) kelimesinin kaynağı budur: sınıf olarak bu hatalardan korkmaya gerek kalmaz.

### NLL: Referansın Ömrü Nerede Biter?

Modern Rust'ta borrow checker **NLL** (Non-Lexical Lifetimes) yaklaşımını kullanır. Eski davranışta bir referans, kapsayan blok kapanana kadar "canlı" sayılırdı. NLL ile bir referans, **son kullanıldığı noktadan sonra** ölü kabul edilir. Bu, aşağıdaki gibi mantıken güvenli olan kodun derlenmesini sağlar:

```rust
let mut s = String::from("hey");
let r = &s;           // immutable borrow başlar
println!("{}", r);    // r'nin son kullanımı; burada borrow biter
let m = &mut s;       // artık mutable borrow serbest
m.push_str("!");
```

Buradaki içgörü şudur: borrow checker sanıldığından daha akıllıdır; referansların gerçek kullanım aralığına bakar, sadece bloklara değil.

## Lifetime: Referanslar Ne Kadar Yaşar?

### Tanım ve Kök Neden

**Lifetime** (yaşam süresi), bir referansın geçerli olduğu kod bölgesini ifade eder. Lifetime'ların var olma nedeni tek ve nettir: **dangling reference'ı (askıda referans) önlemek**. Yani bir referansın, işaret ettiği veriden daha uzun yaşamasını engellemek.

Klasik hatalı örnek:

```rust
fn tehlikeli() -> &String {
    let s = String::from("gecici");
    &s   // HATA: s bu fonksiyon bitince drop edilir
}      // döndürülen referans askıda kalırdı
```

`s` fonksiyon bitince serbest bırakılır. Eğer ona bir referans döndürebilseydik, çağıran taraf serbest bırakılmış belleği gösteren bir referansa sahip olurdu; bu klasik bir `use-after-free`'dir. Rust derleyicisi bunu reddeder.

### Lifetime Annotation Neden Var?

Çoğu zaman lifetime'ları hiç yazmayız çünkü derleyici bunları **lifetime elision** (yaşam süresi çıkarımı) kuralları ile otomatik çıkarır. Ama bazı durumlarda derleyici, döndürülen referansın hangi girdiden geldiğini kestiremez. İşte o zaman biz `'a` gibi annotation'larla ipucu veririz:

```rust
fn en_uzun<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}
```

Kritik yanlış anlama şudur: **lifetime annotation'ları referansların ne kadar yaşayacağını *değiştirmez*.** Onlar sadece derleyiciye referanslar arasındaki *ilişkiyi* açıklar. Yukarıdaki imza şunu söyler: "Döndürülen referansın ömrü, `x` ve `y`'nin ömürlerinin daha kısa olanı kadardır." Derleyici bu sözleşmeyi çağıran tarafta doğrular. Yani lifetime, bir emir değil, bir **tanımlamadır**; derleyicinin doğrulayabileceği bir sözleşmedir.

### 'static Lifetime

Özel bir lifetime olan `'static`, verinin programın tüm ömrü boyunca yaşadığı anlamına gelir. String literal'ler (`"merhaba"`) doğrudan çalıştırılabilir dosyanın içine gömüldükleri için `&'static str` tipindedir. `'static` güçlü bir garantidir ama onu her yere serpiştirmek genellikle bir tasarım kokusudur (code smell); çoğu zaman gerçek sorunu çözmek yerine borrow checker'ı susturma girişimidir.

## Fearless Concurrency: Aynı Kuralların Paralel Dünyaya Uygulanması

### Neden "Fearless"?

Rust'ın belki de en zarif tarafı şudur: eşzamanlılık (concurrency) için **yeni bir kural sistemi icat etmedi**. Ownership ve borrowing kuralları, `data race`'leri (veri yarışı) önlemek için zaten gereken tam olarak doğru araç setiymiş.

Bir `data race` şu üç koşul aynı anda sağlandığında oluşur: (1) birden fazla thread aynı veriye erişir, (2) en az biri veriyi yazar, (3) bu erişimleri senkronize eden bir mekanizma yoktur. Şimdi borrow checker'ın altın kuralını hatırlayın: aynı anda ya çok sayıda okuyucu ya da tek bir yazıcı. Bu kural, `data race`'in ilk iki koşulunun bir arada bulunmasını zaten yasaklar. Aynı derleme zamanı analizi, tek thread'lik `iterator invalidation`'ı da, çok thread'lik `data race`'i de aynı prensiple engeller. Bu, tesadüf değil, tasarımın doğal bir sonucudur.

### Send ve Sync: İki İşaretleyici Trait

Bu güvenliği thread sınırları arasında taşıyan iki `marker trait` vardır:

- **`Send`**: Bir tipin sahipliği başka bir thread'e güvenle **taşınabilir**. Çoğu tip `Send`'dir.
- **`Sync`**: Bir tipe birden fazla thread'ten **referansla** güvenle erişilebilir. Yani `&T` `Send` ise, `T` `Sync`'tir.

Bu trait'ler genellikle derleyici tarafından otomatik olarak türetilir (auto trait). Önemli olan, bunların thread güvenliğini **tip sisteminin bir parçası** haline getirmesidir. Örneğin referans sayan `Rc<T>` tipi `Send` değildir; çünkü sayacı atomik olmayan biçimde günceller ve iki thread aynı anda sayacı değiştirirse sayaç bozulur. Onun thread-güvenli kardeşi `Arc<T>` (Atomic Reference Counted) ise sayacı atomik işlemlerle günceller ve `Send + Sync`'tir. Bu ayrımı yanlış yaparsanız kod **çalışma zamanında değil, derleme zamanında** reddedilir.

### Paylaşımlı Durum: Mutex ve Arc

Rust'ta `Mutex<T>`'in tasarımı da öğreticidir. Birçok dilde mutex ile onun koruduğu veri ayrı şeylerdir ve programcının kilidi almayı unutmaması gerekir. Rust'ta ise **veri, mutex'in içinde yaşar**. Veriye erişmenin tek yolu `.lock()` çağırıp bir `guard` almaktır. Kilidi almadan veriye erişmek dilbilgisel olarak mümkün değildir. Dahası, `guard` kapsam dışına çıkınca kilit RAII sayesinde otomatik olarak serbest bırakılır; kilidi açmayı unutmak mümkün değildir.

Birden fazla thread'in aynı `Mutex`'e sahip olması için genellikle onu `Arc` ile sararız: `Arc<Mutex<T>>`. `Arc` paylaşımlı sahipliği, `Mutex` ise senkronize erişimi sağlar. Bu iki tipin birleşimi, Rust'taki paylaşımlı değiştirilebilir durumun standart kalıbıdır.

Not: Rust'ın önlediği şey `data race`'lerdir. **Deadlock** (kilitlenme) hâlâ mümkündür; iki thread'in birbirinin kilidini beklemesini borrow checker engelleyemez. Bu dürüst bir sınırdır: Rust size bir güvence verir ama her eşzamanlılık hatasını çözmez.

## Unsafe: Kontrolü Devraldığınız Kapı

### Neden Unsafe Var?

Borrow checker güçlüdür ama muhafazakârdır: doğruluğunu **kanıtlayamadığı** her şeyi reddeder. Oysa bazı işlemler gerçekte güvenlidir, sadece derleyicinin bunu kanıtlayacak bilgisi yoktur. Ayrıca işletim sistemi çağrıları, donanım erişimi ve C kütüphaneleriyle konuşma (FFI) gibi işlemler doğaları gereği derleyicinin göremeyeceği yerlere uzanır. İşte `unsafe` bu boşluğu doldurur.

`unsafe` bloğu, "derleyicinin denetleyemediği ama benim güvenli olduğunu garanti ettiğim bir işlem yapıyorum" demenin yoludur. Kritik bir yanlış anlamayı düzeltelim: `unsafe`, borrow checker'ı **kapatmaz**. Sahiplik, borrow ve lifetime kuralları `unsafe` blok içinde de aynen geçerlidir. `unsafe` yalnızca beş ekstra "süper güç" açar; en önemlileri şunlardır:

- Raw pointer'ları (`*const T`, `*mut T`) dereference etmek,
- `unsafe` olarak işaretlenmiş fonksiyonları çağırmak (FFI dahil),
- Değiştirilebilir statik değişkenlere (`static mut`) erişmek.

### Kök Sorumluluk: Güvenli Soyutlama

`unsafe`'in doğru kullanım felsefesi şudur: `unsafe` kodu **küçük, denetlenebilir bir alanda hapset** ve etrafını, dışarıya güvenli bir arayüz (safe abstraction) sunan koda sar. Bu, Rust'ın "gizli sırrıdır": standart kütüphanenin büyük bölümü (`Vec`, `String`, `Arc`, `Mutex`, kanallar) içeride `unsafe` içerir. Ama bu `unsafe` bloklarını yazan kişiler, dışarıya sundukları API'nin **her koşulda** güvenli olduğunu elle kanıtlamıştır. Böylece siz `Vec`'i milyonlarca kez tamamen güvenli biçimde kullanırsınız.

Buradaki anlaşma nettir: `unsafe` yazdığınız anda, o beş satırın **bellek güvenliği kanıtını** derleyiciden devralmış olursunuz. Derleyici artık size güvenir; hata yaparsanız Rust'ın tüm garantileri o noktadan itibaren çöker (Undefined Behavior). Bu yüzden `unsafe` bir "kolay çıkış yolu" değil, bir "sorumluluk sözleşmesidir".

## Yaygın Hatalar ve Tuzaklar

**1. Borrow checker'la savaşıp `.clone()` ile kaçmak.** Yeni başlayanlar borrow hatalarını sürekli `.clone()` çağırarak susturur. Bu bazen doğrudur ama çoğu zaman gerçek sorun, verinin akışını (data flow) yanlış tasarlamaktır. Önce "bu veriyi gerçekten kim sahiplenmeli?" diye sormak, körü körüne kopyalamaktan iyidir.

**2. `Rc<RefCell<T>>`'i refleks haline getirmek.** Paylaşımlı-değiştirilebilir durum sorununu `Rc<RefCell<T>>` ile çözmek caziptir ama `RefCell`, borrow kuralını derleme zamanından **çalışma zamanına** taşır. Kuralı ihlal ederseniz derleme hatası yerine `panic` alırsınız. Yani güvenliği kaybetmezsiniz ama derleme zamanı garantisini kaybedersiniz. Bunu ancak gerçekten gerektiğinde kullanın.

**3. `'static`'i sihirli değnek sanmak.** Bir lifetime hatasını `'static` ekleyerek "çözmek" çoğu zaman sorunu daha derine iter. `'static`, verinin sonsuza dek yaşamasını *talep eder* ve bu talep gerçek dünyada nadiren karşılanır.

**4. `unsafe`'i anlamadan kopyalamak.** İnternetten bulunan bir `unsafe` bloğunu bağlamını anlamadan yapıştırmak, Rust'ın tüm güvenlik modelini bir satırla çökertebilir. `unsafe` içindeki bir hata, programın tamamen alakasız bir yerinde bellek bozulması olarak ortaya çıkabilir.

**5. `self` referansı tutan yapılar kurmaya çalışmak.** Kendi içinde kendine referans tutan yapılar (self-referential structs) Rust'ın move semantiğiyle temelde çelişir; çünkü yapı bellekte taşındığında iç referans geçersiz olur. Bu ihtiyaç genellikle `Pin`, arena tabanlı tasarım veya index kullanımı gibi kalıplarla çözülür.

## En İyi Pratikler

- **Ownership'i tasarımın merkezine koyun.** "Bu veriye kim sahip, kim ödünç alıyor?" sorusunu kod yazmadan önce cevaplayın. Rust'ta iyi mimari, büyük ölçüde net bir sahiplik grafiğidir.
- **Referansları tercih edin, sahipliği ancak gerektiğinde devredin.** Fonksiyon imzalarında mümkün olduğunca `&T` veya `&mut T` alın; değeri gerçekten tüketmiyorsanız (consume) sahipliği istemeyin.
- **`unsafe`'i küçük ve iyi belgelenmiş tutun.** Her `unsafe` bloğunun başına, o bloğun neden güvenli olduğunu açıklayan bir yorum (yaygın gelenek `// SAFETY:` yorumudur) yazın. Bu, geleceğin okuyucusuna kanıtınızı sunar.
- **Derleyiciyi bir düşman değil, bir eş programcı gibi görün.** Rust derleyicisinin hata mesajları sektördeki en açıklayıcı mesajlar arasındadır; genellikle sorunu gösterir ve düzeltme önerir. Borrow checker'ı "yanlış" sanmadan önce, çoğu zaman gerçekten bir sorunu işaret ettiğini varsayın.
- **`Arc<Mutex<T>>` kalıbını bilin ama abartmayın.** Paylaşımlı durum yerine, mümkünse durumu thread'ler arasında **mesaj geçişiyle** (channel, `mpsc`) taşımayı değerlendirin. Paylaşmadığınız veriyi kilitlemeniz gerekmez.
- **Denetim araçlarını kullanın.** `clippy` (linter) yaygın hataları ve daha iyi kalıpları önerir; `unsafe` içeren kod için `Miri` gibi araçlar Undefined Behavior'ı çalışma zamanında yakalamaya yardımcı olur.

## Sonuç

Rust'ın güvenlik modelinin en güçlü yanı, birbirinden kopuk kuralların bir yığını olmaması, **tek bir tutarlı fikrin** farklı yüzleri olmasıdır. Ownership belleğin ne zaman serbest bırakılacağını çözer. Borrowing aynı fikri erişime taşır. Lifetime aynı fikri zamana yayar. Fearless concurrency ise aynı borrow kurallarının paralel dünyada `data race`'i nasıl engellediğini gösterir. `unsafe` ise bu sistemin dışına çıkmak gerektiğinde, sorumluluğu açıkça programcıya devreden dürüst bir kapıdır.

Bu tasarımın bedeli gerçektir: öğrenme eğrisi diktir ve borrow checker başta sinir bozucu olabilir. Ama karşılığında elde edilen şey, sistem programlamanın on yıllardır ödediği bir bedeli, yani bütün bir bellek güvenliği hata sınıfını **derleme zamanında ortadan kaldırmaktır**. Bir kez bu düşünce biçimini içselleştirdiğinizde, borrow checker bir engel değil, kodunuzun doğruluğunu size en baştan kanıtlayan sessiz bir ortak haline gelir.
