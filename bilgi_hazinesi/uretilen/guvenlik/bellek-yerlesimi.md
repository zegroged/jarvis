# Bellek Yerleşimi ve Çağrı Konvansiyonları

## Giriş: Neden Bir Programcının Belleği Tanıması Gerekir?

Bir programın diskte duran pasif bir dosyadan, işlemcide çalışan canlı bir sürece dönüşmesi, işletim sistemi tarafından titizlikle düzenlenmiş bir bellek yerleşimi (memory layout) sayesinde olur. Güvenlik açısından bakıldığında, `buffer overflow`, `use-after-free`, `format string` ve `return-oriented programming` gibi klasik ve hâlâ güncel olan açıkların neredeyse tamamı, bu yerleşimin ve işlemci ile derleyici arasındaki çağrı sözleşmesinin (calling convention) mantığını iyi kavramaktan geçer. Saldırgan da savunmacı da aynı haritaya bakar; farkları haritayı ne kadar iyi okuduklarıdır.

Bu makalede bir sürecin sanal adres uzayındaki bölütleri (text, data, BSS, heap, stack), işlemci register'larının rolünü ve bir fonksiyonun çağrılırken argümanların, dönüş adresinin ve yerel değişkenlerin nasıl yerleştirildiğini derinlemesine ele alacağız. Ardından bu yapıların hem nasıl istismar edildiğini hem de nasıl savunulduğunu, gerçek mekanizmalar üzerinden inceleyeceğiz.

## Sürecin Bellek Yerleşimi

### Sanal Adres Uzayı Kavramı

Modern işletim sistemlerinde her sürece kendi izole sanal adres uzayı verilir. Bu, süreçin belleğe erişirken kullandığı adreslerin gerçek fiziksel RAM adresleri olmadığı, işlemcinin bellek yönetim birimi (MMU) ve işletim sisteminin sayfa tabloları (page tables) aracılığıyla çevrildiği anlamına gelir. Bunun kök nedeni izolasyon ve güvenliktir: bir süreç, kendi adres uzayında bir adrese yazarken başka bir sürecin verisini bozamaz, çünkü o adres fiziksel olarak bambaşka bir yere veya hiçbir yere işaret ediyordur.

Bu sanal uzay, mantıksal olarak bölütlere (segment) ayrılır. Bölütlerin varlığının temel sebebi, farklı verilerin farklı erişim izinlerine (okuma, yazma, çalıştırma) ve farklı yaşam döngülerine ihtiyaç duymasıdır. Kod değişmemeli ama çalıştırılabilmeli; yerel değişkenler hızlı ayrılıp bırakılabilmeli; dinamik veriler ise talebe göre büyüyebilmelidir. Tek tip bir bellek bu ihtiyaçları karşılayamaz.

### Text (Kod) Bölütü

Text bölütü, programın makine komutlarını barındırır. Bu bölüt tipik olarak salt-okunur (read-only) ve çalıştırılabilir (executable) olarak işaretlenir. Salt-okunur olmasının kök nedeni hem güvenlik hem de verimliliktir: kod çalışma sırasında kendini değiştirmemelidir (self-modifying code istisnaları dışında), ve aynı çalıştırılabilir dosyayı çalıştıran birden fazla süreç, aynı fiziksel kod sayfalarını paylaşarak RAM tasarrufu sağlayabilir.

Güvenlik açısından bu ayrımın kritik bir sonucu vardır: text bölütü yazılamaz olduğu için saldırgan çalışan kodu doğrudan değiştiremez; veri bölütleri yazılabilir olduğu ama (savunmalar aktifse) çalıştırılamaz olduğu için de oraya kod enjekte edip çalıştıramaz. Bu W^X (write xor execute) ilkesinin temelini oluşturur.

### Data ve BSS Bölütleri

Başlatılmış global ve statik değişkenler data bölütünde tutulur. Örneğin `int sayac = 5;` şeklinde global bir değişken, hem kendisi hem başlangıç değeri ile çalıştırılabilir dosyanın içinde yer kaplar ve süreç başlarken belleğe yüklenir.

