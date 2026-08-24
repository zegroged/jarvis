# Bellek Adli Bilişimi (Memory Forensics)

## Tanım

Bellek adli bilişimi, bir bilgisayarın çalışır durumdaki uçucu belleğinin (RAM) bir kopyasını (memory dump / bellek imajı) alıp bu ham veriyi analiz ederek olay anındaki sistem durumunu yeniden inşa etme disiplinidir. Amaç; hangi süreçlerin (process) çalıştığını, hangi ağ bağlantılarının açık olduğunu, hangi kullanıcı kimlik bilgilerinin bellekte durduğunu, hangi kötücül kodun (malware) yüklü olduğunu ve diskte hiçbir iz bırakmamış saldırı bileşenlerini ortaya çıkarmaktır.

Bu disiplinin var oluş nedeni basittir: Modern saldırıların önemli bir kısmı diske dokunmadan, yalnızca bellekte yaşar (fileless malware, in-memory injection, living-off-the-land teknikleri). Diski ne kadar iyi incelerseniz inceleyin, sadece RAM'de var olan bir Cobalt Strike beacon'ını ya da PowerShell ile belleğe reflectively yüklenmiş bir .NET assembly'sini disk imajında göremezsiniz. Ayrıca şifreleme anahtarları, açık metin (plaintext) parolalar, oturum token'ları ve TLS oturum sırları da çoğunlukla yalnızca bellekte bulunur. Bellek adli bilişimi, "sistem o an ne düşünüyordu?" sorusunun cevabıdır.

## Kök Neden ve Çalışma Mantığı: Neden RAM Bu Kadar Değerli?

### Uçuculuk (volatility) hiyerarşisi

Adli bilişimde delillerin bir "uçuculuk sırası" (order of volatility) vardır. En uçucu delil CPU register'ları ve cache'idir; onu RAM izler; sonra ağ durumu, çalışan süreçler, disk ve en sonda arşiv ortamları gelir. RAM, elektrik kesildiği anda (ya da sistem kapandığında) kaybolur. Bu yüzden bir olay müdahalesinde (incident response) sıklıkla ilk toplanması gereken delil disk değil, bellektir. "Önce fişi çek" (pull the plug) geleneksel tavsiyesi, fileless tehdit çağında çoğu zaman en değerli delili yok etmek anlamına gelir.

### İşletim sistemi bellekte veri yapıları tutar

Bellek analizinin mümkün olmasının kök nedeni şudur: İşletim sistemi (özellikle Windows çekirdeği) her süreci, her thread'i, her açık dosyayı, her ağ soketini, her yüklü sürücüyü belleğe yerleştirilmiş yapısal veri nesneleri (kernel objects / structures) olarak tutar. Örneğin Windows'ta her süreç `EPROCESS` adı verilen bir çekirdek yapısıyla temsil edilir ve bu yapılar birbirine çift yönlü bağlı liste (doubly linked list) ile bağlanır (`ActiveProcessLinks`). Volatility gibi araçlar tam olarak bu yapıları bellek imajı içinde bulup çözümleyerek çalışır.

