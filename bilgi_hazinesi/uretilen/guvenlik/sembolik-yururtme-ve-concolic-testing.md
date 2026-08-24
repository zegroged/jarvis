# Sembolik Yürütme ve Concolic Testing (angr, KLEE ile Otomatik Exploit/PoC Üretimi)

## Tanım ve Kapsam

**Symbolic execution** (sembolik yürütme), bir programı somut (concrete) girdilerle değil, **sembolik değişkenlerle** çalıştıran bir program analizi tekniğidir. Klasik bir çalıştırmada bir girdi baytı `0x41` gibi belirli bir değere sahiptir; sembolik yürütmede ise o baytın değeri "α" gibi bir sembol olur. Program ilerledikçe her aritmetik ve mantıksal işlem bu semboller üzerinde bir **cebirsel ifade** biriktirir ve her koşullu dallanmada (`if`, `jne`, `cmp/branch`) bu ifadeler üzerine bir **kısıt** (constraint) eklenir. Belirli bir kod yoluna (path) ulaşmak için sembolik girdilerin sağlaması gereken kısıtların birikmiş kümesine **path constraint** ya da **path condition** denir.

Bu kısıt kümesi bir **SMT solver** (Satisfiability Modulo Theories çözücü, tipik olarak Z3, STP, Boolector, Bitwuzla) tarafından çözülür. Solver "bu kısıtları aynı anda sağlayan somut bir girdi var mı?" sorusunu yanıtlar. Cevap "evet" ise, o yolu tetikleyen gerçek bir girdi (satisfying assignment) üretir. İşte sembolik yürütmenin gücü buradadır: **belirli bir kod noktasına ulaşan girdiyi elle tahmin etmek yerine, matematiksel olarak türetir.**

**Concolic execution** (concrete + symbolic) ise saf sembolik yürütmenin ölçeklenme sorunlarını hafifletmek için tasarlanmış melez bir yaklaşımdır. Program gerçek (somut) bir girdiyle çalıştırılır, ancak aynı anda sembolik durum da yan yürütülür (bunun tekniği "dynamic symbolic execution" olarak da geçer). Somut çalıştırma, sembolik motorun çözemediği veya çok pahalı bulduğu kısımlarda "yol gösterici" olarak kullanılır; sembolik taraf ise mevcut yoldan **sapmak** için hangi girdi baytının değişmesi gerektiğini hesaplar. Bu iki dünyanın birbirini beslemesine **concolic testing** denir ve modern otomatik güvenlik test araçlarının çoğunun temelidir.

Bu makale, bu tekniklerin çalışma mantığını, ikili (binary) analiz ve exploit/PoC otomasyonundaki rolünü, sınırlarını ve savunma/tespit perspektifini eğitim amacıyla ele alır.

## Kök Neden ve Çalışma Mantığı

### Neden fuzzing yeterli değil, sembolik yürütme neyi çözer?

**Fuzzing** rastgele/mutasyona dayalı girdilerle programı bombalar ve çökme arar. Çok verimlidir ama kör bir aramadır: derin ve dar koşullara (örneğin `if (input == 0xDEADBEEF)`) rastlantısal olarak ulaşması pratikte imkânsıza yakındır — 32 bitlik tam eşleşme için ortalama iki milyarlarca deneme gerekir. Fuzzer bu "sihirli sayı" (magic value) ve checksum kapılarının önünde takılır.

Sembolik yürütme tam da bu noktada güçlüdür. `input == 0xDEADBEEF` dalını gördüğünde, solver'a "α = 0xDEADBEEF olmalı" kısıtını verir ve doğru girdiyi **tek adımda** türetir. Bu yüzden ikisi tamamlayıcıdır: fuzzer geniş yüzeyi hızlıca tarar, sembolik motor ise fuzzer'ın takıldığı dar geçitleri açar. Bu birleşime **hybrid fuzzing** denir (örn. Driller, QSYM, SymCC + fuzzer eşlemeleri).

