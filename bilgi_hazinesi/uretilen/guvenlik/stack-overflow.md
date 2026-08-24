# Stack Buffer Overflow: Return Adresi Ezme, Shellcode ve Klasik Sömürü

## Giriş ve Tanım

Stack buffer overflow (yığın tampon taşması), bilgisayar güvenliğinin en eski ama hâlâ öğretici değeri en yüksek zafiyet sınıflarından biridir. Kısaca söylemek gerekirse: bir programın çağrı yığını (call stack) üzerinde yer alan sabit boyutlu bir tamponun (buffer) kapasitesinden daha fazla veriyle doldurulması ve bu fazla verinin, tamponun bittiği yerin ötesindeki bellek hücrelerini ezmesidir. "Overflow" derken kelimenin tam anlamıyla verinin taşıp komşu bellek alanlarına akmasından bahsediyoruz.

Bu zafiyetin tehlikeli olmasının sebebi, taşan verinin yalnızca zararsız komşu değişkenleri değil, programın kontrol akışını belirleyen kritik verileri de ezebilmesidir. Bunların en önemlisi return address (dönüş adresi), yani bir fonksiyon işini bitirdiğinde CPU'nun geri döneceği talimatın adresidir. Saldırgan bu adresi kontrol edebilirse, programın nereye "geri döneceğini" belirleyebilir; bu da çoğu zaman keyfi kod çalıştırma (arbitrary code execution) anlamına gelir.

Bu makalede önce yığının neden bu şekilde çalıştığını (kök neden), sonra somut bir örnek üzerinden taşmanın nasıl gerçekleştiğini, ardından hem sömürü mantığını hem de savunma tekniklerini, yaygın hataları ve modern en iyi pratikleri inceleyeceğiz. Amacım, ezberletmek değil "neden böyle oluyor" sorusunu cevaplamak.

## Kök Neden: Yığın Neden Bu Şekilde Çalışır?

Bu zafiyeti anlamak için önce çağrı yığınının mimari düzeyde nasıl kurgulandığını görmek gerekir. Modern işlemcilerde (x86/x86-64 üzerinden anlatacağım, çünkü klasik sömürü literatürü büyük ölçüde buradan doğdu) her fonksiyon çağrısı, yığın üzerinde bir stack frame (yığın çerçevesi) oluşturur.

### Yığının Mimari Yapısı

Yığın, bellekte yüksek adreslerden düşük adreslere doğru büyür. Yani yeni veri eklendikçe stack pointer (yığın işaretçisi, x86'da `esp`, x86-64'te `rsp`) daha küçük adreslere doğru iner. Buna karşılık, bir tampona veri yazma işlemi (örneğin bir string kopyalama) düşük adreslerden yüksek adreslere doğru ilerler. İşte bu iki yönün zıt olması, klasik stack overflow'un temel sebebidir: tampon içinde ileri doğru yazarken, aslında return address gibi "daha sonra yazılmış" (yüksek adreste duran) kritik verilere doğru ilerlersiniz.

Bir fonksiyon çağrıldığında yığın çerçevesi tipik olarak şu bileşenleri barındırır (adres sırası düşükten yükseğe doğru):

- Yerel değişkenler ve tamponlar (yerel `char buf[64]` gibi)
- Kaydedilmiş base pointer (`ebp`/`rbp`) — çağıran fonksiyonun çerçeve tabanı
- Return address — fonksiyon bittiğinde geri dönülecek adres
- Fonksiyona geçirilen argümanlar (çağrı kuralına göre değişir)

`call` talimatı çalıştığında CPU, bir sonraki talimatın adresini otomatik olarak yığına iter (push eder); bu, return address'tir. Fonksiyonun sonundaki `ret` talimatı ise yığının tepesindeki değeri alıp `eip`/`rip` (talimat işaretçisi) içine yükler ve oraya atlar. Burada kritik nokta şudur: `ret` talimatı, yığından okuduğu değerin meşru bir dönüş adresi mi yoksa saldırganın enjekte ettiği bir çöp mü olduğunu sorgulamaz. CPU için yığın sadece bayttır; anlamı yazılım katmanının kurgusudur.