BSS bölütü ise başlatılmamış (veya sıfıra başlatılmış) global ve statik değişkenleri barındırır. `int tampon[1000];` gibi bir global dizi için diskteki dosyada yer ayrılmaz, yalnızca "şu kadar baytlık alanı sıfırla" bilgisi tutulur. Bunun kök nedeni ekonomidir: bin tane sıfırı dosyada saklamak yerine, işletim sistemine süreç başlarken bu bölgeyi sıfırlaması söylenir. Bu iki bölüt yazılabilir ama normalde çalıştırılamazdır.

### Heap (Yığın Bellek)

Heap, çalışma zamanında dinamik olarak ayrılan belleğin bölgesidir. C dilinde `malloc`, C++'ta `new`, üst düzey dillerde ise nesne oluşturma bu bölgeden alan tahsis eder. Heap tipik olarak düşük adreslerden yüksek adreslere doğru büyür. Büyümesi işletim sisteminden ek sanal bellek istemekle (klasik olarak `brk`/`sbrk` veya `mmap` mekanizmaları üzerinden) gerçekleşir.

Heap'in yönetimi çekirdek tarafından değil, süreç içinde çalışan bir bellek ayırıcı (allocator) tarafından yapılır. Ayırıcı, serbest blokların listesini, blok boyutlarını ve meta verileri kendi veri yapılarında tutar. İşte güvenlik açısından kritik nokta budur: bu meta veriler çoğu zaman ayrılan kullanıcı verisinin hemen yanında, aynı yazılabilir bölgede durur. Bir `heap overflow` bu meta verileri bozarak ayırıcının davranışını saldırganın lehine çevirebilir.

### Stack (Yığıt)

Stack, fonksiyon çağrılarının, yerel değişkenlerin, argümanların ve dönüş adreslerinin tutulduğu, son-giren-ilk-çıkar (LIFO) mantığıyla çalışan bölgedir. Çoğu mimaride stack yüksek adreslerden düşük adreslere doğru büyür. Bu, heap'in aksi yöndür ve bunun tarihsel bir mantığı vardır: iki bölge adres uzayının iki ucundan birbirine doğru büyüyerek ortadaki boş alanı esnek biçimde paylaşırlar.

Stack'in en önemli özelliği hızıdır. Bir fonksiyona girildiğinde tek bir register'ı (stack pointer) kaydırarak onlarca yerel değişkene anında yer açılır; fonksiyondan çıkınca aynı register geri kaydırılarak tüm bu alan tek hamlede serbest bırakılır. Bu hızın bedeli ise disiplindir: stack'in düzeni son derece öngörülebilir olduğu için, bir taşma tam olarak nereye ne yazacağını bilen bir saldırgan için değerli bir hedeftir.

## Register'lar: İşlemcinin Çalışma Belleği

Bellek hızlıdır ama işlemci çekirdeğinin içindeki register'lar ondan kat kat hızlıdır. Register'lar, işlemcinin üzerinde doğrudan işlem yaptığı, sınırlı sayıda ve çok küçük depolama birimleridir. Aritmetik, adres hesaplama ve veri taşıma işlemleri register'lar üzerinden yürür.

x86-64 mimarisinde genel amaçlı register'lar (`rax`, `rbx`, `rcx`, `rdx`, `rsi`, `rdi`, `rbp`, `rsp` ve `r8`-`r15`) bulunur. Bunların bir kısmı sözleşme gereği özel roller üstlenir:

