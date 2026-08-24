# PowerShell: Nesne Pipeline, Remoting, Güvenlik ve Kötüye Kullanım

## Tanım

PowerShell, Microsoft'un geliştirdiği bir komut satırı kabuğu (shell) ve betik dilidir. Ama onu geleneksel Unix kabuklarından (bash, zsh, sh) ayıran temel şey, bir "kabuk" olmasının ötesinde bir **otomasyon platformu** olmasıdır. Klasik kabuklarda her şey metin (text) üzerinden akar; PowerShell'de ise her şey **.NET nesneleri** üzerinden akar. Bu tek cümle, PowerShell'in tüm karakterini belirler: pipeline'ının neden bu kadar güçlü olduğunu, hata ayıklamanın neden daha kolay olduğunu ve güvenlik açısından neden hem çok yetenekli hem de saldırganlar için çok cazip bir hedef olduğunu buradan anlarız.

İki ayrı ürün olduğunu bilmek önemlidir. **Windows PowerShell** (5.1'de dondurulmuş, artık yeni sürüm almıyor) Windows ile birlikte gelir ve .NET Framework üzerine kuruludur. **PowerShell** (eski adıyla PowerShell Core, 6.0 sonrası, `pwsh` komutuyla çağrılır) ise açık kaynaklı, çapraz platform (Windows, Linux, macOS) ve modern .NET üzerine kuruludur. Bu ayrım güvenlik açısından kritiktir, çünkü bazı savunma mekanizmaları iki sürümde farklı davranır.

## Nesne Pipeline: Kök Neden ve Çalışma Mantığı

### Neden nesne, neden metin değil?

Unix felsefesinde pipeline'ın harcı metindir. `ps aux | grep firefox | awk '{print $2}' | xargs kill` gibi bir zincirde her araç metin üretir, bir sonraki araç o metni **yeniden ayrıştırmak (parse etmek)** zorundadır. Bu, `awk '{print $2}'` gibi sütun sayma numaralarına, `grep` ile satır filtrelemeye, boşluk ve sekme karakterlerinin kırılganlığına bağımlıdır. Çıktı formatı bir milimetre değişirse zincir kırılır.

PowerShell'in tasarımcıları (baş mimar Jeffrey Snover, "Monad Manifesto" belgesinde) bu ayrıştırma zorunluluğunu kök sorun olarak gördü. Çözüm şuydu: araçlar birbirlerine metin değil, **yapısal veri**, yani üzerinde özellikleri (property) ve metotları (method) olan canlı .NET nesneleri geçirsin. Böylece bir sonraki komutun metni yeniden ayrıştırmasına gerek kalmaz; nesnenin özelliğine doğrudan ismiyle erişir.

Aynı işi PowerShell'de yazalım:

```powershell
Get-Process firefox | Stop-Process
```

Burada `Get-Process`, string satırları değil `System.Diagnostics.Process` nesneleri üretir. `Stop-Process` bu nesnelerin `Id` özelliğini kendisi okur. Sütun saymak, ikinci alanı ayıklamak yoktur. Zincir, çıktının görsel formatından tamamen bağımsızdır.

### Görüntü ile veri neden ayrıdır?

PowerShell'de kritik bir kavram, bir nesnenin **ne olduğu** ile **nasıl görüntülendiğinin** birbirinden ayrı olmasıdır. Ekranda gördüğünüz tablo, nesnenin kendisi değildir; pipeline'ın en sonunda devreye giren biçimlendirme (formatting) sisteminin ürettiği bir temsildir. Yani `Get-Process`'in ekrandaki çıktısı sadece birkaç sütun gösterir, ama nesnenin arkasında onlarca özellik durur.

Bunu görmek için en değerli komut `Get-Member`'dır:

```powershell
Get-Process firefox | Get-Member
```

Bu, nesnenin gerçekte hangi özelliklere ve metotlara sahip olduğunu listeler. Yeni başlayanların en büyük hatası ekrandaki metne bakıp "bu bilgi burada yok" sanmaktır; oysa bilgi nesnede vardır, sadece varsayılan görünüm onu göstermiyordur. Bu yüzden PowerShell öğrenirken refleks şu olmalıdır: bir nesneyle ne yapabileceğini bilmiyorsan onu `Get-Member`'a boru ile bağla.

### Pipeline'da nesneler nasıl bağlanır: parameter binding

Pipeline'ın en derin mekaniği, bir komutun çıktısının bir sonraki komutun hangi parametresine bağlanacağının nasıl belirlendiğidir. PowerShell iki yöntem kullanır. Birincisi **ByValue**: gelen nesnenin tipi, hedef parametrenin beklediği tiple eşleşiyorsa doğrudan bağlanır. İkincisi **ByPropertyName**: gelen nesnenin bir özelliğinin adı, hedef parametrenin adıyla aynıysa o özelliğin değeri o parametreye bağlanır.

Bu ByPropertyName mekanizması çok güçlüdür ama görünmezdir, bu yüzden şaşırtıcı davranışlara yol açabilir. Örneğin bir CSV'den okuduğunuz nesnelerin sütun başlıkları, bir cmdlet'in parametre adlarıyla çakışırsa, sizin farkında olmadığınız bir eşleşme oluşabilir. Kök neden şudur: pipeline "akıllı" olmaya çalışır ve bu akıllılık, isimlendirme çakışmalarında beklenmedik sonuç verebilir. Bu yüzden karmaşık pipeline'larda bir sorun çıktığında ilk bakılacak yer, nesnenin özellik adlarıyla cmdlet'in parametre adlarının çakışıp çakışmadığıdır.

### Somut bir örnek: filtreleme ve sıralama

```powershell
Get-Service |
    Where-Object { $_.Status -eq 'Running' -and $_.StartType -eq 'Automatic' } |
    Sort-Object -Property DisplayName |
    Select-Object Name, DisplayName, Status
```

Burada `$_` içinde bulunulan nesneyi temsil eder. `Where-Object` metin arayarak değil, nesnenin `Status` ve `StartType` özelliklerine gerçek değerleriyle bakarak filtreler. `-eq 'Running'` karşılaştırması bir string eşleştirmesi gibi görünse de aslında bir enum değeriyle yapılan yapısal bir karşılaştırmadır. Bu, `grep Running` yaklaşımının aksine, "Running" kelimesinin açıklama metninde geçtiği yanlış eşleşmelerden (false positive) etkilenmez.

### Tuzaklar: nesne pipeline'ında yaygın hatalar

**Where-Object'in pahalı olması.** `Get-ChildItem | Where-Object { $_.Name -like '*.log' }` yazmak, tüm nesneleri üretip sonra süzmek demektir. Oysa çoğu cmdlet'in kendi süzme parametresi vardır: `Get-ChildItem -Filter *.log`. Filter, sağlayıcı (provider) katmanında, çoğu zaman dosya sistemi API'sinin kendi seviyesinde çalışır; `Where-Object` ise nesneler PowerShell'e geldikten sonra çalışır. Büyük dizinlerde bu fark ciddi performans farkı yaratır. Kök neden: `-Filter` işi kaynağa yakın yapar, `Where-Object` işi tüketiciye yakın yapar.

**Karşılaştırma operatörlerinin yönü.** `-eq`, bir dizi (array) üzerine uygulandığında eşitliği test etmez; eşleşen elemanları filtreler. `@(1,2,3,2) -eq 2` sonucu `True` değil, `2,2` dizisidir. Bu, `if ($array -eq $value)` yazan kişileri şaşırtır çünkü boş olmayan dizi `$true` sayılır ama beklenen anlam bu değildir.

**Metin refleksinden kurtulamamak.** Unix alışkanlığıyla `Get-Process | Select-String firefox` yazmak, nesneyi metne çevirip sonra metinde arar; bu, nesne pipeline'ının bütün avantajını çöpe atar. Doğrusu özelliğe göre filtrelemektir.

## Remoting: Uzaktan Yönetim Mimarisi

### Temel kavram ve neden var olduğu

PowerShell Remoting, komutları veya tüm oturumları uzak makinelerde çalıştırmayı sağlar. Amaç, yüzlerce sunucuyu tek merkezden, her birine RDP ile tek tek bağlanmadan yönetebilmektir. Kritik nokta şudur: remoting'de de metin değil, **serileştirilmiş nesneler** ağ üzerinden taşınır. Uzak makinede bir cmdlet çalışır, ürettiği nesneler serileştirilip (deserialization için) yerel makinenize gelir ve orada tekrar nesneye dönüşür.

### Çalışma mantığı: WinRM ve WS-Management

Windows'ta remoting'in taşıyıcısı **WinRM** (Windows Remote Management) servisidir; bu servis WS-Management adlı, SOAP tabanlı bir web servis protokolünü uygular. Trafik varsayılan olarak HTTP tabanlı bir kanaldan akar (kurumsal ortamda genellikle 5985 numaralı port HTTP, 5986 HTTPS için kullanılır). "HTTP" kelimesi burada yanıltıcı olmasın: kimlik doğrulama başarılı olduğunda oturum trafiği **şifrelenir**. Domain ortamında Kerberos kimlik doğrulaması kullanıldığında, uygulama katmanı mesajları HTTP taşınsa bile şifreli olur. Yani "5985 açık, demek ki her şey açık metin" çıkarımı yanlıştır; kimlik doğrulama mekanizması şifrelemeyi sağlar.

PowerShell 6+ ile birlikte, çapraz platform çalışabilmek için **SSH tabanlı remoting** de desteklenir. Bu, özellikle Linux tarafında WinRM kurmak istemeyen yöneticiler için önemlidir ve remoting'i standart bir SSH altyapısı üzerinden çalıştırır.

### Somut örnekler

Tek seferlik bir komutu uzakta çalıştırmak:

```powershell
Invoke-Command -ComputerName SRV01, SRV02 -ScriptBlock {
    Get-Service -Name Spooler
}
```

Bu komut iki sunucuda paralel çalışır, her sunucudaki servis nesnelerini toplar ve size döndürür. Dönen nesnelere otomatik olarak `PSComputerName` özelliği eklenir; böylece hangi sonucun hangi makineden geldiğini ayırt edebilirsiniz.

Kalıcı, etkileşimli bir oturum için:

```powershell
$oturum = New-PSSession -ComputerName SRV01
Enter-PSSession -Session $oturum
# Artık komutlar uzak makinede çalışır
Exit-PSSession
```

`New-PSSession` ile oluşturulan kalıcı oturum, birden çok `Invoke-Command` çağrısı arasında durumu (değişkenler, yüklü modüller) korur ve her seferinde yeni bağlantı kurma maliyetinden kaçınır.

### Serileştirme (serialization) tuzağı

Remoting'in en sık yanlış anlaşılan yönü şudur: uzaktan gelen nesneler **canlı nesneler değildir**. Ağdan geçebilmek için serileştirilirler ve yerel tarafta "deserialized" (yeniden canlandırılmış) bir kopya oluşur. Bu kopyaların çoğu zaman **metotları çalışmaz**; yalnızca özellikleri (property değerleri) korunur. Yani uzaktan bir `Process` nesnesi aldıysanız, üzerinde `.Kill()` metodunu çağıramazsınız çünkü o artık gerçek süreci temsil eden canlı bir nesne değil, o anki durumun bir anlık görüntüsüdür.

Kök neden: nesnenin davranışı (metotları) uzak makinenin belleğindeki gerçek kaynağa bağlıdır; o kaynak ağ üzerinden taşınamaz. Bu yüzden doğru desen, **nesneyi yerele getirip metot çağırmak değil**, metodu çağıran kodu uzağa gönderip orada çalıştırmaktır. Yani `.Kill()`'i script block'un içine koyup uzakta çağırın.

### Double-hop (çift atlama) sorunu

Remoting'in en meşhur tuzağı çift atlamadır. A makinesinden B makinesine bağlanıp, B üzerinden C makinesindeki bir kaynağa (örneğin bir dosya paylaşımına) erişmeye çalıştığınızda erişim reddedilir. Kök neden güvenliktir: B makinesi, sizin kimliğinizi C'ye iletmek için gereken kimlik bilgilerini varsayılan olarak elinde tutmaz. Kerberos'un standart delegasyonu, kimlik bilgisinin ikinci bir atlamaya taşınmasını engeller; bu, çalınmış bir oturumun sınırsız yayılmasını önleyen bir savunmadır.

Bunu aşmak için CredSSP, kaynak tabanlı kısıtlı delegasyon (resource-based constrained delegation) gibi mekanizmalar vardır. Ancak CredSSP güvenlik açısından tehlikelidir: kimlik bilgilerinizi ikinci makineye tam olarak devreder, dolayısıyla o makine ele geçirilmişse kimliğiniz de ele geçmiş olur. Bu yüzden double-hop'u çözerken tercih, mümkünse kısıtlı delegasyon gibi daha dar kapsamlı yöntemlerdir; CredSSP en son çare olmalıdır.

## Güvenlik: Katmanlar ve Kök Mantık

### Execution Policy: bir güvenlik sınırı değildir

En çok yanlış anlaşılan özellik budur. `Set-ExecutionPolicy`, betiklerin çalıştırılmasını kısıtlıyor gibi görünür (`Restricted`, `RemoteSigned`, `AllSigned`, `Unrestricted` gibi ayarları vardır). Ama Microsoft bunun bir güvenlik sınırı **olmadığını** açıkça belirtir. Amacı, kullanıcının yanlışlıkla bir betiği çift tıklayıp çalıştırmasını önlemektir; kötü niyetli birini durdurmak değildir.

Kök neden neden bir sınır olmadığıdır: execution policy yalnızca `.ps1` dosyalarının doğrudan çalıştırılmasını denetler. Ama saldırgan betiği bir dosyaya yazmak zorunda değildir. Komutu `-Command` parametresiyle geçebilir, betik içeriğini bir string'e alıp `Invoke-Expression` ile çalıştırabilir, base64 ile kodlanmış komutu `-EncodedCommand` ile verebilir, ya da `powershell.exe -ExecutionPolicy Bypass` diyerek politikayı doğrudan geçersiz kılabilir. Hepsi meşru, belgelenmiş özelliklerdir. Dolayısıyla execution policy'yi bir savunma katmanı sanmak tehlikeli bir yanılgıdır; o sadece kaza önleyici bir çittir.

### Gerçek güvenlik katmanları

PowerShell'in ciddi savunması başka yerlerdedir:

**Constrained Language Mode (kısıtlı dil kipi).** Bu kip, PowerShell'in tam .NET erişimini kısar. Normalde PowerShell içinden herhangi bir .NET tipini çağırabilir, Win32 API'lerine erişebilirsiniz; bu muazzam bir güçtür ama saldırgan için de öyle. Kısıtlı dil kipi, bu doğrudan tip erişimini engeller, yalnızca güvenli sayılan çekirdek cmdlet'lere izin verir. AppLocker veya Windows Defender Application Control (WDAC) ile birlikte uygulandığında, güvenilmeyen betikler otomatik olarak bu kısıtlı kipe düşer. Bu, betik tabanlı saldırıların cephaneliğini gerçekten daraltan bir mekanizmadır.

**Script Block Logging.** Bu özellik, çalıştırılan her script block'un tam içeriğini olay günlüğüne (event log) yazar. Kritik değeri şudur: saldırgan komutu ne kadar gizlerse gizlesin (base64, string birleştirme, karakter kaydırma), PowerShell o komutu **çalıştırmak için önce çözmek zorundadır**, ve çözülmüş hali loglanır. Yani gizleme (obfuscation) motorun kendi loglamasını atlatamaz. Bu, savunmacıların en değerli görünürlük kaynaklarından biridir.

**AMSI (Antimalware Scan Interface).** AMSI, PowerShell ile antivirüs/EDR ürünleri arasında bir köprüdür. PowerShell, çalıştırmadan hemen önce script içeriğini AMSI'ye gönderir; kayıtlı tarayıcı onu inceler ve zararlı bulursa çalıştırma engellenir. Buradaki dahiyane fikir tarama noktasının **yürütme anında** olmasıdır: komut ne kadar diskte gizlenmiş olursa olsun, çalışmak için bellekte açık hale gelmek zorundadır, ve AMSI tam o noktada bakar. Bu yüzden basit dosya tabanlı gizleme AMSI'yi yenemez.

**Transcription.** `Start-Transcript` veya grup ilkesiyle etkinleştirilen bu özellik, oturumdaki tüm girdi ve çıktıyı bir metin dosyasına kaydeder; adli inceleme için değerlidir.

### JEA (Just Enough Administration)

JEA, en az ayrıcalık (least privilege) ilkesini remoting'e taşır. Fikir şudur: bir yöneticiye sunucunun tamamı üzerinde tam yetki vermek yerine, ona yalnızca yapması gereken belirli işleri yapabileceği kısıtlı bir remoting uç noktası (endpoint) tanımlarsınız. Örneğin yardım masası personeli yalnızca belirli servisleri yeniden başlatabilir ama başka hiçbir komut çalıştıramaz. JEA, sanal hesaplar (virtual account) kullanarak bu işlemleri gerçekleştirir, böylece personelin gerçek yönetici kimlik bilgilerini bilmesi bile gerekmez. Bu, ele geçirme durumunda saldırının yayılabileceği yüzeyi (attack surface) dramatik biçimde daraltır.

## Kötüye Kullanım: Neden Saldırganlar PowerShell'i Sever

### "Living off the land" mantığı

PowerShell, saldırganların "living off the land" (arazide yaşama) dediği yaklaşımın en güçlü aracıdır. Bu terim, saldırganın sisteme kendi zararlı ikili dosyasını (binary) getirmek yerine, sistemde **zaten var olan meşru araçları** kötü amaçla kullanmasını anlatır. PowerShell bunun için idealdir çünkü:

- Her Windows makinesinde varsayılan olarak kuruludur; getirmeye gerek yoktur.
- İmzalı, güvenilir bir Microsoft ikilisi tarafından çalıştırılır; basit "beyaz liste" savunmalarını atlar.
- Doğrudan .NET ve Win32 API'lerine erişebildiği için neredeyse her şeyi yapabilir.
- **Dosyasız (fileless)** çalışabilir: kod tamamen bellekte durabilir, diske hiç yazılmayabilir, dolayısıyla dosya tarayan klasik antivirüs onu göremez.

Kök neden şudur: PowerShell'i saldırgan için güçlü kılan tam da onu yönetici için güçlü kılan şeydir. Sistemin derinliklerine erişebilen bir otomasyon motoru, ele geçirildiğinde aynı derinliği saldırgana açar.

### Tipik kötüye kullanım desenleri

**Bellekte indir ve çalıştır.** Klasik bir tek satırlık saldırı, uzaktaki bir script'i indirip diske hiç yazmadan doğrudan belleğe alıp çalıştırma desenidir; kavramsal olarak "web'den içerik çek, sonra o içeriği ifade olarak yürüt" şeklindedir. Diske dokunmadığı için imza tabanlı dosya taramasını atlar. AMSI'nin var olma sebebi büyük ölçüde tam olarak bu tekniktir.

**Gizleme (obfuscation).** Saldırganlar komutlarını okunamaz hale getirir: base64 kodlama, string ters çevirme ve birleştirme, değişken adlarını rastgeleleştirme, biçim dizisi (format string) hileleri. Amaç hem insan analistin hem de örüntü (pattern) tabanlı imzaların komutu tanımasını zorlaştırmaktır. Ancak yukarıda anlatılan sebeple, gizleme motorun kendi çalışma anı loglamasını (script block logging) ve AMSI taramasını yenemez, çünkü kod eninde sonunda çözülmek zorundadır.

**Kimlik bilgisi hasadı ve yanal hareket (lateral movement).** PowerShell, bellekteki kimlik bilgilerini toplamak, remoting ve WMI/CIM üzerinden başka makinelere sıçramak için kullanılır. Meşru remoting yetenekleri, saldırganın ağ içinde yatay olarak yayılması için hazır bir altyapı sunar.

**Kalıcılık (persistence).** Zamanlanmış görevler, WMI olay abonelikleri ve profil betikleri aracılığıyla saldırgan, makine yeniden başlasa bile kodunun tekrar çalışmasını sağlar.

### Savunmacının bakışı: neden loglama her şeyin merkezinde

Buradan çıkan en önemli savunma dersi şudur: PowerShell'i yasaklamak çoğu ortamda mümkün değildir, çünkü yönetim için gereklidir. O halde strateji **görünürlüktür**. Script block logging, module logging, transcription ve AMSI birlikte çalıştığında, saldırganın gizlemeye çalıştığı her komut çalışma anında açığa çıkar ve kaydedilir. Bir saldırgan bu logları kapatmayı deneyebilir, ama logların kapatılması girişiminin kendisi de bir logdur ve güçlü bir uyarı sinyalidir.

İkinci ders sürüm yönetimidir. Eski PowerShell v2, modern güvenlik özelliklerinin (AMSI, gelişmiş loglama) çoğundan yoksundur. Saldırganlar bilinçli olarak `powershell -Version 2` diyerek daha eski, daha az izlenen motora **geri düşmeye (downgrade)** çalışır. Bu yüzden sağlam bir savunmanın ilk adımlarından biri, sistemde PowerShell v2 motorunu tamamen kaldırmaktır.

## En İyi Pratikler

**Yazarken netlik.** Takma adlardan (alias) betiklerde kaçının. `gps`, `?`, `%` interaktif kullanımda pratiktir ama betikte `Get-Process`, `Where-Object`, `ForEach-Object` yazmak okunabilirliği ve bakımı ciddi biçimde artırır. Betik başka birinin (ya da altı ay sonraki kendinizin) okuyacağı bir belgedir.

**Nesneyle çalışın, metinle değil.** Bir cmdlet'in çıktısını `Out-String` ile metne çevirip sonra o metni işlemek neredeyse her zaman bir hatadır. Nesnenin özelliklerine erişin. Ne olduğunu bilmiyorsanız `Get-Member` kullanın. Bu tek alışkanlık, PowerShell'i doğru kullanmakla yanlış kullanmak arasındaki çizgidir.

**Filtreyi sola alın.** Mümkünse cmdlet'in kendi `-Filter`, `-Include`, `-Name` gibi kaynağa yakın süzme parametrelerini kullanın; `Where-Object`'i ancak kaynak tarafında süzme imkânı yoksa devreye sokun. Bu hem performans hem netlik kazandırır.

**Hataları ciddiye alın.** `$ErrorActionPreference` ve `-ErrorAction Stop` ile hataların sessizce yutulmasını engelleyin. `try/catch` bloklarını gerçekten fırlatan (terminating) hatalar için kullanın; unutmayın ki birçok cmdlet varsayılan olarak "non-terminating" hata üretir ve `catch` bunları yakalamaz, bu yüzden `-ErrorAction Stop` gerekir.

**Güvenlikte katman düşünün.** Execution policy'ye güvenlik sınırı olarak asla güvenmeyin. Gerçek savunma için Constrained Language Mode, AppLocker/WDAC, script block logging, AMSI ve JEA'yı birlikte devreye alın. En az ayrıcalık ilkesini uygulayın: kimseye ihtiyacından fazla yetki vermeyin.

**Remoting'de HTTPS ve dar delegasyon.** Duyarlı ortamlarda remoting'i HTTPS üzerinden yapılandırın. Double-hop gerektiğinde CredSSP yerine kaynak tabanlı kısıtlı delegasyonu tercih edin. Kalıcı oturumları (`New-PSSession`) işiniz bitince `Remove-PSSession` ile kapatın.

**Kimlik bilgilerini koda gömmeyin.** Parolaları betik içinde düz metin yazmayın. `Get-Credential`, güvenli dize (SecureString) ve mümkünse yönetilen kimlik/kasa (vault) çözümlerini kullanın. Bir betikte açık parola görmek, bir güvenlik denetiminde ilk işaretlenecek şeydir.

**Sürümü modernleştirin, eskiyi kaldırın.** PowerShell v2 motorunu sistemden kaldırın. Yeni geliştirmelerde çapraz platform ve modern özellikler için `pwsh` (PowerShell 7+) tarafına yönelin, ancak Windows'a özgü bazı modüllerin uyumluluğunu her zaman doğrulayın.

## Sonuç

PowerShell'in tüm karakteri tek bir tasarım kararından türer: pipeline'da metin değil nesne akar. Bu karar, onu geleneksel kabuklardan çok daha güçlü ve güvenilir bir otomasyon aracı yapar; ayrıştırma kırılganlığını ortadan kaldırır, uzaktan yönetimi yapısal veriyle mümkün kılar. Ama aynı güç, ele geçirildiğinde saldırgana sistemin derinliklerini açar. Bu yüzden PowerShell'i anlamak, hem onun nesne modelini içselleştirmeyi hem de execution policy gibi görünürdeki savunmaların neden yeterli olmadığını, gerçek savunmanın (AMSI, kısıtlı dil kipi, script block logging, JEA) neden yürütme anına ve görünürlüğe dayandığını kavramayı gerektirir. Güçlü araç, güçlü sorumluluk ister.
