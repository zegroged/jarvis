# Return-Oriented Programming (ROP)

## Tanım

Return-Oriented Programming (ROP), saldırganın hedef sürece **hiçbir yeni makine kodu enjekte etmeden**, sürecin belleğinde **zaten var olan** kod parçalarını (gadget) art arda çalıştırarak keyfi bir hesaplama gerçekleştirdiği bir sömürü (exploitation) tekniğidir. Klasik stack overflow saldırılarında saldırgan, stack'e shellcode yazıp dönüş adresini (return address) o shellcode'a yönlendirirdi. Modern işletim sistemlerinde stack ve heap gibi veri bölgeleri **çalıştırılamaz (non-executable)** işaretlendiği için bu klasik yaklaşım artık çalışmaz. ROP tam da bu savunmayı aşmak için doğmuştur: veri yazma yasağını hiç ihlal etmeden, sadece **var olan çalıştırılabilir kodu yeni bir sırayla** yürütür.

ROP'un temel içgörüsü şudur: Bir programın `.text` bölümü ve bağlı kütüphaneler (özellikle `libc`) yüzlerce kilobayt hazır, çalıştırılabilir makine kodu içerir. Saldırgan bu kodu **komut komut** değil, **komut dizisi (gadget) düzeyinde** yeniden kullanır. Her gadget, birkaç faydalı komutun ardından bir `ret` (dönüş) komutuyla biten küçük bir kod parçasıdır. Saldırgan, stack'i özenle kurgulayarak bu gadget'ları bir zincir hâlinde peş peşe tetikler. Bu yüzden teknik "return-oriented" — yani `ret` komutunun akışı yönlendirmesine dayalı — olarak adlandırılır.

ROP, kod enjeksiyonunu (code injection) kod yeniden kullanımına (code reuse) dönüştürerek W^X / DEP / NX gibi savunmaların temel varsayımını çürütür. Bu nedenle sadece bir teknik değil, aynı zamanda bir sömürü paradigmasıdır; ret2libc onun en basit hâli, tam gadget zinciri ise Turing-tam bir uzantısıdır.

## Kök Neden: Neden ROP Mümkün Oluyor?

ROP'un neden var olduğunu anlamak için önce hangi savunmayı aştığını anlamak gerekir.

### NX / DEP / W^X'in doğuşu

2000'lerin başında en yaygın sömürü yöntemi, stack tabanlı buffer overflow ile stack'e shellcode yazmak ve dönüş adresini bu shellcode'a yönlendirmekti. Buna karşı üreticiler donanım destekli bir savunma getirdi: **NX bit** (No-eXecute; Intel'de XD, AMD'de NX). İşletim sistemi bu biti kullanarak her bellek sayfasını "yazılabilir ama çalıştırılamaz" ya da "çalıştırılabilir ama yazılamaz" olarak işaretleyebilir. Bu ilkeye **W^X** (Write XOR eXecute) denir; Windows'ta **DEP** (Data Execution Prevention), Linux'ta genelde **NX** olarak anılır. Sonuç: stack ve heap gibi saldırganın veri yazabildiği bölgeler artık çalıştırılamaz. Enjekte edilen shellcode'a atlandığında CPU bir erişim ihlali (segmentation fault) üretir.

Ama bu savunmanın kritik bir boşluğu vardır: **Program kodunun kendisi hâlâ çalıştırılabilir olmak zorundadır.** `.text` bölümü ve `libc` gibi kütüphaneler doğaları gereği çalıştırılabilir işaretlidir. NX, "veriyi çalıştırma" der ama "var olan kodu yeni bir sırayla çalıştırma" konusunda hiçbir şey söyleyemez. İşte ROP bu boşluğa yerleşir.

### `ret` komutunun akış kontrolünü stack'e devretmesi

Asıl kök neden mimari bir gerçektir: x86/x86-64'te `ret` komutu, stack'in tepesindeki değeri alır (pop eder) ve program sayacına (RIP/EIP) yazar. Yani **dönüş adresi verinin içindedir, stack'tedir.** Eğer saldırgan bir overflow ile stack'i kontrol edebiliyorsa, `ret` komutunun nereye döneceğini de kontrol eder.

