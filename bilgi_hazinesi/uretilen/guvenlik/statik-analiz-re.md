# Statik Analiz ve Tersine Mühendislik

## Tanım ve Kapsam

Tersine mühendislik (reverse engineering), derlenmiş bir yazılımın (binary) kaynak kodu elimizde olmadan nasıl çalıştığını anlamaya yönelik disiplindir. Amaç, makine diline (machine code) çevrilmiş bir programı geriye doğru okuyarak insanın anlayabileceği bir mantığa dönüştürmektir. Bu disiplinin iki büyük kolu vardır: **statik analiz** ve **dinamik analiz**.

Statik analiz, programı *çalıştırmadan* incelemek demektir. Binary dosyanın baytlarını, komut dizilerini (instruction sequences), string sabitlerini, import edilen fonksiyonlarını ve kontrol akışını (control flow) çalıştırmadan çözümlersiniz. Dinamik analiz ise programı bir debugger içinde veya bir sandbox'ta *koştururken* gözlemlemektir. Bu makale ağırlıklı olarak statik tarafa, yani disassembly, decompilation ve kontrol akışı analizine odaklanır; ama iki yaklaşımın birbirini nasıl tamamladığını da anlatır çünkü gerçek dünyada usta bir analist ikisini iç içe kullanır.

Statik analizin cazibesi şudur: zararlı bir yazılımı (malware) çalıştırmadan onu inceleyebilirsiniz. Bu, hem güvenlik açısından (kendi makinenizi enfekte etmezsiniz) hem de kapsam açısından (kod içindeki *hiç çalıştırılmayan*, örneğin belirli bir tarihte veya belirli bir komuta yanıt olarak tetiklenen dallar dahil her yolu görebilirsiniz) çok değerlidir. Dinamik analizde yalnızca o çalıştırmada tetiklenen yolu görürsünüz; statik analizde ise teorik olarak tüm yolları.

## Kök Neden: Derleme Neden Geri Döndürülebilir?

Tersine mühendisliğin mümkün olmasının temel nedeni, derleme (compilation) işleminin **kayıplı ama deterministik** bir dönüşüm olmasıdır. Bir C dosyasını derlediğinizde derleyici (compiler) yüksek seviye ifadelerinizi mimariye özgü makine komutlarına (x86-64, ARM, RISC-V vb.) çevirir. Bu çevirimde bazı bilgiler kalıcı olarak kaybolur: değişken isimleri, fonksiyon isimleri (semboller strip edilmişse), yorum satırları, tip bilgisinin çoğu ve kaynak kodun görsel yapısı.

Ancak kaybolmayan çok kritik bir şey vardır: **programın mantığı ve semantiği**. CPU'nun ne yapacağı tam olarak baytlara kodlanmıştır. `if` bir karşılaştırma komutu (`cmp`) ve bir koşullu atlama komutuna (`jz`, `jnz`, `jg` gibi) dönüşür; bir `for` döngüsü bir sayaç, bir karşılaştırma ve geriye doğru bir atlama olarak belirir; bir fonksiyon çağrısı `call` komutuna ve çağrı yığınının (call stack) yönetimine dönüşür. Bu kalıplar **öngörülebilir** olduğu için geriye çevrilebilirler. Bir decompiler, tam da bu kalıpları tanıyıp `if`/`for`/`while` gibi yapılara yeniden eşleyerek çalışır.

Kısacası: kaynak kod bir dönüşümle makine koduna gider, isimler ve süsler kaybolur ama **hesaplamanın kendisi korunmak zorundadır** çünkü aksi halde program çalışmazdı. Tersine mühendislik bu korunmuş hesaplamayı yeniden okunabilir hale getirme sanatıdır.

## Katmanlar: Baytlardan Anlama

Statik analizi anlamak için bir binary'nin katmanlarını görmek gerekir.

