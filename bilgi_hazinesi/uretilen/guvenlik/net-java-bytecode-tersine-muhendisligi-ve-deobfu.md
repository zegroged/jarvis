# .NET / Java Bytecode Tersine Mühendisliği ve Deobfuscation (ConfuserEx, ProGuard/DexGuard)

## Giriş ve Bağlam

Klasik tersine mühendislik (RE) eğitimi çoğunlukla native binary'ler (x86/x64/ARM makine kodu) üzerine kuruludur: disassembler, decompiler ve debugger ile ham CPU talimatlarını okuruz. Fakat günümüz tehdit ortamının önemli bir kısmı **managed code** (yönetilen kod) üzerinde çalışır. .NET ailesindeki RAT (Remote Access Trojan) ve stealer'lar (AgentTesla, AsyncRAT, Quasar türevleri gibi C#/VB.NET ile yazılan aileler), Android malware ise Dalvik/ART bytecode üzerinde çalışır. Bu dünyada analiz araçları ve teknikleri native RE'den ciddi biçimde farklıdır.

Temel fark şudur: hem .NET (**CIL** — Common Intermediate Language, eski adıyla **MSIL/IL**) hem de Java/Android (**JVM bytecode** ve **Dalvik/DEX bytecode**) yüksek seviyeli **metadata** taşır. Managed derleyici, kaynak koddaki sınıf adları, metot imzaları, alan (field) adları, tip bilgisi ve yerel değişken tablolarının çoğunu binary'e gömer. Bu metadata sayesinde decompiler'lar neredeyse orijinaline yakın kaynak kod üretebilir. İşte tam bu güç, saldırganı **obfuscation** (kod karartma) kullanmaya iter: metadata'yı bozarak, şifreleyerek veya anlamsızlaştırarak decompile edilebilirliği düşürmeye çalışır. Bu makale hem decompile mekaniğini hem de yaygın obfuscator'ların (ConfuserEx, ProGuard/DexGuard) çalışma mantığını, bunların **tespitini ve savunma/analiz stratejilerini** eğitim amaçlı ele alır.

---

## 1. Managed Bytecode Neden Kolay Decompile Edilir?

### Tanım

**Decompilation**, derlenmiş bytecode'dan okunabilir yüksek seviye kaynak koda (C#, Java) geri dönüş işlemidir. Native koda kıyasla managed kodda bu işlem çok daha başarılıdır.

### Kök Neden / Çalışma Mantığı

.NET assembly'leri PE (Portable Executable) formatında saklanır ama içinde native talimat değil, **CIL** ve zengin bir **metadata table** bulunur. Metadata; `#Strings`, `#Blob`, `#GUID`, `#US` (user strings) gibi heap'lerde tip ve üye tanımlarını taşır. CIL yığın tabanlı (stack-based) bir ara dildir: `ldstr`, `call`, `ldarg`, `stloc`, `newobj` gibi opcode'lar yüksek seviye yapıları neredeyse birebir yansıtır. Decompiler bu yapıyı analiz edip C#'a geri çevirir.

Java tarafında da `.class` dosyaları (veya Android'de `.dex`) benzer şekilde constant pool, metot tablosu ve tip bilgisi taşır. JVM bytecode da yığın tabanlıdır. Bu yüzden decompile başarı oranı native'e göre dramatik biçimde yüksektir; native'de kaybolan yerel değişken adları ve tip bilgisi burada büyük ölçüde korunur.

### Örnek

Basit bir C# metodu:

```csharp
string Merhaba(string ad) => "Selam " + ad;
```

Bunun CIL karşılığı kavramsal olarak şöyledir:

```
ldstr    "Selam "
ldarg.1
call     string System.String::Concat(string, string)
ret
```

Burada `"Selam "` string'i `#US` heap'inde açıkça durur; metot adı (`Merhaba`), parametre (`ad`) ve dönüş tipi metadata'da kayıtlıdır. Decompiler bunları toplayıp orijinale çok yakın C# üretir. İşte obfuscator'ın hedefi bu açıklığı bozmaktır.

### Analiz Araçları

- **dnSpy / dnSpyEx**: .NET için hem decompiler hem debugger. Kaynak kodu görebilir, breakpoint koyabilir, çalışan managed süreci adım adım izleyebilir ve hatta assembly'yi düzenleyip yeniden kaydedebilirsiniz. dnSpyEx aktif sürdürülen fork'tur.
- **ILSpy**: Açık kaynak, hafif decompiler (debugger'ı sınırlı). CIL/C# görünümü sağlar.
- **dotPeek**: JetBrains'in ücretsiz decompiler'ı.
- **ilasm / ildasm**: .NET SDK ile gelen resmi assembler/disassembler; CIL'i metne döküp geri derlemeye izin verir (round-trip patch için kullanışlı).
- **JADX**: Android APK/DEX için decompiler; DEX'ten Java kaynağı üretir, GUI ve CLI'sı vardır.
- **jadx, jd-gui, CFR, Procyon**: JVM `.class` decompiler'ları.
- **Bytecode Viewer**: birden çok decompiler'ı tek arayüzde toplar.
- **apktool**: APK'yı `smali` (Dalvik bytecode'un okunabilir metin biçimi) olarak açar; kaynak yerine bytecode düzeyinde düzenleme/yeniden paketleme sağlar.

---

## 2. Obfuscation'ın Genel Mantığı

### Tanım

**Obfuscation**, programın işlevini koruyup anlaşılabilirliğini düşüren dönüşümler bütünüdür. Amaç fikri mülkiyet koruması (ticari yazılım) veya analiz zorlaştırma (malware) olabilir. Tersine mühendisin gözünde iki durum da aynı teknik zorlukları doğurur.

### Yaygın Dönüşüm Kategorileri

- **Renaming (yeniden adlandırma)**: Anlamlı tip/metot/alan adlarını `a`, `b`, `A1`, ya da görünmez Unicode karakterlere çevirmek. En ucuz ve en yaygın teknik. Metadata korunur ama semantik ipucu kaybolur.
- **String encryption**: Sabit string'leri şifreleyip çalışma zamanında bir çözücü (decryptor) metotla açmak. `ldstr "http://c2..."` yerine `call StringDecryptor::Get(0x1F3)` görürsünüz.
- **Control flow obfuscation / flattening**: Doğal `if/while` yapısını, bir `switch` ve durum değişkeni (state machine) etrafında düzleştirmek. Kontrol akışı grafiği (CFG) okunamaz hale gelir.
- **Proxy / call hiding**: Doğrudan API çağrısı yerine reflection veya ara "proxy" metotlarla çağrı yapmak; böylece statik çağrı grafiği bulanır.
- **Anti-tamper / anti-debug**: Bütünlük (integrity) kontrolleri, debugger tespiti (`Debugger.IsAttached`, `IsDebuggerPresent`, timing kontrolleri), dnSpy/profiler tespiti.
- **Resource/assembly encryption & packing**: Asıl payload'ı şifreli bir kaynak (resource) olarak saklayıp runtime'da bellekte çözüp `Assembly.Load` ile yüklemek. Diskte "boş" görünen bir loader kalır.
- **Metadata bozma (invalid metadata)**: Decompiler'ı çökertmek için standarda uyan ama araçların beklemediği metadata üretmek.

### Kök Neden

Managed kodun decompile edilebilirliği yüksek olduğu için, saldırgan/koruyucu metadata ve string açıklığını bilinçli olarak "kirletir". Ancak kritik nokta şudur: **kod çalışması için sonunda gerçek talimatların ve gerçek string'lerin belleğe ulaşması gerekir.** Bu, savunmacının en güçlü kozudur — dinamik analiz ve bellek dökümü çoğu statik obfuscation'ı aşar.

---

## 3. ConfuserEx (.NET) — Çalışma Mantığı ve Karşı-Analiz

### Tanım

**ConfuserEx**, .NET assembly'leri için açık kaynak, ücretsiz ve çok yaygın bir obfuscator'dır. Orijinali arşivlenmiş olsa da çok sayıda fork ve türev (ör. "ConfuserEx2" gibi topluluk sürümleri) malware'de ve crackme'lerde sık görülür. AgentTesla, çeşitli .NET stealer ve loader'lar geçmişte ConfuserEx türevleriyle korunmuş örnekler barındırır.

### Çalışma Mantığı (Protection'lar)

ConfuserEx modüler "protection" katmanları uygular. Tipik olanları:

- **Anti-debug / anti-dump / anti-tamper**: Süreç bütünlüğünü kontrol eder; metot gövdelerini şifreli tutup çalışma anında çözer (anti-tamper). Bu, statik olarak IL'in "bozuk" görünmesine yol açar — metot gövdeleri disk üzerinde geçerli IL değildir, ancak JIT sırasında bir çözücü rutin tarafından açılır.
- **Constants / string encryption**: String ve sabitleri bir tabloya taşıyıp çözücü çağrılarla açar.
- **Control flow**: IL düzeyinde akışı düzleştirir; `switch` tabanlı devasa durum makineleri üretir.
- **Renaming**: Genelde görünmez/karışık Unicode veya çok kısa adlar. Namespace ve tip adları kaybolur.
- **Reference proxy**: Metot çağrılarını dinamik olarak çözülen delegate/proxy'lere yönlendirir.

Karakteristik bir işaret: `ConfusedByAttribute` benzeri bir attribute veya modül seviyesinde tuhaf/geçersiz görünen metadata, dnSpy'da metot gövdesi yerine "invalid" uyarıları.

### Örnek Analiz Akışı (Eğitimsel)

1. **Tanıma**: `DIE (Detect It Easy)` veya benzeri araçlar assembly'nin .NET olduğunu ve muhtemel obfuscator'ı işaret eder. dnSpy'da açtığınızda anlamsız tip adları, çözücü metotlar ve bozuk gövdeler görürsünüz.
2. **Statik deobfuscation denemesi**: **de4dot** tarihsel olarak birçok .NET obfuscator'ı (eski ConfuserEx dahil) tanıyıp string'leri çözebilen, renaming'i düzeltmeye çalışan bir araçtır. Ancak modern ConfuserEx fork'larında de4dot her zaman tam başarılı olmaz; bu normaldir ve dinamik yönteme geçilir.
3. **Dinamik yaklaşım (en güvenilir)**: Malware'i **izole edilmiş, ağ kontrollü bir sanal makinede** dnSpy debugger ile çalıştırırsınız. Anti-tamper metot gövdesini bellekte çözdüğü an, JIT edilmiş gerçek IL bellekte bulunur. String decryptor'a breakpoint koyup her çözülen string'i dönüş değerinde okuyabilirsiniz. Bu, "çözücüyü tersine mühendisliğe uğratmak yerine sadece çıktısını gözlemlemek" prensibidir — analiz ekonomisinde çok değerlidir.
4. **Bellek dökümü**: Süreç kendini çözdükten sonra managed assembly'yi bellekten dump eden araçlar (ör. .NET süreçleri için managed dump araçları / dnSpy'ın modül kaydetme özelliği) kullanılabilir. Böylece "temizlenmiş" bir assembly elde edip yeniden decompile edersiniz.

> Not: de4dot'un tam sürüm-özel davranışları, ConfuserEx fork'larının kesin sürüm numaraları ve bayrakları zamanla değişir; burada verilen isimler kavramsaldır. Belirli bir örnekte hangi tekniğin işe yaradığını **deneysel olarak** doğrulamak esastır.

### Anti-Debug ile Baş Etme

ConfuserEx'in anti-debug'ı genelde `Debugger.IsAttached`, çevre kontrolü ve zaman ölçümü gibi tekniklere dayanır. dnSpy tarafında bu kontrollerin döndüğü değeri patch'lemek (ör. ilgili metodu `return false` yapacak şekilde IL düzenlemek) yaygın bir analiz manevrasıdır. Bu **savunmacı/analist** bir işlemdir: örneği anlamak için yapılır, dağıtım için değil.

---

## 4. ProGuard ve DexGuard (Java / Android) — Çalışma Mantığı

### Tanım

**ProGuard**, Java/Android için açık kaynak bir **shrinker + optimizer + obfuscator**'dır. Öncelikli amacı kullanılmayan kodu atmak (shrink) ve isimleri kısaltmaktır; güçlü bir anti-analiz aracı değildir. **DexGuard** ise ProGuard'ın ticari, çok daha agresif "kardeşidir": string şifreleme, sınıf şifreleme, reflection ile API gizleme, resource şifreleme, kök/emülatör/tamper tespiti ve native koruma katmanları ekler. Kötü amaçlı Android uygulamaları çoğunlukla DexGuard benzeri ticari koruyucular veya özel packer'lar kullanır.

### Kök Neden / Çalışma Mantığı

- **ProGuard renaming**: `com.sirket.PaymentManager.processPayment()` gibi adlar `a.b.a()` olur. Bir **mapping.txt** dosyası (orijinal↔yeni ad eşlemesi) üretir; bu dosya normalde geliştiricide kalır, crash raporlarını çözmek için kullanılır. Analiz eden taraf bu dosyaya erişemez, bu yüzden adlar geri getirilemez ama davranış hâlâ okunur — çünkü ProGuard string veya kontrol akışı şifrelemez.
- **DexGuard string encryption**: String literal'leri şifreli byte dizilerine çevirip runtime'da bir çözücü ile açar; JADX'te doğrudan URL/anahtar görmek yerine çözücü çağrıları görürsünüz.
- **DexGuard reflection & API hiding**: Hassas API çağrılarını (`getDeviceId`, `sendTextMessage` vb.) doğrudan yerine reflection üzerinden isimleri şifreli olarak çağırır; statik çağrı grafiğini bulanıklaştırır.
- **Class/resource encryption ve dinamik yükleme**: Asıl kod şifreli asset olarak paketlenir, çalışma anında `DexClassLoader` benzeri mekanizmalarla belleğe/geçici dosyaya çözülüp yüklenir. Bu, .NET'teki resource-şifreli loader mantığının Android karşılığıdır.
- **Anti-analiz**: Root tespiti, emülatör tespiti (build parmak izleri, sensor yokluğu), Frida/debugger tespiti, imza (signature) doğrulaması ile tamper kontrolü.

### Örnek Analiz Akışı (Eğitimsel)

1. **Statik başlangıç**: `apktool` ile APK'yı açıp manifest, izinler ve `smali`'yi incelersiniz; `jadx` ile Java'ya decompile edersiniz. ProGuard'la korunmuş sade bir uygulamada mantık büyük ölçüde okunur, sadece adlar anlamsızdır.
2. **DexGuard karşısında**: string'ler ve çağrılar gizlendiğinde statik analiz tıkanır. Burada **dinamik enstrümantasyon** öne çıkar: **Frida** ile çalışan uygulamaya bağlanıp, string çözücü metoduna hook takarak dönüş değerlerini loglarsınız. Böylece C2 adresleri, şifreleme anahtarları ve çözülmüş string'ler çalışma anında ortaya çıkar.
3. **Unpacking**: Dinamik olarak yüklenen DEX'i yakalamak için `DexClassLoader`/`loadDex` çağrılarını hook'layıp belleğe düşen DEX'i diske dump eder, sonra tekrar JADX'e verirsiniz.
4. **Anti-analiz atlatma**: Root/emülatör/Frida tespit metotlarını Frida ile patch'leyerek (dönüş değerini zorlayarak) örneğin çalışmaya devam etmesini sağlarsınız — yine **analiz** amaçlı.

> Not: DexGuard tescilli olduğu için kesin katman isimleri ve sürüm davranışları örnekten örneğe değişir; "DexGuard benzeri" ifadesi çoğu zaman özel packer'ları da kapsar. Kesin tanı, örneğin davranışına bakılarak yapılır.

---

## 5. Tespit ve Savunma

Bu bölüm, obfuscation'ı **tespit etmek** ve managed malware'e karşı **savunma** kurmak içindir.

### Statik / Dosya Düzeyi Tespit

- **Obfuscator imzaları**: `DIE`, YARA kuralları ve topluluk imzaları ConfuserEx/DexGuard izlerini (attribute'lar, tipik çözücü desenleri, entropi yüksek resource'lar) yakalayabilir. Yüksek entropili gömülü resource + küçük "loader" kodu klasik bir "packed .NET" işaretidir.
- **.NET metadata anomalileri**: Görünmez Unicode adlar, geçersiz görünen metot gövdeleri, `Assembly.Load(byte[])` / `Activator.CreateInstance` + şifre çözme çağrılarının bir arada bulunması güçlü şüphe işaretidir.
- **Android**: Çok sayıda `reflection` çağrısı, `DexClassLoader` kullanımı, şifreli asset dosyaları, izinlerle kod arasındaki uyumsuzluk (izni var ama statik olarak kullanan kod yok — çünkü reflection'la gizli) incelenir.

### Davranışsal / Runtime Tespit (En Etkili Katman)

Obfuscation statik imzayı bozar ama davranışı değiştiremez. Bu yüzden **EDR ve davranışsal tespit** managed malware'de kritiktir:

- **.NET tarafında**: `Assembly.Load` ile bellekten modül yükleme, **AMSI** (Antimalware Scan Interface) — .NET'te `Assembly.Load`, PowerShell ve script'ler AMSI'a hooklanır; bellekte çözülen payload tarama anında görülebilir. AMSI bypass girişimlerini (ör. `amsi.dll` yaması) izlemek ayrı bir tespit sinyalidir.
- **ETW (Event Tracing for Windows)** ve özellikle CLR ETW sağlayıcıları JIT edilen metotları, yüklenen assembly'leri gözlemleyebilir; "in-memory" .NET yüklemeleri buradan yakalanır.
- **Process davranışı**: Beklenmeyen ebeveyn-çocuk süreç ilişkileri, `RegAsm`/`InstallUtil`/`MSBuild` gibi LOLBIN'ler üzerinden .NET çalıştırma, şüpheli ağ bağlantıları (C2), keylogger davranışı (AgentTesla tarzı stealer'lar SMTP/FTP/HTTP ile veri sızdırır) izlenir.
- **Android**: Uygulamanın çalışma anında ek DEX yüklemesi, dinamik reflection ile hassas API çağrıları, beklenmeyen ağ trafiği MDM/EDR ve kum havuzu (sandbox) ile yakalanır.

### Savunma Kontrolleri

- **Uygulama beyaz listeleme** (WDAC / AppLocker): İmzasız veya bilinmeyen .NET assembly'lerinin, script host'ların ve LOLBIN kötüye kullanımının çalışmasını engeller. Bu, obfuscation ne kadar iyi olursa olsun **yürütme kapısını** kapatır.
- **AMSI + güncel EDR** ile bellek-içi yükleme tespiti açık tutulmalı.
- **E-posta ve ağ katmanı**: .NET stealer'lar çoğunlukla e-posta ekiyle (script/loader) gelir; ek filtreleme, makro/script kısıtları ve egress (C2) filtreleme birincil savunmadır.
- **Android**: Yalnızca güvenilir kaynaklardan uygulama, Play Protect/MDM, çalışma anında dinamik kod yükleyen uygulamalara şüpheyle yaklaşan politikalar.
- **Sandbox/telemetri**: Şüpheli örnekleri izole ortamda çalıştırıp çözülen string'leri (C2, anahtar) IOC olarak toplayıp SIEM'e beslemek.

### Analist İçin Anahtar İlke

**"Kod çalışmak için kendini çözmek zorundadır."** ConfuserEx string şifrelemesi de DexGuard reflection'ı da statik olarak zorlayıcıdır, ama runtime'da çözücü çağrısının çıktısını gözlemlemek (dnSpy breakpoint / Frida hook) neredeyse her zaman gerçek veriyi verir. Deobfuscation'da hedef, "çözme algoritmasını yeniden inşa etmek" değil çoğu zaman "çözücünün çıktısını yakalamaktır".

---

## 6. Yaygın Hatalar

- **Malware'i izole olmayan ortamda çalıştırmak**: Dinamik analiz güçlüdür ama .NET/Android örnekleri gerçek zararlıdır. Ağı kontrollü, snapshot alınmış, kurumsal ağdan yalıtık bir VM/emülatör şart. Aksi halde C2'ye gerçekten bağlanır veya yayılır.
- **de4dot / tek araca körü körüne güvenmek**: Modern fork'lar bilinen deobfuscator'ları atlatabilir. Araç başarısız olduğunda "örnek çözülemez" sonucu çıkarmak hatadır; dinamik yönteme geçmek gerekir.
- **String'i "çözmek yerine anlamaya" çalışmak**: Çözücü algoritmasını elle tersine mühendisliğe uğratmak saatler alabilirken, decryptor'ın dönüşüne breakpoint koymak dakikalar alır. Yanlış ekonomi büyük zaman kaybıdır.
- **Anti-tamper IL'ini disk üzerinde okumaya çalışmak**: ConfuserEx anti-tamper'da metot gövdesi diskte geçerli IL değildir; sadece runtime'da çözülür. Statik decompile'da "bozuk" görmek beklenen durumdur, örnek bozuk değildir.
- **Renaming'i "şifreleme" sanmak**: Yeniden adlandırma metadata'yı korur; davranış hâlâ okunur. Adların anlamsız olması analizi zorlaştırır ama imkânsız kılmaz. Panik yerine akışı izlemek yeterlidir.
- **mapping.txt beklentisi**: ProGuard mapping dosyası geliştiricide kalır; analistte olmaz. Adları geri getirmeye çalışmak yerine davranış üzerinden anlam çıkarmak doğru yaklaşımdır.
- **Sadece statik veya sadece dinamik analiz**: İkisi tamamlayıcıdır. Statik yapıyı verir, dinamik gizli veriyi açar. Managed malware'de ikisini birlikte kullanmayan analiz eksik kalır.
- **AMSI/ETW'yi göz ardı etmek**: Savunma tarafında obfuscation'a takılıp bellek-içi yükleme telemetrisini (AMSI, CLR ETW) kullanmamak, en etkili tespit katmanını boşa harcamaktır.

---

## Özet

.NET (CIL/metadata) ve Java/Android (JVM/DEX bytecode) managed kod olduğu için native'e göre çok daha iyi decompile edilir; bu güç, obfuscation'ı (ConfuserEx, ProGuard/DexGuard) zorunlu kılar. Obfuscation renaming, string/kod şifreleme, kontrol akışı düzleştirme ve anti-analiz katmanlarıyla statik analizi zorlaştırır, ama çalışan kod eninde sonunda gerçek talimatları ve string'leri belleğe getirmek zorundadır. Bu nedenle en güvenilir analiz yolu dnSpy/Frida ile **dinamik** çözücü çıktısını gözlemlemek, en güçlü savunma ise imza tabanlı statiği değil AMSI/ETW/EDR ile **davranışsal** tespiti ve WDAC/AppLocker ile yürütme kontrolünü esas almaktır.
