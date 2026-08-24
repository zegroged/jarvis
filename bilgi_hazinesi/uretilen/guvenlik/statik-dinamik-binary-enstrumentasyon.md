# Statik/Dinamik Binary Enstrumentasyon (Pin, DynamoRIO, QBDI ile Runtime Analiz ve Exploitation Desteği)

## Tanım

**Binary enstrümentasyon (binary instrumentation)**, bir programın makine kodunu; kaynak koduna erişmeden, çalışması sırasında veya öncesinde, ek analiz kodu ("instrumentation kodu") enjekte ederek gözlemlenebilir ve ölçülebilir hâle getirme tekniğidir. Amaç, programın her komutunu (instruction), her temel bloğunu (basic block), her fonksiyon çağrısını ve her bellek erişimini yakalayıp bu olaylar hakkında bilgi toplamaktır.

İki temel yaklaşım vardır:

- **Statik binary instrumentation (SBI):** Analiz kodu, program çalışmadan önce, doğrudan binary dosyaya (ELF, PE) yeniden yazılarak (binary rewriting) gömülür. Örnek çerçeveler: **Dyninst**, **RetroWrite**, **Zipr**, **e9patch**. Avantajı düşük çalışma-anı ek yükü (runtime overhead); dezavantajı, kod ile veriyi kesin ayırt etmenin (disassembly doğruluğu) teorik olarak zor olmasıdır.
- **Dinamik binary instrumentation (DBI):** Analiz kodu, program çalışırken, komutlar yürütülmeden hemen önce **just-in-time (JIT)** olarak araya eklenir. Örnek çerçeveler: **Intel Pin**, **DynamoRIO**, **QBDI**, **Frida (Stalker)**, **Valgrind**. Avantajı, gerçekte çalışan kod yolunu (kendini çözen/paketlenmiş kod dahil) kesin görmesidir; dezavantajı yüksek performans ek yüküdür (çoğu zaman 2x-100x arası yavaşlama).

Bu makale ağırlıklı olarak **DBI**'ye odaklanır, çünkü güvenlik araştırmasında (taint analizi, kod kapsama, gadget doğrulama) asıl güç buradadır.

## Kök Neden / Çalışma Mantığı

### DBI çerçeveleri neyi çözer?

Klasik dinamik analiz araçları iki uçta durur:
- **Debugger (ptrace, breakpoint) tabanlı** izleme: Esnek ama her komut için trap almak çok yavaştır ve gözlemlenebilirlik sınırlıdır.
- **Emülatör (QEMU, Unicorn) tabanlı** izleme: Tam kontrol sağlar ama gerçek donanım/OS davranışından sapabilir ve kurulum maliyeti yüksektir.

DBI, bu ikisinin arasında konumlanır: Program **gerçek CPU üzerinde** çalışmaya devam eder, fakat çerçeve her kod bloğunu çalıştırmadan önce onu bir **kod önbelleğine (code cache)** kopyalar, araya kendi analiz "kancalarını" (callbacks) yerleştirir ve kopyayı çalıştırır.

### JIT tabanlı kod dönüşümü — mekanik

DynamoRIO ve Pin gibi araçların temel döngüsü kabaca şudur:

1. Program bir kod bloğuna (genelde bir **basic block** veya "trace") girmek üzeredir.
2. Çerçeve bu bloğu daha önce görmemişse, orijinal komutları okur (disassemble eder), araştırmacının tanımladığı enstrümantasyon kurallarını uygular (örneğin "her `mov` komutundan önce şu callback'i çağır") ve dönüştürülmüş bloğu code cache'e yazar.
3. Kontrol, orijinal koda değil bu **dönüştürülmüş kopyaya** aktarılır.
4. Blok sonundaki dallanma (branch) tekrar çerçeveye döner; sonraki blok için 1. adıma gidilir. Sık çalışan yollarda bloklar birbirine "link"lenerek (trace linking) çerçeveye dönüş maliyeti azaltılır.