**1. Ham baytlar ve dosya formatı.** Her çalıştırılabilir dosyanın bir yapısı vardır: Windows'ta PE (Portable Executable), Linux'ta ELF, macOS'ta Mach-O. Bu formatlar bir header, bölümler (sections: `.text` kodu, `.data` başlatılmış veriyi, `.rodata`/`.rdata` salt-okunur sabitleri barındırır), import/export tabloları ve giriş noktası (entry point) bilgisi içerir. Analize genellikle bu yapıyı okumakla başlanır çünkü hangi kütüphaneleri ve fonksiyonları import ettiği (örneğin `WinInet`, `CreateProcess`, `socket`) programın niyeti hakkında güçlü ipuçları verir.

**2. Disassembly.** Ham makine kodu baytları, insan-okur assembly mnemonic'lerine (mov, push, call, cmp, jmp) çevrilir. Bu adım bire-bir bir dönüşümdür: her bayt dizisi tam olarak bir komuta karşılık gelir. Disassembly *doğru* olduğu sürece kayıpsızdır; ama "doğru olması" göründüğünden zordur (bunu birazdan açacağım).

**3. Decompilation.** Assembly, yaklaşık bir sözde-C (pseudo-C) koduna yükseltilir. Bu adım **kesin değildir, tahminidir**. Decompiler değişken tiplerini çıkarsar, döngüleri ve koşulları yeniden yapılandırır, isimleri (`iVar1`, `param_1` gibi) atar. Çıktı derlenemeyebilir ama insanın okuması için assembly'den kat kat daha hızlıdır.

