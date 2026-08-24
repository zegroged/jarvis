# Windows Servis/Zamanlanmış Görev İstismarı ve DLL Hijacking/Search Order

## Tanım ve Kapsam

Bu makale, Windows üzerindeki en klasik ve hâlâ en yaygın **yerel yetki yükseltme (local privilege escalation)** ve **kalıcılık (persistence)** vektörlerinden birini sistematik olarak ele alıyor: yüksek yetkiyle çalışan bir bileşenin (bir **service**, bir **scheduled task** veya SYSTEM olarak koşan herhangi bir process), düşük yetkili bir kullanıcının kontrol edebildiği bir dosya yoluna, konfigürasyona veya **DLL arama sırasına (DLL search order)** güvenmesi.

LOLBins/GTFOBins tarzı "meşru ikili dosyayı kötüye kullanma" konuları genel olarak bilinir; ancak **DLL search order hijacking**, **phantom DLL**, **service binary ve config yol izinleri** gibi vektörler ayrı, derin ve sürekli tekrar eden bir alt-alandır. Bunların ortak kök nedeni tektir: bir **güven sınırının (trust boundary)** yanlış çizilmesi. Yüksek yetkili taraf, düşük yetkili tarafın müdahale edebildiği bir girdiye güvenir.

Bu bir kavramsal referanstır; amaç mekanizmayı anlamak ve buna karşı **tespit (detection)** ile **savunma (hardening)** kurmaktır — canlı saldırı talimatı değil.

## Kök Neden: Windows'un Yol Çözümleme ve DLL Yükleme Modeli

Windows'ta bir process başladığında ve çalışırken sürekli olarak iki tür kaynağı "arar": çalıştırılacak ikili dosyalar (executable) ve bağımlı kütüphaneler (**DLL**). Bu aramaların ikisi de belirli bir **sıraya** göre yapılır ve bu sıra, tarihsel geriye dönük uyumluluk uğruna oldukça esnek — dolayısıyla istismara açık — bırakılmıştır.

Bir DLL, tam yolla değil de yalnızca adıyla yüklenmeye çalışıldığında (`LoadLibrary("foo.dll")`), loader belirli dizinleri sırayla tarar. Bu **DLL search order** kabaca şöyledir (Safe DLL Search Mode açıkken, ki modern sistemlerde varsayılan açıktır):

1. Uygulamanın çalıştığı dizin (application directory)
2. Sistem dizini (`System32`)
3. 16-bit sistem dizini
4. Windows dizini
5. Geçerli çalışma dizini (current working directory)
6. `PATH` ortam değişkenindeki dizinler (hem sistem hem kullanıcı)

Safe DLL Search Mode kapalı olsaydı, geçerli çalışma dizini (current working directory) çok daha erken taranır ve saldırı yüzeyi genişlerdi; bu yüzden bu modun açık kalması önemli bir savunma önlemidir.

Buradaki kritik gözlem: DLL adıyla aranıyorsa ve **arama sırasındaki daha erken bir dizine** saldırganın kontrol ettiği bir dosya yerleştirilebiliyorsa, meşru DLL yerine sahte DLL yüklenir. Aynı mantık executable'lar için de `PATH` ve tırnaksız yol çözümlemesinde geçerlidir.

Saldırgan bakış açısından tüm bu vektörler tek bir soruya indirgenir: **"SYSTEM (veya benden yüksek biri) olarak çalışan, ama benim yazabildiğim bir şeye bağımlı olan ne var?"** Aşağıdaki her başlık bu sorunun bir cevabıdır.

## DLL Search Order Hijacking

En temel varyanttır. Bir uygulama, ihtiyaç duyduğu DLL'i tam yol vermeden yüklerse, loader arama sırasını takip eder. Eğer saldırgan, meşru DLL'in bulunduğu `System32` gibi bir dizinden **daha önce taranan** bir konuma (tipik olarak uygulamanın kendi dizinine) aynı adlı bir DLL koyabilirse, sahte DLL yüklenir ve içindeki `DllMain` kodu, host process'in ayrıcalıklarıyla çalışır.

