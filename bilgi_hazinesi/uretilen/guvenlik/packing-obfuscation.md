# Packing ve Obfuscation

## Tanım

**Packing** (paketleme), bir çalıştırılabilir dosyanın (executable) asıl kodunu ve verisini sıkıştırılmış ya da şifrelenmiş bir bloğa dönüştürüp, dosyanın başına bu bloğu çalışma anında (runtime) açan küçük bir yükleyici kod (unpacking stub / loader) yerleştirme işlemidir. Dosya çalıştırıldığında önce bu stub çalışır, orijinal kodu bellekte geri açar (in-memory), sonra kontrolü asıl programa devreder.

**Obfuscation** (belirsizleştirme / karartma) ise daha geniş bir şemsiye terimdir: kodun işlevini değiştirmeden, insan ve otomatik analiz araçları için anlaşılmasını zorlaştırma tekniklerinin tümünü kapsar. Packing, obfuscation'ın en agresif alt kümelerinden biridir; ama obfuscation ayrıca string şifreleme, control-flow flattening, dead code enjeksiyonu, API çağrılarının gizlenmesi gibi daha ince teknikleri de içerir.

İkisi birbiriyle karıştırılır ama ayrım önemlidir: packing statik olarak **kodu görünmez yapar** (disassembler açtığında anlamlı komut göremezsiniz), obfuscation ise genelde **kodu görünür ama anlaşılmaz** yapar. İkisi çoğu zaman birlikte kullanılır.

Bu teknikler hem meşru amaçlarla (dosya boyutu küçültme, fikri mülkiyet koruması, lisans kontrolü, DRM) hem de kötü amaçlı yazılım (malware) tarafından tespitten kaçmak için kullanılır. Bir güvenlik uzmanı için asıl beceri, "bu dosya paketlenmiş mi?" sorusundan "hangi paketleyici, neden ve altında ne saklı?" sorusuna geçebilmektir.

## Kök Neden: Neden Packing ve Obfuscation Var?

Bu tekniklerin varlığı, iki taraflı bir gerilimin sonucudur. Bir tarafta savunmacılar statik analiz yapmak ister: dosyayı çalıştırmadan içindeki string'leri, import edilen fonksiyonları, kod akışını okumak. Diğer tarafta saldırgan (ya da meşru koruyucu) bu okumayı imkânsızlaştırmak ister.

Statik analizin gücü şuna dayanır: bir PE (Portable Executable) veya ELF dosyasında kod bölümü (`.text`), veri bölümü, import tablosu (IAT — Import Address Table) ve string'ler açıkça durur. Bir antivirus imza tabanlı motoru, dosyanın belirli byte dizilerini (signature) bilinen zararlı örneklerle karşılaştırır. Analist ise `strings` aracıyla saniyeler içinde bir C2 (command and control) adresi ya da şüpheli komut görebilir.

Packing tam da bu zinciri kırar. Orijinal kod sıkıştırıldığında veya şifrelendiğinde:

- **String'ler kaybolur.** `strings` çalıştırdığınızda anlamlı metin çıkmaz, sadece rastgele görünen byte'lar çıkar.
- **Import tablosu incelir.** Paketlenmiş bir dosya genelde çok az sayıda API import eder (`LoadLibrary`, `GetProcAddress`, `VirtualAlloc`/`VirtualProtect` gibi). Çünkü asıl import'lar unpacking anında dinamik olarak çözülür (resolve). Bu "yağsız" import tablosu başlı başına bir kırmızı bayraktır.
- **İmza eşleşmesi bozulur.** Aynı zararlı yazılım farklı bir key ile paketlenirse byte imzası tamamen değişir. Bu yüzden tek bir malware ailesi, sadece packing katmanını değiştirerek yüzlerce farklı imza üretebilir (polymorphism).

Burada asıl kök neden şudur: **kod, çalışmak için eninde sonunda bellekte açık haliyle bulunmak zorundadır.** CPU şifreli komut çalıştıramaz. Bu, packing'in temel zafiyetidir ve bütün unpacking stratejisinin dayandığı fiziksel gerçektir. Ne kadar katman koyarsanız koyun, en son katmanda CPU'nun göreceği plaintext (açık) makine kodu bir yerde, bir anda bellekte belirir. Savunmacının işi o anı yakalamaktır.

## Entropi: Paketlemenin Termodinamik İzi

