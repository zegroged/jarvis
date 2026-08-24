# Çok Mimarili Assembly ve Calling Convention Uzmanlığı (ARM32/64, MIPS, x86 Ötesi)

## Giriş ve Neden Önemli

Zafiyet analizi ve malware tersine mühendisliği literatürünün büyük kısmı tarihsel olarak **x86/x64** üzerine kuruludur: stack buffer overflow, ROP zincirleri, bellek yerleşimi anlatımları hep Intel/AMD semantiği üzerinden verilir. Ancak sahadaki gerçek şu ki, **IoT, mobil, router, kamera, endüstriyel gateway ve firmware** dünyasının ezici çoğunluğu **ARM** (32-bit AArch32 ve 64-bit AArch64) ile **MIPS** üzerinde koşar. Mirai ve türevleri MIPS/ARM binary'leri dağıtır; Android malware AArch64 native kütüphaneler içerir; router botnet'leri big-endian MIPS'te derlenir.

Bu mimariler yalnızca "farklı opcode" meselesi değildir. **Calling convention** (fonksiyon çağırma sözleşmesi), **endianness** (bayt sırası), **register semantiği**, **delay slot** gibi kavramlar temelden farklıdır. x86 reflekslerini bu binary'lere uygulamak yanlış analiz üretir: yanlış argümanı takip edersiniz, dönüş adresini yanlış yerde ararsınız, string'i ters okursunuz. Bu makale, çok mimarili analizde **doğru zihinsel modeli** kurmayı ve bunun tespit/savunma sonuçlarını amaçlar.

---

## Temel Kavram: Calling Convention Nedir?

**Calling convention**, bir fonksiyon çağrıldığında argümanların nereye konacağı, dönüş değerinin nereden okunacağı, hangi register'ların çağıran (caller) hangilerinin çağrılan (callee) tarafından korunacağı ve stack'in nasıl temizleneceğini belirleyen sözleşmedir. Derleyici ile işletim sistemi arasındaki bu ABI (Application Binary Interface) anlaşması, tersine mühendisin bir çağrıyı doğru yorumlaması için kritiktir.

### Kök Neden: Neden Mimariden Mimariye Değişir?

Fark, **register bolluğu** ve **tasarım felsefesinden** doğar. x86 (32-bit) yalnızca 8 genel amaçlı register'a sahiptir; bu kıtlık, argümanları büyük ölçüde **stack üzerinden** geçirmeye zorlar. ARM ve MIPS gibi RISC mimarileri ise 16-32 register sunar; bu bolluk, ilk birkaç argümanı **register'lar üzerinden** geçirmeyi verimli kılar. Register'da argüman geçirmek stack erişiminden hızlıdır (bellek erişimi yok), bu yüzden RISC ABI'ları register-ağırlıklıdır.

---

## x86 ve x64: Referans Nokta

Kıyaslama için önce tanıdık zemini netleştirelim.

### x86 (32-bit)

- **cdecl** (Linux/çoğu C): Tüm argümanlar **stack'e** ters sırayla (sağdan sola) push edilir. Dönüş değeri `EAX`. Stack'i **caller** temizler. Bu yüzden klasik stack overflow anlatımlarında dönüş adresi ve argümanlar hep stack'te aranır.
- **stdcall** (Win32 API): Argümanlar yine stack'te ama stack'i **callee** temizler (`ret N`).
- **fastcall**: İlk iki argüman `ECX`/`EDX`, gerisi stack.

### x86-64

- **System V AMD64** (Linux/macOS): İlk 6 tamsayı/pointer argümanı sırayla `RDI, RSI, RDX, RCX, R8, R9`. Dönüş `RAX`. Fazlası stack'te.
- **Microsoft x64** (Windows): İlk 4 argüman `RCX, RDX, R8, R9`. Ayrıca caller, callee'nin kullanabilmesi için **32 byte "shadow space"** ayırır — Windows binary analizinde bu boşluk kafa karıştırır.

Kritik nokta: x86'dan x64'e geçerken bile "argümanlar stack'te" refleksi kırılır. RISC'e geçince tamamen değişir.

---

## ARM32 / AArch32 (32-bit)

### Register Modeli

16 görünür register: `R0`–`R12` genel amaçlı, `R13 = SP` (stack pointer), `R14 = LR` (link register), `R15 = PC` (program counter). Ayrıca durum register'ı `CPSR` (flag'ler burada).

### Calling Convention (AAPCS)

**ARM Architecture Procedure Call Standard** (AAPCS) geçerlidir:

- İlk 4 argüman: `R0, R1, R2, R3`.
- Kalan argümanlar: **stack**.
- Dönüş değeri: `R0` (64-bit ise `R0:R1`).
- Callee-saved (korunması gereken): `R4`–`R11`. Caller-saved (scratch): `R0`–`R3`, `R12`.