Kritik önkoşul: saldırganın, arama sırasında öncelikli bir dizine **yazma izni** olması. Eğer hedef uygulama `Program Files` altında ve varsayılan ACL'lerle kuruluysa standart kullanıcı oraya yazamaz. Ama üçüncü parti kurulumcular sık sık uygulama dizinini herkese yazılabilir bırakır (yanlış ACL); istismar tam burada doğar.

Sahte DLL genellikle iki işlevi birden görmelidir: hem payload'unu çalıştırmalı, hem de orijinal DLL'in ihracat (export) fonksiyonlarını **proxy** ederek host uygulamanın çökmesini önlemelidir. Aksi halde process, beklediği fonksiyonları bulamayınca hata verir ve dikkat çeker. Bu "proxying/forwarding" tekniği, hijacking'i sessiz kılmanın anahtarıdır.

**Çalışma mantığı özeti:** Yüksek yetkili process adıyla bir DLL arar → arama sırasında saldırganın yazabildiği bir dizin, meşru DLL'in dizininden önce gelir → sahte DLL yüklenir → kod yüksek bağlamda koşar → orijinal export'lar proxy edilerek uygulama normal görünür.

## Phantom DLL Hijacking (Ghost DLL)

Bu, search order hijacking'in özel ve tespiti daha zor bir alt türüdür. Bazı uygulamalar, aslında **hiç var olmayan** bir DLL'i yüklemeye çalışır. Kod, `LoadLibrary` çağrısının başarısız olmasını zaten graceful biçimde ele aldığı için (opsiyonel bir bağımlılık, artık kaldırılmış bir eklenti, eski bir sürümden kalma bir referans) uygulama sorunsuz çalışmaya devam eder — DLL bulunamayınca sessizce ilerler.

Saldırgan burada meşru bir dosyanın üzerine yazmak zorunda bile değildir; sadece **arama yolundaki bir dizine, uygulamanın boşuna aradığı o "hayalet" DLL'i koyar**. Dosya orada olmadığı için hiçbir bütünlük kontrolü tetiklenmez, hiçbir meşru dosya değişmez. Bu, phantom DLL'i özellikle sinsi yapan şeydir: değiştirilen bir sistem dosyası yoktur, yalnızca yeni bir dosya belirir. Dolayısıyla dosya-bütünlüğü izleme (file integrity monitoring) sistemleri "değişmiş dosya" değil, sadece "yeni dosya" görür — bu da genelde daha az alarm üretir.

Phantom DLL adaylarını bulmanın klasik yöntemi, **Process Monitor (Procmon)** ile bir uygulamayı izleyip `CreateFile` operasyonlarında `NAME NOT FOUND` sonucu dönen `.dll` yollarını süzmektir. Bu yollar, uygulamanın var olmayan bir DLL'i, saldırganın yazabileceği bir dizinde aradığı anları tam olarak gösterir. Aynı yöntem, yazılabilir konumlarda aranıp bulunamayan meşru DLL'leri de ortaya çıkarır.

## Servis Binary ve Config Yol İzinleri

Windows servisleri çoğunlukla `LocalSystem` bağlamında en yüksek yetkiyle çalışır. Bu yüzden bir servisin herhangi bir "girdisi" (çalıştırdığı ikili, yüklediği DLL, konfigürasyonu) üzerinde düşük yetkili kontrol, doğrudan SYSTEM'e yükselme demektir. Başlıca alt-vektörler:

### Zayıf İkili Dosya İzinleri (Weak Binary Permissions)

Servisin çalıştırdığı `.exe` dosyasının kendisi veya onun yüklediği bir DLL, standart kullanıcıya **yazma izni** veriyorsa, saldırgan dosyayı doğrudan kendi payload'u ile değiştirir. Servis bir sonraki başlangıçta (veya yeniden başlatmada) bu payload'u SYSTEM olarak çalıştırır. Bu, DLL hijacking'in en dolaysız kuzenidir: search order oyununa bile gerek yok, dosyanın kendisi zaten yazılabilir.

### Zayıf Servis Konfigürasyon İzinleri (Weak Service ACL)

