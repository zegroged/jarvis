# Web Shell — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Web shell, bir web sunucusunun içine yerleşen ve saldırgana o sunucu üzerinde uzaktan komut çalıştırma imkânı veren, çoğu zaman tek bir dosyaya sığan bir arka kapıdır. Onu tespit edebilmek için önce ne olduğunu, sunucunun kimliğine büründüğünde nasıl davrandığını ve arkasında hangi izleri bıraktığını anlamamız gerekir. Bu metin savunma ve tespit odaklıdır; amaç, canlı bir saldırı reçetesi vermek değil, mavi takımın web shell'i logların içinde nasıl yakalayacağını göstermektir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Web shell'in temel fikri son derece basittir ve tam da bu basitlik onu tehlikeli kılar: Saldırgan, web sunucusunun servis ettiği bir dizine, sunucunun yorumlayıcısı (PHP, ASP/ASPX, JSP, Perl vb.) tarafından çalıştırılabilen küçük bir dosya bırakır. Bu dosya, dışarıdan gelen bir HTTP isteğindeki parametreyi alıp altındaki işletim sistemine bir komut olarak iletir. Böylece saldırgan, tarayıcısından veya bir `curl` isteğinden gönderdiği metni, sunucu üzerinde çalışan bir işleme dönüştürür.

**Neyi istismar eder?** Web shell tek başına bir zafiyet değildir; bir zafiyetin *sonucudur*. Saldırgan dosyayı sunucuya koyabilmek için önce bir giriş yolu bulur:

- **Dosya yükleme zafiyetleri** — profil fotoğrafı, belge, eklenti yükleyen bir formun uzantı/tip denetiminin zayıf olması (`.php` dosyasının `.jpg` gibi sızması).
- **Uzaktan/yerel dosya dahil etme (RFI/LFI)** ve **komut enjeksiyonu** ile diske dosya yazdırma.
- **Yama uygulanmamış uygulama/eklenti zafiyetleri** (CMS eklentileri, uygulama sunucuları, edge cihazları). Web shell, bu tür zafiyetlerin sömürülmesinden sonra kalıcılık (persistence) sağlamak için bırakılır.
- **Zayıf kimlik bilgileri** ile ele geçirilen yönetim panelleri üzerinden şablon/tema düzenleme.

**Saldırgan kavramsal olarak ne yapar?** Dosyayı yerleştirdikten sonra, ona bir HTTP isteğiyle "seslenir". İstek gövdesindeki ya da parametredeki komut, web sunucusu sürecinin altında, yani web sunucusunun çalıştığı kullanıcı kimliğiyle (Linux'ta tipik olarak `www-data`, `apache`, `nginx`; Windows'ta `IIS APPPOOL\...` veya `NETWORK SERVICE`) yürütülür. Buradan itibaren saldırganın hedefi genellikle şudur: keşif (whoami, ağ yapılandırması), yatay hareket için kimlik bilgisi toplama, yetki yükseltme ve kalıcılık. Web shell, sunucuya her geri dönüşünde yeniden sömürü yapmasını gerektirmeyen sessiz bir kapı olduğu için MITRE ATT&CK'te **T1505.003 (Server Software Component: Web Shell)** altında, persistence taktiği içinde sınıflandırılır.

Web shell'lerin bir spektrumu vardır. Bir uçta, tek satırlık son derece küçük "one-liner" shell'ler bulunur — sadece gelen bir parametreyi yorumlayıcıya (`eval`, `system`, `passthru`, `Runtime.exec`, `child_process`) verirler; küçük oldukları için imza tabanlı taramadan kaçmaları kolaydır. Diğer uçta ise China Chopper, WSO, c99, b374k, Weevely gibi tam teşekküllü, dosya yöneticisi/veritabanı istemcisi/proxy içeren "framework" shell'ler yer alır. Savunmacı açısından kritik nokta şudur: shell'in *kendisi* ne kadar gizlenirse gizlensin, **çalıştığı anda** web sunucusu sürecinin bir alt süreç (child process) doğurması gibi davranışsal bir iz bırakır. İşte tespitin sağlam ayağı burasıdır.

