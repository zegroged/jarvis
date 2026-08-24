# Disk Adli Bilişimi: MFT, Registry, Prefetch, Silinmiş Dosya ve Timeline

## Giriş ve Tanım

Disk adli bilişimi (disk forensics), bir depolama biriminden (HDD, SSD, USB, disk imajı) hukuken savunulabilir ve teknik olarak doğrulanabilir biçimde delil çıkarma disiplinidir. Amaç yalnızca "ne var" sorusunu değil, çok daha zor olan "ne zaman, kim tarafından, hangi sırayla, hangi niyetle yapıldı" sorularını yanıtlamaktır. Bir saldırganın sisteme girip girmediğini, hangi dosyaları çalıştırdığını, neyi sildiğini ve izlerini nasıl temizlemeye çalıştığını disk üzerinde bıraktığı **artefakt** (artifact) izlerinden yeniden inşa ederiz.

Bu disiplinin kalbinde temel bir gerçek vardır: işletim sistemi verimlilik için tasarlanmıştır, gizlilik için değil. Windows, kullanıcı deneyimini hızlandırmak amacıyla her yerde önbellek, indeks ve meta veri tutar. Kullanıcının veya saldırganın haberi olmadan tutulan bu izler, adli bilişimcinin en değerli kaynağıdır. Prefetch dosyaları uygulamayı daha hızlı açmak için vardır; ama biz onları "hangi program çalıştırıldı" sorusuna cevap olarak kullanırız. Bu, adli bilişimin temel felsefesidir: **sistemin performans için ürettiği yan ürünleri delile çevirmek.**

Bu makale Windows/NTFS ekseninde beş temel odağı derinlemesine işler: MFT, registry, prefetch, silinmiş dosya kurtarma ve tüm bunları birleştiren timeline analizi.

## Temel İlke: İmaj Alma ve Delil Bütünlüğü

Herhangi bir analize başlamadan önce anlaşılması gereken kök prensip şudur: **canlı sistem üzerinde asla doğrudan çalışılmaz.** Bir dosyayı açmak bile `$STANDARD_INFORMATION` içindeki erişim zaman damgasını değiştirebilir, yani delili incelerken deliller bozulur. Bu yüzden ilk adım, diskin bit-bit birebir kopyasını (**forensic image**) almaktır.

İmaj alırken **write blocker** (yazma engelleyici) donanım veya yazılımı kullanılır; bu, işletim sisteminin kaynak diske hiçbir byte yazmamasını garanti eder. İmaj alındıktan sonra hem kaynak diskin hem imajın kriptografik **hash** değeri (tarihsel olarak MD5/SHA-1, günümüzde SHA-256 tercih edilir) hesaplanır ve eşleştirilir. Bu eşleşme, mahkemede "delil değiştirilmedi" iddiasının teknik temelidir. Analiz her zaman imaj üzerinde (veya onun bir kopyası üzerinde) yapılır. Bu bütünlük zinciri (chain of custody) bozulursa en mükemmel teknik bulgu bile hukuken değersizleşir.

Neden bu kadar katıyız? Çünkü adli bilişimin ürünü bir "his" değil, tekrar üretilebilir bir kanıttır. Başka bir uzman aynı imajı alıp aynı adımları izlediğinde aynı sonuca ulaşabilmelidir. Reprodüksiyon (reproducibility) olmadan bilim de, hukuk da yoktur.

## MFT: NTFS'in Omurgası ve Adli Bilişimin Altın Madeni

### Tanım ve Çalışma Mantığı

NTFS dosya sisteminde her şey bir dosyadır; dizinler bile. Ve tüm bu dosyaların merkezi kaydı **MFT** (Master File Table) adlı özel bir dosyada tutulur; bu dosyanın kendisi de `$MFT` metadata dosyasıdır. MFT, her dosya ve dizin için genellikle 1024 byte boyutunda bir **kayıt** (record) barındırır. Diskteki dosya sayısı arttıkça MFT büyür.

Her MFT kaydı, dosyayı tanımlayan **attribute** (öznitelik) yapılarından oluşur. Adli bilişim açısından en kritik olanlar şunlardır:

- **`$STANDARD_INFORMATION` ($SI):** Dosyanın oluşturma, değiştirme, MFT kayıt değişimi ve erişim zaman damgalarını (**MACB** timestamps) tutar. Bu alan işletim sistemi API'leri tarafından rutin olarak güncellenir ve önemlisi, kullanıcı seviyesinden manipüle edilmesi görece kolaydır.
- **`$FILE_NAME` ($FN):** Dosyanın adını ve **ayrı bir MACB zaman damgası setini** tutar. Bu zaman damgaları normalde yalnızca dosya oluşturulduğunda, taşındığında veya yeniden adlandırıldığında çekirdek (kernel) tarafından güncellenir; standart API'lerle kolayca değiştirilemez.
- **`$DATA`:** Dosyanın gerçek içeriği. Küçük dosyalarda (yaklaşık 700-900 byte altı) içerik doğrudan MFT kaydının içinde tutulur; buna **resident data** denir. Bu, çok küçük ama önemli dosyaların sadece MFT'de yaşayabileceği anlamına gelir.

### Kök Neden: Neden MFT Bu Kadar Değerli?

MFT değerlidir çünkü dosya diskten silinse bile MFT kaydı bir süre daha **artık** (residual) olarak orada durabilir. Bir dosya silindiğinde NTFS çoğu zaman kaydın içeriğini hemen sıfırlamaz; sadece kaydı "kullanılabilir" olarak işaretler. Yeni bir dosya o kayıt slotunu kullanana kadar, silinmiş dosyanın adı, zaman damgaları ve hatta küçükse içeriği MFT'de okunabilir kalır.

### Somut Örnek: Timestomping Tespiti

Saldırganlar izlerini gizlemek için **timestomping** yapar: kötü amaçlı bir dosyanın zaman damgalarını, sistem dosyalarıyla karışsın diye eskiye çeker (örneğin dosyayı 2009 tarihli bir Windows kurulum dosyası gibi göstermek). Çoğu timestomping aracı yalnızca `$SI` zaman damgalarını değiştirir, çünkü bunlara erişmek kolaydır. Ama `$FN` zaman damgalarına dokunmak çok daha zordur.

İşte adli bilişimcinin ustalık noktası: bir dosyanın `$SI` oluşturma tarihi 2009 iken `$FN` oluşturma tarihi 2024 ise, bu güçlü bir manipülasyon göstergesidir. Ayrıca `$SI` zaman damgalarındaki alt-saniye hassasiyeti (100 nanosaniyelik çözünürlük) düzgün gerçek olaylarda dolu iken, kaba manipülasyon araçları çoğu zaman bu alanları sıfırlanmış (`.0000000`) bırakır. Yuvarlak, sıfırla biten zaman damgaları şüphe uyandırır.

### İstismar / Anti-Forensics Mantığı

Saldırganın bakış açısından MFT'ye saldırmanın yolları: zaman damgalarını manipüle etmek (timestomping), dosyayı **Alternate Data Stream** (ADS) içine gizlemek (`dosya.txt:gizli.exe` gibi ikincil `$DATA` akışları), ya da MFT kaydını doğrudan silmek/bozmak. ADS, NTFS'in bir dosyaya birden fazla `$DATA` akışı iliştirebilme özelliğidir ve klasik dizin listelemesinde görünmez; bu yüzden zararlı yük gizlemek için tarihsel olarak kullanılmıştır.

### Savunma / Tespit Mantığı

Savunma tarafında, `$SI` ve `$FN` zaman damgalarını çapraz karşılaştırmak birincil yöntemdir. `$FN < $SI` gibi mantıksız durumlar veya iki set arasındaki tutarsızlıklar araştırılır. ADS'leri tespit etmek için dosya sistemini ADS-farkındalıklı araçlarla taramak gerekir; standart Explorer bunları göstermez. Ayrıca MFT'yi bütün olarak parse edip zaman çizelgesine dökmek (aşağıdaki timeline bölümü), anormal sıralamaları ortaya çıkarır. Modern EDR ürünleri de dosya oluşturma olaylarını gerçek zamanlı loglayarak sonradan yapılan timestomping'i yakalayabilir, çünkü onların kaydı ile diskteki zaman damgası çelişir.

## Windows Registry: Sistemin Uzun Süreli Hafızası

### Tanım ve Yapı