Bir tek dönüş adresini ele geçirmek klasik saldırıdır. ROP'un dehası, bunu **zincirlemesidir**: Saldırgan stack'e arka arkaya birçok adres yerleştirir. Çalışan ilk gadget birkaç komut yürütüp kendi `ret`'ine ulaştığında, bu `ret` stack'ten **bir sonraki gadget'ın adresini** çeker ve ona atlar. O gadget da kendi `ret`'iyle biter ve zincir böyle ilerler. Stack, adeta bir "program" hâline gelir; her `ret`, bu programın bir sonraki komutuna geçiş yapan bir "yer imi" işlevi görür. Bu yüzden ROP zincirinde stack, saldırganın gerçek talimat akışını taşıyan yapıdır.

### Neden gadget'lar her yerde bulunur?

x86, **değişken uzunlukta komut kodlaması** (variable-length instruction encoding) kullanan bir mimaridir. Bir komut 1 ile 15 bayt arasında olabilir. Bu, ilginç bir yan etki doğurur: İcra akışını **komutun ortasından** başlatırsanız, işlemci baytları tamamen farklı komutlar olarak yorumlayabilir. Yani derleyicinin ürettiği "resmî" komutların dışında, kod bölümünde **niyet edilmemiş (unintended) gadget'lar** da mevcuttur. Bu, gadget arzını devasa boyutlara çıkarır; yeterince büyük bir ikili dosyada neredeyse her ihtiyaca uygun gadget bulunabilir. ARM gibi sabit uzunluklu mimarilerde bu "hizasız çözümleme" yoktur, dolayısıyla gadget arzı daha kısıtlıdır ama yine de ROP mümkündür.

## Gadget Nedir? Anatomisi ve Türleri

Bir **gadget**, bir veya birkaç faydalı komutun ardından bir akış-yönlendirme komutuyla (genellikle `ret`) biten kısa bir kod dizisidir. Amaç, `ret`'in zincirin bir sonraki halkasına geçişi otomatik yapmasıdır.

En temel ve en değerli gadget türü, bir register'a stack'ten değer yükleyen türdür:

```
pop rdi
ret
```

Bu gadget çalıştığında, stack'in tepesindeki değeri `rdi`'ye çeker, sonra `ret` ile bir sonraki gadget'a döner. Saldırgan stack'i şöyle kurar: önce `pop rdi; ret` gadget'ının adresi, hemen ardından `rdi`'ye yüklenmesini istediği değer, sonra bir sonraki gadget'ın adresi. Böylece register'lar tek tek istenen değerlerle doldurulur. x86-64 System V çağrı sözleşmesinde (calling convention) ilk argümanlar `rdi, rsi, rdx, rcx, r8, r9` register'larından geçtiği için `pop rdi; ret`, `pop rsi; ret` gibi gadget'lar bir fonksiyon çağrısı kurmanın anahtarıdır.

Gadget türlerini işlevlerine göre şöyle gruplayabiliriz:

- **Yükleme (load) gadget'ları:** `pop reg; ret`. Register'lara sabit değer koyar. Zincirin en çok kullanılan yapı taşıdır.
- **Bellek yazma gadget'ları:** `mov [reg1], reg2; ret`. Bir register'daki değeri, başka bir register'ın işaret ettiği belleğe yazar. Stack dışı bir bölgeye (ör. yazılabilir `.data`) veri yerleştirmek için kritiktir; `/bin/sh` gibi bir dizeyi belleğe yazmak buna örnektir.
- **Aritmetik gadget'lar:** `add`, `sub`, `xor` ile biten diziler. İhtiyaç duyulan ama doğrudan pop edilemeyen değerleri hesaplamak için kullanılır.
- **Syscall/çağrı gadget'ları:** `syscall; ret` (x86-64) veya `int 0x80` (x86). Register'lar doğru kurulduktan sonra doğrudan çekirdek çağrısı yapar; ret2libc'ye alternatif olarak "ret2syscall" kurmayı sağlar.
- **Yığın döndürücü (stack pivot) gadget'ları:** `xchg rsp, reg; ret` veya `mov rsp, reg; ret` gibi. Stack pointer'ı saldırganın kontrol ettiği başka bir bölgeye taşır. Overflow alanı dar olduğunda zinciri heap gibi geniş bir alana "pivotlamak" için kullanılır.