Bir başka önemli kavramsal nokta, web shell'in "iletişim modeli"dir. Klasik shell'ler komutu URL parametresinde (GET) taşır; bu, erişim log'larında görünür ve nispeten kolay yakalanır. Daha gelişmiş shell'ler komutu HTTP **POST** gövdesine, hatta çerezlere (Cookie) veya özel HTTP başlıklarına gömer — çünkü sunucu erişim log'ları tipik olarak yalnızca URI ve query string'i kaydeder, POST gövdesini kaydetmez. China Chopper'ın meşhur olmasının bir sebebi, komutu POST gövdesinde taşıyan ve istemci tarafında çok küçük ama işlevsel olan yapısıdır. Bu yüzden yalnızca erişim log'una bakan bir tespit, en tehlikeli shell'leri kaçırabilir; savunmacının süreç ve dosya katmanına inmesi bu nedenle şarttır.

---

## 2. Bıraktığı izler / artefaktlar

Web shell birden fazla katmanda iz bırakır. İyi bir tespit stratejisi bu katmanların en az ikisini kesiştirir.

### 2.1 Süreç (process) izleri — en güvenilir katman

Bir web sunucusu süreci normalde işletim sistemi kabuğu (shell) çocukları doğurmaz. Web shell komut çalıştırdığında ise tam olarak bu olur:

- **Linux'ta:** `httpd`, `apache2`, `nginx`, `lighttpd`, `caddy`, `node` gibi bir ebeveyn sürecin altında birden `/bin/sh`, `/bin/bash`, `whoami`, `id`, `uname`, `curl`, `wget`, `nc`, `python`, `perl` gibi çocuk süreçlerin belirmesi. Uygulama sunucularında ebeveyn komut satırında `/bin/java` ile birlikte `tomcat` veya `websphere` geçmesi ve bunların kabuk çocuğu doğurması.
- **Windows/IIS'te:** `w3wp.exe` (IIS worker process) ya da `httpd.exe`'nin altında `cmd.exe`, `powershell.exe`, `whoami.exe`, `net.exe`, `nltest.exe` gibi süreçlerin doğması. Bu, Sysmon **Event ID 1 (Process Creation)** veya Windows Security **Event ID 4688 (A new process has been created)** ile `ParentImage` / `Creator Process Name` alanında `w3wp.exe` görülerek yakalanır.
- Linux tarafında `auditd`, `execve`/`execveat` sistem çağrılarını web sunucusu kullanıcı kimliğine (örneğin `euid=33`, yani `www-data`) göre etiketleyerek bu çocuk süreçleri log'lar.

### 2.2 Dosya sistemi izleri

- Web kök dizininde (`/var/www/html`, `wwwroot`, `htdocs`) **yeni oluşmuş** ya da beklenmedik zamanda değişmiş yorumlanabilir dosyalar (`.php`, `.asp`, `.aspx`, `.jsp`, `.jspx`, `.phtml`).
- Yükleme/upload dizinlerinde çalıştırılabilir uzantılı dosyalar — normalde orada yalnızca resim/PDF olması gerekirken.
- Dosya içinde `eval(`, `assert(`, `base64_decode(`, `gzinflate(`, `system(`, `shell_exec(`, `passthru(`, `Runtime.getRuntime().exec`, `Request.Item[...]` gibi tehlikeli fonksiyon+kullanıcı girdisi kombinasyonları; ağır obfuscation (uzun base64 blokları, `chr()` zincirleri, `\x` hex dizileri).
- Dosya sahibinin web sunucusu kullanıcısı olması ve dosyanın son değişiklik zamanının (mtime) bir sömürü penceresine denk gelmesi.

### 2.3 Antivirüs / EDR izleri