Servisin çalıştırdığı ikilinin dosya izni değil, **servis nesnesinin DACL'ı** kritik olabilir. Bir servisin DACL'ı standart kullanıcıya `SERVICE_CHANGE_CONFIG` hakkı veriyorsa, kullanıcı servisin `binPath` değerini doğrudan istediği bir komuta yönlendirebilir. `SERVICE_START`/`SERVICE_STOP` hakları ise bu değişikliği tetiklemek için tamamlayıcı yetkidir. `SERVICE_ALL_ACCESS` gibi aşırı geniş DACL'ler bu vektörün en tehlikeli hâlidir. Bu tür zayıf servis ACL'lerini denetlemek için klasik araçlar `accesschk` (Sysinternals) ve PowerShell tabanlı denetim modülleridir.

### Unquoted Service Path (Tırnaksız Servis Yolu)

Bir servisin `ImagePath` değeri boşluk içerir ve tırnak içine alınmamışsa, Windows yolu soldan sağa parçalayarak her boşluğa kadar olan kısmı bir çalıştırılabilir aday olarak dener. Örneğin:

```
C:\Program Files\Bir Uygulama\alt klasor\service.exe
```

Tırnaksızsa loader sırayla şunları arar:

```
C:\Program.exe
C:\Program Files\Bir.exe
C:\Program Files\Bir Uygulama\alt.exe
C:\Program Files\Bir Uygulama\alt klasor\service.exe
```