### Neden Sınır Kontrolü Yok?

Asıl kök neden mimaride değil, dilde ve API tasarımındadır. C ve C++ gibi diller bellek güvenliğini (memory safety) garanti etmez. `char buf[64]` tanımladığınızda, dil size bu tamponun yalnızca 64 bayt olduğunu hatırlatmaz; `strcpy`, `gets`, `sprintf`, `memcpy` gibi klasik fonksiyonlar hedef tamponun boyutunu bilmez ve dolayısıyla kontrol etmez. Bu fonksiyonlar veriyi, kaynak bitene (veya sabit bir uzunluğa) kadar kopyalar. Kaynak hedeften büyükse, fazlası komşu belleğe taşar.

Bu bilinçli bir tasarım tercihiydi: performans ve programcıya tam kontrol vermek uğruna güvenlik yükü programcıya bırakıldı. Sorun, insanların hata yapmasıdır. İşte "neden hâlâ bu kadar yaygın" sorusunun cevabı burada: zafiyet, tek bir hatalı satırdan (eksik bir sınır kontrolünden) doğar ve bu satır milyonlarca kod satırının içinde kolayca gizlenir.

## Somut Örnek: Taşma Nasıl Gerçekleşir

Aşağıdaki basit ama tipik olarak zafiyetli C fonksiyonunu ele alalım:

```c
#include <string.h>
#include <stdio.h>

void islev(char *girdi) {
    char buf[64];
    strcpy(buf, girdi);   // Sınır kontrolü YOK
    printf("Girdi: %s\n", buf);
}

int main(int argc, char **argv) {
    islev(argv[1]);
    return 0;
}
```

Burada `buf` yalnızca 64 baytlık bir tampondur. Ancak `strcpy`, `girdi` işaret ettiği string'i null bayta (`\0`) rastlayana kadar kopyalar. Eğer kullanıcı 64 bayttan uzun bir argüman verirse, kopyalama `buf`'un sınırını aşar.

Bellek düzenini kabaca düşünelim (x86 32-bit, adresler yukarı çıktıkça artar):

```
[ buf[64] ][ kaydedilmis ebp (4 bayt) ][ return address (4 bayt) ]
   ^--- yazma buradan baslar ve saga (yuksek adreslere) dogru ilerler --->
```

Saldırgan 64 bayt "dolgu" (padding) yazdıktan sonra 4 baytlık kaydedilmiş `ebp`'yi, ardından 4 baytlık return address'i ezer. Örneğin 68 bayt çöp + kendi seçtiği 4 baytlık bir adres gönderirse, fonksiyon `ret` ile döndüğünde CPU o adrese atlar. Saldırgan artık programın kontrol akışını ele geçirmiştir.

Bu davranışı kanıtlamanın klasik yolu, kademeli olarak artan uzunlukta girdiler denemek ve programın hangi noktada çöktüğünü (segmentation fault) gözlemlemektir. Return address tam olarak ezildiğinde, çökme mesajındaki hatalı talimat adresi çoğu zaman gönderdiğiniz baytların bir yansımasıdır (örneğin `0x41414141`, ki bu ASCII'de "AAAA" demektir). Bu, ofseti (yani return address'in girdinin kaçıncı baytında olduğunu) bulmanın pratik bir işaretidir.

## Sömürü / İstismar Mantığı

Return address'i ezebilmek tek başına yeterli değildir; saldırgan onu *anlamlı* bir yere yönlendirmek ister. Klasik sömürünün amacı genellikle shellcode çalıştırmaktır.

### Shellcode Nedir?