Packing'i tespit etmenin en klasik ve en güçlü sezgisel yöntemi **entropi** ölçümüdür. Buradaki entropi, Shannon entropisidir: bir byte dizisindeki bilgi yoğunluğunun / rastgeleliğin ölçüsü. Değer 0 ile 8 bit/byte arasında ifade edilir.

Mantığı şudur: normal makine kodu ya da düz metin, istatistiksel olarak öngörülebilirdir. Belirli byte'lar (örneğin `0x00`, `0x90` NOP, sık kullanılan opcode'lar) diğerlerinden çok daha fazla geçer. Bu yüzden normal bir `.text` bölümünün entropisi tipik olarak 6.0–6.5 civarındadır. Düz İngilizce metin daha da düşüktür.

Ama sıkıştırılmış ya da şifrelenmiş veri **maksimum rastgeleliğe yakınsar.** İyi bir sıkıştırma algoritması tanım gereği fazlalığı (redundancy) yok eder; iyi bir şifreleme çıktısı rastgeleden ayırt edilemez olmalıdır. Sonuç: bu bölümlerin entropisi 7.0'ın, çoğu zaman 7.5–8.0'ın üstüne çıkar.

Bu yüzden bir analist, PE bölümlerinin entropisine bakar. Eğer `.text` gibi bir kod bölümünün entropisi 7.2 gibi anormal yüksek bir değerdeyse, ya da normalde boş olması gereken bir bölüm yüksek entropi taşıyorsa, orada paketlenmiş/şifrelenmiş bir yük olduğuna güçlü şekilde işaret eder.

Somut olarak: `pefile` gibi kütüphaneler ya da PEStudio, Detect It Easy (DIE) gibi araçlar her bölümün entropisini raporlar. Basit bir Python yaklaşımıyla bir byte bloğunun entropisi, her byte değerinin olasılığı üzerinden Shannon formülüyle hesaplanır:

```
H = -Σ p(x) * log2(p(x))
```

Burada dürüst olmak gerekir: **yüksek entropi packing'in kesin kanıtı değildir.** Sıkıştırılmış kaynaklar (gömülü PNG, ZIP, video), TLS trafiği, dijital imzalanmış kod parçaları da yüksek entropi verir. Meşru sıkıştırıcılar da (UPX ile paketlenmiş bir açık kaynak araç gibi) yüksek entropi üretir. Entropi bir **sinyaldir, hüküm değil.** Deneyimli analist entropiyi diğer belirtilerle (ince import tablosu, tuhaf bölüm isimleri, yazılabilir+çalıştırılabilir bölümler) birlikte değerlendirir.

## Yaygın Paketleyiciler ve Çalışma Mantıkları

Paketleyicileri kabaca üç kategoriye ayırabiliriz:

**1. Sıkıştırıcı paketleyiciler (compressors).** En bilineni **UPX** (Ultimate Packer for eXecutables). UPX aslen kötü amaçlı değildir; boyut küçültmek için tasarlanmıştır. Kodu sıkıştırır, açan bir stub ekler. UPX'in güzel yanı çoğu zaman `upx -d` ile temiz bir şekilde geri açılabilmesidir — çünkü format belgelidir ve stub standarttır. Malware yazarları UPX kullanır ama genelde onu **değiştirir** (bölüm isimlerini bozar, header'ı kurcalar) ki standart `upx -d` çalışmasın. Bu durumda dosya hâlâ UPX mantığıyla açılır ama otomatik araç reddeder; manuel unpacking gerekir.

**2. Koruyucular / protector'lar.** Bunlar sadece sıkıştırmaz, aktif olarak analiz karşıtı katman ekler: anti-debugging, anti-VM, kod bütünlüğü kontrolleri, lisanslama. Ticari örnekler bu sınıfa girer. Bu araçlar çok katmanlı stub, şifreli bölümler ve bazen çalışma anında kodu parça parça açıp tekrar şifreleyen mekanizmalar kullanır.

**3. Virtualizer'lar (kod sanallaştırıcılar).** En zoru bunlardır. Orijinal x86 komutlarını, sadece kendi ürettikleri özel bir sanal makinenin (VM) anladığı bir bytecode'a çevirirler. Çalıştırıldığında dosya içinde gömülü bir yorumlayıcı (interpreter) bu bytecode'u okuyup yürütür. Burada artık bellekte hiçbir noktada orijinal x86 kodu belirmez — çünkü orijinal kod artık x86 değil, sizin bilmediğiniz bir ISA'dır. Bunları çözmek, VM'in kendisini tersine mühendislikle çıkarıp bytecode semantiğini yeniden inşa etmeyi gerektirir; haftalar süren bir iştir.

