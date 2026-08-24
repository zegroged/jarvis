# Derleyici/IR Düzeyinde Analiz ve Binary Fark Analizi (Decompiler IR, BinDiff/Diaphora ile Patch Diffing)

## Giriş ve Bağlam

Profesyonel zafiyet araştırmasının (vulnerability research) merkezinde, kaynak kodu elimizde olmayan derlenmiş ikili dosyaları (binary) anlama problemi yatar. Ham makine kodu ya da disassembly çıktısı insan için son derece yorucu bir okumadır; on binlerce satır assembly arasında bir tamsayı taşması (integer overflow) veya sınır dışı yazma (out-of-bounds write) bulmaya çalışmak pratikte çok zordur. Bu noktada iki teknik alan devreye girer:

1. **Decompiler ara temsili (Intermediate Representation, IR) analizi:** Assembly'i, C benzeri okunabilir yüksek seviye bir temsile ve altında yatan matematiksel ara dile çevirmek.
2. **Binary fark analizi (binary diffing / patch diffing):** İki ikili dosyanın (tipik olarak yamalı ve yamasız sürüm) fonksiyon bazında karşılaştırılıp değişen yerlerin tespiti.

Bu ikisi birlikte, modern "1-day exploit" geliştirmenin ve savunma tarafında "yamayı doğru anlamanın" standart iş akışını oluşturur. Bu makale mekanizmayı, çalışma mantığını ve savunma/tespit perspektifini eğitim amacıyla açıklar; operasyonel bir saldırı reçetesi değildir.

---

## Bölüm 1: Decompiler Ara Temsili (IR) Nedir?

### Tanım

Bir decompiler, makine kodunu geriye doğru işleyerek insan tarafından okunabilir bir üst seviye dile (çoğunlukla C benzeri sözde-kod / pseudocode) çevirir. Ancak bu çeviri doğrudan olmaz; arada bir **ara temsil (IR)** katmanı vardır. IR, mimariden (x86, ARM, MIPS, RISC-V...) bağımsız, düzenli ve analiz edilebilir bir dildir.

Öne çıkan iki IR ekosistemi:

- **Ghidra P-Code:** NSA'in açık kaynak tersine mühendislik aracı Ghidra'nın kullandığı IR. Her mimarinin komutu, bir dizi mimari-bağımsız P-Code işlemine (`COPY`, `LOAD`, `STORE`, `INT_ADD`, `INT_SUB`, `CALL`, `BRANCH`, `CBRANCH` gibi) çevrilir.
- **IDA Hex-Rays microcode:** IDA Pro'nun Hex-Rays decompiler'ının kullandığı çok katmanlı ara dil (microcode). Ham microinstruction'lardan başlayıp, optimizasyon geçişleriyle sadeleşerek nihai sözde-koda ulaşır.

Bunların yanında akademik/araştırma dünyasında **VEX IR** (Valgrind ve angr tarafından kullanılır), **BAP BIL**, **REIL** ve **LLVM IR tabanlı lifter'lar** (örneğin retdec, McSema mantığı) da bulunur.

### Kök Neden: IR'a Neden İhtiyaç Var?

Assembly doğrudan analiz için üç açıdan uygunsuzdur:

- **Mimari çeşitliliği:** x86'da `lea`, ARM'de `add` + shift, her mimaride farklı komut setleri vardır. Aynı analizi her mimari için yeniden yazmak istemeyiz. IR, "bir kez yaz, her mimaride çalıştır" prensibini getirir. Lifter (yükseltici) katmanı, mimariye özgü assembly'i tek bir ortak IR'a taşır.
- **Yan etkilerin açık hale gelmesi:** Assembly komutları gizli yan etkiler taşır; örneğin bir aritmetik komut CPU bayraklarını (flags: ZF, CF, OF, SF) sessizce değiştirir. IR bu yan etkileri açık işlemler olarak yazar. Böylece "bu karşılaştırma aslında hangi bayrağa bakıyor" sorusu netleşir.
- **Analiz uygunluğu:** IR genellikle **SSA (Static Single Assignment)** formuna yakın veya dönüştürülebilir yapıdadır. SSA'da her değişkene yalnızca bir kez atama yapılır; bu, veri akışı analizini (data-flow analysis), sabit yayılımını (constant propagation) ve ölü kod eleme (dead code elimination) gibi optimizasyonları matematiksel olarak temiz kılar.