Shellcode, saldırganın çalıştırmak istediği, genellikle makine diliyle yazılmış küçük ve bağımsız bir kod parçasıdır. İsmi, tarihsel olarak amacının çoğu zaman bir komut kabuğu (shell, örneğin `/bin/sh`) açmak olmasından gelir; böylece saldırgan hedef sistemde etkileşimli komut çalıştırabilir. Ancak shellcode her türlü işlemi yapabilir: bir port dinleyebilir (bind shell), saldırgana geri bağlantı kurabilir (reverse shell) veya başka bir yük indirebilir.

Shellcode'un iki önemli özelliği vardır. Birincisi, position-independent (konumdan bağımsız) olması gerekir; çünkü bellekte tam olarak nereye yerleşeceği önceden kesin bilinmez. İkincisi, klasik olarak null bayt (`\0`) içermemesi tercih edilir, çünkü string kopyalayan fonksiyonlar null baytı string sonu sanıp kopyalamayı erken keser. Bu yüzden shellcode yazarken belirli talimatlar, null bayt üretmeyecek şekilde seçilir (bad chars / kötü karakter eleme).

### Klasik "Stack'e Shellcode Enjekte Et ve Atla" Yaklaşımı

En eski ve en öğretici sömürü senaryosunda saldırgan tek bir girdinin içine şunları paketler:

1. **Shellcode** — çalıştırılacak makine kodu.
2. **Dolgu (padding)** — tamponu ve araya giren verileri doldurup return address'e ulaşmak için.
3. **Yeni return address** — shellcode'un yığındaki başlangıcını (veya yakınını) gösteren adres.

Fonksiyon döndüğünde `ret`, ezilmiş return address'i yükler ve doğrudan yığındaki shellcode'a atlar. Yürütme başlar. Bu, "kodun yığında çalıştırılabildiği" bir dünyada çalışır — ki bu, savunma bölümünde göreceğimiz gibi modern sistemlerde artık varsayılan değildir.

### NOP Sled: Belirsizliği Yönetmek

Saldırganın karşılaştığı pratik bir zorluk, shellcode'un yığındaki tam adresini kesin bilememektir; çünkü çevre değişkenleri, argümanlar ve diğer faktörler yığın adreslerini kaydırabilir. Bu belirsizliği aşmak için NOP sled (NOP kızağı) tekniği kullanılır.