Bu ayrım pratikte önemlidir: bir UPX örneğiyle karşılaşan analistin işi yarım saatlik, bir virtualizer örneğiyle karşılaşanın işi haftalıktır. İlk adım hep "hangi kategoriyle karşı karşıyayım?" tespitidir.

## Obfuscation Teknikleri: Kodu Görünür Ama Anlaşılmaz Yapmak

Packing kodu gizlerken, obfuscation kodu okunabilir bırakıp anlamsızlaştırır. Başlıca teknikler:

**String şifreleme.** En yaygın olanı. Zararlı yazılım, C2 adresini, dosya yollarını, kayıt defteri (registry) anahtarlarını düz metin bırakmaz; bir XOR anahtarıyla ya da basit bir algoritmayla şifreler ve kullanacağı anda bellekte çözer. `strings` bu yüzden boş çıkar. Karşı hamle: string'lerin çözüldüğü decrypt fonksiyonunu bulup ya emülasyonla ya breakpoint ile çözülmüş halini yakalamak.

**Control-flow flattening (kontrol akışı düzleştirme).** Normalde bir fonksiyonun akışı if/else, döngü gibi doğal bir yapı taşır ve decompiler bunu güzel gösterir. Flattening bu yapıyı yıkar: bütün kod bloklarını tek bir dev `switch` deyiminin (bir "dispatcher") içine koyar ve bir durum değişkeni (state variable) ile hangi bloğun sırada olduğunu yönetir. Sonuç: decompiler çıktısı, birbirini rastgele çağıran yüzlerce durumdan oluşan, insan gözüyle takip edilemez bir spagettiye döner.

**Opaque predicate (opak koşul) enjeksiyonu.** Sonucu her zaman aynı olan ama analistin (ve statik aracın) bilemeyeceği matematiksel koşullar eklenir. Örneğin "eğer `x*x` her zaman negatif değilse" gibi. Bu koşullar hiçbir işe yaramayan (dead) kod dallarına yol açar ve analiz aracını yanlış yollara sokar.

**API gizleme / dynamic import resolution.** Zararlı yazılım hangi Windows API'lerini kullandığını import tablosunda göstermek istemez. Bunun yerine API isimlerini hash'ler, çalışma anında yüklü DLL'lerin export tablosunu tarayıp hash'i eşleştirerek fonksiyon adresini bulur (API hashing tekniği). Böylece IAT boş görünür ve statik analist hangi yeteneklere sahip olduğunu göremez.

Bu tekniklerin ortak kök nedeni aynıdır: analistin ve otomatik aracın **bilişsel yükünü** ve **hesaplama maliyetini** o kadar artırmaktır ki analiz ekonomik olarak zahmete değmesin. Obfuscation asla mutlak koruma sağlamaz; sadece maliyeti artırır. Bu, güvenliğin genel bir prensibidir: amaç imkânsızlaştırmak değil, saldırganı yeterince yavaşlatmaktır.

## Anti-Analiz: Analizciyi Fark Edip Davranış Değiştirmek

Packing ve obfuscation kodu gizler; **anti-analiz** ise bir adım öteye geçip aktif olarak "beni inceliyorlar mı?" diye kontrol eder ve incelendiğini anlarsa davranışını değiştirir (genelde zararsız görünür ya da çöker). Başlıca aileler:

**Anti-debugging.** Bir debugger (WinDbg, x64dbg, GDB) altında çalışıp çalışmadığını tespit eder. Klasik yöntemler: Windows'ta `IsDebuggerPresent` API'sini ya da doğrudan PEB (Process Environment Block) içindeki `BeingDebugged` bayrağını okumak; komutların çalışma süresini ölçmek (debugger tek adım attırınca zaman anormal uzar — timing check); `INT 3` breakpoint byte'ı olan `0xCC`'yi kendi kodunda aramak (breakpoint tespiti); Windows'ta kasıtlı exception fırlatıp debugger'ın onu yutup yutmadığına bakmak.