Windows Registry, işletim sistemi ve uygulama yapılandırmasının saklandığı hiyerarşik bir veritabanıdır ama adli bilişimci için bundan çok daha fazlasıdır: kullanıcı davranışının, takılan cihazların, çalıştırılan programların ve kalıcılık mekanizmalarının kaydını tutan devasa bir olay hafızasıdır. Registry, diskte **hive** adı verilen dosyalarda saklanır: `SYSTEM`, `SOFTWARE`, `SECURITY`, `SAM` hive'ları `Windows\System32\config` altında, her kullanıcının `NTUSER.DAT` hive'ı ise kendi profil dizininde bulunur. Kullanıcı-özel uygulama verisi için `UsrClass.dat` de kritiktir.

### Kök Neden: Neden Registry Delil Doludur?

Registry, Windows'un "hatırlaması gereken" her şeyi biriktirdiği yerdir. Kullanıcı bir USB taktığında Windows onu tekrar tanısın diye kaydeder; bir program çalıştırıldığında uyumluluk verisi tutulur; bir dosya açıldığında "son kullanılanlar" listesine eklenir. Bunların hiçbiri delil amaçlı değildir, ama hepsi delildir.

### Somut Örnekler ve Analiz Kaynakları

Adli açıdan öne çıkan bazı registry alanları ve ne anlattıkları:

- **USB/aygıt geçmişi (`SYSTEM\...\USBSTOR` ve ilgili anahtarlar):** Sisteme takılmış her USB depolama aygıtının üreticisi, seri numarası ve ilk/son bağlanma zamanları. Veri sızdırma (data exfiltration) soruşturmalarının belkemiğidir. "Şirket verisi bir USB'ye kopyalandı mı" sorusuna burası cevap verir.
- **Program çalıştırma kanıtları:** **UserAssist** anahtarı (GUI'den başlatılan programları ve çalıştırma sayısını ROT13 ile kodlanmış olarak tutar), **ShimCache/AppCompatCache** ve **AmCache.hve** (çalıştırılabilir dosyaların yollarını, boyutlarını ve bazı durumlarda hash'lerini tutar). Bu üçlü, "bu makinede hangi çalıştırılabilir dosya vardı/çalıştı" sorusunun birincil kaynağıdır.
- **Son kullanılan dosyalar ve klasörler:** **RecentDocs**, **OpenSavePidlMRU**, **ShellBags** (gezinilen klasörlerin yapısını ve görünüm ayarlarını tutar; bir klasöre gidilmiş olması bile ShellBags'te iz bırakabilir).
- **Kalıcılık (persistence):** **Run/RunOnce** anahtarları, hizmet tanımları, ve çeşitli otomatik başlatma noktaları. Zararlının yeniden başlatma sonrası hayatta kalma mekanizması burada saklıdır.
- **Ağ geçmişi:** Bağlanılan kablosuz ağlar ve profiller.

### İstismar / Anti-Forensics Mantığı

Saldırgan registry'yi hem bir hedef hem bir silah olarak görür. Silah olarak: Run anahtarlarına, hizmetlere veya daha egzotik noktalara (örneğin belirli COM nesnesi kaçırma teknikleri) kalıcılık yerleştirir. Hedef olarak: kendi kalıcılık anahtarlarını sildiği gibi, UserAssist veya ShimCache gibi çalıştırma kanıtlarını temizlemeye çalışabilir. Ancak burada bir asimetri vardır: registry o kadar çok yerde iz tutar ki, bir saldırganın **hepsini** temizlemesi neredeyse imkânsızdır. AmCache'i temizler ama ShimCache'i unutur; UserAssist'i siler ama Prefetch'i atlar. Bu "kaynak çeşitliliği" savunmacının avantajıdır.

### Savunma / Tespit Mantığı

Registry hive'ları da tıpkı MFT gibi silinmiş anahtarların artıklarını içerebilir; hive dosyasının içindeki tahsis edilmemiş (unallocated) alanlar taranarak silinmiş anahtarlar kurtarılabilir. Ayrıca her registry anahtarının bir **LastWrite** zaman damgası vardır; bu, o anahtarın en son ne zaman değiştirildiğini söyler ve timeline'a katkı sağlar. Örneğin bir Run anahtarının LastWrite zamanı, zararlının kurulum anıyla örtüşebilir. Temiz bir "baseline" ile karşılaştırma (bilinen iyi bir sistemin registry'si ile fark alma) da kalıcılık noktalarını ortaya çıkarmanın güçlü bir yoludur.

## Prefetch: "Hangi Program Çalıştırıldı" Sorusunun Cevabı

### Tanım ve Çalışma Mantığı

Prefetch, Windows'un uygulama başlatmayı hızlandırmak için tuttuğu bir önbellek mekanizmasıdır. Bir çalıştırılabilir dosya ilk kez veya sonraki kez çalıştırıldığında, Windows onun açılışta hangi dosyaları/DLL'leri okuduğunu izler ve bu bilgiyi `Windows\Prefetch` dizininde `.pf` uzantılı bir dosyada saklar. Böylece bir sonraki açılışta bu kaynakları önceden yükleyip başlatmayı hızlandırır. Bu tamamen performans amaçlı bir özelliktir; ama adli bilişim için "program çalıştırma kanıtı" (evidence of execution) açısından paha biçilmezdir.

Prefetch dosyasının adı genellikle `PROGRAM.EXE-XXXXXXXX.pf` biçimindedir; sondaki hex değeri, çalıştırılabilir dosyanın tam yoluna dayalı bir hash'tir. Bu ayrıntı önemlidir: **aynı isimli program farklı dizinlerden çalıştırılırsa farklı prefetch dosyaları oluşur.** Yani `C:\Windows\System32\cmd.exe` ile `C:\Temp\cmd.exe` iki ayrı `.pf` üretir; bu, sistem aracının şüpheli bir konumdan çalıştırıldığını yakalamanın harika bir yoludur.

### Neden Bu Kadar Değerli: İçerdiği Bilgiler

Bir prefetch dosyası şunları söyler:
- Programın adı ve (hash aracılığıyla ilişkili) çalıştırıldığı yol.
- **Son çalıştırma zamanları:** Modern Windows sürümleri son sekiz çalıştırma zamanını tutar; bu, tek bir "son çalıştırma" değil, bir çalıştırma **örüntüsü** verir.
- **Çalıştırma sayısı** (run count): programın kaç kez çalıştırıldığı.
- Programın açılışta eriştiği dosya ve dizinlerin listesi. Bu liste, zararlının hangi dosyalara dokunduğunu, hangi DLL'leri yüklediğini gösterir; hatta artık diskte olmayan dosyaların isimlerini bile açığa çıkarabilir.

### Somut Örnek

Diyelim ki `C:\Users\Public\svchost.exe-1A2B3C4D.pf` gibi bir prefetch dosyası buluyorsunuz. `svchost.exe` normalde yalnızca `System32`'den çalışır ve orada prefetch üretmez (bazı sürümlerde sistem hizmetleri için prefetch davranışı farklıdır). Kullanıcı dizininden çalışan bir `svchost.exe` neredeyse kesinlikle bir maskeleme (masquerading) girişimidir. Prefetch dosyası size hem bu dosyanın var olduğunu hem kaç kez ve ne zaman çalıştığını, hem de eriştiği kaynakları verir; oysa çalıştırılabilir dosyanın kendisi çoktan silinmiş olabilir.

### İstismar / Anti-Forensics Mantığı

Saldırganlar prefetch'in ne kadar açık ettiğini bildiği için: (1) prefetch'i tamamen devre dışı bırakmaya çalışabilir (registry ayarıyla), (2) çalıştırma sonrası ilgili `.pf` dosyasını silebilir, (3) uygulamayı diske hiç değmeyecek şekilde tamamen bellekte çalıştırmayı (fileless/in-memory execution) tercih edebilir. Prefetch'in devre dışı olması ya da beklenen dosyaların hiç oluşmamış olması **başlı başına şüphe uyandıran bir bulgudur** — normal bir kullanıcı prefetch'i kapatmaz.

### Savunma / Tespit Mantığı

Prefetch dizinini toplu parse edip bir çalıştırma zaman çizelgesi çıkarmak temel tekniktir. Silinmiş `.pf` dosyaları MFT ve unallocated alanlardan kurtarılabilir. Ayrıca prefetch'in devre dışı bırakılıp bırakılmadığı registry'den kontrol edilir; devre dışıysa bu bir anti-forensics işareti olarak not edilir. Prefetch, tek başına yeterli değildir ama ShimCache, AmCache, UserAssist gibi diğer çalıştırma kanıtlarıyla çaprazlandığında çok güçlü bir tablo oluşturur. Bir kanıt kaynağının temizlenmiş olması, diğerlerinin de kontrol edilmesi gerektiğini hatırlatır.

## Silinmiş Dosya Kurtarma ve File Carving

### Tanım ve Kök Neden

Bir dosyanın silinmesi, çoğu dosya sisteminde içeriğin diskten fiziksel olarak yok edilmesi anlamına gelmez. NTFS'te silme işlemi, MFT kaydını "kullanılabilir" işaretler ve dosyanın kapladığı **cluster**'ları $Bitmap'te boş olarak gösterir. Ama gerçek veri, üzerine yeni bir dosya yazılana kadar diskte **unallocated space** (tahsis edilmemiş alan) içinde olduğu gibi durur. Bu, "silinen" verinin neden kurtarılabildiğinin kök nedenidir: silme bir muhasebe işlemidir, bir yok etme işlemi değil.

Kurtarmanın iki temel yöntemi vardır:

**1. Metadata tabanlı kurtarma:** MFT kaydı hâlâ mevcutsa, dosyanın adını, boyutunu ve hangi cluster'larda yaşadığını (`$DATA` attribute'unun **data run** bilgisi) okuyabiliriz. Bu bilgiyle dosyayı doğrudan, adıyla ve yeriyle kurtarırız. Bu, en yüksek kaliteli kurtarmadır çünkü dosyanın parçalanmış (fragmented) olsa bile hangi parçalardan oluştuğunu biliriz.

**2. File carving (dosya oymacılığı):** MFT kaydı da yok edilmişse, artık dosya sistemi bize yol gösteremez. Bu durumda diski ham byte dizisi olarak tarar ve dosya türlerinin karakteristik imzalarını ararız. Çoğu dosya formatının bilinen bir **magic number** başlığı (örneğin JPEG dosyaları belirli bir byte dizisiyle başlar) ve bazen bir footer'ı vardır. Carving, bu başlık ve bitiş imzaları arasındaki byte'ları toplayarak dosyayı yeniden kurar.

### Somut Örnek ve Sınırlar

Bir çalışan hassas bir sözleşmeyi silip Geri Dönüşüm Kutusu'nu da boşalttı diyelim. MFT kaydı hâlâ duruyorsa, dosya adıyla, orijinal zaman damgalarıyla ve içeriğiyle tam olarak kurtarılabilir. Kayıt üzerine yeni bir dosya yazılmışsa metadata kayıptır ama içerik cluster'ları henüz ezilmemişse carving ile içerik (ama dosya adı olmadan) kurtarılabilir.

Carving'in kök zorluğu **fragmentasyondur.** Carving temelde dosyanın diskte ardışık (contiguous) durduğunu varsayar. Dosya parçalanmışsa (araya başka verinin girdiği durum), naif carving dosyanın ilk parçasını doğru toplar ama devamında yanlış cluster'ları ekleyerek bozuk bir çıktı üretir. Gelişmiş carving araçları format-farkındalıklı doğrulama ile bunu kısmen aşar ama fragmentasyon her zaman kurtarma kalitesinin en büyük düşmanıdır.

### SSD ve TRIM: Modern Bir Zorluk

Burada dürüst olmak gerekir: geleneksel silinmiş dosya kurtarma büyük ölçüde manyetik disk (HDD) mantığına dayanır. SSD'lerde **TRIM** komutu işleri kökten değiştirir. İşletim sistemi bir dosyayı sildiğinde, SSD denetleyicisine "bu cluster'lar artık kullanılmıyor" bilgisini TRIM ile bildirir; denetleyici de bu blokları **arka planda ve geri dönülmez biçimde** sıfırlamaya başlar (garbage collection). Sonuç: TRIM aktif bir SSD'de silinen veri saniyeler ile dakikalar içinde gerçekten yok olabilir. Bu yüzden SSD üzerinde silinmiş dosya kurtarma çoğu zaman başarısızdır ve adli bilişimci bunu baştan kabul etmelidir. TRIM'in davranışı denetleyiciye, işletim sistemi sürümüne ve konfigürasyona göre değişir; bu yüzden "SSD'den kesinlikle kurtarılamaz" veya "kesinlikle kurtarılır" gibi mutlak iddialardan kaçınmak gerekir.

### Savunma / Anti-Forensics Dengesi

Bir tarafta veri kurtarma (soruşturmacının işi), diğer tarafta güvenli silme (gizliliği korumak isteyen veya iz temizleyen tarafın işi) vardır. Gerçek güvenli silme için üzerine yazma (overwriting) veya diski komple şifreleyip anahtarı yok etme (crypto-erase) gerekir; basit "delete" yeterli değildir. Adli bilişimci açısından ders şudur: bir alanın "boş" görünmesi verinin gitmiş olduğu anlamına gelmez; unallocated space, slack space (cluster'ların dosya bittikten sonraki artık kısmı) ve MFT artıkları her zaman incelenmelidir.

## Timeline Analizi: Parçaları Bir Hikâyeye Dönüştürmek

### Tanım ve Neden Gerekli

Yukarıdaki tüm artefaktlar tek tek değerli ama izole hâlde birer veri noktasıdır. Adli bilişimin asıl gücü, bunları **zaman ekseninde birleştirmekten** doğar. Timeline analizi, tüm kaynaklardan (MFT zaman damgaları, registry LastWrite değerleri, prefetch çalıştırma zamanları, event log kayıtları, tarayıcı geçmişi, dosya sistemi olayları) gelen zaman damgalı olayları tek bir kronolojik akışta toplama işlemidir. Amaç, dağınık artefaktlardan bir **olay anlatısı** (narrative) inşa etmektir: "23:14'te bir phishing eki açıldı, 23:14'te prefetch bir PowerShell çalıştırması kaydetti, 23:15'te bir Run anahtarı yazıldı, 23:16'da giden bir ağ bağlantısı loglandı."

### Kök Neden: Neden Süper-Zaman Çizelgesi (Super Timeline)?

Tek bir kaynağa güvenmek yanıltıcıdır çünkü her kaynak manipüle edilebilir veya eksik olabilir. Ama farklı kaynakların zaman damgaları **birbirini doğrular veya çelişir.** Bir dosyanın `$SI` zaman damgası timestomp ile 2009'a çekilmişse bile, o dosyanın 2024'teki prefetch çalıştırma kaydı, AmCache girişi ve MFT'deki `$FN` zaman damgası gerçeği ele verir. Süper-zaman çizelgesi (super timeline), bu çapraz doğrulamayı mümkün kıldığı için timestomping ve iz temizlemeye karşı en dayanıklı tekniktir. Anti-forensics tek bir kaynağı yenebilir; ama on farklı kaynağı tutarlı biçimde yalan söyletmek pratikte imkânsıza yakındır.

### Somut Örnek: Bir İhlalin Yeniden İnşası

Fidye yazılımı (ransomware) soruşturması düşünün. Timeline şöyle bir hikâye ortaya koyabilir: Sabah 09:02'de bir kullanıcının `NTUSER.DAT` içindeki RecentDocs bir makro içeren Office dosyasını açtığını gösterir. 09:02'de prefetch bir script motoru çalıştırmasını kaydeder. 09:03'te bir registry Run anahtarının LastWrite zamanı güncellenir (kalıcılık). 09:05-09:40 arası MFT'de binlerce dosyanın `$SI` değiştirme zaman damgası aynı dakikalara sıkışır ve dosya uzantıları değişir (şifreleme). Her kaynak izole hâlde sadece bir ipucu; ama zaman ekseninde dizildiğinde saldırının başlangıç vektöründen etkisine kadar tam anlatısını verir.

### Yaygın Analiz Tuzağı: Zaman Dilimi ve Saat Kayması

Timeline analizinin en sinsi hatası zaman dilimi (timezone) karışıklığıdır. Farklı artefaktlar zamanı farklı referanslara göre saklar: dosya sistemi zaman damgaları genellikle UTC iken, bazı registry ve log değerleri yerel saate göre veya farklı formatlarda olabilir. Bunları normalize etmeden birleştirirseniz, aslında eşzamanlı olan olaylar saatlerce ayrık görünür ve yanlış sonuç çıkarırsınız. Bu yüzden profesyonel pratik **her şeyi UTC'ye normalize etmektir.** Ayrıca sistemin BIOS saatinin doğru olup olmadığı (clock skew) kontrol edilmelidir; saldırgan sistem saatini değiştirmişse tüm zaman damgaları kayar.

## Yaygın Hatalar

**1. Canlı sistemde çalışmak.** Delili incelemek için orijinal diski mount etmek, tam da korunması gereken zaman damgalarını bozar. Her zaman write-blocker ve imaj kullanılır.

**2. Tek kaynağa güvenmek.** "Prefetch yok, demek ki program çalışmadı" hatalı bir çıkarımdır. Prefetch devre dışı bırakılmış, dosya silinmiş veya program filelessexecute edilmiş olabilir. Bir kaynağın yokluğu, olayın olmadığını değil, başka kaynaklara bakmak gerektiğini gösterir.

**3. Zaman damgalarını sorgusuz kabul etmek.** `$SI` zaman damgaları manipüle edilebilir. Bunları `$FN` ve diğer bağımsız kaynaklarla çaprazlamadan kesin sonuç çıkarmak, timestomping'e düşmek demektir.

**4. Timezone normalize etmemek.** Farklı zaman referanslarını karıştırmak, sahte eşzamanlılıklar veya sahte boşluklar yaratır ve tüm anlatıyı bozar.

**5. Unallocated space ve slack'i atlamak.** Sadece "aktif" dosyalara bakmak, silinmiş delillerin çoğunu gözden kaçırır. Silinmiş dosyalar, MFT artıkları ve slack space adli bilişimin en zengin bölgeleridir.

**6. SSD/TRIM gerçekliğini görmezden gelmek.** HDD sezgileriyle SSD'ye yaklaşmak, kurtarılamayacak veriyi kovalayarak zaman kaybetmeye yol açar. Medya türü baştan tespit edilmelidir.

## En İyi Pratikler

**İmaj-önce, analiz-sonra:** Hiçbir zaman orijinal medyaya dokunmayın. Write-blocker ile imaj alın, hash ile doğrulayın, kopya üzerinde çalışın. Chain of custody'yi belgeleyin.

**Kaynak çeşitliliğini kucaklayın:** Program çalıştırma için tek başına prefetch'e değil; prefetch + ShimCache + AmCache + UserAssist dörtlüsüne bakın. Kaynakların birbirini doğrulaması, hem manipülasyona hem de eksik veriye karşı direnç sağlar.

**Süper-zaman çizelgesi kurun:** Mümkünse tüm zaman damgalı artefaktları tek bir UTC-normalize timeline'da birleştirin. En güçlü anlatı, tek bir aracın çıktısından değil, kaynakların kesişiminden doğar.

**Anti-forensics'i sinyal olarak okuyun:** Prefetch'in kapatılmış olması, event log'ların temizlenmiş olması, yuvarlak sıfırla biten zaman damgaları — bunlar veri kaybı değil, delildir. İz temizlemenin kendisi bir davranış izidir.

**Varsayımlarınızı belgeleyin ve dürüst kalın:** Bir bulgunun ne söylediğini olduğu kadar ne söylemediğini de belirtin. "Prefetch bu programın çalıştığını gösteriyor" doğrudur; "bu kullanıcının bilinçli çalıştırdığını gösteriyor" çoğu zaman fazla iddialıdır — otomatik/uzaktan çalıştırma da mümkündür. Adli bilişimin gücü, kanıtın sınırlarını dürüstçe çizmekten gelir.

**Reprodüksiyonu koruyun:** Attığınız her adım başka bir uzmanca tekrarlanabilir olmalı. Araç sürümlerini, hash'leri ve yöntemleri kaydedin. Tekrar üretilemeyen bir bulgu, mahkemede savunulamaz.

## Sonuç

Disk adli bilişimi, işletim sisteminin performans için ürettiği devasa yan ürün yığınını — MFT kayıtları, registry hive'ları, prefetch önbellekleri, silinen ama yok olmayan dosyalar — sistematik biçimde delile çeviren bir disiplindir. Her artefakt tek başına bir cümle, timeline ise bunların birleştiği hikâyedir. Ustalık, tek bir sihirli araçta değil; kaynakların çeşitliliğini kullanmakta, birbirleriyle çeliştikleri noktalarda gerçeği bulmakta ve her zaman kanıtın sınırlarına dürüstçe saygı göstermektedir.