Ghidra (NSA tarafından açık kaynak olarak yayımlanan) ve IDA Pro (Hex-Rays'in ticari, uzun yıllardır sektör standardı olan aracı) bu üç katmanı da sunan başlıca araçlardır. Ghidra'nın decompiler'ı ücretsiz olduğu için son yıllarda çok yaygınlaştı; IDA ise özellikle geniş mimari desteği, olgunluğu ve eklenti ekosistemiyle tercih edilir. Bunlara ek olarak Binary Ninja, radare2/rizin, Cutter gibi araçlar da vardır.

## Disassembly'nin Zorluğu: x86'da Değişken Uzunluklu Komutlar

Disassembly'nin neden zor olabileceğini anlamak, analizde neden bazen "çöp" gördüğünüzü açıklar. ARM gibi RISC mimarilerde komutlar sabit uzunluktadır (örneğin 4 bayt), bu yüzden nereden başlarsanız başlayın hizalama tutarlıdır. Ama x86/x86-64 mimarisinde komutlar **değişken uzunluktadır** (1 bayttan 15 bayta kadar). Bu, disassembler'ın "bir komut nerede başlıyor?" sorusunu doğru cevaplamasını kritik hale getirir.

İki temel disassembly stratejisi vardır:

**Linear sweep (doğrusal tarama):** Kod bölümünün başından başlar, komutu çözer, uzunluğu kadar ilerler, sonraki komutu çözer ve bu böyle devam eder. Basittir ama tehlikelidir: kodun ortasına gömülü veri (örneğin bir jump table veya inline string) komut sanılıp yanlış çözülürse, o noktadan itibaren hizalama kayar ve arkasından gelen gerçek komutlar da yanlış yorumlanır. Buna **desenkronizasyon** denir.

**Recursive descent (özyinelemeli iniş):** Giriş noktasından başlar ve kontrol akışını *takip eder*. Bir `jmp` görürse hedefe atlar, bir `call` görürse çağrılan fonksiyonu kuyruğa alır, koşullu bir atlamada iki dalı da takip eder. Böylece yalnızca gerçekten "kod olarak erişilebilen" baytları komut olarak çözer. Bu yaklaşım genelde daha doğrudur ve Ghidra/IDA'nın temel çalışma prensibidir. Ancak dolaylı atlamalarda (`jmp rax` gibi hedefin çalışma anında hesaplandığı durumlar) hedefi statik olarak bilemez, bu yüzden bazı kod bölgelerini kaçırabilir.

Bu ayrım, saldırganların **anti-disassembly** tekniklerinin de temelidir. Kötü niyetli yazılım yazarları, disassembler'ı kasıtlı yanıltmak için sahte atlamalar, örtüşen komutlar (aynı baytların iki farklı komut dizisi olarak okunabildiği hileler) veya opak koşullar (opaque predicates: her zaman aynı sonucu veren ama analistin bunu kolayca göremediği karşılaştırmalar) ekler. Analistin işi, aracın yanıldığı yeri fark edip bölgeyi manuel olarak "kod" veya "veri" olarak yeniden tanımlamaktır.

## Kontrol Akışı: Analizin Omurgası

Kontrol akışı (control flow), bir programın komutları hangi sırayla çalıştırdığını tanımlar ve statik analizin en önemli kavramıdır. Analiz araçları kodu **temel bloklar (basic blocks)** halinde parçalar. Bir temel blok, dallanmasız (dalın içine girmeyen ve dışına çıkmayan) doğrusal bir komut dizisidir: baştan girer, sondan çıkarsınız, ortada dallanma yoktur. Blok bir dallanma komutuyla (koşullu/koşulsuz atlama, çağrı, dönüş) biter.

Bu blokları, aralarındaki geçişleri (kenarları) çizerek birbirine bağladığınızda **Kontrol Akış Grafiği (Control Flow Graph, CFG)** elde edersiniz. IDA ve Ghidra'nın grafik görünümü tam olarak budur: kutular temel bloklardır, oklar ise olası akış yollarıdır. Yeşil ok genelde koşulun doğru olduğu dalı, kırmızı ok yanlış dalı temsil eder (araca göre değişir).

CFG neden bu kadar kıymetlidir? Çünkü bir fonksiyonun *şeklini* bir bakışta anlamanızı sağlar. Uzun düz bir zincir basit ardışık kod demektir; kendine geri dönen bir kenar bir döngü demektir; birden çok dala ayrılıp tekrar birleşen bir yapı bir `if/else` veya `switch` demektir. Deneyimli bir analist, tek bir komutu okumadan grafiğin topolojisine bakarak "bu bir input doğrulama fonksiyonu", "bu bir şifre çözme döngüsü" gibi hipotezler kurar.

Bir seviye yukarıda **Çağrı Grafiği (Call Graph)** vardır: hangi fonksiyonun hangi fonksiyonu çağırdığını gösterir. Bu, programın mimarisini kuşbakışı görmenizi sağlar; örneğin `main`'den ağ fonksiyonlarına, kriptografi fonksiyonlarına ve dosya sistemi fonksiyonlarına giden dalları izleyerek programın kabaca ne yaptığını haritalayabilirsiniz.

## Somut Örnek: Basit Bir Lisans Kontrolü

Bir programın şöyle bir C mantığı olduğunu düşünelim:

```c
if (strcmp(kullanici_girisi, gizli_anahtar) == 0) {
    printf("Erişim verildi\n");
    calistir_program();
} else {
    printf("Hatali anahtar\n");
    exit(1);
}
```

Derlendikten sonra decompiler'da yaklaşık şuna benzer bir çıktı görürsünüz (isimler tabii ki `iVar1`, `param_1` gibi olur, temizlenmiştir):

```c
iVar1 = strcmp(kullanici_girisi, "S3CR3T-KEY");
if (iVar1 == 0) {
    printf("Erisim verildi\n");
    calistir_program();
} else {
    printf("Hatali anahtar\n");
    exit(1);
}
```

Assembly seviyesinde bu, kabaca bir `call strcmp`, ardından sonucu sıfırla karşılaştıran bir `test eax, eax` (veya `cmp`), ardından bir koşullu atlama (`jnz hatali_dal`) şeklinde belirir. İşte tersine mühendisliğin öğretici anı burada: statik analizde `"S3CR3T-KEY"` string'ini `.rodata` bölümünde düz metin olarak görürsünüz. Yani karşılaştırılan gizli değeri okumak için bir dizi çözme yapmanıza bile gerek kalmaz.

Bu örnek, hem sömürü hem savunma mantığını netleştiriyor; ayrıntısına birazdan geleceğim. Önce iş akışını görelim: string'i buldunuz, string'e referans veren (cross-reference / xref) komutu buldunuz, oradan fonksiyona ulaştınız, fonksiyonun CFG'sinde karşılaştırma-ve-atlama kalıbını gördünüz. Bu "string → xref → fonksiyon → mantık" zinciri, gerçek dünya analizinin en sık kullanılan başlangıç yöntemidir.

## Sömürü / İstismar Mantığı

Tersine mühendislik saldırı tarafında birkaç amaca hizmet eder.

**Yazılım kırma (cracking) ve korumaların atlatılması.** Yukarıdaki lisans örneğinde saldırgan, `jnz` koşullu atlamasını bir `jz`'ye çevirerek veya karşılaştırmayı hep-doğru yapan bir yamaya (patch) dönüştürerek kontrolü baypas edebilir. Tek bir baytı değiştirmek (örneğin atlama opcode'unu ters çevirmek) tüm doğrulamayı etkisiz kılabilir. Buna "patch" veya "keygen/crack" saldırısı denir. Kök neden şudur: koruma mantığı ile korunan içerik aynı ikili dosyada bulunur ve saldırgan her ikisine de sahiptir.