**Anti-VM / anti-sandbox.** Otomatik analiz kum havuzlarında (sandbox) veya sanal makinelerde çalışıp çalışmadığını anlar. Belirtiler: VMware/VirtualBox'a özgü sürücü, registry anahtarı ve MAC adresi ön ekleri; anormal az CPU çekirdeği ya da RAM; fare hareketi olmaması; disk boyutunun küçük olması; belirli süreçlerin (analiz araçları) çalışıyor olması. Bir sandbox tespit edilirse malware "uyur" veya hemen çıkar — böylece otomatik analiz onu zararsız sanar.

**Timing ve ortam kontrolleri.** Bazı malware kasıtlı olarak dakikalarca bekler (sleep) ya da belirli sayıda kullanıcı etkileşimi bekler, çünkü sandbox'lar genelde birkaç dakikada analizi keser. Diğerleri sadece belirli bir dil ayarında (locale) ya da belirli bir tarihten sonra tetiklenir.

Bu tekniklerin kök nedeni yine ekonomiktir: modern tespit büyük ölçüde otomatik sandbox'lara dayanır. Malware, bu otomatik hattı atlatabilirse, insan analistin önüne hiç düşmeden binlerce makineye yayılabilir. Anti-analiz, otomasyona karşı açılmış bir savaştır.

## Somut Örnek: Bir Paketlenmiş Örneğin Analiz Akışı

Elimize adı verilmeyen, şüpheli bir Windows `.exe` geldiğini varsayalım. Tipik bir triyaj (triage) akışı şöyle işler:

1. **Statik ilk bakış.** Detect It Easy ya da PEStudio ile dosyayı açarız. Bölüm entropilerine bakarız: `.text` bölümü 7.4 entropi gösteriyor — yüksek. Bölüm isimleri standart değil, `UPX0`/`UPX1` gibi ya da tamamen çöp. Import tablosu sadece üç-dört fonksiyon içeriyor: `GetProcAddress`, `LoadLibraryA`, `VirtualAlloc`. Bu tablo başlı başına "burada dinamik unpacking var" der.

2. **Paketleyici tespiti.** DIE bize imza eşleşmesi verir: "muhtemelen UPX (modifiye)". Standart `upx -d` deneriz; header bozuk olduğu için reddeder. Demek ki manuel unpacking gerekiyor.

3. **Dinamik unpacking.** Dosyayı bir debugger'da (x64dbg) kontrollü bir ortamda açarız. Amaç: stub'ın işini bitirip kontrolü orijinal koda devrettiği anı, yani **OEP'yi (Original Entry Point)** yakalamak. Klasik bir yöntem, unpacking stub'ının açtığı belleğe yazıp sonra oraya atladığı anı yakalamaktır. Stub, sıkıştırılmış veriyi `VirtualAlloc` ile ayrılan yazılabilir+çalıştırılabilir belleğe açar; biz o bölgeye bir hardware breakpoint (execute üzerine) koyarız. Kod oraya sıçradığında dururuz — işte açılmış orijinal kod artık bellektedir.

4. **Bellek dökümü (dump).** OEP'de dururken, açılmış process belleğini diske dökeriz (Scylla gibi bir eklentiyle) ve import tablosunu yeniden inşa ederiz (IAT reconstruction). Sonuçta artık statik olarak incelenebilir, açılmış bir örneğimiz olur.

5. **Asıl analiz.** Artık string'ler görünür, gerçek import'lar görünür, kod akışı disassembler'da anlamlıdır. C2 adreslerini, davranışı, persistence yöntemini buradan çıkarırız.

Bu akışın kalbindeki fikir baştan söylediğimiz fiziksel gerçektir: **kod bir yerde açılmak zorunda; biz o anı yakalarız.** Virtualizer'larda bu akış çalışmaz çünkü hiçbir noktada tanıdık x86 belirmez — o zaman iş VM interpreter'ını çözmeye kayar.

## Sömürü / İstismar Mantığı: Saldırgan Neyi, Nasıl Kullanır?

Saldırgan tarafından bakınca packing ve obfuscation üç somut fayda sağlar:

**İmzadan kaçış (signature evasion).** Aynı zararlı payload'ı her kurban için farklı anahtarla yeniden paketleyerek (crypter kullanarak) her seferinde byte düzeyinde farklı, ama işlevi aynı bir dosya üretilir. Buna server-side polymorphism denir. Böylece imza tabanlı AV'ler sürekli bir adım geride kalır.