Kritik nokta: Uygulama **kendi orijinal kodunu asla doğrudan çalıştırmaz**; her zaman çerçevenin ürettiği kopya çalışır. Bu, mükemmel gözlemlenebilirlik sağlar ama aynı zamanda tespit edilebilir bir imzadır (bkz. Tespit bölümü).

### Çerçevelerin karşılaştırması

| Özellik | Intel Pin | DynamoRIO | QBDI |
|---|---|---|---|
| Lisans/kaynak | Kapalı kaynak (Intel), ücretsiz | Açık kaynak (BSD) | Açık kaynak (Apache) |
| Soyutlama düzeyi | Yüksek (kolay API, "Pintool") | Orta/düşük (daha çok kontrol) | Kütüphane (embed edilebilir) |
| Ana kullanım | Hızlı prototip, akademik | Yüksek performans, üretim | Kendi aracına gömme, fuzzing |
| Mimari | x86/x64 ağırlıklı | x86/x64/ARM/AArch64 | x64/ARM ağırlıklı |

**QBDI** (QuarkslaB Dynamic binary Instrumentation) özellikle dikkat çeker: Ayrı bir "aracı" olarak değil, kendi programınıza/fuzzer'ınıza gömebileceğiniz bir **kütüphane** olarak tasarlanmıştır. Bu, özel taint motorları ve kapsam-güdümlü fuzzer'lar inşa etmeyi kolaylaştırır.

## Güvenlik Araştırmasındaki Kullanım Alanları

### 1. Kod kapsama (code coverage) ölçümü

Fuzzing'in temelidir. Fuzzer, ürettiği girdinin programda **yeni bir kod yolu** açıp açmadığını bilmek ister. DBI ile her çalıştırılan basic block'un adresi kaydedilir; kaynağa erişim ("white-box") gerekmez.

- **AFL++**'ın QEMU modu, **Frida modu** ve **Nyx** gibi motorlar tam da bunu yapar. Kaynak kodu olmayan (closed-source) hedeflerde kapsam sinyali üretmek için DBI/emülasyon şarttır.
- Ölçülen sinyal genellikle bir **coverage bitmap**'idir: `(önceki_blok ⊕ şimdiki_blok)` gibi kenar (edge) tabanlı bir karma, hangi geçişlerin görüldüğünü işaretler.

Kavramsal Pin/DynamoRIO psödokodu:

```
her_basic_block(bb):
    bb_giris_noktasinda_callback_ekle(kaydet_kapsam)

kaydet_kapsam(blok_adresi):
    kenar = (onceki_blok >> 1) ^ blok_adresi
    coverage_bitmap[kenar % BITMAP_BOYUTU] += 1
    onceki_blok = blok_adresi
```

### 2. Taint analizi (dynamic taint tracking / DTA)

**Taint analizi**, "kirli" (attacker-controlled) verinin — örneğin ağdan gelen bir baytın veya dosya girdisinin — program boyunca nasıl yayıldığını izler. Amaç: Kullanıcı girdisinin, güvenlik açısından kritik bir noktaya (örneğin `EIP/RIP` register'ı, bir `memcpy` boyutu, bir SQL sorgu dizesi) **ulaşıp ulaşmadığını** tespit etmek.

Mekanik:
- Her bayta/register'a bir **taint etiketi** (shadow memory'de tutulan gölge bilgi) atanır.
- Her komut için **taint yayılma kuralı** uygulanır. Örneğin `MOV dst, src` → `taint(dst) = taint(src)`; `ADD a, b` → `taint(a) = taint(a) OR taint(b)`.
- Kritik "sink" noktalarında (dallanma hedefi, format string, allocator boyutu) taint kontrol edilir.