### Çalışmanın çekirdeği: durum ağacı ve kısıt biriktirme

Sembolik motor programı bir **execution tree** (yürütme ağacı) olarak keşfeder. Her koşullu dallanma ağacı ikiye böler:

- **True dalı**: mevcut path constraint'e `koşul == true` eklenir.
- **False dalı**: `koşul == false` eklenir.

Motor her yeni **state** (durum) için kayıt/bellek değerlerini sembolik ifadeler olarak, path constraint'i de bir kısıt listesi olarak tutar. Bir hedefe (örneğin bir bellek bozulması noktasına) ulaşan bir durum bulunduğunda, o durumun path constraint'i solver'a verilir ve tetikleyici girdi elde edilir.

Kavramsal bir örnek (pseudocode):

```c
void process(char *buf) {
    int len = buf[0];              // len sembolik: α0
    char tmp[64];
    if (buf[1] == 'K') {           // kısıt: α1 == 'K'
        if (len > 64) {            // kısıt: α0 > 64
            memcpy(tmp, buf + 2, len);  // stack overflow!
        }
    }
}
```

`memcpy` satırındaki taşmaya ulaşmak için solver'a giden kısıtlar: `α1 == 'K'` **ve** `α0 > 64`. Solver bunları sağlayan somut bir girdi üretir; örneğin ikinci bayt `'K'`, ilk bayt `0x65` (101). Fuzzer'ın bu iki koşulu rastlantıyla birlikte tutturması zorken, sembolik motor bunu deterministik olarak çözer.

### Neden "state explosion" temel sınırdır?

Her dallanma durum sayısını potansiyel olarak ikiye katlar. Döngüler, özyineleme ve iç içe koşullar durum sayısını **üstel** büyütür — buna **path/state explosion** denir. 100 bağımsız dallanma teorik olarak 2^100 yol demektir; bunları tek tek keşfetmek imkânsızdır. Bu, sembolik yürütmenin **temel ve kaçınılmaz** ölçek sorunudur ve tüm araçların etrafında dolaştığı ana kısıttır.

İkinci büyük darboğaz **constraint solving maliyetidir**. SMT çözümü genel olarak NP-hard sınıfındadır; özellikle çarpma, bölme, doğrusal olmayan aritmetik, hash/kripto fonksiyonları ve büyük bit vektörleri solver'ı saatlerce oyalayabilir veya "unknown" ile geri döndürebilir. Bir SHA-256 karşılaştırmasını "tersine çözmek" pratikte mümkün değildir — solver bunu çözemez, çünkü bu zaten kriptografik olarak zor olacak şekilde tasarlanmıştır.

### Ortam etkileşimi (environment) sorunu

Gerçek programlar sistem çağrıları yapar, dosya okur, ağdan veri alır, `malloc` çağırır. Sembolik motorun bu dış dünyayı **modellemesi** gerekir. angr'ın **SimProcedures**'ı ve KLEE'nin ortam modeli bu amaçla yazılmış "sahte" fonksiyon uygulamalarıdır: `strlen`, `printf`, `read` gibi çağrıları sembolik olarak taklit ederler. Modellenmemiş her syscall bir belirsizlik kaynağıdır; eksik modelleme ya yanlış sonuç (unsoundness) ya da analizin durması demektir.

## Araçlar ve Ekosistem

### KLEE