- Sunucu üzerindeki AV veya ClamAV'ın web shell imzası vermesi çok kuvvetli bir sinyaldir. ClamAV log'larında `Webshell*FOUND`, `Trojan*FOUND`, `VirTool*FOUND` gibi mesajlar geçer. AV bu dosyayı bloklamış olsa bile **görmezden gelinmemelidir**: dosyanın oraya *nasıl* geldiği araştırılmalıdır, çünkü tespit edilen shell muhtemelen daha geniş bir ihlalin ucudur.

### 2.4 Ağ / proxy / web sunucusu erişim log izleri

- Erişim log'larında (`access.log`, IIS log) aynı, çoğu zaman "olağandışı" bir dosyaya (`/uploads/x.php`, `/images/logo.php`) yönelik tekrarlayan **POST** istekleri; bazen sürekli aynı istemci IP'sinden, bazen sabit bir URI'ye.
- Anormal veya bilinen kötücül **User-Agent** dizeleri (araç/RAT imzaları). Proxy log'larında zararlıların kullandığı şüpheli User-Agent'lar tespit edilebilir.
- İç ağdan dışarıya doğru beklenmedik `curl`/`wget` çıkışları (araç indirme), veri sızdırma trafiği.

### 2.5 İz katmanlarının bir sömürü zaman çizgisinde sıralanışı

Bir olay incelemesinde (DFIR) bu izler genellikle şu sırayla belirir ve savunmacı bunları geriye doğru örer:

1. **Dosyanın diske yazılması** — FIM alarmı veya web kök dizinindeki yeni `.php`/`.aspx` dosyanın mtime'ı, sömürünün gerçekleştiği anı işaret eder. Bu, "kök neden" için en değerli zaman damgasıdır.
2. **Dosyaya ilk HTTP erişimi** — erişim log'unda o dosyaya gelen ilk istek (çoğu zaman POST). Kaynak IP, saldırganın altyapısına dair ilk ipucudur.
3. **Komut yürütme** — süreç oluşturma / `auditd` `execve` olayları; web sunucusu kullanıcısının doğurduğu `whoami`, `id`, `net` gibi keşif komutları.
4. **İkincil aktivite** — araç indirme (`curl`/`wget` çıkışı), kimlik bilgisi erişimi, yatay hareket, kalıcılık mekanizmaları.

Bu zaman çizgisini kurmak, tek bir alarmı "olay" bağlamına oturtur ve web shell'in yalnızca bir semptom olduğunu, asıl hastalığın onu oraya koyan zafiyet olduğunu gösterir.

Bu beş katmanın önem sırası pratikte şöyledir: **süreç izleri > AV imzası > dosya bütünlüğü > erişim log deseni.** Süreç izleri en az yanlış pozitif üreten ve obfuscation'dan en az etkilenen katmandır. Ancak tek bir katman asla yeterli değildir; olgun bir tespit programı bunları korelasyon kuralları ile birbirine bağlar (örneğin "FIM'de yeni PHP dosyası" + "aynı dosyaya POST" + "web sunucusundan kabuk çocuğu" birbirini 10 dakika içinde takip ederse kritik alarm).

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki tespit mantığı, tekniğe ait gerçek Sigma kurallarına dayanır. Her birinin hangi log kaynağına (`logsource`), hangi alana (`field`) ve hangi koşula baktığını Türkçe açıklıyorum.

### 3.1 Linux — Web sunucusu sürecinin şüpheli çocukları

**Dayandığı kural:** `Linux Webshell Indicators` (id: 818f7b24-0fba-4c49-a073-8b755573b9c7), `logsource: product: linux, category: process_creation`.

Bu kuralın mantığı temiz ve güçlüdür. İki koşulu birbirine bağlar:

1. **Ebeveyn seçimi (`selection_general`):** `ParentImage` alanı şu değerlerden biriyle **bitiyor** mu? `/httpd`, `/lighttpd`, `/nginx`, `/apache2`, `/node`, `/caddy`. Ayrıca uygulama sunucuları için `ParentCommandLine` içinde hem `/bin/java` hem `tomcat` (ya da `websphere`) birlikte geçiyor mu?
2. **Şüpheli çocuk süreç (`sub_processes`):** Bu ebeveynin altında bir kabuk ya da keşif aracı (`whoami`, `id`, `/bin/sh`, `nc` vb.) doğuyor mu?