### En Kritik Fark: LR (Link Register)

x86'da `call` komutu dönüş adresini **otomatik olarak stack'e** yazar. ARM'da `BL` (Branch with Link) komutu dönüş adresini **`LR` register'ına** yazar — stack'e değil. Bu, tersine mühendislik ve exploitation açısından derin sonuçlar doğurur:

- **Leaf fonksiyonlar** (başka fonksiyon çağırmayan): `LR`'ı hiç stack'e kaydetmeyebilir, dönüş adresi register'da kalır. Klasik "stack'teki return adresini ez" saldırısı burada çalışmaz.
- **Non-leaf fonksiyonlar**: `LR`'ı prolog'da stack'e **push** eder (genellikle `PUSH {..., LR}`), epilog'da geri yükler (`POP {..., PC}` — doğrudan PC'ye pop ederek döner). Kontrol akışı ancak bu kaydedilmiş `LR` ezildiğinde ele geçirilir.

Bu yüzden ARM'da bir fonksiyonun sömürülebilirliğini anlamak için prolog/epilog'a bakıp `LR`'ın stack'e kaydedilip kaydedilmediğini görmek gerekir.

### Thumb Modu ve BX Bit'i

ARM32 iki komut setini destekler: 32-bit **ARM** ve daha yoğun 16/32-bit **Thumb/Thumb-2**. İşlemci hangi moddadır? Bunu **hedef adresin en düşük bit'i (bit 0)** belirler: bir dallanma adresinin bit 0'ı `1` ise Thumb moduna, `0` ise ARM moduna geçilir. Adres gerçekte 2/4-byte hizalıdır; bit 0 asla gerçek adres bit'i değil, bir **mod bayrağıdır**.

Bunun analiz sonucu: disassembler'da bir fonksiyon adresi `0x8001` görünür ama gerçek kod `0x8000`'dedir ve Thumb'dır. Yanlış mod seçilirse disassembler tamamen anlamsız çıktı üretir — çok mimarili analizde en sık yapılan hatalardan biridir.

---

## AArch64 (ARM64, 64-bit)

### Register Modeli

31 adet 64-bit genel amaçlı register: `X0`–`X30` (32-bit alt yarıları `W0`–`W30`). Ayrıca `SP` (ayrı, X31 sayılmaz), `PC` doğrudan erişilemez. Özel isimler:

- `X30 = LR` (link register — hâlâ ayrı!)
- `X29 = FP` (frame pointer, geleneksel)
- `X0`–`X7`: ilk 8 argüman.
- `X8`: bazı çağrılarda indirect result / syscall numarası (Linux).

### Calling Convention (AAPCS64)

- İlk **8** argüman: `X0`–`X7`. Fazlası stack.
- Dönüş: `X0`.
- Callee-saved: `X19`–`X28` ve `X29/X30`.
- 16-byte **stack alignment** zorunluluğu (SP her zaman 16'nın katı).

AArch64'te de dönüş adresi `LR (X30)` üzerinden gelir; non-leaf fonksiyonlar prolog'da `STP X29, X30, [SP, ...]` (store pair) ile FP ve LR'ı birlikte kaydeder, epilog'da `LDP` ile geri yükler ve `RET` çalıştırır. Bu ikili push/pop deseni AArch64 fonksiyonlarını görsel olarak tanımlamanın en hızlı yoludur.

### Pointer Authentication (PAC) — Modern Savunma

AArch64'ün 8.3-A sürümüyle gelen **Pointer Authentication**, pointer'ların kullanılmayan üst bitlerine kriptografik bir imza (PAC) yerleştirir. `PACIASP` prolog'da LR'ı imzalar, `AUTIASP` epilog'da doğrular; imza tutmuyorsa dönüş bir fault üretir. Bu, ROP/JOP saldırılarını doğrudan hedefleyen donanımsal bir mitigasyondur ve modern Apple Silicon / yeni Android cihazlarda yaygındır. Analizde `PACIASP`/`AUTIASP`/`RETAA` komutlarını görmek, hedefin ROP'a karşı sertleştirildiğini gösterir.

---

## MIPS

MIPS, ev/ofis router'ları ve eski gömülü sistemlerde hâlâ çok yaygındır; router malware analizinin belkemiğidir.

### Register Modeli ve İsim Karışıklığı

32 register vardır ama numaralar yerine **ABI isimleri** kullanılır (bu, MIPS'e yeni geçenlerin en çok yanıldığı yerdir):

- `$zero` ($0): daima 0.
- `$a0`–`$a3`: argümanlar (argument).
- `$v0`, `$v1`: dönüş değeri (value).
- `$t0`–`$t9`: geçici (temporary, caller-saved).
- `$s0`–`$s7`: kaydedilen (saved, callee-saved).
- `$sp`: stack pointer, `$fp`: frame pointer, `$ra`: return address, `$gp`: global pointer.

### Calling Convention (O32 ve Ötesi)

En yaygın **O32** ABI:

- İlk 4 argüman: `$a0`–`$a3`.
- Dönüş: `$v0` (`$v1` ek).
- Kritik ve tuhaf ayrıntı: O32'de, argümanlar register'da geçse bile caller stack'te **argümanlar için 16 byte'lık boşluk** ("argument slots" / home space) ayırır. Bu, Windows x64 shadow space'e benzer bir tuzaktır.
- 64-bit varyantlar (N32, N64) 8 argüman register'ı kullanır (`$a0`–`$a7`).

### Return Address: $ra

x86'daki gibi stack'te değil, ARM'daki `LR` gibi bir register'da (`$ra`) tutulur. Non-leaf fonksiyonlar `$ra`'yı stack'e kaydeder.

### En Ünlü Tuzak: Delay Slot

MIPS'te bir dallanma/atlama komutundan (`jal`, `beq`, `j`, `jr` vb.) **hemen sonraki komut**, dallanma gerçekleşmeden önce **daima çalıştırılır**. Buna **branch delay slot** denir. Kökeni klasik MIPS pipeline'ıdır: dallanma kararı hesaplanırken pipeline'ın bir sonraki komutu zaten getirmiştir; bu komutu boşa harcamak yerine mimari onu "meşru" kabul eder.

Sonuçları:

- **Statik analizde**: `jr $ra` (dönüş) komutundan sonraki satır, fonksiyon "dönmüş" gibi görünse de **çalışır**. Delay slot'u dönüş sonrası ölü kod sanmak ciddi bir hatadır.
- **Sıralama**: Assembly'de dallanma komutundan sonra yazılan komut, kavramsal olarak dallanmadan **önce** etkisini gösterir. Analist kod akışını buna göre okumalıdır.
- Derleyici çoğu zaman delay slot'a faydalı bir komut yerleştirir; kullanılamıyorsa `nop` koyar.

---

## Endianness: Bayt Sırası

**Endianness**, çok baytlı bir değerin bellekte hangi sırayla saklandığını belirler.

- **Little-endian (LE)**: En düşük anlamlı byte önce (düşük adreste). x86/x64, çoğu ARM (varsayılan olarak LE çalışır).
- **Big-endian (BE)**: En yüksek anlamlı byte önce. Ağ protokollerinin "network byte order"ı BE'dir; birçok **MIPS router firmware'i BE**'dir.

ARM ve MIPS aslında **bi-endian**'dır — yani her iki modda da çalışabilirler; hangisi olduğu derleme/donanım yapılandırmasına bağlıdır. Bu yüzden bir MIPS binary'sini analiz ederken "MIPS mi yoksa MIPSEL mi (little-endian MIPS)?" sorusu kritiktir.

### Analitik Sonuç

- **String'ler**: LE olarak açılmış BE bir binary'de ASCII string'ler 4'lü gruplar hâlinde ters okunur (örneğin "HTTP" yerine "PTTH" gibi kırık çıktılar). Bu, endianness'ı yanlış seçtiğinizin en hızlı işaretidir.
- **Sabitler ve adresler**: Yanlış endianness ile immediate değerler ve pointer'lar tamamen anlamsız çıkar; disassembler geçerli görünen ama yanlış bir kod üretebilir.
- **file komutu** çoğu zaman doğru cevabı verir: `ELF 32-bit MSB executable, MIPS` (MSB = big-endian) ya da `LSB ... MIPS` (little-endian).

---

## Örnek: Aynı Fonksiyonun Üç Mimarideki İskeleti

`int topla(int a, int b) { return a + b; }` fonksiyonunun kavramsal karşılığı:

- **x86-64 (System V)**: `a`→`EDI`, `b`→`ESI`; `lea eax, [rdi+rsi]`; sonuç `EAX`; `ret` (dönüş adresi stack'ten).
- **AArch64**: `a`→`W0`, `b`→`W1`; `add w0, w0, w1`; sonuç `W0`; `ret` (dönüş adresi `X30/LR`'dan). Leaf olduğu için stack'e hiç dokunmayabilir.
- **MIPS (O32)**: `a`→`$a0`, `b`→`$a1`; `addu $v0, $a0, $a1`; sonuç `$v0`; `jr $ra` ve ardından delay slot'ta muhtemelen `nop` veya `move`.

Aynı kaynak kod, üç farklı register hedefi, üç farklı dönüş mekanizması. x86 refleksiyle `$a0`'ı görmezden gelip stack'te argüman aramak, MIPS analizinde tamamen yanlış yola sokar.

---

## Tespit ve Savunma

Bu bilgi yalnızca akademik değildir; savunmacı için doğrudan operasyonel karşılığı vardır.

### Tespit (Detection Engineering)

1. **Mimari tespiti otomasyonu**: Firmware/örnek toplama pipeline'ında her binary için ELF header'dan mimari + endianness çıkarılmalı (`e_machine`, `EI_DATA` alanları). Yanlış disassembler yapılandırması sessiz yanlış-negatif üretir. YARA kurallarınızın mimari-bağımsız (byte deseni) mi yoksa mimari-özel mi olduğunu bilinçli seçin.

2. **Cross-architecture YARA/Sigma**: Aynı malware ailesi ARM, MIPS ve MIPSEL için ayrı derlenir. Tek bir opcode-tabanlı imza tüm varyantları yakalamaz. Config string'leri, C2 domain'leri, XOR anahtarları gibi **mimariden bağımsız** artefaktlara dayanan kurallar daha dayanıklıdır. Aynı botnet'in farklı mimari binary'lerini tek aileye bağlamak için import/string hash'leri kullanın.

3. **Behavioral / runtime tespit**: Statik disassembly mimariye göre değişse de, çalışma zamanı davranışı (dosya yazma, `/dev/watchdog` erişimi, telnet tarama, iptables manipülasyonu) mimariden bağımsızdır. Gömülü cihazlarda syscall/erişim tabanlı telemetri, opcode analizinden daha taşınabilir bir tespit katmanıdır.

### Savunma (Hardening)

1. **Derleme-zamanı mitigasyonlar**: `-fstack-protector-strong`, konumdan bağımsız yürütülebilir (**PIE/ASLR**), ve gömülü toolchain destekliyorsa **NX/XN** (execute-never bellek) etkinleştirin. Birçok ucuz IoT firmware'i bu korumaları kapalı derler — kök neden çoğu zaman eski toolchain ve boyut/performans kaygısıdır.

2. **AArch64'e özgü**: Donanım destekliyorsa **PAC (Pointer Authentication)** ve **BTI (Branch Target Identification)** etkinleştirin — bunlar ROP/JOP zincirlerini donanımsal olarak kırar. **MTE (Memory Tagging Extension)** bellek güvenliği hatalarını çalışma zamanında yakalayabilir.

3. **Mimari-farkında SBOM ve tarama**: Firmware tedarik zinciri kontrollerinde her mimari varyantın ayrı taranması gerekir; bir mimaride yamalı bir kütüphane, başka mimari derlemede eski kalabilir.

---

## Yaygın Hatalar (Sık Yapılan Yanlışlar)

- **x86 refleksiyle argüman aramak**: RISC'te ilk argümanlar register'da (`R0`/`X0`/`$a0`); stack'te aramak yanlış çağrı yorumu üretir.
- **Dönüş adresini stack'te sanmak**: ARM/MIPS'te dönüş adresi `LR`/`$ra`'dadır; leaf fonksiyonlarda hiç stack'e kaydedilmeyebilir. Klasik stack overflow şablonu her fonksiyonda geçerli değildir.
- **Thumb/ARM modunu karıştırmak**: Adresin bit 0'ını gerçek adres sanmak; disassembler'ı yanlış modda çalıştırıp çöp çıktı almak.
- **Delay slot'u yok saymak (MIPS)**: `jr $ra` sonrası komutu ölü kod sanmak; kontrol akışını yanlış sıralamak.
- **Endianness'ı varsaymak**: Her MIPS'i little-endian sanmak; ters okunan string'leri "şifreli" sanmak. Önce `file`/ELF header'a bakın.
- **Tek imzayla tüm varyantları yakalamaya çalışmak**: Aynı ailenin ARM/MIPS/MIPSEL derlemeleri farklı byte desenleri üretir; imzalarınızı mimari-farkında tasarlayın.
- **Shadow space / argument slot boşluğunu argüman sanmak**: MS x64 shadow space ve MIPS O32 arg slot'ları çağrı öncesi ayrılan boşluklardır, gerçek veri değil.

---

## Özet

Çok mimarili yetkinlik, "yeni bir komut seti öğrenmek" değil, **doğru ABI zihinsel modelini** kurmaktır: argümanların register'da geçtiğini (ARM `R0`/`X0`, MIPS `$a0`), dönüş adresinin `LR`/`$ra` register'ında yaşadığını, Thumb bit'inin bir mod bayrağı olduğunu, MIPS delay slot'unun akışı kaydırdığını ve endianness'ın string ile pointer okumasını temelden değiştirdiğini içselleştirmek. IoT/mobil/firmware malware'in koştuğu gerçek zemin budur; savunmacının hem doğru statik analiz yapması hem de mimari-farkında, davranış-temelli tespit kurabilmesi bu temele bağlıdır.