**Zafiyet keşfi (vulnerability research).** Kaynak kodu olmayan kapalı yazılımlarda (firmware, sürücüler, ticari ürünler) hafıza güvenliği hatalarını bulmak için statik analiz kullanılır. Analist, kullanıcı girdisinin (attacker-controlled data) sınır kontrolü yapılmadan bir tampona (buffer) kopyalandığı yerleri (`memcpy`, `strcpy`, `sprintf` çağrıları) arar. Bir `buffer overflow` veya `use-after-free` çoğu zaman CFG'de ve decompile çıktısında görülebilir: örneğin sabit boyutlu bir yığın tamponuna (stack buffer) uzunluğu doğrulanmamış bir kopyalama görürseniz, orada bir taşma adayınız var demektir. Bulunan zafiyet daha sonra bir exploit'e dönüştürülür.

**Malware analizi (saldırgan bakışıyla anlama).** Bir zararlının komuta-kontrol (C2) sunucu adreslerini, şifreleme anahtarlarını, tetikleme koşullarını ve yaptığı işleri statik analizle çıkarmak; hem savunma hem de tehdit istihbaratı için gereklidir. Saldırganlar bunu zorlaştırmak için string'leri şifreler (analist çözme rutinini bulup yeniden uygular), packer/kripter kullanır (kod çalışma anında kendini açar) ve anti-analiz hileleri ekler.

**Protokol ve format tersine mühendisliği.** Kapalı bir ağ protokolünü veya dosya formatını anlamak için, onu üreten/işleyen kodun ayrıştırma (parsing) mantığı okunur. Bu, hem birlikte çalışabilirlik (interoperability) hem de saldırı yüzeyi analizi için yapılır.

## Savunma: Tersine Mühendisliği Zorlaştırmak

Savunma tarafında amaç, tersine mühendisliği *imkânsız* kılmak değildir (yeterli zaman ve beceriyle her binary çözülebilir), amaç **maliyeti saldırganın kazancının üzerine çıkarmaktır**. Başlıca teknikler:

**Kod karartma (obfuscation).** Kontrol akışını yapay olarak karmaşıklaştırmak (control flow flattening: normal iç içe yapıyı, tek bir devasa switch'in yönettiği düz bir duruma çevirir ve CFG'yi okunamaz hale getirir), opak koşullar eklemek, gereksiz kod (junk code) enjekte etmek. Bunlar decompiler çıktısını insanın izini kaybedeceği kadar karmaşıklaştırır.

**String ve sabit şifreleme.** Yukarıdaki lisans örneğinin en büyük hatası, gizli anahtarın düz metin olmasıydı. Savunmada hassas sabitler şifrelenir veya çalışma anında türetilir, böylece statik `strings` taraması hiçbir şey bulamaz. Bu tek başına yetmez ama başlangıç maliyetini yükseltir.

**Packing ve kriptleme.** Gerçek kod sıkıştırılıp/şifrelenip küçük bir açıcı (unpacker) stub'ının arkasına saklanır. Statik analiz yalnızca stub'ı görür; gerçek mantığı görmek için ya çalıştırıp hafızadan dökmek (memory dump) ya da açıcıyı elle tersine çevirmek gerekir. Bu, statik analizi tek başına yetersiz bırakan ve dinamik analizi zorunlu kılan bir savunmadır.