Alarm koşulu: `selection_general (veya tomcat/websphere) AND sub_processes`. Yani "bir web sunucusu, olmaması gereken bir kabuk çocuğu doğurdu." Bu, web shell'in çalıştığı anı davranışsal olarak yakalar; shell dosyası ne kadar obfuscate edilirse edilsin komut çalıştırmak için bir alt süreç doğurmak zorundadır.

Basit Sigma-benzeri örnek:

```yaml
title: Web Sunucusu Surecinin Supheli Kabuk Cocugu
logsource:
    product: linux
    category: process_creation
detection:
    parent_web:
        ParentImage|endswith:
            - '/httpd'
            - '/apache2'
            - '/nginx'
            - '/node'
    suspicious_child:
        Image|endswith:
            - '/sh'
            - '/bash'
            - '/whoami'
            - '/id'
            - '/wget'
            - '/curl'
    condition: parent_web and suspicious_child
level: high
```

### 3.2 Linux — auditd ile web sunucusu kimliğinin komut çalıştırması

**Dayandığı kural:** `Webshell Remote Command Execution` (id: c0d3734d-330f-4a03-aae2-65dacc6a8222), `logsource: product: linux, service: auditd`.

Bu kural bir katman daha aşağıya, sistem çağrısı seviyesine iner. Ön koşul olarak `auditd`'nin web sunucusu kullanıcı kimliğine göre yapılandırılmış olmasını ister. Kural tanımındaki örnek `auditd` kuralları `execve`/`execveat` çağrılarını `euid=33` (varsayılan `www-data:x:33:33`) filtresiyle `detect_execve_www` anahtarına etiketler. Kendi ortamınızda web sunucusu kullanıcınızın UID'si farklıysa `33` yerine onu yazmanız gerekir.

Sigma tarafında `detection` mantığı: `type: 'SYSCALL'` ve `SYSCALL` alanı `execve` ya da `execveat` olan olayları seçer. Mantık şudur: web sunucusu kullanıcısı (normalde interaktif kabuk çalıştırmaması gereken bir servis hesabı) bir program çalıştırdığında, bu bir web shell komut yürütmesinin güçlü işaretidir. 3.1'deki `process_creation` yaklaşımından farkı, burada denetimin doğrudan çekirdek sistem çağrısı ve kullanıcı kimliği üzerinden yapılmasıdır — bu, Image adına güvenmek zorunda kalmadan "kim çalıştırdı" sorusuna cevap verir.

### 3.3 Antivirüs / ClamAV imzası

**Dayandığı kurallar:** `Antivirus - Web Shell Detection Signature` (id: fdf135a2-9241-4f96-a114-bb404948f736) ve `Relevant ClamAV Message` (id: 36aa86ca-fd9d-4456-814e-d3b1b8e1e0bb, `logsource: product: linux, service: clamav`).

ClamAV kuralının mantığı doğrudan anahtar kelime eşlemesidir: log mesajında `Webshell*FOUND`, `Trojan*FOUND`, `VirTool*FOUND`, `Rootkit*FOUND` ya da `Htran*FOUND` kalıplarından biri geçiyorsa alarm üretir (`condition: keywords`, `level: high`). AV kuralı ise sunucudaki antivirüsün ürettiği web shell alarmını yakalar. Nextron'ın notu önemlidir: bu kuralı kendi AV çözümünüzün ürettiği spesifik dizelere göre ayarlamanız (tune etmeniz), örneğin GitHub'daki büyük web shell depolarını indirip AV'nizin ne yakaladığını görmeniz önerilir. Ve tekrar: AV bloklamış olsa bile olay kapatılmaz, kök neden araştırılır.

### 3.4 Proxy log'unda kötücül User-Agent

**Dayandığı kural:** `Malware User Agent` (id: 5c84856b-55a5-45f1-826f-13f37250cf4e), `logsource: category: proxy`.