DBI, bu tekniği pratik kılar çünkü her komutun operandlarına ve bellek erişimlerine callback ile erişebilirsiniz. **libdft** (Pin üzerine kurulu klasik bir taint kütüphanesi) ve **Triton** (QBDI/Pin ile beraber kullanılabilen bir sembolik/taint motoru) bu alanın referans araçlarıdır.

Savunma açısından taint analizi hem saldırı yüzeyi keşfinde hem de **exploit tespitinde** (kullanıcı girdisinin instruction pointer'a ulaşması alarm üretir) kullanılır.

### 3. ROP gadget doğrulama ve exploit geliştirme desteği

**Önemli ayrım:** Gadget *bulmak* aslında statik bir iştir — `ROPgadget`, `ropper` gibi araçlar `.text` bölümünü tarayıp `ret`/`jmp` ile biten kısa komut dizilerini listeler. Buna DBI gerekmez.

DBI'nin katkısı gadget **doğrulama ve zincir hata ayıklama** aşamasındadır:
- **ASLR/gerçek çalışma-anı adresleri:** Statik tarama modülün taban adresini bilmez. DBI, çalışan süreçteki gerçek yüklenmiş adresleri (loaded base) ve register durumlarını verir; bu da bir zincirin neden istenen state'e ulaşmadığını görmeyi sağlar.
- **Yan etki tespiti:** Bir gadget'in beklenmeyen bellek yazması veya flag değiştirmesi, sadece statik listede görünmez. DBI ile gadget'i izole çalıştırıp gerçek etkilerini gözlemlemek mümkündür.
- **Coverage/taint ile birleştirme:** Girdinin `RIP`'i kontrol ettiği ana kadar olan yolun izlenmesi, hangi gadget zincirinin gerçekten ulaşılabilir olduğunu netleştirir.

Bu makalenin amacı savunma ve kavram olduğu için; buradaki değer, savunmacıların **exploit'lerin çalışma-anı imzalarını** (kod cache'te olmayan adreslere dallanma, `ret` sonrası yığın anomalisi) anlayabilmesidir.

### 4. Deobfuscation ve unpacking

Paketlenmiş (packed) veya kendini çözen (self-decrypting) zararlı yazılımlar statik analize direnir. DBI, kodun bellekte çözüldüğü **gerçek çalışma anını** yakalar: Yazılabilir bir bellek bölgesine yazılan ve sonra o bölgeden **çalıştırılan** (write-then-execute) baytlar, unpacked payload'un güçlü bir göstergesidir. DBI ile bu geçiş anı tam olarak enstrümante edilebilir.

## Örnek: Basit Bir Kapsam Aracı Mantığı (Kavramsal)

Aşağıda bir DynamoRIO tarzı istemcinin (client) mantığı özetlenmiştir. Not: Bu sözde-kod, gerçek API imzalarını birebir yansıtmaz; amaç mekanizmayı göstermektir.

```
// Çerçeve, her yeni basic block çevrildiğinde bu kancayı çağırır.
event_basic_block(bb):
    ilk_komut = bb.ilk_komut()
    adres = ilk_komut.adres()
    // Bloğun girişine "bu blok çalıştı" kaydını enjekte et
    enjekte_et_once(ilk_komut, callback = blok_calisti, arg = adres)

blok_calisti(adres):
    goruldu_kume.ekle(adres)   // benzersiz bloklar = kapsam

program_bittiginde():
    dosyaya_yaz(goruldu_kume)  // fuzzer bu sinyali okur
```

Bu yapı sayesinde, kaynak koduna hiç dokunmadan, kapalı bir ikili dosyanın hangi kod yollarının test edildiğini ölçebilirsiniz. Fuzzer bu sinyali "yeni kapsam bulundu mu?" kararına besler.

## Tespit ve Savunma

DBI hem savunmacının aracıdır (analiz için) hem de saldırganın/analistin varlığını ele veren bir imzadır. Zararlı yazılımlar **anti-instrumentation** teknikleriyle DBI altında çalıştıklarını anlamaya çalışır. Savunmacı ve blue-team perspektifinden her iki yönü de bilmek gerekir.