**Anti-debugging ve anti-tampering.** Program kendi bütünlüğünü kontrol eder (kod baytlarının hash'ini alır, değiştirilmişse çöker), bir debugger'ın varlığını tespit eder ve davranışını değiştirir. Bu, dinamik analizi zorlaştırır.

**Sembol strip'leme ve minimum bilgi.** Yayın (release) derlemesinde tüm debug sembollerini, fonksiyon isimlerini ve gereksiz string'leri kaldırmak, analistin işini belirgin biçimde zorlaştırır. Bu, hiçbir maliyeti olmayan temel bir savunmadır ve mutlaka uygulanmalıdır.

Kritik gerçekçilik notu: Bu savunmaların hiçbiri kriptografik bir garanti sunmaz. Kontrolü *istemcide* (client-side) yapan her koruma, o istemciye tam erişimi olan bir saldırgan tarafından teorik olarak yenilebilir. Bu yüzden güvenlik açısından kritik doğrulamalar (lisans, yetki, ödeme) mümkün olduğunca **sunucu tarafında** yapılmalıdır. İstemci tarafı obfuscation yalnızca bir yavaşlatma katmanıdır, bir güvenlik sınırı (security boundary) değildir.

## Statik ve Dinamik Analizin Birlikte Kullanımı

Usta analistlerin bir sırrı şudur: statik ve dinamik analiz birbirinin körlüğünü giderir. Statik analiz size tüm yolları gösterir ama dolaylı atlamalarda, çalışma anında hesaplanan değerlerde ve packer'larda tıkanır. Dinamik analiz (debugger içinde adım adım koşturma, breakpoint koyma, hafıza inceleme) tam da bu noktaları çözer: dolaylı atlamanın gerçek hedefini görürsünüz, şifre çözme rutininin *çıktısını* hafızada okursunuz, packer kendini açtıktan sonra gerçek kodu döküp tekrar statik analize koyarsınız.

Tipik iş akışı şöyledir: önce statik olarak keşif yapılır (dosya formatı, importlar, string'ler, ilginç fonksiyonlar), CFG üzerinde hipotez kurulur, sonra kritik noktalara dinamik olarak breakpoint konup varsayımlar doğrulanır. Ghidra ve IDA bu geçişi kolaylaştırmak için debugger entegrasyonu sunar.

## Yaygın Hatalar

**Decompiler çıktısına mutlak doğru gibi güvenmek.** Decompile edilmiş sözde-C bir *yorumdur*, kaynak kod değildir. Tip çıkarımı yanlış olabilir, işaret/işaretsiz (signed/unsigned) karışabilir, bir `union` veya inline assembly yanlış yorumlanabilir. Kritik bir karar veriyorsanız (özellikle bir zafiyetin gerçekliğini teyit ederken) daima altındaki assembly'ye inip doğrulayın. Decompiler'ın "kaybettiği" bir taşma, assembly'de görülebilir.

**Desenkronize disassembly'yi fark etmemek.** Ekranda anlamsız komut yığınları, "bozuk" görünen bloklar veya araçların çözemediği bölgeler gördüğünüzde bunu kodun kendisi değil, disassembler'ın hizalama hatası olarak değerlendirmeyi öğrenin. Bölgeyi manuel "undefine/redefine" etmek çoğu zaman düzeltir.

**Packer'ı fark etmeden statik analize gömülmek.** Bir binary'nin section'ları çok yüksek entropiye (rastgeleliğe) sahipse, importları anlamsız derecede azsa ve string'leri boşsa, muhtemelen packer'lıdır. Bunu fark etmeden saatlerce açıcı stub'ını analiz etmek zaman kaybıdır; önce unpack edin.

**Sadece bir yola odaklanıp tetiklenmeyen dalları atlamak.** Özellikle malware'de kötü niyetli davranış çoğu zaman bir koşulun arkasına saklıdır (belirli bir tarih, belirli bir ülke, belirli bir C2 yanıtı). Yalnızca dinamik analize güvenirseniz bu dalları hiç görmezsiniz. Statik analizin en büyük üstünlüğü tam olarak bu gizli dalları ortaya çıkarabilmesidir; onu kullanın.

**xref'leri (çapraz referanslar) kullanmamak.** Yeni analistler kodu baştan sona doğrusal okumaya çalışır. Verimli yol tam tersidir: ilginç bir string veya API çağrısı bulun, ona *kimin referans verdiğini* (xref) sorun, oradan mantığa ulaşın. Bu, saatler yerine dakikalar demektir.

**Malware'i izole olmayan ortamda çözmek.** Statik analiz görece güvenli olsa da, dosyayı yanlışlıkla çalıştırmak veya bazı araç eklentilerinin dosyaya dokunması risk yaratabilir. Zararlı analizini daima ağı izole edilmiş, anlık görüntü (snapshot) alınabilen bir sanal makinede yapın.

## En İyi Pratikler

**Yukarıdan aşağıya keşif, aşağıdan yukarı doğrulama.** Önce çağrı grafiği ve importlarla programın *ne yaptığına* dair üst düzey bir harita çıkarın. Sonra ilgilendiğiniz fonksiyona inip CFG'yi, ardından decompile'ı, en son gerektiğinde assembly'yi inceleyin. Her seferinde tüm binary'yi okumaya çalışmayın; hedefinizi tanımlayın.

**Sürekli isimlendirin ve not alın.** Ghidra ve IDA, keşfettiğiniz fonksiyonları, değişkenleri ve yapıları yeniden adlandırmanıza izin verir. `FUN_00401230`'u `dogrula_lisans` olarak, `iVar1`'i `karsilastirma_sonucu` olarak adlandırdıkça binary'nin okunabilirliği katlanarak artar. Analiz, aslında araca bilgi *geri besleyerek* onu okunur kılma sürecidir. Bir tipi (struct) doğru tanımladığınızda decompiler çıktısı dramatik biçimde düzelir.

**String ve import analizini ilk adım yapın.** Düşük maliyetli, yüksek getirili bu adım programın niyetini hızla açığa çıkarır: ağ fonksiyonları mı var, kriptografi mi, kayıt defteri (registry) erişimi mi, süreç enjeksiyonu mu.

**Otomasyon ve script kullanın.** IDAPython ve Ghidra'nın script API'si (Java/Python) tekrarlayan işleri otomatikleştirmenizi sağlar: toplu string çözme, kalıp arama, otomatik yeniden adlandırma. Büyük binary'lerde bu vazgeçilmezdir.

**Hipotez kurup test edin, çıktıya köle olmayın.** Analiz bilimsel bir süreçtir: "bu fonksiyon girdiyi doğruluyor olmalı" hipotezini kurup, xref'lerle, veri akışıyla ve gerekirse dinamik doğrulamayla sınayın. Aracın verdiği isimlere ve tahminlere değil, kanıtladığınız davranışa güvenin.

**Statik ile dinamiği bilinçli dönüşümlü kullanın.** Statikte tıkandığınız her noktada (dolaylı atlama, şifreli veri, packer) dinamiğe geçmeyi refleks haline getirin; dinamikte kavradığınız yapıyı statik haritanıza geri işleyin. İki disiplin ayrı araçlar değil, aynı işin iki gözüdür.

**Güvenlik istemciye yaslanmamalı.** Savunma tarafındaysanız, tersine mühendisliğe karşı obfuscation ve packing kullanın ama bunların kesin koruma olmadığını bilin. Gerçek güvenlik sınırını her zaman kontrol ettiğiniz tarafta (sunucu, donanım güvenlik modülü) tutun; istemci tarafı korumaları sadece maliyet artıran katmanlardır.

Sonuç olarak statik analiz ve tersine mühendislik, bir binary'yi baytlardan başlayıp anlama katmanlarına doğru sistematik biçimde tırmanma sanatıdır. Disassembly size *ne* çalıştığını, decompilation *nasıl* çalıştığının okunabilir bir yorumunu, kontrol akışı ise programın *mantıksal iskeletini* verir. Ghidra ve IDA bu katmanları erişilebilir kılar; ama gerçek yetkinlik, araçların yanıldığı yeri fark etmek, hipotez kurmak ve statik ile dinamik analizi ustaca dönüşümlü kullanmakta yatar.