Bu kural doğrudan web shell'i değil, çoğu zaman ona *eşlik eden* trafiği yakalar. Web shell istemcileri (özellikle otomatik araçlar) bazen sabit, olağandışı User-Agent dizeleri kullanır; benzer şekilde shell aracılığıyla indirilen RAT/araçlar da bilinen kötücül User-Agent'larla dışarı bağlanır. Kural, proxy log'undaki `c-useragent` alanını bilinen zararlı imzalarla karşılaştırır. Web shell tespitinde bunu destekleyici bir sinyal olarak kullanırız: erişim log'undaki şüpheli POST deseni + proxy'deki tanıdık kötücül User-Agent, ikisi bir araya geldiğinde güven seviyesini yükseltir. Tek başına User-Agent tespiti kolayca atlatılabilir (saldırgan meşru bir tarayıcı User-Agent'ı taklit eder), bu yüzden asla tek dayanak yapılmaz.

### 3.5 Windows/IIS için aynı mantığın izdüşümü

Yukarıdaki gerçek Sigma kuralları Linux odaklıdır, ancak davranışsal mantık platformdan bağımsızdır. Windows'ta 3.1'in karşılığı, Sysmon **Event ID 1** ya da Security **Event ID 4688** üzerinden `ParentImage`/`Parent Process Name` alanının `w3wp.exe` (IIS worker) veya `httpd.exe` olduğu ve çocuğun `cmd.exe`/`powershell.exe`/`whoami.exe`/`net.exe` olduğu durumdur. Field ve event adlarını Windows'a taşırken mantığı aynen koruruz: "web sunucusu süreci bir komut yorumlayıcısı doğurdu."

Özetle tespit felsefesi: **davranışa (süreç ağacı, sistem çağrısı) demir at, imzayı (AV, dosya deseni) destekleyici sinyal olarak kullan.** Davranışsal kurallar obfuscation'a dayanıklıdır; imza kuralları hızlı ve düşük gürültülüdür ama atlatılabilir.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan bu tespiti nasıl atlatmaya çalışır?

**İmza tabanlı tespite karşı (dosya taraması / AV):**
- **Obfuscation ve encoding:** `base64_decode`, `gzinflate`, `str_rot13`, `chr()` zincirleri, değişkene atanmış fonksiyon adları (`$f='sys'.'tem'; $f(...)`) ile imzalardan kaçınma. Bu yüzden AV imzası tek başına yeterli değildir.
- **Minimalizm:** Tek satırlık, jenerik görünümlü shell'ler kullanmak; yakalanacak belirgin bir dize bırakmamak.
- **Meşru dosyaya sızma:** Var olan yasal bir `.php`/`.aspx` dosyasının içine birkaç satır kötücül kod gizleyerek "yeni dosya" tespitinden kaçmak.

**Davranışsal tespite karşı (süreç ağacı):**
- **Kabuk doğurmamak:** Komutu OS'a hiç indirmeden, doğrudan yorumlayıcı içi fonksiyonlarla (PHP'de dosya işlemleri, veritabanı erişimi, in-memory işlem) çalışmak. Bu, `process_creation` kurallarını sessizleştirir — ama saldırganın yapabildiklerini de kısıtlar; keşif/yatay hareket genelde er ya da geç bir alt süreç gerektirir.
- **"Living off the land":** Sunucuda zaten var olan meşru binary'leri kullanmak; yeni araç indirmemek ki ağ ve dosya izi azalsın.

**Savunmacının karşı hamlesi:**
- Katmanları kesiştir: davranışsal (`process_creation`/`auditd`) + imza (AV/ClamAV) + dosya bütünlüğü izleme (FIM) + web erişim log analizi. Tek bir katmanı atlatmak kolay, üçünü birden atlatmak zordur.
- **File Integrity Monitoring (FIM):** Web kök ve upload dizinlerini izle; yorumlanabilir uzantılı yeni/değişen dosyalarda alarm ver. Kabuk doğurmayan shell bile diske yazıldığı an yakalanır.
- **En az yetki:** Upload dizinlerini `noexec` yapmak/web sunucusundan yorumlanmalarını engellemek (örn. yükleme klasöründe PHP çalıştırmayı kapatmak) hem önlemedir hem de anomaliyi belirginleştirir.
- **Baseline çıkar:** Her web sunucusunun normalde hangi çocuk süreçleri doğurduğunu (varsa) öğren; sapmaları öne çıkar.