**Otomatik analizi geçmek.** Anti-VM ve anti-sandbox ile örnek, güvenlik ürünlerinin otomatik hattında zararsız görünür, ancak gerçek kurban makinesinde tetiklenir. Bu, "hedefli" hissi veren bir seçicilik yaratır.

**Analiz maliyetini fırlatmak.** Virtualizer ve ağır obfuscation, tersine mühendislik süresini günlerden haftalara çıkarır. Bir tehdit istihbaratı ekibinin kaynakları sınırlıdır; maliyet yeterince yüksekse örnek hiç derinlemesine analiz edilmez.

Modern saldırgan bunları **katmanlar.** Tipik bir zincir: obfuscate edilmiş bir loader → şifreli bir payload'ı bellekte açar → hiç diske yazmadan (fileless) doğrudan bellekte çalıştırır (reflective loading / process hollowing). Diske hiç açık kod düşmediği için disk tabanlı taramalar da atlatılır.

## Savunma: Nasıl Tespit ve Nötralize Edilir?

Savunma tarafı, packing'in temel zafiyetinden faydalanır: **kod bellekte açılmak zorundadır.** Bu yüzden modern savunma statik imzadan davranışsal ve bellek temelli tespite kaymıştır.

**Statik heuristik'ler.** Entropi analizi, ince import tablosu, yazılabilir+çalıştırılabilir bölümler, tuhaf bölüm isimleri, header anomalileri — bunların hepsi "paketlenmiş" bayrağı kaldırır. Bir dosyanın paketli olması onu zararlı yapmaz ama incelenmeye değer yapar; kurumsal ortamda "neden bu iş uygulaması paketli?" sorusu sorulmalıdır.

**Dinamik / davranışsal analiz.** Örneği kontrollü bir sandbox'ta çalıştırıp gerçekte ne yaptığını gözlemlemek: hangi dosyalara dokunuyor, hangi registry anahtarını yazıyor, hangi ağ bağlantısını kuruyor. Packing bunu engellemez — çünkü örnek çalışmak zorundadır. Ama saldırganın anti-sandbox tekniklerine karşı sandbox'ın gerçekçi görünmesi (fare hareketi simülasyonu, gerçekçi donanım, gecikmeli analiz) gerekir.

**Bellek tarama (memory scanning).** En güçlü modern yaklaşımlardan biri. Örnek çalışıp kendini bellekte açtıktan **sonra** belleği taramak. Statik olarak imzasız olan malware, bellekte açıldığında bilinen imzasıyla eşleşir. EDR (Endpoint Detection and Response) ürünleri tam da bunu yapar: `VirtualAlloc` ile yazılabilir+çalıştırılabilir bellek ayrılmasını, oraya kod yazılıp çalıştırılmasını (RWX anomalisi), process hollowing'i davranışsal olarak yakalar.

**Otomatik unpacking.** Bazı savunma hatları örneği emülatörde ya da hafif bir sanal ortamda çalıştırıp unpacking stub'ının işini bitirmesini bekler, sonra açılmış belleği imza taramasından geçirir. Bu, saldırganın packing avantajını büyük ölçüde nötralize eder.

**Import ve API-hashing tespiti.** API hashing kullanan malware, çalışma anında `GetProcAddress` benzeri çözümleme yapar. EDR bu tür şüpheli dinamik çözümleme davranışını ya da yaygın hash algoritmalarının imzalarını tespit edebilir.

Buradaki savunma felsefesi nettir: **statik gizleme ne kadar iyi olursa olsun, davranış yalan söyleyemez.** Kod çalışmak zorundaysa, çalışırken izlenebilir. Bu yüzden derinlemesine savunma (defense in depth), statik imza tek başına değil; statik heuristik + davranışsal sandbox + bellek/EDR katmanlarının birlikte kullanımıdır.

## Yaygın Hatalar

**"Yüksek entropi = zararlı" varsaymak.** En sık hata. Meşru sıkıştırılmış installer'lar, DRM'li oyunlar, imzalı ticari yazılımlar da yüksek entropi taşır. Entropi bir tetikleyicidir, hüküm değil. Bağlamla birlikte değerlendirilmezse yüksek false positive üretir.

**UPX'i "her zaman `upx -d` ile açılır" sanmak.** Malware yazarları UPX header'ını kasıtlı bozar. `upx -d` reddettiğinde "demek UPX değil" sonucuna atlamak yanlıştır; genelde hâlâ UPX mantığındadır ama manuel unpacking gerekir.