**KLEE**, LLVM **bitcode** (IR) üzerinde çalışan, akademide doğmuş klasik bir sembolik yürütme motorudur. Kaynak kodu olan (ya da LLVM IR'a derlenebilen) programlar için güçlüdür ve tarihsel olarak GNU coreutils gibi araçlarda daha önce bilinmeyen hatalar bulmasıyla ünlüdür. Öne çıkan özellikleri:

- Otomatik olarak **yüksek kapsama sağlayan test durumları** (test case) üretir; her keşfedilen yol için bir `.ktest` girdi dosyası çıkarır.
- Bellek hatalarını (out-of-bounds, bölme sıfıra, hatalı serbest bırakma) tespit ettiğinde onları tetikleyen girdiyi kaydeder.
- STP/Z3 gibi solver'lar kullanır.
- Sınırı: kaynak/IR gerektirir; salt ikili (binary-only) hedeflerde doğrudan uygulanamaz.

### angr

**angr**, Python tabanlı, **ikili (binary) düzeyde** çalışan bir analiz çerçevesidir. Kaynak kod gerektirmez; ELF/PE gibi derlenmiş dosyaları **VEX IR**'a (Valgrind'in ara diline) çevirerek analiz eder. CTF ve gerçek dünya binary analizinde en yaygın araçlardan biridir. Temel bileşenleri kavramsal olarak:

- **Project**: yüklenen binary'yi ve mimari bilgisini tutar.
- **Simulation manager**: durum kümelerini (active, deadended, found, avoid) yönetir ve keşfi yürütür. Tipik akış "belirli bir adrese ulaşan, başka bir adresten kaçınan girdiyi bul" şeklinde ifade edilir.
- **SimState / claripy**: sembolik değişkenleri ve kısıtları temsil eder; `claripy` angr'ın solver soyutlama katmanıdır (arkasında Z3 vardır).
- **SimProcedures**: kütüphane fonksiyonlarının sembolik modelleri.

angr'ın CTF'lerde çok bilinen kullanımı basit "hangi giriş bu `Correct!` dalını tetikler?" tipi crackme'leri otomatik çözmesidir. Motor, "başarı" adresini `find`, "başarısızlık" adresini `avoid` olarak alır, o yola ulaşan girdiyi solver'la türetir. Bu, sembolik yürütmenin **otomatik girdi üretimi** yeteneğinin en somut gösterimidir.

### Diğer önemli yaklaşımlar

- **SAGE** (Microsoft): büyük ölçekli concolic testing'in endüstriyel bir örneği; parser/dosya formatı hatalarını sistemli olarak bulmuştur.
- **SymCC / SymQEMU**: derleme zamanında ya da QEMU üzerinden sembolik izleme ekleyerek concolic yürütmeyi hızlandıran, fuzzer ile birlikte kullanılan modern yaklaşımlar.
- **Driller / QSYM**: hibrit fuzzing örnekleri — fuzzer takıldığında sembolik motoru devreye alıp yeni yollar "delen" sistemler.
- **Manticore**: hem yerel ikili dosyalar hem de EVM (akıllı sözleşme) bytecode üzerinde sembolik analiz yapabilen bir çerçeve.

## Otomatik Exploit/PoC Üretimindeki Rol

Sembolik/concolic tekniklerin savunma ve araştırma değerinin özü, **zafiyeti kanıtlayan bir girdiyi (PoC) otomatik türetebilmeleridir**. Bu, akademik literatürde **AEG (Automatic Exploit Generation)** olarak bilinen alanın çekirdeğidir. Kavramsal mekanizma şöyle işler:

1. **Zafiyet noktasının bulunması**: Sembolik motor, bir bellek yazma işleminin sembolik (yani saldırgan kontrolündeki) bir adres ya da boyut kullandığı durumları arar. Örneğin instruction pointer'ın (`PC`/`RIP`) sembolik hale geldiği bir durum — bu, kontrol akışının ele geçirilebildiğinin işaretidir.

2. **Exploitability kısıtının eklenmesi**: Motor, "bu sembolik `PC` belirli bir hedef değere eşit olsun" gibi ek bir kısıt koyar. angr'da bu, `state.solver.add(pc == hedef_adres)` benzeri bir kavramsal adımdır. Böylece "kontrolü ele geçir" hedefi bir kısıt problemine dönüşür.

3. **Girdinin türetilmesi**: Path constraint + exploitability kısıtı solver'a verilir ve bunları sağlayan somut girdi elde edilir. Bu girdi, zafiyeti güvenilir biçimde tetikleyen bir **PoC**'tir.