### 4.2 Tipik false positive kaynakları ve nasıl ayıklanır

Davranışsal web shell kuralları güçlüdür ama meşru bir web sunucusu da bazen alt süreç doğurabilir. Başlıca yanlış pozitif kaynakları:

- **Uygulamanın meşru sistem çağrıları:** Bir web uygulaması, görüntü işleme (ImageMagick/`convert`), PDF üretimi, `git` çağrısı, zamanlanmış bakım scriptleri gibi işler için bilinçli olarak alt süreç doğurabilir. Bunlar `process_creation` kuralında görünür.
  - *Ayıklama:* Bu bilinen, beklenen `Image`/`CommandLine` değerlerini allowlist'e al. Kritik ayrım: web shell'in doğurduğu çocuklar tipik olarak *keşif* araçlarıdır (`whoami`, `id`, `net`, `nltest`), meşru uygulamanınkiler ise *iş fonksiyonu* araçlarıdır. Argümanlara ve doğuran ebeveynin bağlamına bakarak ayrış.
- **CI/CD, deploy ve yönetim ajanları:** Deploy sırasında web dizinine dosya yazılması ve script çalışması FIM ve `process_creation` alarmlarını tetikleyebilir.
  - *Ayıklama:* Bakım pencerelerini ve deploy hesaplarını bağlama kat; değişiklik yönetimi kayıtlarıyla eşleştir.
- **AV imzasının kendi tarama/güncelleme mesajları:** ClamAV log'unda `FOUND` içermeyen bilgi mesajları ya da test dosyaları (EICAR) yanıltabilir. Kural zaten `*FOUND` kalıbına bağlı olduğu için bu risk düşüktür; yine de test dosyalarını ayırt et.
- **Güvenlik tarayıcıları ve pentest aktivitesi:** Yetkili tarama araçları erişim log'larında web shell benzeri POST desenleri ve şüpheli User-Agent'lar üretebilir.
  - *Ayıklama:* Bilinen tarayıcı IP'lerini ve zamanlanmış tarama pencerelerini bağlama al; `Malware User Agent` kuralının verdiği proxy alarmlarını, kaynağı bilinen tarayıcıysa filtrele.
- **`www-data` altında meşru cron/bakım:** `auditd` kuralı web sunucusu kullanıcısının her `execve`'sine bakar; bu kullanıcı adına çalışan meşru bakım işleri gürültü üretebilir.
  - *Ayıklama:* Bu meşru komutları anahtar ve komut satırına göre allowlist'e al; artakalan her şeyi incele.

Genel prensip: web shell davranışsal alarmları **yüksek öncelikli ama bağlam gerektiren** alarmlardır. Doğru yaklaşım, ebeveyn süreç + çocuk süreç + kullanıcı kimliği + argümanlar + zaman + değişiklik yönetimi kaydını birlikte değerlendirmektir. Tek bir alarmı otomatik kapatmak yerine, "bu web sunucusu neden şu anda bir kabuk doğurdu?" sorusunu her seferinde sormak, hem gerçek web shell'i yakalar hem de gürültüyü sürdürülebilir seviyede tutar.

---

**Kapanış notu:** Web shell'in en zayıf noktası, sonuçta bir iş yapması gerektiğidir. Dosyayı gizleyebilir, imzadan kaçabilir, ama komutu çalıştırmak için ya bir alt süreç doğurur, ya diske yazılır, ya da AV'nin gözüne çarpar. Savunma, bu kaçınılmaz izlerden en az ikisini aynı anda gözleyerek kurulur. İmzaya değil davranışa demirlenmiş, bağlamla zenginleştirilmiş bir tespit hattı, en gizli web shell'i bile er ya da geç ışığa çıkarır.