Analiz aracının çözmesi gereken temel problem şudur: Ham bellek imajı, işlemcinin gördüğü fiziksel adres uzayıdır; oysa işletim sistemindeki tüm işaretçiler (pointer) sanal adreslerdir (virtual address). Araç, sanal adresi fiziksel adrese çevirmek için bellekteki sayfa tablolarını (page tables) ve süreçlerin `DirectoryTableBase` (CR3 register'ının işaret ettiği yer) değerini bulup MMU'nun yaptığı adres çevirisini yazılımda taklit eder. Bunu yapabilmek için de imajın hangi işletim sistemine ve çekirdek sürümüne ait olduğunu bilmesi, yani doğru profili/sembol tablosunu kullanması gerekir. Windows'ta bu sembolleri Microsoft'un PDB sembol dosyalarından türetilen yapı ofsetleri sağlar.

Bu yüzden "profil/sembol eşleşmesi" bellek adli bilişiminde birinci sınıf bir problemdir: Yanlış çekirdek sürümü sembolleriyle bir imajı yorumlamak, yapı ofsetlerinin kaymasına ve çöp veri okunmasına yol açar.

## Volatility: Standart Araç

Volatility, açık kaynaklı ve fiilen endüstri standardı olan bellek analiz çerçevesidir. İki ana nesil vardır ve bu ayrım pratikte önemlidir:

- **Volatility 2**, Python 2 tabanlıdır ve profil kavramına dayanır. Analistin imajın işletim sistemi profilini elle belirlemesi (ya da `imageinfo`/`kdbgscan` ile tahmin ettirmesi) beklenir.
- **Volatility 3**, Python 3 tabanlıdır, profilleri terk edip Microsoft'un sembol sunucusundan indirilen sembol tablolarını (ISF) kullanır ve profili otomatik saptamaya çalışır. Komut adlandırması da değişmiştir (örneğin eklenti adları `windows.pslist` gibi ad uzayı biçimindedir).

Sürümler arası komut adları ve bayrakları farklılaştığı için, bir prosedürü uygularken önce elinizdeki sürümü teyit etmek gerekir; ezberden bayrak yazmak hataya açıktır.

### Volatility'nin çalışma felsefesi: liste değil, tarama

Volatility eklentilerini iki kategoride düşünmek çok öğreticidir çünkü bu ayrım anti-forensic tekniklerin nasıl yenildiğini açıklar:

1. **Liste tabanlı (list-walking) eklentiler**: İşletim sisteminin kendi bağlı listelerini takip eder. Örneğin süreç listesi eklentisi, çekirdeğin aktif süreç bağlı listesini baştan sona yürür. Hızlıdır ve işletim sisteminin gördüğünü gösterir. Zayıflığı şudur: Eğer bir saldırgan bir sürecin `EPROCESS` yapısını listeden çıkarırsa (unlinking), liste yürüyen eklenti o süreci göremez.

2. **Tarama tabanlı (scanning) eklentiler**: Tüm bellek imajını bayt bayt tarayıp belirli yapıların imzalarını (pool tag'leri, yapı sabitleri) arar. Bağlı listeye güvenmez. Bu yüzden listeden çıkarılmış (unlinked) ya da sonlanmış ama belleği henüz geri alınmamış süreçleri de bulabilir.

İkisini karşılaştırmak, bellek adli bilişiminin en güçlü tespit yöntemlerinden biridir. Liste tabanlı eklentinin göstermediği ama tarama tabanlı eklentinin bulduğu bir süreç, güçlü bir gizlenme (DKOM - Direct Kernel Object Manipulation) göstergesidir.

### Tipik bir analiz akışı

Gerçek bir imajda genellikle şu mantıksal sırayla ilerlenir:

- Önce imajı tanı: işletim sistemi ve çekirdek sürümünü sapta, doğru sembolleri yükle.
- Süreç envanterini çıkar: hem liste tabanlı hem tarama tabanlı süreç listelemesini alıp karşılaştır.
- Süreç ağacını (parent-child) incele: şüpheli ebeveyn-çocuk ilişkileri ara.
- Ağ bağlantılarını dök: hangi süreç hangi uzak adrese bağlanmış?
- Yüklü DLL'leri, handle'ları, komut satırlarını incele.
- Belleği string ve YARA kuralı ile tara; şüpheli bölgeleri diske çıkar (dump).
- Kayıt defteri (registry) kovanlarını, olay günlüklerini ve kimlik bilgisi yapılarını bellekten çıkar.

## Süreç (Process) Analizi

### Süreç ağacı neden bu kadar önemli?

Windows'ta her sürecin bir ebeveyn süreç kimliği (PPID) vardır ve normal sistemde bu ilişkiler oldukça öngörülebilirdir. `services.exe`'nin ebeveyni `wininit.exe`'dir; kullanıcı uygulamaları genellikle `explorer.exe` altından doğar. Saldırganın kodu bu beklenen şablonu bozar. Klasik bir kırmızı bayrak, bir ofis uygulamasının (örneğin bir Word süreci) altından bir komut yorumlayıcısının (`cmd.exe` ya da `powershell.exe`) doğmasıdır; bu, makro tabanlı bir ilk erişimin (initial access) tipik izidir.

Süreç ağacını incelerken analistin sorduğu "neden" soruları şunlardır:

- Bu sürecin ebeveyni olması gereken süreç mi? (`lsass.exe`'nin ebeveyni normalde `wininit.exe`'dir; başka bir şeyse şüphelidir.)
- Bu süreç tek olması gereken bir sistem süreci mi, ama birden fazla örneği mi var? (Örneğin sistemde normalde tek bir `lsass.exe` olur; iki tane görmek çok güçlü bir taklit/maskeleme göstergesidir.)
- Sürecin çalıştırılabilir yolu (image path) beklenen sistem dizininde mi, yoksa `%TEMP%` ya da kullanıcı profili gibi anormal bir yerde mi?

### Maskeleme (masquerading) ve içi boş süreçler

Saldırganlar meşru görünmek için süreçlerini sistem süreçleriyle aynı isimle adlandırır (`svch0st.exe`, ya da doğru yazımıyla ama yanlış dizinde `svchost.exe`). Bu yüzden yalnızca isme bakmak yetmez; yolu, ebeveyni, komut satırını ve dijital imzayı birlikte değerlendirmek gerekir.

Daha ileri bir teknik **process hollowing** (süreç oyma) ve genel olarak süreç enjeksiyonudur ki bir sonraki bölümün ana konusudur.

## Injection (Kod Enjeksiyonu) Analizi

### Kök neden: Neden saldırgan başka bir süreç içine kod yerleştirir?

Süreç enjeksiyonunun temel motivasyonu iki yönlüdür. Birincisi **gizlenme**: Kötücül kod, meşru ve güvenilen bir sürecin (örneğin `explorer.exe`, `svchost.exe`, bir tarayıcı) bellek adres uzayı içinde çalışırsa, EDR ve kullanıcı gözünde o meşru süreç gibi görünür. İkincisi **erişim ve kalıcılık**: Hedef sürecin sahip olduğu handle'ları, token'ları ve ağ güveninden faydalanmak; ayrıca diske yazmadan bellekte yaşayarak dosya tabanlı tespitten kaçmak.

### Enjeksiyon tekniklerinin çalışma mantığı

Klasik süreç enjeksiyonu genellikle şu adımların bir varyasyonudur: Hedef sürece bir handle açılır, hedefin adres uzayında bellek ayrılır (yürütülebilir izinlerle), oraya kötücül kod (shellcode ya da DLL yolu) yazılır ve ardından o bölgede yürütme başlatılır (yeni bir uzak thread oluşturarak ya da mevcut bir thread'i saptırarak). Yaygın varyantlar:

- **Classic DLL injection**: Hedefe kötücül DLL'in yolu yazılır ve `LoadLibrary` uzaktan çağrılarak yüklettirilir.
- **Reflective DLL injection**: DLL diske hiç yazılmaz; doğrudan bellekte kendi kendini yükler. Bu yüzden yüklü modül listesinde (loaded modules) görünmeyebilir, çünkü işletim sisteminin normal yükleyicisi devreye girmemiştir.
- **Process hollowing (RunPE)**: Meşru bir süreç askıya alınmış (suspended) halde başlatılır, orijinal imajı bellekten "oyulur" (unmap) ve yerine kötücül imaj yerleştirilip yürütme oraya yönlendirilir. Süreç dışarıdan meşru görünür ama içi tamamen değişmiştir.
- **Thread hijacking**: Yeni thread açmadan, var olan bir thread'in bağlamı (context) değiştirilerek yürütme kaçırılır.

### Bellekte enjeksiyonu ne ele verir?

Bellek adli bilişiminin enjeksiyona karşı en güçlü tarafı, enjeksiyonun bıraktığı **bellek anomalilerini** görebilmesidir. Temel gösterge, bir sürecin adres uzayındaki bellek bölgelerinin izinleri ve kaynağı arasındaki tutarsızlıktır:

- **Özel (private), yürütülebilir (executable) ve yazılabilir (RWX) bellek bölgeleri**: Normalde kod, diskteki bir dosyadan (image-backed) eşlenir ve salt-okunur/çalıştırılabilir olur. Ama bir sürecin içinde hiçbir dosyaya dayanmayan (private, unbacked), aynı anda hem yazılabilir hem yürütülebilir bir bölge varsa, bu enjekte edilmiş kodun klasik parmak izidir. Volatility'nin bu işi yapan eklentisi (kavramsal olarak "malfind" mantığı), tam olarak bu image-backed olmayan yürütülebilir bölgeleri arayıp içinde çalıştırılabilir kod imzası (örneğin `MZ` başlığı ya da makine kodu kalıpları) olan yerleri işaretler.
- **Yüklü modül listesinde olmayan kod**: Reflective yüklenmiş bir DLL, VAD (Virtual Address Descriptor) ağacında bir bölge olarak görünür ama işletim sisteminin modül listesinde bulunmaz. VAD ile modül listesini karşılaştırmak bu farkı ortaya çıkarır.
- **Process hollowing tutarsızlığı**: Sürecin bellekteki imajı ile diskteki asıl dosyası karşılaştırıldığında baş bölümlerin (PE header, giriş noktası) uyuşmaması hollowing'e işaret eder.

Buradaki temel "neden" şudur: Saldırgan kodu diske yazmaktan kaçınmak için belleğe koyar; ama bu davranışın kendisi belleği "normal" bir süreçten ayırt edilebilir kılar. Diskten kaçış, bellekte iz bırakır. Bellek adli bilişimi bu değiş tokuşun tam kalbindedir.

### Somut senaryo

Diyelim ki `pslist` ile bakıldığında sistemde iki `explorer.exe` görünüyor, biri normal PPID'ye sahipken diğerinin ebeveyni garip bir süreç. Analist ikinci `explorer.exe`'nin bellek bölgelerini incelediğinde image-backed olmayan bir RWX bölge buluyor, o bölgeyi diske çıkarıp içinde bir shellcode/PE bulmuş oluyor. Ağ eklentisiyle o sürecin bilinmeyen bir uzak IP'ye 443 portundan bağlandığını görüyor. String taramasında beacon yapılandırmasına benzer izler var. Bu adımların her biri tek başına şüphe, hepsi birlikte güçlü bir uzlaşma (compromise) delilidir.

## Kimlik Çıkarımı (Credential Extraction)

### Kök neden: Parolalar neden bellekte durur?

Windows'ta oturum açan kullanıcıların kimlik bilgileri, tek oturum açma (SSO) deneyimini sağlamak için çalışma zamanında bellekte tutulur. Bunların büyük kısmı `lsass.exe` (Local Security Authority Subsystem Service) sürecinin adres uzayında bulunur: NTLM hash'leri, Kerberos biletleri (ticket) ve bazı eski/uyumluluk yapılandırmalarında düz metne yakın kimlik materyali. Bu materyal orada durur çünkü sistem, kullanıcı her ağ kaynağına eriştiğinde parolayı tekrar sormamak için kimlik doğrulama sırlarını canlı tutmak zorundadır. Yani zafiyet bir hata değil, bir tasarım tavizidir (usability vs. security).

Saldırganların meşhur `lsass` bellek boşaltma (dumping) saldırısının özü budur: `lsass.exe` sürecinin belleğini alıp içindeki hash ve biletleri çıkarmak. Bellek adli bilişimi açısından ilginç olan şudur: Aynı işi bir saldırgan da, bir savunmacı adli analist de yapabilir. Farkı niyet ve yetki belirler; teknik aynıdır.

### Bellekten kimlik çıkarımının mantığı

Bir bellek imajından kimlik materyali çıkarmanın birkaç yolu vardır:

- **`lsass` içindeki kimlik sağlayıcı yapıları**: `lsass` belleğindeki ilgili yapılar çözümlenerek NTLM hash'leri ve Kerberos biletleri çıkarılabilir. Mimikatz'ın canlı sistemde yaptığı işin adli karşılığı budur; bellek imajı üzerinde çalışan araçlar ve Volatility eklentileri benzer yapıları hedefler.
- **Kayıt defteri kovanlarından hash**: `SAM` kovanından yerel hesap NTLM hash'leri ve `SECURITY` kovanından cached domain credentials (DCC/DCC2) çıkarılabilir. Bunların şifresini çözmek için `SYSTEM` kovanındaki boot key gerekir. Bu kovanlar bellek imajında da bulunur çünkü çalışan sistemde bellekte eşlenmişlerdir.
- **Kerberos biletleri**: Bellekte duran TGT ve servis biletleri, pass-the-ticket saldırısına ya da adli olarak "kim neye erişmiş" analizine kaynak olur.
- **Düz metin izleri**: Tarayıcılarda, komut satırlarında (bir betikte gömülü parola), ortam değişkenlerinde ve çeşitli uygulama tamponlarında düz metin parolalar bellekte string taramasıyla bulunabilir. Komut satırlarını incelemek (process command line), gömülü kimlik bilgilerini yakalamanın şaşırtıcı derecede verimli bir yoludur.

### Hash'in anlamı: sömürü tarafı

Çıkarılan bir NTLM hash mutlaka kırılmak zorunda değildir. **Pass-the-hash** saldırısında hash doğrudan kimlik doğrulama için kullanılabilir, çünkü NTLM protokolü esasen hash'i bilmeyi ispat üzerine kuruludur. Benzer şekilde Kerberos biletleri **pass-the-ticket** ile yeniden oynatılabilir. Bu yüzden bellekten tek bir yüksek yetkili hesabın hash'inin sızması, çoğu zaman tüm etki alanının (domain) tehlikeye girmesine giden yolun ilk taşıdır (lateral movement). Adli analist bu yüzden yalnızca "hangi hash sızdı" değil, "bu hash nereye erişebilir" sorusunu da sormalıdır.

## Savunma: İkili Bakış

Yukarıdaki her istismar tekniğinin bir savunma karşılığı vardır. Bellek adli bilişimi hem saldırıyı anlamak hem de savunmayı kurmak için kullanılır.

### Enjeksiyona karşı savunma

- **RWX bellek avı**: EDR ürünleri ve periyodik bellek taramaları, image-backed olmayan yürütülebilir bölgeleri ve RWX izinli özel bellekleri arar. Bu, enjeksiyonun temel imzasını hedefler.
- **API telemetrisi**: `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread`, `NtMapViewOfSection` gibi enjeksiyonda kullanılan çağrı dizilerinin izlenmesi. Tek başına her çağrı meşru olabilir; şüpheli olan sıralı kalıptır.
- **Sürecin bütünlüğü**: İmza doğrulama, beklenen ebeveyn-çocuk ilişkilerinin izlenmesi, hollowing'e karşı imaj-disk karşılaştırması.

### Kimlik hırsızlığına karşı savunma

- **`lsass` koruması**: Credential Guard gibi çözümler, kimlik sırlarını izole (VBS/virtualization-based security) bir bileşende tutarak `lsass` belleğinden çıkarılmasını zorlaştırır. RunAsPPL ile `lsass`'ı korumalı süreç yapmak, belleğine erişimi kısıtlar.
- **Cached credential ve yetki azaltma**: Cached domain logon sayısını azaltmak, yerel yönetici parolalarını benzersizleştirmek (LAPS mantığı), en az yetki ilkesi.
- **Tespit**: `lsass` sürecine anormal handle açan ya da belleğini okuyan süreçlerin izlenmesi. Meşru olmayan bir sürecin `lsass`'a `PROCESS_VM_READ` ile erişmesi çok güçlü bir alarmdır.

### Anti-forensic'e karşı savunma

Saldırganlar bellek toplamayı zorlaştırmak için imaj alma araçlarını engellemeye ya da yapıları bozmaya çalışabilir. Buna karşı savunma; erken ve güvenilir bellek toplama, birden fazla toplama yöntemi (kernel sürücüsü tabanlı, hipervizör tabanlı) ve liste-tarama karşılaştırması gibi çapraz doğrulamalardır. DKOM ile listeden çıkarma, tam da bu yüzden tarama tabanlı eklentilerle yenilir.

## Yaygın Hatalar

Bellek adli bilişiminde deneyimsizlikten kaynaklanan tipik hatalar, çoğu zaman sessizce yanlış sonuca götürdükleri için tehlikelidir:

1. **Belleği geç ya da hiç toplamamak**: Sistemi hemen kapatıp yalnızca disk imajı almak, fileless tehditlerin tek delilini yok eder. Uçuculuk sırasına uymamak en pahalı hatadır.
2. **Bellek toplarken sistemi kirletmek**: Analiz araçlarını hedef sistemin diskine kurmak, ağır süreçler çalıştırmak belleği ve diski değiştirir. Toplama mümkün olduğunca küçük ayak iziyle, tercihen harici ortamdan yapılmalıdır. Toplama işleminin kendisi de belleği bir miktar değiştirir; bu kaçınılmazdır ama en aza indirilmelidir.
3. **Yanlış profil/sembol kullanmak**: Yanlış çekirdek sürümü sembolleriyle çalışmak, ofsetlerin kaymasına ve tamamen yanıltıcı (çöp) çıktılara yol açar. Çıktının makul görünmesi doğruluğunu garanti etmez.
4. **Yalnızca liste tabanlı eklentilere güvenmek**: DKOM ile gizlenmiş süreçleri kaçırmak. Tarama tabanlı doğrulama atlanırsa gizlenen tehdit görünmez kalır.
5. **Bütünlük (hash) ve zincirleme delil (chain of custody) kaydı tutmamak**: Adli çıktının mahkemede ya da kurumsal soruşturmada geçerli olması için imajın hash'i alınmalı, kim ne zaman ne yaptı kaydedilmelidir. Teknik doğru ama süreç kayıtsızsa delil değeri düşer.
6. **Tek bir göstergeye dayanıp sonuca atlamak**: Tek bir RWX bölge ya da tek bir isim benzerliği yanlış pozitif olabilir. Bağlam (ağ, ebeveyn, komut satırı, imza, zaman) birlikte değerlendirilmelidir.
7. **Sanallaştırılmış/şifrelenmiş belleği hesaba katmamak**: Modern sistemlerde VBS/Credential Guard ile bazı sırlar klasik yöntemle çıkarılamaz. "Çıkaramadım, demek ki yok" sonucu yanlıştır.

## En İyi Pratikler

- **Uçuculuk sırasına uy**: Mümkünse sistemi kapatmadan önce belleği topla. Canlı müdahalede önce en uçucu delili al.
- **Küçük ayak izi**: Bellek toplamayı güvenilir, imzalı, mümkünse harici bir araçla ve minimum sistem etkisiyle yap. Toplama anını ve yöntemini kaydet.
- **Bütünlüğü doğrula**: İmajın kriptografik hash'ini toplama anında al, zincirleme delili belgele, çalışma kopyası üzerinde analiz yap, orijinali dokunulmaz tut.
- **Profili/sembolleri titizlikle eşleştir**: İmajın işletim sistemi ve çekirdek sürümünü doğrula, doğru sembolleri kullan; şüphede kalırsan çıktının içsel tutarlılığını denetle.
- **Çapraz doğrula**: Liste tabanlı ve tarama tabanlı eklentileri birlikte çalıştırıp farkları araştır. Bir bulguyu tek eklentiyle değil, birden çok bağımsız göstergeyle destekle.
- **Bağlamı birleştir**: Süreç ağacı, ağ bağlantıları, yüklü modüller, handle'lar, komut satırları, kayıt defteri ve zaman çizelgesini (timeline) bir arada değerlendir. Tek gösterge değil, örüntü karar verir.
- **Otomatikleştir ama körlemesine güvenme**: YARA kuralları, bilinen kötücül imza taramaları ve otomatik triage faydalıdır; ama her otomatik bulguyu elle doğrula, otomasyonun kaçırdıklarını da düşün.
- **Kimlik varlıklarını önceliklendir**: Bir uzlaşma tespit edilirse, bellekte hangi kimlik materyalinin açıkta olduğunu değerlendir ve etkilenen hesapların parolalarını/biletlerini geçersiz kıl. Sızmış hash pass-the-hash için hâlâ değerlidir; müdahale kimlik rotasyonunu içermelidir.
- **Öğren ve güncel kal**: İşletim sistemi çekirdek yapıları sürümden sürüme değişir; enjeksiyon ve kimlik hırsızlığı teknikleri sürekli evrilir. Araç sürümünü ve tekniği güncel tut, ezber bayrak/komut yerine kavramı anla.

## Kapanış

Bellek adli bilişimi, "diskte iz yok, demek ki temiz" yanılgısını yıkan disiplindir. RAM, sistemin o anki bilincidir: çalışan süreçler, enjekte edilmiş kod, açık bağlantılar ve en kritiği canlı kimlik sırları oradadır. Volatility gibi araçlar bu ham belleği anlamlı çekirdek yapılarına çevirir; analistin işi ise tek tek göstergeleri bir hikâyeye bağlamaktır. Saldırgan diske yazmaktan kaçtıkça belleğe bağımlı hâle gelir ve tam da bu yüzden bellek, modern savunmanın en aydınlatıcı delil kaynağıdır. Sömürü ile savunma aynı yapıları hedefler; farkı yaratan, bu yapıları kimin, hangi niyet ve titizlikle okuduğudur.