NOP (no operation), hiçbir şey yapmayan, yürütmeyi bir sonraki talimata geçiren bir talimattır (x86'da tipik olarak `0x90` baytı). Saldırgan shellcode'un önüne uzun bir NOP dizisi koyar. Return address'i bu NOP bölgesinin *herhangi bir yerine* düşürebilirse, CPU NOP'ları birer birer "kayarak" geçer ve sonunda shellcode'a ulaşır. Böylece saldırganın tahmininin milimetrik kesin olması gerekmez; NOP bölgesi ne kadar genişse hedef o kadar büyük olur. Bu, "yaklaşık doğru" bir adresin bile işe yaramasını sağlayan zarif bir mühendislik hilesidir.

## Savunma: Zafiyeti Kıran Katmanlar

Klasik stack overflow sömürüsünün tarihi, aynı zamanda savunma tekniklerinin gelişim tarihidir. Her savunma, sömürünün bir varsayımını hedef alır. Bunları anlamak, hem saldırının hem de korunmanın mantığını netleştirir.

### 1. Stack Canary (Yığın Kanaryası)

İsmini madenlerdeki "grizu gazı kanaryalarından" alan bu teknik, derleyicinin fonksiyon girişinde tampon ile return address arasına bilinen (genellikle rastgele) bir değer yerleştirmesidir. Fonksiyon dönmeden hemen önce bu değer kontrol edilir. Eğer bir buffer overflow return address'e ulaşmışsa, yol üzerindeki canary değerini de ezmiş olacaktır. Kontrolde uyuşmazlık görülünce program güvenli şekilde sonlandırılır.

Mantığı şudur: return address'e ulaşmak için, ardışık bir yazma işlemi mutlaka canary'nin üzerinden geçmek zorundadır. Canary'yi bilmeden doğru değeri yeniden yazmak çok zordur. GCC'de bu tipik olarak `-fstack-protector` ailesindeki bayraklarla etkinleştirilir (kesin bayrak adlandırmalarının sürüme göre değiştiğini not düşerek, kavramsal olarak: stack protector'ın standart ve "strong" varyantları vardır). Bu savunma, ardışık taşmalara karşı etkilidir ama ör. keyfi yazma primitifi veya canary sızıntısı varsa aşılabilir.

### 2. NX / DEP (Çalıştırılamaz Yığın)

Klasik sömürünün en kritik varsayımı, shellcode'un yığında çalıştırılabilmesidir. NX bit (No-eXecute, Intel terminolojisinde XD, Windows'ta DEP — Data Execution Prevention) bu varsayımı kökten yıkar: bellek sayfaları hem yazılabilir hem çalıştırılabilir olamaz (W^X — Write XOR eXecute ilkesi). Yığın yazılabilirdir, dolayısıyla çalıştırılamaz olarak işaretlenir. Return address yığındaki shellcode'a atlasa bile, CPU o bölgede kod yürütmeyi reddeder ve süreç çöker.

Bu savunma o kadar etkili oldu ki, saldırganları tamamen yeni bir yaklaşıma zorladı: koddaki mevcut, zaten çalıştırılabilir parçaları kullanmak. Bu, ret2libc ve daha genel olarak ROP (Return-Oriented Programming) tekniklerini doğurdu. ROP'ta saldırgan yeni kod enjekte etmek yerine, programda veya kütüphanelerde zaten var olan küçük talimat dizilerini ("gadget"leri, genellikle `ret` ile biten kısa parçaları) yığındaki adres zinciriyle art arda çalıştırır. Yani W^X, kod *enjeksiyonunu* engeller ama kod *yeniden kullanımını* tamamen değil — bu yüzden tek başına yeterli değildir.

### 3. ASLR (Address Space Layout Randomization)

ROP ve ret2libc'nin çalışması için saldırganın atlayacağı adresleri (kütüphane fonksiyonlarını, gadget'ları, yığın konumunu) bilmesi gerekir. ASLR, süreç her başladığında bellek bölgelerinin (yığın, heap, paylaşımlı kütüphaneler, çoğu zaman ana çalıştırılabilir) yükleneceği taban adresleri rastgeleleştirir. Böylece saldırgan sabit bir adres varsayamaz.

ASLR'nin etkinliği entropinin miktarına bağlıdır; 64-bit sistemlerde rastgeleleştirme uzayı çok daha geniştir ve kaba kuvvet çok daha zordur. ASLR'yi tam etkili kılmak için çalıştırılabilirin de konumdan bağımsız derlenmesi gerekir (PIE — Position Independent Executable). ASLR'nin klasik zayıf noktası, bir bellek sızıntısı (info leak) zafiyetidir: saldırgan tek bir gerçek adresi sızdırabilirse, aynı kütüphanedeki diğer adresleri sabit ofsetlerle hesaplayabilir ve rastgeleleştirmeyi etkisiz hale getirebilir. Bu yüzden modern sömürü zincirleri sıklıkla "önce sızdır, sonra atla" mantığıyla iki aşamalıdır.

### 4. Derleyici ve Kütüphane Sertleştirmeleri

Modern derleyiciler ek koruma katmanları sunar. Örneğin `_FORTIFY_SOURCE`, derleme zamanında boyutu bilinen tamponlara yapılan `memcpy`/`strcpy` gibi çağrıları, çalışma zamanında sınır denetimi yapan güvenli varyantlarla değiştirebilir. RELRO (Relocation Read-Only), GOT (Global Offset Table) gibi yapıları salt-okunur yaparak belirli overwrite saldırılarını zorlaştırır. Bu katmanların hiçbiri tek başına mutlak değildir; güç, birlikte kullanıldıklarında ortaya çıkan derinlemesine savunmadadır (defense in depth).