- **Stack pointer** (x86-64'te `rsp`): Stack'in tepesini gösterir. Fonksiyon çağrıları, yerel değişken tahsisi ve dönüşlerde sürekli güncellenir. Stack'in mevcut sınırını temsil ettiği için istismar senaryolarının merkezindedir.
- **Base/frame pointer** (`rbp`): Geleneksel olarak mevcut fonksiyonun stack çerçevesinin (stack frame) sabit bir referans noktasını gösterir. Yerel değişkenlere ve argümanlara `rbp`'ye göre sabit ofsetlerle erişilir; bu, çerçeve içinde `rsp` değişse bile referansın kararlı kalmasını sağlar. Optimizasyonlu derlemede `rbp` bazen genel amaçlı kullanıma bırakılır.
- **Instruction pointer** (`rip`): İşlemcinin çalıştıracağı bir sonraki komutun adresini tutar. Doğrudan yazılamaz; `call`, `ret`, `jmp` gibi akış kontrol komutları üzerinden değişir. Bir saldırganın nihai hedefi neredeyse her zaman `rip`'i kontrol etmektir, çünkü onu kontrol etmek yürütme akışını kontrol etmek demektir.
- **Bayrak register'ı** (`rflags`): Karşılaştırma ve aritmetik sonuçlarının bayraklarını (sıfır, taşma, işaret vb.) tutar; koşullu dallanmalar buna bakar.

Register'ların anlaşılması, çağrı konvansiyonunu anlamanın önkoşuludur, çünkü konvansiyon esasen "hangi register neyi taşır ve çağrı boyunca kim korur" sorusunun cevabıdır.

## Çağrı Konvansiyonları (Calling Conventions)

### Neden Bir Sözleşmeye İhtiyaç Var?

Bir fonksiyon başka bir fonksiyonu çağırdığında ortak bir dile ihtiyaç vardır: argümanlar nereye konacak, dönüş değeri nereden okunacak, çağrıdan sonra hangi register'ların değeri korunmuş olacak, stack'i kim temizleyecek? Eğer çağıran (caller) ve çağrılan (callee) bu konularda anlaşmazsa, örneğin çağıran argümanı stack'e koyup çağrılan onu bir register'da ararsa, program çöker. Çağrı konvansiyonu bu anlaşmayı standartlaştırır. Farklı platformlar farklı sözleşmeler benimser; bu yüzden aynı kaynak kodu farklı ABI'lerde farklı makine koduna derlenir.

### Argümanların Geçirilmesi

Modern 64-bit sistemlerde performans için ilk birkaç argüman stack yerine register'larda geçirilir, çünkü register erişimi bellek erişiminden çok daha hızlıdır. Register'lar dolunca kalan argümanlar stack'e taşar.

- **System V AMD64 ABI** (Linux, macOS ve çoğu Unix türevinde tamsayı/işaretçi argümanları için): İlk altı tamsayı argümanı sırayla `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` register'larında geçirilir. Kayan noktalı argümanlar için ayrı bir register kümesi (`xmm0` ve devamı) kullanılır. Dönüş değeri `rax` register'ında verilir.
- **Microsoft x64 çağrı konvansiyonu** (Windows): İlk dört tamsayı argümanı `rcx`, `rdx`, `r8`, `r9` register'larında geçirilir. Ayrıca çağıran, çağrılan fonksiyonun bu register'ları geçici olarak saklaması için stack'te "shadow space" (gölge alan) adı verilen bir bölge ayırır.

Bu iki sözleşmenin farklı olması, tersine mühendislik ve exploit geliştirmede hedef platformu doğru tanımanın neden şart olduğunu gösterir. Burada verdiğim register atamaları yaygın olarak belgelenmiş kurallardır; ancak bir ikili dosyayı analiz ederken kesin davranışı her zaman disassembly üzerinden doğrulamak gerekir, çünkü derleyici optimizasyonları ve inline'lama beklenen kalıbı değiştirebilir.

### Caller-saved ve Callee-saved Register'lar

Register sayısı sınırlı olduğundan, bir çağrı sırasında bazı register'ların değerinin korunacağına, bazılarının ise ezilebileceğine dair bir bölüşüm yapılır. Kök neden performanstır: her çağrıda bütün register'ları kaydedip geri yüklemek pahalı olurdu.

- **Callee-saved (çağrılanın koruduğu)** register'lar: Çağrılan fonksiyon bunları kullanacaksa, önce eski değerlerini saklamalı ve dönmeden önce geri yüklemelidir. Böylece çağıran, çağrıdan sonra bu register'ların değişmemiş olduğuna güvenebilir.
- **Caller-saved (çağıranın koruduğu)** register'lar: Çağrılan bunları serbestçe ezebilir. Çağıran, bir çağrının ötesinde bu register'lardaki değerlere ihtiyaç duyuyorsa çağrıdan önce kendisi saklamalıdır.

Bu ayrım, derlenmiş kodda fonksiyon başlarında ve sonlarında görülen `push`/`pop` dizilerinin sebebidir ve tersine mühendislikte fonksiyon sınırlarını tanımaya yarar.

### Stack Frame ve Prologue/Epilogue

Bir fonksiyon çağrıldığında kendi stack frame'ini kurar. Tipik akış şöyledir:

1. `call` komutu, bir sonraki komutun adresini (dönüş adresi) stack'e iter (`push`) ve akışı hedef fonksiyona dallandırır. Dönüş adresinin stack'te olması, `return address` üzerine yazan taşmaların neden bu kadar tehlikeli olduğunun tam sebebidir.
2. Fonksiyonun başındaki **prologue** kısmı genellikle eski `rbp`'yi stack'e iter, `rsp`'yi `rbp`'ye kopyalar (yeni çerçeve tabanını belirler) ve yerel değişkenler için `rsp`'yi aşağı kaydırarak yer açar.
3. Fonksiyon gövdesi yerel değişkenlere ve argümanlara `rbp`'ye göre sabit ofsetlerle erişir.
4. Fonksiyon biterken **epilogue** kısmı `rsp`'yi geri toplar, saklanan `rbp`'yi geri yükler ve `ret` komutuyla stack'in tepesindeki dönüş adresini `rip`'e alarak çağırana geri döner.

Bu düzenin öngörülebilirliği hem hata ayıklamayı kolaylaştırır hem de saldırgana net bir harita sunar: dönüş adresinin, saklanan frame pointer'ın ve yerel tamponların birbirine göre konumu bellidir.

## Somut Örnek: Bir Stack Çerçevesinin Anatomisi

Aşağıdaki gibi basit bir C fonksiyonunu düşünelim:

```c
void selamla(char *isim) {
    char tampon[64];
    strcpy(tampon, isim);   // sınır kontrolü YOK
    printf("Merhaba %s\n", tampon);
}
```

Bu fonksiyon çağrıldığında stack, yüksek adresten düşük adrese doğru kabaca şöyle dizilir: en üstte (yüksek adreste) çağıranın dönüş adresi, onun altında saklanan eski `rbp`, onun altında ise 64 baytlık `tampon` dizisi. `strcpy`, kaynak dizgede sonlandırıcı sıfır baytı görene kadar kopyalar. Eğer `isim` 64 bayttan uzunsa, kopyalama `tampon`ın sınırını aşar ve düşük adresten yüksek adrese doğru yazmaya devam ederek önce saklanan `rbp`'yi, sonra dönüş adresini ezer.

İşte klasik **stack buffer overflow** budur. `strcpy` hedef tamponun boyutunu bilmez, yalnızca kaynağın sonunu arar; sınır bilgisinin kaybolması açığın kök nedenidir.

## Sömürü Mantığı: Saldırgan Bu Yapıyı Nasıl Kullanır?

Saldırganın nihai amacı yürütme akışını, yani `rip`'i ele geçirmektir. Yukarıdaki taşmada dönüş adresi ezildiğinde, fonksiyon `ret` komutuna geldiğinde artık saldırganın koyduğu değere dallanacaktır. Buradan itibaren birkaç klasik teknik devreye girer.

**Doğrudan kod enjeksiyonu (shellcode):** Tarihsel olarak saldırgan, tamponun içine kendi makine kodunu (shellcode) yerleştirir ve dönüş adresini bu kodun başına yönlendirirdi. İşlemci `ret` yaptığında saldırganın kodunu çalıştırırdı. Bu tekniğin işe yaraması için stack'in çalıştırılabilir olması gerekir.

**Return-oriented programming (ROP):** Stack çalıştırılamaz hale getirilince saldırganlar yeni kod enjekte etmek yerine, mevcut kod içinde zaten bulunan küçük komut dizileri olan "gadget"leri zincirlemeye başladı. Her gadget birkaç işlem yapıp bir `ret` ile biter; saldırgan stack'i bu gadget'ların adresleriyle doldurarak, hiç yeni kod enjekte etmeden bir hesaplama zinciri kurar. Bu teknik, W^X korumasını doğrudan kod çalıştırmadan atlatmak için geliştirilmiştir.

**Meta veri bozma (heap):** Heap tarafında saldırgan, ayırıcının serbest blok meta verilerini bozarak, ileride yapılacak bir tahsis veya serbest bırakma işlemi sırasında ayırıcının seçtiği adrese kontrollü bir yazma yaptırmayı hedefler. `use-after-free` durumunda ise serbest bırakılmış ama hâlâ kullanılan bir işaretçi, saldırganın araya soktuğu sahte nesne üzerinden akışı yönlendirebilir.

Bu tekniklerin ortak noktası, bellek yerleşiminin öngörülebilirliğini ve register/stack sözleşmesinin katılığını silah olarak kullanmalarıdır.

## Savunma Mantığı: Aynı Yapı Nasıl Korunur?

Savunmalar, saldırganın dayandığı iki varsayımı kırmayı hedefler: bellek düzeninin bilinebilir olması ve enjekte edilen verinin kod olarak çalışabilmesi.

**Non-executable memory (DEP / NX bit):** Veri bölgelerini (stack ve heap) çalıştırılamaz olarak işaretleyerek, oraya enjekte edilen shellcode'un çalışmasını engeller. Bu, W^X ilkesinin donanım desteğiyle uygulanmasıdır. ROP'un doğuş sebebi tam olarak bu savunmadır; dolayısıyla NX tek başına yeterli değildir.

**ASLR (Address Space Layout Randomization):** Text, stack, heap ve paylaşılan kütüphanelerin başlangıç adreslerini her çalıştırmada rastgeleleştirir. Saldırgan dönüş adresini veya gadget adreslerini bilemezse, exploit'ini doğru hedefe yönlendiremez. Etkinliği rastgeleliğin entropisine bağlıdır; düşük entropili ortamlarda veya bir bellek sızıntısıyla adres öğrenildiğinde atlatılabilir. En etkili biçimi, çalıştırılabilirin de yeniden konumlandırılabildiği (PIE) yapılarda görülür.

**Stack canary (stack koruma değeri):** Derleyici, prologue sırasında dönüş adresi ile yerel tamponlar arasına rastgele bir "canary" değeri yerleştirir ve epilogue'da fonksiyondan dönmeden önce bu değerin bozulup bozulmadığını kontrol eder. Bir stack taşması dönüş adresine ulaşmak için canary'nin üzerinden geçmek zorunda olduğundan, bozulan canary saldırıyı ele verir ve program güvenli biçimde sonlandırılır. Canary değerinin gizli kalması bu savunmanın temelidir; sızdırılırsa atlatılır.

**CFI (Control-Flow Integrity) ve donanım destekli akış koruması:** Dolaylı çağrıların ve dönüşlerin yalnızca meşru hedeflere gitmesini zorlayarak ROP/JOP zincirlerini kırmayı amaçlar. Bazı modern işlemciler dönüş adreslerini ayrı bir gölge yığıtta (shadow stack) tutan donanım mekanizmaları sunar; bu, dönüş adresinin sessizce değiştirilmesini tespit eder.

**Bellek-güvenli diller ve güvenli API'ler:** Kök nedeni ortadan kaldırmanın en kalıcı yolu, sınır kontrolünü dile ya da kütüphaneye yaptırmaktır. Sınır denetimi yapan dizge fonksiyonlarını kullanmak, ya da sahiplik ve ödünç alma modeliyle bellek güvenliğini derleme zamanında garanti eden dilleri tercih etmek, taşma sınıfını büyük ölçüde yok eder.

Sağlam bir savunma bu katmanların hiçbirine tek başına güvenmez; NX, ASLR, canary ve CFI birlikte kullanıldığında saldırganın atması gereken adım sayısını ve ihtiyaç duyduğu ön bilgiyi (özellikle bir bellek sızıntısını) katlar.

## Yaygın Hatalar

- **Tampon boyutunu bilmeyen fonksiyonlara güvenmek:** Kaynağın sonunu arayan, hedef sınırını umursamayan kopyalama ve birleştirme fonksiyonları taşmaların baş kaynağıdır. "Bu girdi hiç bu kadar uzun olmaz" varsayımı, saldırganın tam olarak sınadığı varsayımdır.
- **İşaretçi aritmetiğinde bir-hata (off-by-one):** Bir bayt fazla yazmak bile, komşu değişkeni, saklanan frame pointer'ın en düşük baytını veya bir uzunluk alanını bozarak sömürülebilir bir duruma yol açabilir.
- **Serbest bıraktıktan sonra işaretçiyi sıfırlamamak:** `free` sonrası işaretçiyi kullanılamaz hale getirmemek `use-after-free` ve çift serbest bırakma (double free) açıklarının kapısını aralar.
- **Savunmaların açık olduğunu varsaymak:** ASLR, NX ve stack koruma her zaman ve her derleme bayrağında etkin değildir. Üretim ikililerinin gerçekten bu korumalarla derlendiğini doğrulamamak yaygın bir gözden kaçırmadır.
- **Platform çağrı konvansiyonunu karıştırmak:** Bir platformun register atamalarını başka platformda varsaymak, hem exploit geliştirmede hem de düşük seviyeli entegrasyonda sessiz ve tehlikeli hatalar üretir.
- **İşaretsiz/işaretli tamsayı karışıklığı:** Bir boyut hesabında işaretli bir değerin negatife düşüp devasa bir işaretsiz değere dönüşmesi, sınır kontrolünü baypas ederek taşmaya zemin hazırlar.

## En İyi Pratikler

- **Sınır denetimini asla girdiye bırakmayın.** Her kopyalama ve tahsis işleminde hedef kapasitesini açıkça hesaplayın ve zorlayın; boyut hesaplarında taşmayı (integer overflow) ayrıca kontrol edin.
- **Derleyicinin sunduğu tüm koruma katmanlarını etkinleştirin.** Stack koruma, non-executable bellek, tam ASLR/PIE ve varsa CFI ile shadow stack özelliklerini üretim derlemelerinde açık tutun ve ürettiğiniz ikilide gerçekten var olduklarını doğrulayın.
- **Mümkün olan yerde bellek-güvenli dil veya güvenli soyutlamalar kullanın.** Yeni bileşenlerde sınır güvenliğini dile devretmek, bütün bir açık sınıfını tasarımdan kaldırır.
- **En az ayrıcalık ve izolasyon uygulayın.** Bir bellek açığı sömürüldüğünde etkisini sınırlamak için süreç ayrıcalıklarını düşürün, sandbox ve ayrık süreç mimarilerini değerlendirin.
- **Güvenlik açısından hassas sırları register/stack yaşam döngüsüne göre yönetin.** Anahtar gibi hassas verileri kullandıktan hemen sonra bellekten temizleyin; derleyicinin bu temizliği optimize edip atmasını engelleyen yöntemleri tercih edin.
- **Analizi varsayıma değil kanıta dayandırın.** Bir ikilinin çağrı konvansiyonunu, savunma durumunu ve stack düzenini disassembly ve dinamik analizle doğrulayın; belgelenmiş kural ile derlenmiş gerçek arasında fark olabileceğini daima aklınızda tutun.

## Sonuç

Bellek yerleşimi ve çağrı konvansiyonları, kuru bir mimari ayrıntı değil; hem güvenliğin hem de saldırının üzerine kurulduğu zemindir. Text, data, BSS, heap ve stack bölütlerinin neden ayrıldığını, register'ların hangi rolleri üstlendiğini ve bir fonksiyon çağrısının stack'te tam olarak ne bıraktığını kavrayan bir uzman, bir `buffer overflow`u da, onu durduran `stack canary`yi de, o canary'yi atlatmaya çalışan bir bilgi sızıntısını da aynı netlikte görür. Savunmanın gücü tek bir mekanizmadan değil, bu haritayı saldırgandan daha iyi okumaktan ve katmanlı korumaları doğru biçimde bir araya getirmekten gelir.