Eğitim ve savunma bağlamında bunun değeri şudur: Bir triyaj ekibi elinde yüzlerce fuzzer çökmesi olduğunda, sembolik analiz "bu çökme gerçekten kontrol akışı ele geçirmeye yol açar mı, yoksa yalnızca zararsız bir null-deref mi?" sorusunu otomatikleştirebilir. Yani AEG çoğu zaman **zafiyet önceliklendirme** (crash triage) ve **yamanın gerçekten kapattığının doğrulanması** için kullanılır. Tam, silahlaştırılmış exploit üretimi ise modern korumalar (ASLR, NX/DEP, stack canary, CFI) yüzünden pratikte çok daha zordur; araçlar tipik olarak korumaların kapalı olduğu ya da bilgi sızıntısının bilindiği idealize senaryolarda başarılıdır. Bu makalede odak, mekanizmayı anlamak ve savunma kurmaktır; operasyonel silahlaştırma adımları kapsam dışıdır.

## Savunma ve Tespit

Sembolik yürütme bir saldırı vektörü değil, bir **analiz tekniğidir**; bu yüzden "tespit"in iki farklı anlamı vardır ve ikisini de ele almak gerekir.

### 1) Tekniği kendi lehine kullanan savunma (proaktif)

En sağlıklı savunma, aracı **kendi yazılımına** uygulamaktır:

- **CI/CD'ye entegre concolic test**: KLEE'yi parser'lar, protokol çözücüleri, dosya format işleyicileri gibi girdi-yoğun kod yollarına yönlendirmek, fuzzer'ın ulaşamadığı derin dalları kapatır. Bulunan her `.ktest`/PoC bir regresyon testine dönüştürülür.
- **Hedefli doğrulama**: Bir CVE yaması çıktığında, sembolik motorla "yamanın gerçekten o path constraint'i erişilemez kıldığını" doğrulamak, sessizce yetersiz kalan yamaları yakalar.
- **Bulunan hatanın önceliklendirilmesi**: AEG mantığıyla "sembolik PC" ya da "sembolik yazma adresi" içeren durumları işaretleyip yüksek öncelikli kabul etmek, triyajı hızlandırır.

### 2) Sembolik analizi zorlaştıran koruyucu tasarım (anti-analiz)

Kötü amaçlı yazılımlar ve DRM/lisans korumaları, tersine mühendisi ve otomatik çözücüleri yavaşlatmak için sembolik yürütmeye özel karşı önlemler kullanır. Bunları tanımak hem savunmacı hem analist için önemlidir:

- **Path explosion tuzakları**: Kasıtlı olarak çok sayıda anlamsız dallanma, geniş `switch`, karmaşık döngüler ekleyerek durum sayısını patlatmak. Bu, opaque predicate ve control-flow flattening obfuscation'ının doğal bir yan etkisidir.
- **Solver'ı boğan kısıtlar**: Girdiyi bir hash/kripto fonksiyonundan geçirip sonucu karşılaştırmak. Solver bunu tersine çözemez, dolayısıyla o dalın ötesine geçemez.
- **Environment/anti-VM kontrolleri**: Modellenmemiş nadir syscall'lar, donanım özelliği okumaları, zamanlama kontrolleri motoru saptırabilir.

Savunmacı taraf bu tekniklerin varlığını, tersine mühendislikte "analizin belli bir noktada patlaması ya da takılması" olarak gözlemler ve buna karşı somutlaştırma (concretization), fonksiyon özetleme (function summarization) veya seçici SimProcedure yazımı ile karşılık verir.

### 3) İkili düzeyde savunma önlemlerinin AEG'yi kırması

AEG'nin pratikte zorlanmasının nedeni de aslında bir savunma listesidir; bunları etkin tutmak en somut korumadır:

- **ASLR** (adres uzayı rastgeleleştirme): sabit hedef adres kısıtını geçersiz kılar; solver'ın "PC == sabit adres" çözümü artık her çalıştırmada değişir.
- **NX/DEP**: enjekte edilen veriyi çalıştırılamaz kılar; AEG'nin shellcode türetme yolunu keser.
- **Stack canary**: taşmanın sessizce dönüş adresine ulaşmasını engeller, exploitability kısıtını sağlanamaz hale getirebilir.
- **CFI ve shadow stack**: sembolik olarak ele geçirilmiş bir dönüş/çağrı hedefini geçersiz kılar.

Bu korumaların **birlikte** açık ve doğru yapılandırılmış olması, otomatik exploit üretimini kavramsal olarak çözülebilir bir problemden pratikte çok pahalı bir probleme dönüştürür.

## Yaygın Hatalar ve Yanlış Anlamalar

**"Sembolik yürütme her hatayı bulur."** Yanlış. State explosion ve solver limitleri yüzünden gerçek programlarda motor yolların yalnızca küçük bir kısmını keşfedebilir. Ölçeklenmesi için mutlaka **yol seçim stratejileri** (path prioritization, coverage-guided search), **döngü sınırlama**, **fonksiyon özetleme** ve **somutlaştırma** ile ehlileştirilmesi gerekir.

**"Fuzzing yerine geçer."** Hayır, tamamlar. Doğru mimari hibrittir: fuzzer hızla geniş kapsama sağlar, sembolik motor yalnızca fuzzer'ın takıldığı dar geçitlere cerrahi müdahale eder. Sembolik motoru her şeye salmak, saatler süren solver çağrılarında boğulmakla sonuçlanır.

**"Solver her kısıtı çözer."** Doğrusal olmayan aritmetik, kripto ve hash fonksiyonları pratikte çözülemez; motor bu dalların ötesine geçemez. Bunu bilmeden "araç neden buradan geçemedi?" diye zaman kaybetmek yaygındır.

**"AEG çıktısı gerçek bir silahtır."** Genellikle değil. Modern korumalar (ASLR/NX/canary/CFI) altında araçların ürettiği çıktı çoğunlukla idealize bir PoC'tir; gerçek hedefte çalışması için bilgi sızıntısı, ret2libc/ROP zinciri gibi ek ve büyük ölçüde manuel adımlar gerekir. Aracın "exploitable" demesini bitmiş exploit sanmak ciddi bir yanılgıdır.

**"Ortam otomatik doğru modellenir."** Modellenmemiş syscall'lar sessizce **unsound** sonuç (yanlış negatif) ya da hatalı yollar üretebilir. Kritik kod yollarında ortam modelinin doğruluğunu denetlemek şarttır.

**"Sonuçlar deterministiktir."** Solver seçimi, arama stratejisi, zaman aşımı ayarları ve somutlaştırma kararları sonucu ciddi biçimde değiştirir. Aynı hedefte farklı stratejiler farklı yollar/PoC'ler bulur; "araç bir şey bulamadı" ifadesi "zafiyet yok" anlamına gelmez.

## Özet

Symbolic ve concolic execution, program dallanmalarını **kısıt problemlerine** çevirip bir SMT solver ile çözerek, belirli kod yollarını tetikleyen girdileri elle tahmin etmek yerine **matematiksel olarak türetir**. Bu, fuzzing'in kör kaldığı "magic value" ve derin koşul kapılarını açar; bu yüzden ikisi hibrit olarak birlikte en güçlüdür. KLEE kaynak/IR düzeyinde, angr ise ikili düzeyde bu paradigmayı somutlaştırır ve CTF'den gerçek zafiyet triyajına kadar geniş bir alanda otomatik girdi/PoC üretir. Tekniğin gücü **state explosion** ve **solver maliyeti** ile, silahlaştırma tarafı ise ASLR/NX/canary/CFI gibi savunmalarla sınırlanır. Savunmacı için doğru okuma nettir: aracı kendi yazılımınıza **CI'da** uygulayıp derin hataları erkenden kapatın, yama doğrulamasında kullanın, ve ikili düzey korumalarını eksiksiz açık tutarak otomatik exploit üretimini pratikte pahalı hale getirin.