### 5. Bellek-Güvenli Diller

En köklü savunma, kök nedeni ortadan kaldırmaktır. Rust, Go, Java, C# gibi diller ya çalışma zamanında sınır denetimi yapar ya da (Rust örneğinde) derleme zamanında sahiplik/ödünç alma modeliyle bellek güvenliğini büyük ölçüde garanti eder. Bu diller stack buffer overflow'u bir sınıf olarak neredeyse ortadan kaldırır (unsafe blokları veya FFI sınırları dışında). Yeni geliştirilen güvenlik-kritik bileşenler için C/C++ yerine bellek-güvenli bir dil seçmek, tek tek zafiyet avlamaktan stratejik olarak çok daha güçlüdür.

## Yaygın Hatalar

Zafiyeti üreten ve savunmayı zayıflatan tekrar eden hatalar vardır. Bunları tanımak, hem yazarken hem denetlerken çok değerlidir.

- **Sınırsız kopyalama fonksiyonları kullanmak.** `gets` (kesinlikle kaçınılmalı, standarttan kaldırıldı), `strcpy`, `strcat`, `sprintf` ve sınır almayan `scanf("%s", ...)` gibi kullanımlar. Bunlar hedef boyutunu hiç bilmez.
- **"n"'li varyantları yanlış kullanmak.** `strncpy` gibi fonksiyonlar güvenli sanılır ama tuzakları vardır: `strncpy`, kaynak hedeften uzunsa sonuç string'i null ile sonlandırmayabilir; bu da sonraki okuma işlemlerinde başka bir taşmaya yol açabilir. Boyut argümanını da yanlış hesaplamak (hedefin boyutu yerine kaynağın boyutunu vermek gibi) sık görülen bir hatadır.
- **Off-by-one hataları.** Bir baytlık taşmalar. Örneğin `<= n` yerine `< n` gibi bir döngü sınırı hatası veya null bayt için bir baytlık yer ayırmayı unutmak. Tek bir baytlık taşma bile, ezdiği şey kritikse (örneğin kaydedilmiş base pointer'ın en düşük baytı) sömürülebilir olabilir.
- **İşaretli/işaretsiz (signed/unsigned) uzunluk karışıklığı.** Negatif bir uzunluğun büyük bir işaretsiz sayıya dönüşüp `memcpy`'ye dev bir kopyalama miktarı olarak geçmesi klasik bir felakettir.
- **Güvenlik korumalarını farkında olmadan kapatmak.** Derleyici bayraklarıyla stack protector'ı devre dışı bırakmak, PIE'yi kapatmak veya eski derleyici varsayılanlarına güvenmek. Bazen performans kaygısıyla yapılır ama risk çoğu zaman kazançtan büyüktür.
- **Kullanıcı girdisinin uzunluğuna güvenmek.** İstemci tarafından gelen "uzunluk alanına" tampon boyutunu doğrulamadan güvenmek; ağ protokollerinde çok yaygın bir taşma kaynağıdır.

## En İyi Pratikler

Savunmayı tek bir tekniğe değil, birbirini destekleyen katmanlara yaymak gerekir. Aşağıdaki pratikler "neden" gerekçeleriyle birlikte düşünülmelidir.

**Sınır-farkındalıklı API'ler kullanın.** Hedef tampon boyutunu argüman olarak alan fonksiyonları tercih edin (`snprintf` gibi ve kesin uzunluk sınırı geçirilen `memcpy` kullanımları). Boyut hesaplamalarında her zaman hedefin gerçek kapasitesini kullanın ve null sonlandırıcı için yer bırakmayı unutmayın. Mümkünse boyutu ve sınırı tek noktada tutan yardımcı fonksiyonlar/sarmalayıcılar yazın; her çağrı noktasında elle boyut hesaplamak hata üretir.

**Derleyici sertleştirmelerini varsayılan açık tutun.** Stack protector, FORTIFY, PIE/ASLR, NX ve RELRO gibi korumaları üretim derlemelerinde etkin bırakın. Bunlar tek tek aşılabilir olsa da, birlikte saldırganın işini kat kat zorlaştırır ve sömürü geliştirme maliyetini yükseltir. Güvenlik ekonomisinde amaç çoğu zaman "imkânsız" değil "yeterince pahalı" kılmaktır.

**Statik ve dinamik analiz araçlarını süreçle bütünleştirin.** Derleme sırasında static analyzer'lar riskli çağrı kalıplarını yakalar. Çalışma zamanında AddressSanitizer (ASan) gibi araçlar, tampon sınırı ihlallerini test sırasında anında ve net biçimde yakalar; bu, üretime çıkmadan zafiyet bulmanın en pratik yollarından biridir. Fuzzing (özellikle sanitizer'larla birlikte çalıştırılan coverage-güdümlü fuzzing) beklenmedik girdilerle taşmaları otomatik keşfetmede son derece etkilidir.