### Çalışma Mantığı: Kaldırma (Lifting) → Analiz → Sözde-kod

Süreç kabaca şöyle işler:

1. **Disassembly:** Ham baytlar komutlara ayrıştırılır.
2. **Lifting:** Her komut IR işlemlerine çevrilir. Örneğin x86 `add eax, ebx` işlemi Ghidra P-Code'da yaklaşık olarak `EAX = INT_ADD(EAX, EBX)` ve ayrıca bayrak hesaplamaları (`CF = INT_CARRY(...)`, `OF = INT_SCARRY(...)`) olarak açılır.
3. **Veri akışı ve tip analizi:** Register ve bellek erişimleri değişkenlere dönüştürülür; kullanılmayan bayrak hesapları elenir; tekrar eden ifadeler sadeleşir.
4. **Kontrol akışı yapılandırması (control flow structuring):** Ham `goto`/`branch` grafiği, `if/else`, `while`, `for` gibi yapılara yeniden inşa edilir. Bu adım "spaghetti" atlamaları okunabilir bloklara çevirir.
5. **Sözde-kod üretimi:** Nihai C benzeri çıktı üretilir.

### Örnek: Assembly'den Sözde-koda

Kavramsal bir örnek. Şu assembly parçasını düşünelim (uydurma değil, tipik bir kalıp):

```asm
mov  eax, [rbp+len]
add  eax, 8
cmp  eax, 0x100
jae  hata
```

IR düzeyinde bu, yaklaşık olarak şu adımlara ayrılır: `len` yükle, 8 ekle (32-bit tamsayı toplamı, taşma bayrağı hesaplanır), 0x100 ile karşılaştır, koşullu dallan. Decompiler sözde-kodu ise şuna benzer:

```c
uint32_t total = len + 8;
if (total >= 0x100)
    goto hata;
// ...buffer[total] gibi bir kullanım
```

Buradaki kritik nokta: `len + 8` **32-bit** aritmetiktir. Eğer `len` değeri 0xFFFFFFF8'e yakınsa toplam sarmalanır (wraps around) ve küçük bir değere düşer; kontrol `>= 0x100` yanlış çıkar ve arkadan gelen bellek erişimi taşar. IR/sözde-kod bu integer overflow → OOB zincirini assembly'e göre çok daha görünür kılar. Zafiyet araştırmacısının IR okumasının amacı tam olarak budur: mantık hatasını yüksek seviyede yakalamak.

### IR Okumada Dikkat: Sözde-kod Gerçek Değildir

Sözde-kod bir **yeniden yapılandırmadır**, kaynak kodun kendisi değil. Derleyici optimizasyonları (inlining, loop unrolling, tail-call, register allocation) orijinal yapıyı bozmuştur ve decompiler bunu tahmin ederek geri kurar. Bu yüzden değişken tipleri yanlış çıkabilir, `undefined4` gibi belirsiz tipler görülebilir, işaretli/işaretsiz (signed/unsigned) karışıklığı olabilir. Uzman, sözde-koda güvenirken kritik noktalarda **daima disassembly ve IR seviyesine inip doğrulama** yapar.

---

## Bölüm 2: Binary Fark Analizi ve Patch Diffing

### Tanım

**Binary diffing**, iki ikili dosyayı karşılaştırıp aralarındaki farkları fonksiyon, temel blok (basic block) ve komut düzeyinde bulma tekniğidir. **Patch diffing** ise bunun en yaygın uygulamasıdır: bir yazılımın yama öncesi (vulnerable) ve yama sonrası (patched) sürümlerini karşılaştırmak.

En bilinen araçlar:

- **BinDiff:** Google tarafından açık kaynak yapılan, IDA/Ghidra ile entegre çalışan endüstri standardı fark aracı. Grafik izomorfizmi (graph isomorphism) temelli eşleştirme yapar.
- **Diaphora:** IDA için açık kaynak, çok esnek ve heuristik açıdan zengin bir diffing eklentisi. Sözde-kod bazlı karşılaştırma da yapabilir.

### Kök Neden: Yama Neden Zafiyeti Ele Verir?