Gadget'ları elle aramak zahmetlidir; pratikte `ROPgadget`, `ropper` veya `pwntools`'un ROP modülü gibi araçlar ikili dosyayı tarayıp uygun gadget'ları listeler. Yine de iyi bir saldırgan, hangi gadget'ın *neden* seçildiğini anlar: register kirlenmesi (bir gadget'ın istemediğiniz bir register'ı da bozması), gadget'ın `ret`'ten önce ekstra `pop` yapması (bu durumda stack'e "dolgu" değerler eklemek gerekir) gibi ayrıntılar zincirin çalışıp çalışmayacağını belirler.

## NX Bypass'in Mantığı

NX'in aştığı şey açıktır: veri çalıştırılamaz. ROP bunu, **hiç veri çalıştırmayarak** aşar. Zincirdeki her adres, halihazırda çalıştırılabilir işaretli bir kod bölgesine (`.text`, `libc`) işaret eder. CPU asla saldırganın yazdığı baytları komut olarak yorumlamaz; yalnızca saldırganın *seçtiği sırada* var olan komutları yürütür. Stack'te duran şey ise **veri**dir — adresler ve argümanlar — ve bu veri hiçbir zaman çalıştırılmaz, sadece `ret` tarafından okunur. Böylece W^X ilkesi teknik olarak hiç ihlal edilmez; savunma "yasak" dediği şeyi (veri çalıştırma) görmez bile.

Bu, savunma ve saldırı arasındaki kedi-fare oyununun temel dersidir: Bir savunma bir varsayıma dayanır (burada: "kötü kod ancak enjekte edilerek çalışır"), saldırgan da o varsayımı geçersiz kılan bir yol bulur (kodu enjekte etmeden yeniden kullanmak). NX'e karşı ROP'un çıkışı, güvenlik mimarisinin neden **katmanlı** olması gerektiğini gösterir: Tek başına NX yetmez; ASLR, stack canary ve CFI gibi ek katmanlarla desteklenmelidir.

## ret2libc: En Basit Kod Yeniden Kullanımı

**ret2libc**, ROP'un tarihsel ve kavramsal atasıdır; aslında tam bir gadget zincirine ihtiyaç duymadan, tek bir kütüphane fonksiyonunu doğrudan çağırma tekniğidir. Fikir şudur: Enjekte edilen shellcode çalıştırılamıyorsa, neden `libc` içindeki hazır bir fonksiyonu — örneğin `system("/bin/sh")` — çağırmayalım? `libc` çalıştırılabilir olduğu için NX buna engel olamaz.

Saldırının iskeleti mimariye göre değişir:

**32-bit (x86) ret2libc:** Çağrı sözleşmesi argümanları stack üzerinden geçirdiği için düzenleme sezgiseldir. Overflow ile stack şöyle kurulur:
- Dönüş adresi olarak `system`'in adresi,
- Onun hemen ardından `system` döndüğünde gidilecek sahte dönüş adresi (genellikle `exit` ki temiz çıksın),
- Onun ardından `system`'in argümanı olacak `"/bin/sh"` dizesinin adresi.

`system` çağrıldığında, kendi bakış açısından stack'i normal bir çağrı gibi görür: hemen üstünde dönüş adresi, onun üstünde ilk argüman.

**64-bit (x86-64) ret2libc:** Burada argümanlar register'lardan geçtiği için ret2libc'nin kendisi bir mini ROP zinciri gerektirir. `system("/bin/sh")` çağırmak için önce `pop rdi; ret` gadget'ıyla `rdi`'ye `"/bin/sh"` dizesinin adresini yüklemek, sonra `system`'in adresine dönmek gerekir. Yani 64-bit dünyada ret2libc ile ROP arasındaki sınır bulanıklaşır; ret2libc pratikte küçük bir ROP zinciridir.

`"/bin/sh"` dizesinin adresi çoğu zaman `libc`'nin kendi içinde hazır bulunur (birçok `libc` bu diziyi gömülü içerir), bu da işi kolaylaştırır. Bulunmazsa, bir bellek-yazma gadget'ı ile diziyi yazılabilir bir bölgeye kurmak gerekir.

Bir de kritik bir zorluk vardır: `system` gibi fonksiyonların **adresi** ASLR nedeniyle her çalıştırmada değişir. ret2libc'nin çalışması için saldırganın `libc`'nin bellekteki taban adresini bilmesi ya da sızdırması gerekir — bunu bir sonraki bölümde ele alacağız.

## Zincir Kurma: Adım Adım Mantık

Tam bir ROP zinciri kurmak, üç sorunun sırayla çözülmesidir: (1) akış kontrolünü ele geçirmek, (2) gadget'ları bulmak, (3) onları doğru sırada stack'te dizmek.

**1. Akış kontrolü.** Genellikle bir stack buffer overflow ile dönüş adresinin üzerine yazılır. Bu noktada `ret`, artık saldırganın verisini okuyacaktır. Overflow'a kadar olan "dolgu" (padding) miktarı — buffer'ın başından dönüş adresine kadar olan tam uzaklık — dikkatle belirlenmelidir; bir bayt hata zinciri bozar.

**2. Amacı belirleme.** Nihai hedef genellikle bir kabuk (shell) elde etmektir. Klasik hedef: `execve("/bin/sh", NULL, NULL)` syscall'ını çağırmak. Bunun için register'ların şöyle olması gerekir (x86-64 System V): `rax = 59` (execve numarası), `rdi = "/bin/sh" adresi`, `rsi = 0`, `rdx = 0`, ardından `syscall`.

**3. Gadget seçimi ve stack düzeni.** Yukarıdaki register durumunu kurmak için tipik bir zincir şöyle görünür (kavramsal):

```
[pop rdi; ret]      -> rdi'ye "/bin/sh" adresini yükle
["/bin/sh" adresi]
[pop rsi; ret]      -> rsi = 0
[0]
[pop rdx; ret]      -> rdx = 0
[0]
[pop rax; ret]      -> rax = 59
[59]
[syscall; ret]      -> execve tetiklenir
```

Stack'in bu düzeninde her `ret`, bir sonraki gadget adresini pop eder; her `pop reg` ise onun altındaki değeri alır. Yani gadget adresleri ve veri değerleri **dönüşümlü** dizilir. Bu titiz dizilim ROP zincirinin özüdür.

Gerçek dünyada iş nadiren bu kadar temizdir. Sık karşılaşılan komplikasyonlar:
- **İstenen gadget yok.** Örneğin `pop rdx; ret` bulunamayabilir. O zaman `rdx`'i dolaylı yoldan kuran (ör. `xor edx, edx` içeren) alternatif gadget'lar aranır.
- **Kirli gadget'lar.** Bir gadget `pop rdi; pop rbp; ret` şeklindeyse, `rbp` için de stack'e bir dolgu değer koymak gerekir, yoksa hizalama bozulur.
- **Stack hizalaması.** x86-64'te bazı `libc` fonksiyonları (SSE komutları nedeniyle) çağrıldığında `rsp`'nin 16'ya hizalı olmasını bekler. Zincir bunu bozarsa `movaps` gibi komutlarda çökme olur. Çözüm: zincire fazladan tek bir `ret` gadget'ı ekleyerek hizayı düzeltmek.

### ASLR ile başa çıkmak: sızdırma ve pivot

Modern sistemlerde **ASLR** (Address Space Layout Randomization) `libc` ve genellikle ikilinin (PIE ise) taban adreslerini rastgeleleştirir. Bu, sabit adresleri zincire gömme imkânını ortadan kaldırır. Pratik çözüm iki aşamalıdır:

- **Sızdırma (leak) aşaması:** Önce bir bilgi sızıntısı (ör. bir format string açığı ya da `puts(puts@got)` gibi bir çağrıyla GOT'taki gerçek `libc` adresinin ekrana yazdırılması) kullanılarak `libc`'nin bellekteki gerçek taban adresi öğrenilir. Bilinen bir fonksiyonun sızdırılan adresinden, o `libc` sürümünün bilinen ofset'i çıkarılarak taban hesaplanır.
- **İkinci aşama zinciri:** Taban adresi bilindikten sonra, tüm gadget ve fonksiyon adresleri bu taban üzerine ofset eklenerek dinamik hesaplanır ve asıl `system`/`execve` zinciri kurulur.

Overflow alanı çok darsa (ör. sadece birkaç gadget sığıyorsa), bir **stack pivot** ile `rsp` daha geniş, saldırganın kontrol ettiği bir bölgeye (çoğu zaman bir heap tamponu) taşınır ve asıl uzun zincir orada icra edilir.

## Sömürü ve Savunma: İki Taraf Birlikte

### Sömürü tarafının özeti

ROP saldırısının başarısı üç koşula bağlıdır: (a) saldırganın program akışını ele geçirebileceği bir bellek güvenliği açığı (klasik olarak stack overflow ama heap-bazlı akış ele geçirme de olabilir); (b) yeterli gadget arzı sunan çalıştırılabilir kod; (c) ASLR varsa adresleri çözecek bir sızıntı. Bu üçünden herhangi biri kapatılırsa saldırı ciddi biçimde zorlaşır. Bu, savunmanın nereye odaklanması gerektiğini de gösterir.

### Savunma tarafı: katman katman

**1. Kök nedeni kes — bellek güvenliği.** ROP, bir bellek bozulması (memory corruption) açığının *sömürü aşamasıdır*, kaynağı değildir. En kalıcı savunma, overflow'un hiç oluşmamasıdır. Rust, Go gibi bellek-güvenli dillere geçmek; C/C++'ta ise sınır denetimli API'ler kullanmak, `strcpy` yerine güvenli alternatifler, `-D_FORTIFY_SOURCE` gibi derleyici sertleştirmeleri ve statik/dinamik analiz (ASan) uygulamak kök nedeni ortadan kaldırır.

**2. Stack canary (stack protector).** Derleyici, dönüş adresinin hemen öncesine rastgele bir "kanarya" değeri yerleştirir ve fonksiyon dönmeden önce bu değerin bozulup bozulmadığını denetler. Klasik doğrusal bir stack overflow, dönüş adresine ulaşmadan kanaryayı ezmek zorundadır; denetim başarısız olur ve program dönüş gerçekleşmeden sonlanır. Bu, ROP zincirinin tetikleneceği `ret`'i baştan engeller. Sınırı: Kanarya değeri sızdırılırsa (bir bilgi sızıntısıyla) ya da dönüş adresi doğrudan (canary'yi atlayarak) yazılabiliyorsa aşılabilir.

**3. ASLR + PIE.** ASLR, gadget ve fonksiyon adreslerini rastgeleleştirerek saldırganı bir sızıntı bulmaya mecbur eder. İkiliyi **PIE** (Position Independent Executable) olarak derlemek, ikilinin kendi `.text` bölümünü de rastgeleleştirir; böylece PIE olmayan ikililerdeki sabit gadget adresleri ortadan kalkar. 64-bit'te entropi yüksek olduğu için ASLR'ı kaba kuvvetle aşmak pratik değildir — bu yüzden asıl mesele bilgi sızıntılarını kapatmaktır.

**4. CFI (Control-Flow Integrity).** ROP, meşru olmayan akış geçişlerine (bir fonksiyonun ortasına atlama, geçersiz dönüş hedefleri) dayanır. CFI, dolaylı çağrı ve dönüşlerin yalnızca meşru hedeflere gitmesini zorlar. Donanım destekli bir biçim olan **Intel CET**, iki mekanizma sunar: **Shadow Stack**, dönüş adreslerinin ayrı, korumalı bir kopyasını tutar ve `ret` sırasında gerçek stack'teki adresle karşılaştırır — uyuşmazlık ROP'u anında yakalar; **IBT** (Indirect Branch Tracking) ise dolaylı atlamaların yalnızca işaretli hedeflere gitmesini zorlar. ARM tarafında **PAC** (Pointer Authentication) dönüş adreslerini kriptografik olarak imzalayarak benzer koruma sağlar. Shadow stack, ROP'a karşı özellikle güçlüdür çünkü tekniğin can damarı olan "stack'ten sahte dönüş adresi okuma"yı doğrudan hedefler.

**5. Gadget arzını azaltma.** Az kod = az gadget. Gereksiz kütüphane bağımlılıklarını çıkarmak, statik linklemede kullanılmayan kodu elemek (dead code elimination) ve `libc`'yi minimize etmek saldırganın malzemesini kısıtlar.

Bu savunmaların hiçbiri tek başına mutlak değildir; ama birlikte uygulandıklarında saldırının maliyetini katlar. Örneğin ASLR + PIE saldırganı sızıntıya mecbur bırakır, kanarya sızıntıyı da zorlaştırır, shadow stack ise sızıntı olsa bile zincirin tetiklenmesini engeller. Derinlemesine savunma (defense in depth) ROP'a karşı tam olarak bu yüzden gereklidir.

## Yaygın Hatalar

**Saldırı/analiz tarafında:**
- **Yanlış offset hesabı.** Buffer başından dönüş adresine kadarki uzaklığın bir bayt bile yanlış olması zinciri çökertir. Cyclic pattern (De Bruijn dizileri) ile offset'i kesin ölçmek yerine göz kararı tahmin etmek en sık hatadır.
- **Stack hizalama ihmali.** 64-bit'te `movaps` çökmelerini "gadget yanlış" sanıp saatlerce yanlış yerde hata aramak; oysa çözüm tek bir `ret` ekleyerek 16-bayt hizayı düzeltmektir.
- **Yanlış `libc` sürümü.** Sızdırılan adresten taban hesaplarken hedefteki `libc`'nin ofsetleri yerine kendi makinesindekini kullanmak. Ofsetler sürüme özgüdür.
- **Null bayt sorununu gözden kaçırmak.** Girdi bir dize kopyalama fonksiyonundan geçiyorsa (ör. `strcpy`), zincirdeki `0x00` içeren adresler dizeyi erkenden keser.

**Savunma tarafında:**
- **Tek katmana güvenmek.** "NX açık, güvendeyiz" sanmak. NX tek başına ROP'u durdurmaz; bütün örneğimizin çıkış noktası budur.
- **Kanaryayı doğru yerde kullanmamak.** Derleyici bayraklarını her fonksiyona değil sadece bazılarına uygulamak ya da hiç etkinleştirmemek.
- **PIE'yi unutmak.** ASLR'ı açık sanıp ikiliyi PIE derlemeyince, ikilinin kendi gadget'ları sabit adreste kalır ve ASLR'ın koruması büyük ölçüde delinir.
- **Bilgi sızıntılarını hafife almak.** Format string, unicode/uninitialized bellek okuması gibi görünüşte "küçük" açıklar, ASLR'ı çökerten anahtardır; bunlar öncelikli kapatılmalıdır.

## En İyi Pratikler

- **Kök nedene odaklan:** ROP, bellek bozulması açığının sonucudur. Uzun vadede en etkili yatırım, bellek-güvenli diller ve güvenli kodlama disiplinidir. Sömürü tekniğini engellemeye çalışmadan önce açığın kendisini yok etmeye çalış.
- **Derleyici sertleştirmelerini eksiksiz aç:** Stack protector, `_FORTIFY_SOURCE`, PIE, RELRO (özellikle **Full RELRO**, GOT'u salt-okunur yaparak GOT-overwrite tabanlı yönlendirmeleri kapatır), NX. Bunlar düşük maliyetli, yüksek getirilidir.
- **Donanım korumalarını benimse:** Mümkün olan platformlarda Intel CET (shadow stack + IBT) ve ARM PAC'i etkinleştir. Bunlar ROP'un tam kalbini hedefler.
- **Bilgi sızıntılarını birinci sınıf açık say:** ASLR'ın tüm gücü sızıntı olmamasına bağlıdır. Format string, out-of-bounds read, uninitialized memory gibi açıkları düşük şiddetli görme; onlar ROP zincirinin ilk basamağıdır.
- **Saldırı yüzeyini küçült:** Gereksiz kod, kütüphane ve `setuid` ikilileri gadget arzıdır ve hedeftir. Az kod, az gadget.
- **Kırmızı takım ile doğrula:** Savunmaların gerçekten çalıştığını varsaymak yerine, `pwntools`/`ROPgadget`/`ropper` gibi araçlarla kendi ikililerini test et. Bir savunmanın etkisini en iyi, onu aşmaya çalışarak anlarsın.
- **Katmanları birlikte düşün:** Hiçbir tekil savunma yeterli değildir. NX + ASLR/PIE + canary + Full RELRO + shadow stack birlikte, saldırının her aşamasına ayrı bir engel koyar. ROP'a karşı gerçek güvenlik, bu katmanların kesişiminde doğar.

## Kapanış

ROP, güvenlikte bir varsayımın nasıl çürütülebileceğinin ders kitabı örneğidir: "Kötü kod ancak enjekte edilerek çalışır" varsayımı NX'i doğurdu; ROP ise kodu hiç enjekte etmeden, var olanı yeniden kullanarak bu varsayımı geçersiz kıldı. Bu döngü — savunma bir varsayıma yaslanır, saldırı o varsayımı hedefler — modern istismarın motorudur. ROP'u anlamak, yalnızca bir tekniği öğrenmek değil; savunmanın neden katmanlı, kök nedene yönelik ve sürekli sınanan bir mühendislik disiplini olması gerektiğini kavramaktır. Shadow stack ve PAC gibi donanım korumaları bugün ROP'un işini ciddi biçimde zorlaştırsa da, saldırganların JOP (jump-oriented) ve COP (call-oriented) gibi varyantlara yönelmesi, bu kedi-fare oyununun süreceğini gösteriyor.