### DBI'nin tespit edilebilir izleri (anti-DBI teknikleri)

1. **Kod adres uyumsuzluğu (self-address check):** Program, çalışan bir komutun adresini okur (`call $+5; pop reg` gibi) ve bunun beklenen (orijinal) adres aralığında olup olmadığını kontrol eder. DBI code cache'te çalıştığı için adres orijinal `.text`'ten farklı olur → DBI tespiti.
2. **Ek yük/zamanlama (timing) anomalileri:** DBI 2x-100x yavaşlatır. `rdtsc` ile ölçülen sürelerin anormal yüksekliği DBI/emülatör varlığını ele verir.
3. **Bilinen çerçeve artefaktları:** Pin/DynamoRIO süreçlerinin belleğe yüklediği DLL/kütüphaneler, ortam değişkenleri, süreç ağacındaki ebeveyn süreç adı (örneğin `pin.exe`, `drrun`), açık handle'lar taranabilir.
4. **Self-modifying/JIT davranışı ile tuzak:** DBI çerçevelerinin bazı komut dizilerini (özellikle self-modifying code) ele alışındaki farklar, kasıtlı olarak tetiklenerek fark yaratılabilir.
5. **İstisna (exception) davranış farkları:** DBI altında bazı hatalı komutların/hataların ele alınma zamanlaması ve şekli farklılaşabilir; zararlı yazılım kasıtlı exception üretip sonucu inceleyebilir.

### Savunmacı için tespit ve mitigasyon

Bir kurumun endpoint/EDR açısından ilgilendiği asıl senaryo, DBI/instrumentation'ın **kötüye kullanımı** (analiz kaçırma, in-memory patching, canlı manipülasyon) ve genel exploit imzalarıdır:

- **Kontrol akışı bütünlüğü (Control-Flow Integrity, CFI):** Derleme zamanı korumaları (Intel CET'in **shadow stack** ve **IBT** özellikleri, Windows CFG/XFG) `ret`/dolaylı `jmp` hedeflerini doğrular. ROP/JOP zincirlerinin geçersiz hedeflere dallanmasını çalışma-anında engelleyerek DBI ile doğrulanan gadget zincirlerini kırar. Bu, gadget-tabanlı exploitation'a karşı en somut savunmadır.
- **W^X (Write XOR Execute):** Aynı bellek bölgesinin hem yazılabilir hem çalıştırılabilir olmasını yasaklamak, unpacker/JIT-spray davranışını zorlaştırır. DEP/NX bit'in temel prensibidir.
- **Süreç enjeksiyonu ve child-process telemetrisi:** EDR'ların, bilinen DBI ikililerinin (Pin, DynamoRIO çalıştırıcıları) hassas süreçlere iliştirilmesini, olağandışı `ptrace`/`CreateRemoteThread`/`WriteProcessMemory` çağrılarını ve RWX bellek tahsislerini izlemesi. Meşru bir kullanıcı sürecine harici bir instrumentation çerçevesinin bağlanması güçlü bir anomali sinyalidir.
- **Yığın (stack) anomalisi tespiti:** ROP saldırılarında `ret` adresleri yığında beklenmedik yerlere işaret eder; **stack pivot** (yığın işaretçisinin veri bölgesine kaydırılması) davranışı EDR/runtime korumalarınca yakalanabilir.
- **Kritik yazılımda anti-tamper:** Hassas uygulamalar (DRM, ödeme, oyun anti-cheat) kendi bütünlük ve DBI-tespit kontrollerini gömer. Bunu bilerek, savunmacı bu kontrollerin atlatılma girişimlerini de telemetride arayabilir.
- **Sandbox'lama, ama zamanlamaya güvenmeme:** Analiz sandbox'ları DBI/emülasyon kullanır; zararlı yazılım da bunu tespit etmeye çalışır. Sandbox'ın gerçekçi zamanlama ve artefakt gizleme (stealth) ile güçlendirilmesi, kaçırma (evasion) oranını düşürür.

Not: Zararlı yazılım tarafından bakıldığında "DBI tespiti" bir kaçırma tekniğidir; savunmacı/analist tarafından bakıldığında ise "DBI'yi stealth kurma" bir gerekliliktir. Aynı madalyonun iki yüzüdür.

## Yaygın Hatalar ve Yanılgılar

1. **"DBI = debugger" sanmak.** Debugger genelde breakpoint/trap kullanır ve komut-başına yavaştır; DBI ise kodu JIT ile yeniden yazar ve toplu (blok bazlı) çalışır. Farklı mimari, farklı gözlemlenebilirlik, farklı performans profili.
2. **Statik ile dinamik gadget bulmayı karıştırmak.** Gadget *bulma* statik bir taramadır; DBI gadget *doğrulama, adresleme ve zincir hatalarını ayıklama* aşamasında değer katar. "DBI ile gadget bulunur" ifadesi yanıltıcıdır.
3. **Performans ek yükünü hafife almak.** Ağır taint analizi bir programı 50x-100x yavaşlatabilir. Gerçek-zamanlı veya zamanlamaya duyarlı hedeflerde bu, davranışı değiştirir (heisenbug) ve yanlış sonuç üretebilir.
4. **Shadow memory maliyetini unutmak.** Taint takibi her bayt için gölge veri tutar; bellek kullanımı katlanır. Etiket granülaritesi (bit/bayt/register) tasarım kararıdır ve doğruluk-maliyet dengesini belirler.
5. **Kapsam sinyalini "hata sinyali" sanmak.** Yeni kapsam, yeni bir kod yolu demektir — mutlaka bir zafiyet değil. Fuzzer için kapsam yalnızca bir yön bulma pusulasıdır; asıl hedef çökme/bellek hatası (crash/sanitizer) tespitidir.
6. **Anti-DBI'yi göz ardı etmek.** Modern zararlı yazılım DBI altında çalıştığını anlarsa davranışını değiştirir (dormant kalır). Stealth önlemi almadan yapılan DBI analizi, gerçek zararlı davranışı hiç görmeyebilir; bu da yanlış "temiz" kararına yol açar.
7. **Statik binary rewriting'in mükemmel olduğunu varsaymak.** SBI, kod-veri ayrımı ve dolaylı dallanma (indirect jump) hedeflerini çözmede hata yapabilir; yanlış disassembly, yeniden yazılmış ikiliyi bozabilir. Kritik hedeflerde dinamik doğrulama şarttır.

## Özet

Binary enstrümantasyon, kaynak koduna erişmeden makine kodunu ölçülebilir kılan temel bir analiz tekniğidir. **DBI çerçeveleri (Pin, DynamoRIO, QBDI)**, kodu çalışma anında JIT ile yeniden yazarak mükemmel gözlemlenebilirlik sağlar; bu güç, **kod kapsama ölçümü (fuzzing)**, **dinamik taint analizi** ve **exploit zinciri doğrulama** gibi ileri güvenlik uygulamalarının temelini oluşturur. Aynı mekanizma, kaçınılmaz olarak tespit edilebilir izler (code cache adres uyumsuzluğu, zamanlama anomalisi, çerçeve artefaktları) bırakır; savunmacı bu izleri hem **stealth analiz** kurarken hem de **anti-analiz zararlısını** ve **gadget-tabanlı exploitation'ı** (CET shadow stack, CFI/CFG, W^X, stack-pivot tespiti ile) yakalarken kullanır. Doğru anlaşıldığında binary enstrümantasyon, hem saldırı yüzeyini haritalamanın hem de çalışma-anı savunmalarını tasarlamanın en keskin araçlarından biridir.