Bir güvenlik yaması, koddaki hatalı davranışı düzeltmek için çoğunlukla **çok küçük ve odaklı** bir değişiklik içerir: eksik bir sınır kontrolü eklenir, bir tamsayı tipi genişletilir, bir `memcpy` uzunluğu düzeltilir, `signed` karşılaştırma `unsigned`'a çevrilir. Bu değişiklik, düzeltilen zafiyetin tam olarak **nerede ve nasıl** olduğunu ele verir. "Neyi düzelttiler?" sorusunun cevabı, "önceden neyin kırık olduğu" sorusunun cevabıdır.

Bu, "1-day exploit" mantığının temelidir: yama yayınlandığında zafiyet teknik olarak "bilinir" (n-day) hale gelir, ancak dünyadaki milyonlarca sistem henüz yamalanmamıştır. Saldırgan, yamayı diff'leyerek zafiyeti yamalanmamış sistemlere karşı silaha dönüştürebilir. Savunma tarafında ise aynı teknik, "bu yama gerçekten ne düzeltiyor, ne kadar kritik, hemen mi uygulamalıyım" sorusunu yanıtlamak için kullanılır.

### Çalışma Mantığı: Fonksiyon Eşleştirme Nasıl Yapılır?

Diffing araçlarının temel zorluğu şudur: iki sürüm arasında fonksiyon adresleri, sıralamaları ve register kullanımları derleyici yüzünden tamamen kaymış olabilir; sembol (symbol) bilgisi çoğunlukla yoktur (stripped binary). O halde "A dosyasındaki fonksiyon X, B dosyasındaki hangi fonksiyona karşılık geliyor?" sorusunu **isimden bağımsız** yapısal özelliklerle yanıtlamak gerekir. Kullanılan başlıca sinyaller:

- **Kontrol akış grafiği (Control Flow Graph, CFG) yapısı:** Fonksiyonun temel blok sayısı, blok arası kenarlar (edges), döngü yapısı. Grafik izomorfizmi ile iki fonksiyonun "iskeleti" karşılaştırılır.
- **Çağrı grafiği (call graph):** Fonksiyonun kimi çağırdığı ve kim tarafından çağrıldığı. Zaten eşleşmiş komşular, bir fonksiyonun eşleşmesini güçlendirir (yayılım/propagation).
- **Hash imzaları:** Sıralamadan bağımsız komut mnemonic'lerinin hash'i (small primes product), sabitlerin (constants) hash'i, string referansları, çağrılan API isimleri.
- **Heuristik puanlama:** Diaphora onlarca heuristik kullanır; "aynı sabitleri kullanan", "aynı stringlere referans veren", "aynı bytes hash'ine sahip" gibi kurallarla eşleşme güven skoru üretir.

Eşleştirme sonucunda araç fonksiyonları üç kovaya ayırır: **birebir aynı (identical)**, **eşleşti ama değişmiş (matched but changed)** ve **eşleşmedi (unmatched — eklenen/silinen)**. Analistin ilgilendiği yer, "eşleşti ama değişmiş" kovasıdır; özellikle küçük ve odaklı değişiklikler gösteren fonksiyonlar.

### Örnek: Tipik Bir Güvenlik Yaması Deseni

Kavramsal olarak, bir yamada sık görülen değişiklik deseni şudur. Yama öncesi sözde-kod:

```c
void kopyala(char *dst, char *src, int len) {
    memcpy(dst, src, len);   // len negatif/çok büyük olabilir
}
```

Yama sonrası sözde-kod:

```c
void kopyala(char *dst, char *src, int len) {
    if (len < 0 || len > MAX_BUF)   // yeni eklenen sınır kontrolü
        return;
    memcpy(dst, src, len);
}
```

Diff aracı bu fonksiyonu "değişmiş" olarak işaretler; CFG'ye yeni bir dallanma bloğu eklenmiştir. Analist bu ek kontrolü görünce, düzeltilen zafiyetin `len` üzerindeki eksik doğrulamadan kaynaklandığını, yani kontrolsüz `memcpy` ile bir buffer overflow olabileceğini anlar. Buradaki `signed int` kullanımı ayrıca dikkat çeker: negatif `len`, `size_t` parametresine geçerken çok büyük bir değere dönüşerek taşmayı tetikleyebilir.

