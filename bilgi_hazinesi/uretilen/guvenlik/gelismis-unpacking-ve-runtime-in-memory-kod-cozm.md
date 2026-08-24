# Gelişmiş Unpacking ve Runtime/In-Memory Kod Çözme (Custom Packer'lar, VM Tabanlı Protector'lar)

## Giriş: Neden Bu Konu Ayrı Bir Başlığı Hak Ediyor

Standart malware analizi eğitiminde "Packing/Obfuscation" genelde tek bir yüzeysel başlık altında geçer: UPX gibi bilinen bir packer'ı tanı, `upx -d` çalıştır, bitir. Gerçek dünyada saldırganların ve ticari yazılım koruma ürünlerinin kullandığı sistemler bundan çok daha karmaşıktır. Custom packer'lar ve özellikle VM tabanlı (sanal makine tabanlı) protector'lar — VMProtect, Themida, Enigma Protector gibi ürünler — statik analizi neredeyse imkansız hale getirecek şekilde tasarlanmıştır. Bir savunmacı/analist için bu fark hayatidir: "packed" bir örneği görüp sadece "bu paketlenmiş, otomatik unpacker'ı çalıştır" demek, VM tabanlı korumayla karşılaşıldığında işe yaramaz; çünkü ortada "çözülecek" tek bir orijinal kod bloğu yoktur, orijinal kod bir bytecode'a dönüştürülüp yorumlanmaktadır.

Bu makale, bu ileri seviye paketleme/koruma mekanizmalarının iç mantığını, bunları analiz ederken kullanılan kavramsal teknikleri (OEP bulma, IAT rebuilding, dump-and-fix) ve bir savunma/tespit mühendisinin bakış açısıyla bunlara nasıl yaklaşması gerektiğini anlatır. Amaç saldırı tarifi değil; mekanizmayı anlayıp tespit ve savunma kurabilmektir.

## Temel Kavramlar: Packer, Protector, Obfuscator Farkı

Bu üç terim sık karıştırılır ama farklı amaçlara hizmet eder:

- **Packer**: Orijinal binary'yi sıkıştırır veya basitçe şifreler, çalışma zamanında bir "stub" (küçük başlangıç kodu) bu veriyi bellekte açar ve orijinal kodu çalıştırır. Amaç genelde dosya boyutunu küçültmek veya imza tabanlı tespiti zorlaştırmaktır. UPX, ASPack, MPRESS klasik örneklerdir.
- **Protector**: Amacı ters mühendisliği (reverse engineering) zorlaştırmaktır. Anti-debug, anti-VM, kod bütünlüğü kontrolleri, ve çoğunlukla VM tabanlı sanallaştırma içerir. VMProtect, Themida, Enigma Protector, Code Virtualizer bu kategoridedir.
- **Obfuscator**: Kaynak kod veya ara temsil (IR) seviyesinde dönüşümler yapar (control flow flattening, string encryption, dead code injection) ama genelde native x86/x64 kod üretmeye devam eder — VM'ye geçiş yapmaz. .NET dünyasında ConfuseEx, ticari ürünlerde Obfuscator-LLVM gibi örnekler vardır.

Bu ayrım önemlidir çünkü her biri farklı analiz stratejisi gerektirir: basit bir packer'da tek bir OEP (Original Entry Point) ve tek bir "unpack anı" vardır; VM tabanlı bir protector'da ise kodun büyük kısmı hiçbir zaman "native" hale dönüp tek bir bellek bölgesinde durmaz — sürekli bir bytecode yorumlayıcısı (interpreter loop) içinde çalışır.

## Kök Neden: Savunmacılar ve Saldırganlar Neden Bu Yola Girdi