Neden? Çünkü boşluk komut satırında argüman ayırıcıdır; açık tırnak yokluğunda Windows her ara adayı denemek zorundadır. Saldırgan bu ara dizinlerden birine (örneğin `C:\Program Files\Bir Uygulama\` içine `alt.exe`) yazabiliyorsa, sahte ikilisini yerleştirir ve servis SYSTEM olarak onu çalıştırır. `C:\` kök dizinine standart kullanıcı yazamadığı için ilk adaylar genelde işe yaramaz; asıl risk, boşluk içeren **yazılabilir alt dizinlerdedir**.

### Servislerde DLL Hijacking

Servisin yüklediği bir DLL, tam yol verilmeden ve search order'da saldırganın yazabildiği bir dizin öncelikliyken aranıyorsa, servis bağlamında (SYSTEM) DLL hijacking gerçekleşir. Bu, tekil bir kullanıcı uygulamasındaki hijacking'den daha değerlidir çünkü kazanılan bağlam doğrudan en yüksek yetkidir ve servis yeniden başladıkça tekrar tetiklenir — hem yükseltme hem kalıcılık aynı anda.

## Zamanlanmış Görev (Scheduled Task) İstismarı

Scheduled task'lar, bir zamana veya olaya bağlı olarak belirli bir kullanıcı bağlamında (çoğu zaman SYSTEM veya bir yönetici) komut çalıştırır. Servislerle aynı güven-sınırı problemine sahiptirler:

- **Görevin çalıştırdığı ikili/script yazılabilirse:** Görevin `Actions` bölümünde tanımlı `.exe`, `.bat`, `.ps1` veya `.vbs` dosyasına standart kullanıcının yazma izni varsa, dosya payload ile değiştirilir; görev tetiklendiğinde yüksek bağlamda çalışır.
- **Görevin çağırdığı program tırnaksız/PATH'e bağımlıysa:** Aynı unquoted path ve DLL search order mantığı, görev eyleminin çalıştırdığı komut için de geçerlidir.
- **Görev tanımının kendisi (task XML/registry) yazılabilirse:** Scheduled task tanımları hem `C:\Windows\System32\Tasks\` altında XML olarak hem de registry'de tutulur. Bu konumlardaki zayıf ACL, saldırganın görevin `Actions` veya çalışma bağlamını (`RunAs`) değiştirmesine olanak tanır.
- **Yeni görev oluşturma yetkisi:** Bazı ortamlarda standart kullanıcı, yüksek bağlamda çalışacak bir görev tanımlayabilir — bu doğrudan bir kalıcılık ve yükseltme mekanizmasıdır.

Scheduled task ayrıca en yaygın **kalıcılık** yöntemlerinden biridir: saldırgan, kalıcı erişimini bir görevin tetikleyicisine (logon, boot, belli aralık) bağlar ve her tetiklemede payload yeniden çalışır.

## Somut Örnek: Bir Zincirin Anatomisi

Kavramları birleştirelim. Diyelim ki bir üçüncü parti yazılım, `C:\ThirdPartyApp\` dizinine kuruluyor ve kurulumcu bu dizini `Users` grubuna yazılabilir bırakıyor (klasik yanlış ACL). Aynı uygulama, `C:\ThirdPartyApp\service.exe` olarak SYSTEM bağlamında bir servis çalıştırıyor ve bu servis, başlangıçta `helper.dll` adlı bir kütüphaneyi **tam yol vermeden** yüklüyor; `helper.dll` normalde uygulama dizininde bulunuyor.

Savunmacı gözüyle risk zinciri şudur: (1) Uygulama dizini standart kullanıcıya yazılabilir. (2) Servis SYSTEM olarak çalışıyor. (3) DLL adıyla aranıyor ve ilk taranan dizin, yazılabilir olan uygulama dizini. Bu üç koşul aynı anda sağlandığında, o dizine konan sahte `helper.dll` servis yeniden başladığında SYSTEM olarak yüklenir. Buradaki ders, tek bir yanlış ACL'nin yüksek yetkili bir bileşenle birleşince tam sistem ele geçirmeye dönüştüğüdür.

## Tespit (Detection)

**Dosya-sistemi telemetrisi:** DLL hijacking'in en güvenilir işareti, **beklenmedik konumdan yüklenen DLL'lerdir**. Sysmon Event ID 7 (`Image Loaded`) ile, `System32`/`SysWOW64` dışındaki bir dizinden — özellikle kullanıcı-yazılabilir konumlardan (`AppData`, `Temp`, `ProgramData`, uygulama dizinleri) — yüklenen ve imzasız (unsigned) veya imza durumu şüpheli DLL'leri avlayın. "Aynı adlı sistem DLL'inin `System32` dışından yüklenmesi" güçlü bir sinyaldir.

**Yeni dosya oluşumu:** Sysmon Event ID 11 (`FileCreate`) ile, kullanıcı-yazılabilir dizinlerde beliren yeni `.dll` dosyalarını izleyin. Phantom DLL'i yakalamanın en iyi yolu budur, çünkü phantom'da değişen bir dosya yoktur, yalnızca yeni bir dosya belirir.

**Servis ve görev değişiklikleri:** Servis oluşturma/değiştirme (System log Event ID 7045 — yeni servis kurulumu; servis config değişiklikleri) ve scheduled task olayları (Task Scheduler operasyonel log, Security Event ID 4698 — görev oluşturma, 4702 — güncelleme) izlenmelidir. `binPath` değişimi, imzasız bir ikiliye işaret eden yeni servis, ya da alışılmadık bir kullanıcı tarafından oluşturulan SYSTEM görevleri yüksek öncelikli alarmlardır.

**Süreç kökeni (parentage):** `services.exe` veya `svchost.exe` altında beklenmedik bir alt-process (örneğin `cmd.exe`, `powershell.exe`, uygulama dizininden bir ikili) çalışması, servis istismarının klasik izidir. Aynı şekilde `taskeng.exe`/`svchost.exe`'nin Task Scheduler bağlamında şüpheli çocuk üretmesi.

**Periyodik ACL denetimi:** En proaktif tespit, aslında bir **tarama**dır: `Program Files`, servis ikili yolları ve scheduled task dosyaları üzerinde standart kullanıcıya yazma izni veren ACL'leri düzenli olarak araştırın (`accesschk`, PowerUp/WinPEAS tarzı denetim araçları). Zayıf servis DACL'lerini ve tırnaksız yolları listeleyin.

## Savunma (Hardening)

- **Doğru dosya sistemi ACL'leri:** En kritik önlem. `Program Files`, servis ikilileri ve uygulama dizinleri standart kullanıcıya **asla yazılabilir olmamalıdır**. Üçüncü parti kurulumcuların bozduğu ACL'leri kurulum sonrası denetleyin ve düzeltin.
- **DLL'leri tam yolla ve güvenli API'lerle yükleme (geliştirici tarafı):** Uygulamalar DLL'leri mutlak yolla yüklemeli; `LoadLibraryEx`'in güvenli arama bayraklarını (yalnızca `System32`'yi arayan seçenekler gibi) ve `SetDefaultDllDirectories` ile daraltılmış arama dizinlerini kullanmalıdır. `SetDllDirectory` ile current working directory'yi aramadan çıkarmak da etkili bir sertleştirmedir.
- **Safe DLL Search Mode açık kalsın:** Modern Windows'ta varsayılan açıktır; kapatılmadığından emin olun.
- **Tırnaklı servis yolları:** Tüm servis `ImagePath` değerlerini tırnak içine alın. Bu, unquoted path vektörünü tamamen kapatır.
- **En az servis DACL'ı:** Servis nesnelerine standart kullanıcı için `SERVICE_CHANGE_CONFIG`, `WRITE_DAC` veya `SERVICE_ALL_ACCESS` gibi haklar vermeyin. Servisleri mümkün olan en düşük yetkili hesapla (ör. `LocalService`/`NetworkService` veya kısıtlı bir hizmet hesabı) çalıştırın.
- **Scheduled task sertleştirme:** Görevleri gereken en düşük bağlamla çalıştırın; görev dosyaları ve çalıştırdıkları script/ikililer üzerinde ACL'leri sıkın. Standart kullanıcının SYSTEM görevleri oluşturmasını engelleyin.
- **Kod imzalama ve uygulama kontrolü:** WDAC (Windows Defender Application Control) veya AppLocker ile yalnızca imzalı/beyaz listeli DLL ve ikililerin yüklenmesini zorunlu kılmak, imzasız sahte DLL'lerin yüklenmesini büyük ölçüde durdurur — bu, DLL hijacking'e karşı en güçlü mimari savunmalardan biridir.

## Yaygın Hatalar ve Yanlış Anlamalar

- **"Program Files'a yazamam, o zaman güvendeyim" yanılgısı.** Varsayılan ACL güvenlidir, ama üçüncü parti kurulumcular sık sık uygulama dizinini herkese yazılabilir bırakır. Risk teoride değil, pratikteki yanlış yapılandırmadadır. Denetlemeden varsaymayın.
- **Phantom DLL'i görmezden gelmek.** Ekipler dosya-bütünlüğü izlemeye güvenip "hiçbir sistem dosyası değişmedi" diye rahatlar. Phantom DLL hiçbir dosyayı değiştirmez; yalnızca yeni bir dosya ekler. "Değişiklik yok" güvenlik anlamına gelmez.
- **Sadece unquoted path'e odaklanmak.** Unquoted service path meşhur olduğu için ekipler onu düzeltir ama asıl daha yaygın olan zayıf servis DACL'lerini ve yazılabilir ikili dosyaları gözden kaçırır. Tırnak eklemek, dosya yazılabilirse hiçbir işe yaramaz.
- **DLL search order hijacking'i "sadece uygulama sorunu" sanmak.** Aynı mekanizma SYSTEM servislerinde çalıştığında doğrudan yetki yükseltmedir. Bağlam (hangi kullanıcı yüklüyor) her şeydir.
- **Sahte DLL'in uygulamayı çökertmesi.** Saldırgan tarafında bile bu bir "hata"dır: export'lar proxy edilmezse process çöker ve olay görünür hâle gelir. Savunmacı için bu bir avantajdır — çöken/yeniden başlayan servisler bir tespit sinyalidir.
- **Servisi/görevi yeniden başlatma tetiklemesini unutmak.** Payload yerleştirilse bile, servis veya görev tetiklenene kadar çalışmaz. Bu yüzden savunmada, beklenmedik servis yeniden başlatmaları ve manuel görev tetiklemeleri de izlenmeye değer sinyallerdir.

## Özet

Servis istismarı, scheduled task istismarı ve DLL search order/phantom hijacking, yüzeyde farklı görünse de tek bir kök nedene dayanır: **yüksek yetkili bir bileşenin, düşük yetkili birinin kontrol edebildiği bir yola veya konfigürasyona güvenmesi.** Savunma da bu yüzden tek bir ilkeye indirgenir — güven sınırını doğru çizmek: dosya sistemi ACL'lerini sıkı tutmak, DLL'leri tam yolla yüklemek, servisleri en az yetkiyle çalıştırmak, tırnaklı yollar kullanmak ve uygulama kontrolü (WDAC/AppLocker) ile yalnızca güvenilir kodun yüklenmesini zorunlu kılmak. Tespit tarafında ise beklenmedik konumdan yüklenen DLL'ler, kullanıcı-yazılabilir dizinlerde beliren yeni kütüphaneler ve şüpheli servis/görev değişiklikleri en değerli sinyallerdir.