### İş Akışının Bütünü

Pratikte IR analizi ve diffing birlikte çalışır:

1. İki sürüm elde edilir (örneğin bir güncellemeden önce ve sonra).
2. Her ikisi decompiler'a yüklenir, otomatik analizden geçirilir.
3. BinDiff/Diaphora ile fonksiyonlar eşleştirilir.
4. Değişmiş fonksiyonlar önem sırasına göre incelenir; "güvenlik kokusu" olanlara (bellek işlemleri, sınır kontrolleri, tamsayı aritmetiği, parsing kodu) öncelik verilir.
5. Şüpheli fonksiyonun IR/sözde-kodu okunur; değişikliğin hangi zafiyet sınıfını (buffer overflow, integer overflow, use-after-free, type confusion) düzelttiği anlaşılmaya çalışılır.
6. Kök neden ve tetikleme yolu (kod bu fonksiyona nasıl ulaşıyor — reachability) belirlenir.

---

## Bölüm 3: Tespit ve Savunma

Bu teknikler doğası gereği saldırganın **elinde olmayan** bilgiye ulaşmasını sağlar. Savunma tarafı bu gerçeği kabul edip yama süreçlerini buna göre kurgulamalıdır.

### Yama Yönetimi Perspektifi

- **Yama-saldırı penceresini daralt:** Bir yama yayınlandığında, saldırganların onu diff'leyip exploit üretmesi tarihsel olarak günler-haftalar sürebilir; bazı durumlarda saatler. Kritik ve internete açık sistemlerde yamayı **hızlı ve önceliklendirilmiş** uygulamak, bu yarışın savunma tarafını güçlendirir.
- **Yamanın gerçek kapsamını anla:** Aynı diffing tekniği savunmacı tarafından da kullanılabilir. Bir tedarikçi yaması "önemsiz" etiketiyle gelse bile, diff bellek güvenliği düzeltmesi gösteriyorsa, önceliklendirme buna göre yükseltilmelidir. "Silent patch" (sessizce, duyurulmadan yapılan güvenlik düzeltmeleri) bu yüzden risklidir; diffing ile yine de görünür olurlar.
- **Envanter ve maruz kalma yönetimi:** Hangi sürümün nerede çalıştığını bilmeyen bir kurum, hangi 1-day'in kendisini etkilediğini de bilemez. Yazılım envanteri (SBOM dahil) ve sürüm takibi savunmanın önkoşuludur.

### Zorlaştırma (Hardening) — Tersine Mühendisliği Yavaşlatma

Bu teknikler analizi imkânsız kılmaz, ama maliyeti yükseltir:

- **Sembol ve hata ayıklama bilgisini kaldırma (stripping):** Fonksiyon isimleri, değişken isimleri olmayınca analiz zorlaşır. Ancak diffing sembolden bağımsız çalıştığı için tek başına yeterli değildir.
- **Kod karıştırma (obfuscation):** Control flow flattening, opaque predicate, sahte dallanmalar CFG tabanlı eşleştirmeyi bozar. Fakat performans maliyeti ve bakım zorluğu vardır; ayrıca ileri düzey analistler ve simgesel yürütme (symbolic execution) araçları çoğu karıştırmayı çözebilir.
- **Derleyici tabanlı savunmalar:** Stack canary, ASLR, DEP/NX, CFI (Control Flow Integrity) — bunlar zafiyeti gizlemez ama exploit'i çalıştırmayı zorlaştırır. Yani "diff ile zafiyet bulunsa bile onu silaha dönüştürmek pahalı olsun" felsefesi.

### Zafiyet Sınıfını Kökten Kesme

En kalıcı savunma, diff'lenecek zafiyetin en baştan var olmamasıdır:

- **Bellek güvenli diller (memory-safe languages):** Rust gibi diller, patch diffing ile en sık avlanan buffer overflow / use-after-free sınıflarının büyük kısmını dil düzeyinde ortadan kaldırır.
- **Statik analiz ve fuzzing:** Tedarikçinin, saldırgandan **önce** zafiyeti bulup düzeltmesi. Sürekli fuzzing (continuous fuzzing) ve statik analiz, yamaların diff'lenecek "kırık" sürümü hiç yayınlanmadan hataları yakalar.
- **Değişikliği izole etme:** Güvenlik düzeltmelerini büyük refactor'lar içine gömmek, diff'i gürültülü ve maliyetli kılar — ancak bu belirsizlik-yoluyla-güvenlik (security through obscurity) yaklaşımı asıl savunma değil, yalnızca yardımcı bir katmandır ve tek başına güvenilmemelidir.