**Paketlenmiş her dosyayı zararlı ilan etmek.** Fikri mülkiyet koruması, lisanslama ve boyut küçültme için meşru yazılımlar da paketlenir. "Paketli" tek başına suçlama değildir.

**Malware'i izole olmayan ortamda çalıştırmak.** Dinamik analiz cazip olduğunda, örneği internet erişimi olan, ana ağa bağlı ya da anlık görüntüsü (snapshot) alınmamış bir VM'de çalıştırmak felakettir. Anti-VM'i atlatmak için kimileri fiziksel makine kullanır — bu daha da tehlikelidir. İzolasyon, ağ segmentasyonu ve geri dönülebilir snapshot şarttır.

**Tek katmanı çözünce işin bittiğini sanmak.** Modern örnekler çok katmanlıdır. İlk stub'ı açtığınızda çıkan şey ikinci bir paketli katman olabilir. OEP'yi yakaladım demek her zaman "bitti" demek değildir.

**Anti-analiz'i hafife almak.** Sandbox'ta "hiçbir şey yapmadı" demek çoğu zaman "sandbox'ı tespit etti ve uyudu" demektir. Zararsız görünen bir örnek, savunma değil, iyi anti-analiz belirtisi olabilir.

## En İyi Pratikler

**Katmanlı tespit kurun.** Tek bir sinyale (imza ya da entropi) güvenmeyin. Statik heuristik, davranışsal sandbox ve bellek/EDR tabanlı tespiti birlikte kullanın. Her katman bir öncekinin körlüğünü kapatır.

**Bellek temelli tespiti önceliklendirin.** Packing'in fiziksel zafiyeti bellektir. RWX bellek ayrımı, reflective loading, process hollowing gibi davranışlar üzerine güçlü EDR görünürlüğü kurun. Statik olarak görünmez olan, bellekte görünür hale gelir.

**Sandbox'ı gerçekçi yapın.** Anti-VM/anti-sandbox'ı yenmek için analiz ortamının gerçek kullanıcı makinesinden ayırt edilmesini zorlaştırın: gecikmeli tetiklemeye karşı analiz süresini uzatın, kullanıcı etkileşimini simüle edin, sanallaştırma izlerini gizleyin.

**Analiz ortamını sıkı izole edin.** Zararlı örnekleri her zaman ağdan yalıtılmış, snapshot'lı, tek kullanımlık ortamlarda çalıştırın. Analiz makinesinin asla üretim ağına ya da internete kontrolsüz erişimi olmasın.

**Bağlamı analiz edin, sadece dosyayı değil.** Bir dosyanın paketli olması tek başına anlamsızdır. Nereden geldi, hangi süreç başlattı, ne zamandan beri var, imzalı mı — bu bağlam, teknik göstergelerden çoğu zaman daha ayırt edicidir.

**Kaçış maliyetini kabul edin, mükemmelliği değil.** Savunma tarafında amaç saldırganı imkânsızlaştırmak değil, ekonomik olarak caydırmaktır. Her katman saldırganın işini pahalılaştırır. Meşru yazılım korumasında da aynı gerçek geçerlidir: yeterince kararlı bir tersine mühendis her obfuscation'ı eninde sonunda çözer; amaç bu işi zahmete değmez kılmaktır.

**Örnekleri versiyonlayın ve paylaşın.** Bir malware ailesinin farklı paketli varyantları aynı açılmış çekirdeği paylaşır. Açılmış (unpacked) örnekleri ve YARA kurallarını (bellekte eşleşecek şekilde yazılmış) tehdit istihbaratı topluluğuyla paylaşmak, imza değişse bile aileyi yakalamayı mümkün kılar.

## Kapanış

Packing ve obfuscation, güvenlikteki en kalıcı gerilimlerden birinin — gizleme ile açığa çıkarma — somut halidir. İkisinin de dayandığı asimetri şudur: saldırgan kodu ne kadar iyi gizlerse gizlesin, CPU o kodu çalıştırmak için bir noktada açık haline ihtiyaç duyar. Bütün ciddi savunma stratejisi bu tek gerçeğin üstüne kurulur. Bir uzman için mesele "paketli mi?" sorusunda takılmak değil; hangi tekniğin, hangi amaçla kullanıldığını okuyup, doğru katmanda — statikte değilse dinamikte, dinamikte değilse bellekte — o açılma anını yakalamaktır.