Statik analiz araçları (IDA, Ghidra, disassembler'lar) bir PE dosyasının import tablosunu, string'lerini, kod akışını doğrudan okuyabildiği sürece imza tabanlı AV motorları ve insan analistler hızlıca sınıflandırma yapabilir. Saldırgan tarafı için amaç bu statik analiz maliyetini maksimize etmek: dosya diskte dururken hiçbir anlamlı bilgi vermesin, sadece çalışma zamanında (runtime), belleğe açıldığında gerçek davranış ortaya çıksın.

Ticari yazılım koruma ürünleri de aynı motivasyonla (lisans kontrolü kırılmasın, crack'lenmesin) başladı ama teknik olarak malware packer'larıyla neredeyse özdeş mekanizmalar kullanıyor. Bu yüzden VMProtect/Themida gibi ürünler hem meşru yazılım korumasında hem de malware'de (genelde çalıntı/crack'lenmiş lisanslarla) yaygın görülür.

VM tabanlı korumanın kök nedeni şu gözlemdir: klasik bir packer sadece "ne zaman açılıyor" sorusunu zorlaştırır (bir kerelik decrypt + jump), ama bir kez OEP'e ulaşılıp dump alındığında native x86 kodu ortadadır ve klasik disassembler ile okunabilir. VM tabanlı koruma ise kodu **hiç native haline döndürmeden** çalıştırır — bytecode her zaman bytecode kalır, sadece bir yorumlayıcı onu adım adım işler. Bu, "unpack et ve dump al" modelini kökten geçersiz kılar.

## Klasik Packer Mekanizması (Kısa Hatırlatma ve Kıyas Noktası)

VM tabanlı korumayı anlamak için önce klasik modeli hatırlamak faydalı:

1. Orijinal PE, sıkıştırılır/şifrelenir ve yeni dosyanın `.data` benzeri bir bölümüne gömülür.
2. Yeni dosyanın entry point'i, orijinal kodu değil, packer'ın "stub" kodunu gösterir.
3. Program çalıştığında stub, gömülü veriyi bellekte açar (decompress/decrypt), genelde yeni bir bellek bölgesine yazar.
4. Stub, import tablosunu (IAT — Import Address Table) yeniden kurar çünkü orijinal binary'nin import'ları packer tarafından genelde kaldırılmış veya gizlenmiştir.
5. Son olarak stub, CPU'nun instruction pointer'ını orijinal kodun entry point'ine (OEP) atlatır (jump).

Analist açısından kritik an: OEP'e atlama anı. Bu ana kadar bellekte "kirli" (encrypted/compressed) veri vardır; bu andan sonra temiz, native, orijinal kod vardır. Bu yüzden klasik unpacking metodolojisi "OEP'i bul, o anda belleği dump'la, IAT'ı düzelt" şeklinde özetlenir.

## OEP (Original Entry Point) Bulma Teknikleri — Kavramsal

OEP bulma, klasik unpacking'in kalbidir. Yaygın kavramsal yaklaşımlar:

- **Tek adımlık izleme (single-step tracing) ve heuristikler**: Debugger altında her instruction'ı izleyip, kod bölgesinin (memory page) "yeni yazılan ve sonradan çalıştırılan" (write-then-execute) bir davranış sergilediği noktayı arama. Packer stub'ları tipik olarak önce bir belleğe yazar (unpack), sonra oraya atlar; bu "yazma bitti, şimdi çalıştırma başlıyor" geçişi OEP adayıdır.
- **Bellek erişim kesme noktaları (memory breakpoint)**: Stub tarafından decompress edilen bellek bölgesine "execute" erişimi olduğunda debugger'ı durdurma. Bu, OllyDbg/x64dbg gibi araçlarda "memory breakpoint on execution" olarak bilinen tekniğin kavramsal temelidir.
- **API çağrısı desenleri**: `VirtualAlloc`/`VirtualProtect` (bellek ayırma/izin değiştirme) çağrılarını izleyip, hangi bölgenin sonradan `PAGE_EXECUTE` iznine geçtiğini takip etme. Çoğu packer, açılan kodu çalıştırılabilir hale getirmek için mutlaka bir izin değişikliği yapar; bu, savunma tarafında da güçlü bir tespit sinyalidir (aşağıda detaylandırılıyor).
- **Entry point kıyaslaması**: Bilinen packer imzaları (PEiD tarzı veritabanları, tarihsel olarak) stub'ın "tipik son instruction dizisini" (örneğin bir dizi `POPAD`/`PUSHAD` sonrası uzun bir `JMP`) tanıyarak OEP'e yakın konuma doğrudan işaret edebilir. Bu yaklaşım imza tabanlı olduğu için custom/bilinmeyen packer'larda işe yaramaz.
- **Yığın (stack) tabanlı sezgiler**: Birçok x86 packer stub'ı `PUSHAD` ile başlar (tüm register'ları stack'e kaydeder) ve OEP'e atlamadan hemen önce `POPAD` ile geri yükler. `PUSHAD`/`POPAD` çiftini arayıp hemen sonrasındaki uzun mesafeli `JMP`'yi OEP adayı olarak işaretlemek klasik bir sezgidir (yine VM tabanlı korumalarda geçerli değildir, çünkü orada "tek bir OEP" kavramı çoğu zaman anlamsızlaşır).

Önemli dürüstlük notu: Bu teknikler "genel prensip" seviyesindedir; belirli bir araçta hangi menü öğesinin hangi tuş kombinasyonuna bağlı olduğu gibi ayrıntılar üründen ürüne, sürümden sürüme değişir ve burada kesin komut/tuş talimatı verilmeyecektir — amaç mantığı anlamaktır.

## IAT Rebuilding (Import Tablosu Yeniden İnşası) — Neden Gerekli

Bir PE dosyasının import tablosu, hangi DLL'lerden hangi fonksiyonların (örneğin `kernel32.dll!CreateFileA`) kullanılacağını, bu fonksiyonların bellekte nereye yükleneceğine dair adres tablosuyla birlikte tutar. Packer'lar genelde bu tabloyu ya tamamen siler ya da "import trambolini" (import trampoline/IAT redirection) adı verilen bir teknikle dolaylı hale getirir: her API çağrısı doğrudan gerçek fonksiyona değil, packer'ın kendi kod bloğuna gider, o blok gerekli çözümlemeyi (resolve) yapıp asıl fonksiyona atlar.

Bu, dump alma sürecinde şu problemi yaratır: OEP'e ulaşılıp bellek dump edildiğinde, dump edilen dosyanın import tablosu ya boştur ya da packer'ın stub'ına işaret eden anlamsız adreslerle doludur. Böyle bir dosya doğrudan çalıştırılamaz ve statik analiz araçlarında da API çağrıları görünmez (`call sub_12345` gibi anlamsız etiketlerle dolu olur).

IAT rebuilding süreci kavramsal olarak şu adımları içerir:

1. **IAT konumunu bulma**: Process belleğinde, art arda dizilmiş, geçerli API adreslerine benzeyen bir bellek bölgesi aranır (genelde process'in modül listesi/loaded modules üzerinden hangi adreslerin hangi DLL+fonksiyona denk geldiği çözümlenerek).
2. **Geçerli/geçersiz girişleri ayırma**: Bazı girişler packer stub'ına ait "trambolin" adresleridir; bunlar gerçek API değildir ve elenmesi/izlenmesi gerekir (trambolini takip edip gerçek hedefe ulaşma).
3. **Yeni bir import tablosu inşa etme**: Bulunan gerçek API-adres eşleşmeleri, dump edilen dosyanın PE header'ına yeni, geçerli bir import directory olarak yazılır.
4. **Thunk/trampoline temizliği**: Eğer dolaylı çağrı yapıları (trambolin) kod içine gömülüyse, bunların gerçek hedefe doğrudan işaret edecek şekilde düzeltilmesi (patch) gerekebilir.

Bu işlemi otomatikleştiren araçlar (tarihsel olarak "ImpREC" tarzı import reconstruction araçları) süreci kolaylaştırır ama tam otomasyon garanti edilmez, özellikle IAT gizleme (IAT obfuscation) ileri seviyeye çıktıkça (örneğin her çağrı farklı bir dolaylama deseniyle gizlenmişse) manuel müdahale gerekir.

## Dump-and-Fix Metodolojisi — Bütünsel Akış

"Dump-and-fix" klasik unpacking'in özet iş akışıdır ve şu mantıksal sırayı izler:

1. **Çalıştır ve izle**: Örnek kontrollü bir ortamda (izole VM/sandbox) çalıştırılır, debugger veya API-hooking aracı ile davranışı izlenir.
2. **Unpack anını yakala**: Yukarıdaki OEP bulma tekniklerinden biriyle, kodun "kendi kendini açtığı" ve orijinal koda geçiş yaptığı an tespit edilir.
3. **Bellekten dump al**: O anki process belleği (özellikle image/kod bölgesi) diske bir PE dosyası olarak yazılır. Bu ham dump, henüz PE header açısından tutarlı olmayabilir (section boyutları, giriş noktası, vb. process belleğindeki "sanal" adreslere göredir, disk formatına göre değildir).
4. **PE header düzeltme (fix)**: Section'ların RVA (relative virtual address) ve raw offset değerleri arasındaki dönüşüm düzeltilir; entry point, dump anında tespit edilen OEP'e göre ayarlanır.
5. **IAT rebuild**: Yukarıda anlatılan süreçle import tablosu yeniden inşa edilir.
6. **Doğrulama**: Düzeltilmiş dosya, orijinal (unpacked) çalışma davranışını sergiliyor mu diye ayrı bir ortamda test edilir; ayrıca disassembler'da anlamlı fonksiyon çağrıları, string referansları görünür hale gelmiş mi kontrol edilir.

Bu akışın "kolay" versiyonu tek katmanlı, basit packer'lar (UPX vb.) için geçerlidir. Custom packer'larda genelde çoklu katman (multi-layer unpacking — bir stub başka bir stub'ı açar, o da üçüncüsünü açar) ve self-modifying code (kendi kodunu çalışırken değiştiren kod) devreye girer, bu da "tek bir OEP anı" varsayımını karmaşıklaştırır. Bazı gelişmiş packer'lar ayrıca "OEP'i asla tam olarak tek bir noktada göstermeme" stratejisi izler — kod parça parça, farklı zamanlarda decrypt edilip hemen sonra tekrar encrypt edilebilir (bu, aşağıda anlatılan VM tabanlı yaklaşıma kavramsal bir köprüdür).

## VM Tabanlı Protector'lar: Paradigma Değişimi

VMProtect, Themida (VM modu), Enigma Protector gibi araçlar, klasik "aç ve OEP'e atla" modelini tamamen terk eder. Bunun yerine:

1. Orijinal x86/x64 makine kodu, protector'ın kendi tasarladığı **özel bir bytecode formatına** derlenir (compile). Bu bytecode, gerçek CPU'nun anlayacağı bir şey değildir; sadece protector'ın kendi yorumlayıcısının (interpreter/virtual machine) anlayacağı özel bir instruction set'tir.
2. Binary içine, bu bytecode'u çalıştırma zamanında adım adım okuyup yorumlayan bir **VM interpreter (dispatcher loop)** gömülür. Bu interpreter, tipik olarak bir "handler tablosu" (her sanal opcode için bir handler fonksiyonu) ve bir merkezi döngü (fetch-decode-execute) içerir.
3. Program çalıştığında, korunan fonksiyon çağrıldığında gerçekte native kod çalışmaz; VM interpreter devreye girer, bytecode'u satır satır okur, her "sanal instruction"ı kendi el yapımı CPU mimarisinde yorumlar (kendi sanal register'ları, kendi sanal stack'i olabilir).

Bunun sonucu: klasik anlamda bir "OEP" yoktur çünkü kod hiçbir zaman native haliyle bellekte tek parça halde durmaz. Dump alsanız bile elinizde native x86 kodu değil, protector'a özel bytecode ve onu yorumlayan generic bir interpreter olur. Interpreter'ın kendisi analiz edilebilir olsa da (ve zamanla topluluk bazı protector sürümlerinin VM handler'larını haritalamıştır), her yeni sürüm/varyant handler setini, opcode numaralandırmasını, hatta VM mimarisinin temel yapısını (stack-based mı, register-based mi) değiştirebilir; bu da analiz maliyetini sürekli yeniden yükseltir (bu, "polymorphic VM" yaklaşımıdır — protector her derlemede farklı bir sanal mimari üretebilir).

Ek olarak bu ürünler genelde şu katmanları da ekler:
- **Anti-debug kontrolleri**: Debugger varlığını tespit eden çok sayıda teknik (zamanlama ölçümleri, işletim sistemi API'lerini sorgulama, exception-based tuzaklar).
- **Anti-VM/anti-sandbox kontrolleri**: Sanallaştırılmış ortam belirtilerini arama (belirli donanım kimlikleri, zamanlama anormallikleri, ortam yapıtları).
- **Kod bütünlüğü kontrolleri (integrity/checksum)**: Kodun bir bölümü değiştirilmişse (patch/breakpoint konmuşsa) programın farklı davranması veya çökmesi.
- **Mutasyon (code mutation/polymorphism)**: Aynı mantığın her derlemede farklı bytecode dizisiyle ifade edilmesi, imza tabanlı eşleştirmeyi anlamsızlaştırır.

## VM Tabanlı Korumayı Analiz Etme Yaklaşımı (Kavramsal, Savunma Odaklı)

Bir savunmacı/analist olarak VM tabanlı korumaya yaklaşımın klasik unpacking'den temelde farklı olması gerekir; amaç artık "orijinal native kodu geri almak" değil, **davranışı gözlemlemek**tir:

- **Davranışsal analiz önceliklidir**: Statik olarak bytecode'u çözmeye çalışmak yerine, kontrollü bir ortamda çalıştırıp hangi dosyalara dokunduğu, hangi ağ bağlantılarını açtığı, hangi registry anahtarlarını değiştirdiği, hangi process'leri oluşturduğu gözlemlenir (dynamic/behavioral analysis). VM koruması "ne yaptığını" gizleyebilir ama "gerçekte ne yaptığını" — yani sistem çağrılarını, ağ trafiğini — sonsuza dek gizleyemez, çünkü bir noktada gerçek CPU'da gerçek sistem çağrıları yapılmak zorundadır.
- **API/syscall seviyesinde izleme**: Kullanıcı modu API hooking yerine daha derin seviyede (kernel driver tabanlı izleme veya hypervisor tabanlı izleme) yapılan gözlem, VM interpreter'ın kendisini atlayarak doğrudan "sonuçta hangi Windows API'leri çağrıldı" sorusuna cevap arar. Bu, VM'nin obfuscation katmanını etkisiz kılan en pratik savunma yaklaşımıdır.
- **Interpreter'ın kendisini haritalama**: İleri seviye analistler zaman içinde VM dispatcher döngüsünü ve handler tablosunu statik/dinamik analizle çıkarıp bir "devirtualization" (sanallıktan çıkarma) süreci uygulayabilir — bytecode'u tekrar native/okunur bir forma çevirme girişimi. Bu son derece emek yoğun bir süreçtir ve genelde belirli bir protector sürümüne özeldir; her büyük sürüm güncellemesinde tekrar yapılması gerekebilir. Bu makalede belirli bir aracın veya sürümün hangi handler yapısını kullandığına dair iddialarda bulunulmayacaktır çünkü bu bilgi hızla eskir ve sürümden sürüme değişir.
- **Bellek taraması (memory scanning) zaman-tabanlı yaklaşım**: VM içinde çalışan kod bile bir noktada gerçek verileri (decrypted string'ler, gerçek API adresleri, config verileri) RAM'de düz metin/açık halde tutmak zorunda kalabilir çünkü CPU sonunda gerçek işlemi yapmalıdır. Periyodik bellek dump'ları alıp bu "açığa çıkma anlarını" yakalamak, tam devirtualization yapmadan da değerli istihbarat (IOC — indicator of compromise, C2 adresleri, config) çıkarabilir.

## Tespit ve Savunma: Kurumsal Bakış Açısı

Bir savunma mühendisi/tespit mühendisi (detection engineer) için VM tabanlı koruma ve gelişmiş packer'lar şu sinyalleri üretir; bunlar tespit kuralı (detection rule) tasarımında kullanılabilir:

- **Anormal bellek izin değişiklikleri**: Bir process'in kendi belleğinde `RWX` (read-write-execute) izinli bölgeler oluşturması veya `VirtualAlloc`/`VirtualProtect`/`NtProtectVirtualMemory` ile bir bölgeyi sonradan çalıştırılabilir hale getirmesi, hem klasik packer'lar hem VM interpreter'lar için ortak, güçlü bir davranışsal sinyaldir. EDR ürünleri bu deseni (self-modifying/self-unpacking behavior) genelde önceliklendirir.
- **Yüksek entropi bölümler**: PE dosyasının section'larında (özellikle `.text` dışı bölgelerde) yüksek entropi (rastgeleliğe yakın byte dağılımı), sıkıştırma veya şifreleme varlığının istatistiksel bir işaretidir. Bu, tek başına kesin kanıt değildir (meşru sıkıştırılmış kaynaklar da yüksek entropili olabilir) ama şüpheli dosyaları önceliklendirmede kullanılan standart bir triyaj metriğidir.
- **Import tablosu anomalileri**: Çok az sayıda import (örneğin sadece `LoadLibrary`/`GetProcAddress` gibi "self-loading" fonksiyonlar), gerçek işlevselliğin çalışma zamanında dinamik olarak çözüleceğinin işaretidir — bu, packer/protector varlığının klasik bir statik göstergesidir.
- **Anti-debug/anti-VM API çağrı desenleri**: `IsDebuggerPresent`, zamanlama tabanlı kontroller (`RDTSC` gibi), belirli donanım/ortam sorguları gibi çağrıların yoğun kullanımı, örneğin normal bir iş uygulamasında beklenmeyen bir davranıştır ve şüphe uyandırmalıdır.
- **Sandbox/dinamik analiz altyapısı yatırımı**: Statik analiz VM tabanlı korumaya karşı zayıf kaldığı için, kurumsal savunmanın ağırlık merkezi davranışsal/dinamik analiz + EDR telemetrisi + ağ seviyesi tespite kaymalıdır. "Bu dosya nasıl paketlenmiş" sorusu yerine "bu process ne yaptı" sorusuna odaklanan bir mimari (örneğin process oluşturma zincirleri, ağ bağlantı hedefleri, dosya sistemi/registry değişiklikleri üzerinden korelasyon) çok daha dayanıklıdır.
- **Uygulama kontrolü ve imzalama**: Bilinmeyen/imzasız, yüksek entropili, nadir görülen binary'lerin çalışmasını varsayılan olarak engelleyen application allowlisting (izin verilenler listesi) yaklaşımları, VM tabanlı koruma ne kadar sofistike olursa olsun, "bu dosyanın çalışmasına hiç izin verme" ilkesiyle sorunu kökünden bertaraf eder.
- **Bellek adli analizi (memory forensics) yetkinliği**: Olay müdahale (incident response) ekiplerinin disk imajı yerine bellek imajı (memory image) analiz edebilme yetkinliği kritik önemdedir; çünkü VM tabanlı korumalı malware'in "gerçek" davranışı sadece çalışırken, bellekte gözlemlenebilir.

## Yaygın Hatalar

- **"Unpacked = Zararsız" veya "Unpack Edemedim = Analiz Edemem" Yanılgısı**: Bir dosyanın tam olarak statik unpack edilememesi, davranışsal analizin de imkansız olduğu anlamına gelmez. Dinamik/sandbox analizi, VM koruması varken bile IOC üretebilir.
- **Tek Bir OEP Aramak**: VM tabanlı korumalı binary'lerde "klasik OEP" kavramını aramak zaman kaybıdır; bu binary'lerde kod parça parça, ihtiyaç anında yorumlanır, tek bir "gerçek kod başlangıcı" anı çoğu zaman yoktur.
- **Otomatik Unpacker'lara Körü Körüne Güvenmek**: Genel amaçlı otomatik unpacking araçları bilinen/klasik packer imzalarını tanır; custom veya VM tabanlı korumalarda genelde başarısız olur veya yanlış/eksik dump üretir. Sonuç her zaman manuel doğrulama gerektirir.
- **Statik Entropi Analizini Tek Kanıt Sayma**: Yüksek entropi paketleme/şifreleme göstergesi olabilir ama meşru sıkıştırılmış/şifrelenmiş içerik (örneğin gömülü resurslar) de aynı istatistiği verir; entropi tek başına değil, diğer sinyallerle birlikte değerlendirilmelidir.
- **IAT Rebuild'i Atlamak**: Dump alıp "OEP'i buldum" demek yeterli değildir; import tablosu düzeltilmeden dump edilen dosya çoğu zaman çalışmaz ve statik analiz araçlarında anlamsız görünür — bu adımın atlanması, unpacking sürecinin yarım kalmasına yol açan en sık hatalardan biridir.
- **Sandbox Kaçış Tekniklerini Göz Ardı Etmek**: Anti-VM/anti-sandbox kontrolleri olan bir örneği düz bir sandbox'ta çalıştırıp "zararsız görünüyor, hiçbir şey yapmadı" sonucuna varmak yanlış negatif üretir; örnek sandbox'ı tespit edip kötü niyetli davranışını gizlemiş olabilir. Analiz ortamının bu tespit tekniklerine karşı sertleştirilmiş (hardened) olması gerekir.
- **Tek Bir Protector Sürümüne Göre Genelleme Yapmak**: Bir protector'ın bir sürümünde işe yarayan bir devirtualization/analiz yöntemi, sonraki sürümde handler tablosu veya VM mimarisi değiştirildiği için işe yaramayabilir. Analiz metodolojisi sürekli güncellenmesi gereken canlı bir süreç olarak ele alınmalıdır.

## Sonuç

Custom packer'lar ve VM tabanlı protector'lar, savunma tarafının "statik olarak dosyayı incele, imza eşleştir" refleksini kökten geçersiz kılan bir tehdit sınıfını temsil eder. Klasik unpacking (OEP bulma, dump-and-fix, IAT rebuilding) hâlâ tek katmanlı, basit packer'lara karşı geçerli ve öğretici bir zihinsel modeldir, ama VM tabanlı korumayla karşılaşıldığında bu model kavramsal olarak çöker çünkü ortada tek bir "orijinal native kod anı" yoktur. Bu yüzden olgun bir savunma stratejisi, statik unpacking çabasını tamamen terk etmeden, ağırlığı davranışsal analiz, bellek adli analizi, API/syscall seviyesi telemetri ve uygulama kontrolüne kaydırmalıdır — çünkü kod ne kadar gizlenirse gizlensin, bir noktada gerçek CPU üzerinde gerçek bir sistem çağrısı yapmak, gerçek bir dosyaya yazmak veya gerçek bir ağ paketi göndermek zorundadır; savunmanın en güvenilir gözlem noktası tam olarak bu andır.