### Tespit Tarafı

Ağ ve uç nokta savunmasında odak, "zafiyet bulundu mu" değil "sömürülmeye çalışılıyor mu" sorusudur:

- Yeni yamalanmış bir zafiyet için, düzeltilen kod yolunu tetikleyen anormal girdileri (aşırı uzunluklar, negatif değerler, biçimsiz parsing girdileri) izlemek.
- Yamanın işaret ettiği kod bölgesine dayalı, sanal yama (virtual patching / WAF, IPS imzaları) ile geçici koruma sağlamak — asıl yama uygulanana kadar.
- Yama sonrası, sömürü denemelerinin genellikle arttığı gerçeğini kabul edip ilgili loglamayı ve tespit kurallarını proaktif olarak güçlendirmek.

---

## Bölüm 4: Yaygın Hatalar ve Yanlış Anlamalar

- **Sözde-koda kör güven:** Decompiler çıktısı yorumdur, kanıt değil. Kritik integer signedness, tip boyutu ve kaydırma (shift) davranışlarında mutlaka IR/disassembly ile doğrulanmalı. Decompiler'ların ürettiği `undefined`, `__int64` gibi belirsizlikler yanlış sonuçlara yol açabilir.
- **Diff gürültüsünü zafiyet sanmak:** İki sürüm farklı derleyici sürümü veya optimizasyon bayraklarıyla derlendiğinde, güvenlikle ilgisi olmayan yüzlerce fonksiyon "değişmiş" görünür. Analistin işi, gürültüden **anlamlı** güvenlik değişikliğini ayıklamaktır. İdeali, aynı derleyici/ortamla üretilmiş sürümleri karşılaştırmaktır.
- **Eşleştirmeyi mutlak sanmak:** Fonksiyon eşleştirme heuristiktir; yanlış eşleşme (false match) ve kaçırılan eşleşme mümkündür. Özellikle inlining, fonksiyonları birleştirip bölerek eşleştirmeyi bozar. Düşük güven skorlu eşleşmeler el ile teyit edilmelidir.
- **"Yama yayınlandı, güvendeyiz" yanılgısı:** Yama yayınlanması, o zafiyetin artık **bilinir** hale gelmesidir; yamalanmamış sistemler için risk azalmaz, **artar**. Savunmada asıl gösterge yamanın var olması değil, uygulanmış olmasıdır.
- **Obfuscation'a fazla güvenmek:** Karıştırma bir hız tümseğidir, duvar değil. Symbolic/concolic execution ve modern deobfuscation, kararlı bir analiste karşı çoğu karıştırmayı çözer. Tek savunma katmanı olarak kurgulanmamalıdır.
- **Reachability'yi atlamak:** Değişmiş bir fonksiyon bulmak yetmez; o koda saldırgan girdisiyle **ulaşılabildiğini** göstermek gerekir. Ulaşılamayan bir "zafiyet", pratik bir tehdit değildir; savunmada da önceliklendirme buna göre yapılmalıdır.

---

## Sonuç

Decompiler IR analizi ve binary patch diffing, tersine mühendisliğin dağınık disassembly çıktısını anlamlı, karşılaştırılabilir ve akıl yürütülebilir bir düzleme taşır. IR, mimari bağımsızlığı ve veri akışı netliğiyle mantık hatalarını görünür kılar; BinDiff/Diaphora gibi araçlar ise yamaların ele verdiği bilgiyi sistematik biçimde ortaya çıkarır. Bu iş akışı hem saldırı (1-day exploit geliştirme) hem de savunma (yamayı doğru anlama, hızlı yama, sanal yama, sömürü tespiti) tarafında aynı temeli kullanır. Savunmacı için asıl ders açıktır: yama süreci bir yarıştır, zafiyet sınıfını kökten kesmek en kalıcı çözümdür ve "gizlilik yoluyla güvenlik" yalnızca yardımcı bir katmandır — asla tek dayanak değil.