**Güven sınırlarını netleştirin.** Ağdan, dosyadan veya kullanıcıdan gelen her girdiyi güvenilmez kabul edin. Uzunluğu, formatı ve içeriği kullanmadan önce doğrulayın. Özellikle protokol ayrıştırma (parsing) kodunda uzunluk alanlarını mevcut tampon kapasitesine karşı denetleyin.

**Yeni kod için bellek-güvenli dilleri değerlendirin.** Özellikle ayrıştırıcılar, ağ hizmetleri ve saldırı yüzeyi yüksek bileşenler için Rust gibi bir dil seçmek, bütün bir zafiyet sınıfını tasarımdan silebilir. Mevcut C/C++ tabanlarında ise kritik modülleri kademeli olarak güvenli dillere taşımak makul bir strateji olabilir.

**En az ayrıcalık ve izolasyon uygulayın.** Bir taşma yine de sömürülse bile etkisini sınırlayın: süreçleri düşük ayrıcalıkla çalıştırın, sandbox/seccomp gibi mekanizmalarla sistem çağrısı yüzeyini daraltın. Böylece başarılı bir kod çalıştırma bile sınırlı hasar verir. Bu "varsayılan olarak ihlal edilmiş" düşünme biçimi, tek bir zafiyetin tüm sistemi çökertmesini önler.

## Sonuç

Stack buffer overflow, yüzeyde basit bir "tampon taştı" hikâyesi gibi görünür; ama derininde işlemci mimarisi, dil tasarımı, derleyici davranışı ve saldırgan yaratıcılığının kesiştiği zengin bir alan yatar. Kök neden, bellek güvenliğini garanti etmeyen dillerde sınır denetiminin programcıya bırakılmasıdır. Sömürü, return address'i ezip kontrol akışını çalmak ve klasik olarak yığındaki shellcode'a atlamak üzerine kuruludur; NOP sled gibi hilelerle belirsizlik yönetilir.

Savunma tarafında ise her katman bir saldırı varsayımını hedef alır: canary ardışık taşmayı yakalar, NX/DEP kod enjeksiyonunu keser, ASLR adres tahminini bozar, sertleştirmeler ve nihayetinde bellek-güvenli diller kök nedeni ortadan kaldırır. Hiçbiri tek başına mutlak değildir; asıl güç, bu katmanların birlikte oluşturduğu derinlemesine savunmadadır. Saldırıyı anlamak, savunmayı doğru kurmanın önkoşuludur — ve bu ikisini birlikte kavramak, siber güvenlikte kalıcı bir düşünme disiplini kazandırır.
