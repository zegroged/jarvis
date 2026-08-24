# Komut Geçmişi Temizleme — Tespit

MITRE ATT&CK: T1070.003 (Indicator Removal: Clear Command History) · İlgili: T1552.001 (Credentials in Files)

---

## 1. Özet: saldırı + naif tespit

Bir saldırgan bir kabuğa (shell) düştüğünde arkasında en çok iz bırakan şeylerden biri komut geçmişidir. Linux'ta `~/.bash_history` veya `~/.zsh_history`, Windows'ta ise PSReadLine'ın tuttuğu `ConsoleHost_history.txt` dosyası, o oturumda çalıştırılan komutların düz metin kaydını tutar. Bu, olay müdahalesinde (IR) altın değerinde bir kanıttır: hangi araçların indirildiği, hangi kimlik bilgilerinin komut satırında elle girildiği, hangi lateral movement komutlarının denendiği çoğu zaman burada durur. Dolayısıyla saldırgan işini bitirdikten sonra — bazen de işi bitmeden, her komuttan sonra — bu izleri silmeye ya da hiç yazılmamalarını sağlamaya çalışır.

Klasik hamleler herkesin bildiği kadar basittir. Linux'ta `history -c` ile oturum içi geçmişi boşaltmak, `cat /dev/null > ~/.bash_history` veya `> ~/.bash_history` ile dosyayı sıfırlamak, `unset HISTFILE` / `export HISTFILESIZE=0` ile kaydı tamamen kapatmak, `chattr +i ~/.bash_history` ile dosyayı değişmez yapıp kabuğun yazmasını engellemek, ya da `ln -sf /dev/null ~/.bash_history` ile dosyayı çöpe yönlendirmek. Windows tarafında ise `Remove-Item (Get-PSReadlineOption).HistorySavePath`, `Set-PSReadlineOption -HistorySaveStyle SaveNothing`, veya doğrudan `ConsoleHost_history.txt` dosyasını silmek/okumak.

Naif tespit de bu kadar basittir ve zaten hazır Sigma kuralları vardır. Linux için `Linux Command History Tampering` (fdc88d25) `cat /dev/null >*sh_history`, `chattr +i*sh_history`, `export HISTFILESIZE` gibi anahtar kelimeleri process command line içinde arar. Windows için `PowerShell Console History Logs Deleted` (ff301988) `file_delete` kategorisinde `TargetFilename|endswith: '\PSReadLine\ConsoleHost_history.txt'` der; `Clear PowerShell History - PowerShell Module` (f99276ad) ise ScriptBlock/Module payload'ında `Remove-Item` + `HistorySavePath` ya da `Set-PSReadlineOption ... SaveNothing` kombinasyonlarını yakalar; `Potential PowerShell Console History Access` (f4ff7323) da `ConsoleHost_history.txt` veya `(Get-PSReadLineOption).HistorySavePath` string'ini arar. Kısaca: "şu string command line'da geçerse alarm ver." Çalışır — ama sadece aptal saldırgana karşı.

---

## 2. Naif tespit neden yetmez

İlk ve en büyük problem: **bu kurallar görebildikleri kadar iyidir, göremedikleri şey ise varsayılan olarak çok fazladır.** Linux'ta `history -c`, `unset HISTFILE`, `export HISTFILESIZE=0` bir *shell built-in* veya *değişken atamasıdır* — yeni bir process yaratmaz. Yani `execve` tetiklenmez. Eğer telemetriniz sadece process_creation'a (auditd `execve`, Sysmon for Linux ProcessCreate, EDR process olayları) dayanıyorsa, bu komutları **hiçbir zaman görmezsiniz.** Sigma kuralı `logsource: product: linux` diyor ama hangi kategoride? Kural anahtar kelime bazlı; onu process command line'ına map ederseniz `history -c` asla process olmadığı için düşer. Bunu yakalamak istiyorsanız ya kabuğun kendi denetim mekanizmasına (auditd ile `.bash_history` dosyasına `-w` watch koymak, veya PROMPT_COMMAND/`auditd`+`pam` ile session logging) ya da EDR'ın komut satırı yakalama derinliğine bağımlısınız. Çoğu ortamda bu yoktur.

İkincisi, **string eşleşmesi kırılgandır.** `cat /dev/null > ~/.bash_history` yakalanır ama `: > ~/.bash_history` (iki nokta null komut ve truncate), `truncate -s0 ~/.bash_history`, `cp /dev/null ~/.bash_history`, `dd if=/dev/null of=~/.bash_history`, `sed -i '$d'` (tek satır silme), veya dosyayı Python/Perl ile açıp sıfırlamak — bunların hiçbiri "cat /dev/null" içermez. `chattr +i*sh_history` bekliyor ama saldırgan `chattr +i ~/.zsh_history` yerine dosyayı önce siler sonra `mkdir` ile aynı isimde klasör yapar (kabuk yazamaz), ya da `HISTFILE=/dev/null` ile oturumu başlatır. Keyword listesi ne kadar uzarsa uzasın, kabuğun ifade zenginliği her zaman kazanır.

Üçüncüsü — ve operasyonel olarak en yakıcısı — **Windows tarafında false positive seli.** `ConsoleHost_history.txt` dosyasının okunması (`Get-Content`, `type`, hatta bir yedekleme ajanının dosyayı taraması) tamamen meşru ve son derece sık görülür. PSReadLine geçmişi kullanıcının `%AppData%\Roaming\Microsoft\Windows\PowerShell\PSReadLine\` altındadır; her PowerShell oturumu bu dosyayı okur ve yazar. Bir kullanıcı `Ctrl+R` ile geçmişte arama yaptığında, sekme tamamlaması yaptığında PSReadLine bu dosyayla konuşur. `f4ff7323` kuralı `level: medium` ve dokümantasyonunda açıkça "Legitimate access of the console history file is possible" yazıyor — yani kural yazarı bile bunun gürültülü olduğunu itiraf ediyor. Tek başına bu alarma göre triage yapan bir SOC, ekip kahvesini içemez.

Dördüncüsü, **file_delete telemetrisi yalan söyler.** `ff301988` kuralı `TargetFilename|endswith: '\PSReadLine\ConsoleHost_history.txt'` diyor. Ama Windows'ta PSReadLine geçmiş dosyası normal işleyişte de sürekli yeniden yazılır: PowerShell kapanırken geçici dosyaya yazıp `MoveFileEx` ile üzerine taşır; bazı sürümlerde bu bir delete+create desenidir. Yani "silme" olayı, aslında meşru rotasyonun bir parçası olabilir. Ayrıca dosya silme olayını görmek için Sysmon Event ID 23/26 (FileDelete / FileDeleteDetected) gerekir ve bu varsayılan Sysmon config'de **kapalı** ya da aşırı gürültülü olduğu için çoğu ortamda ya hiç toplanmaz ya da sadece belirli uzantılara kısılmıştır. `.txt` genelde o listede değildir.

Sonuç: naif kural, "bir yerde bu string geçti" der. Kıdemli analistin sorduğu soru bambaşkadır — *bu geçmiş temizleme, daha büyük bir hikâyenin neresinde duruyor?*

---

## 3. Korelasyon zinciri (asıl değer)

Komut geçmişi temizleme **tek başına neredeyse hiçbir zaman ilk sinyal değildir ve olmamalıdır.** Çünkü bir sysadmin de arada `history -c` yapar, bir geliştirici de `.bash_history`'sini temizler. Bu olayın değeri, onu çevreleyen olaylarla birleştiğinde ortaya çıkar. Kıdemli bir detection engineer bunu "düşük entropili tekil sinyal, yüksek entropili zincir" diye düşünür. İşte gerçek dünyada yüksek güvene çeviren desenler:

**Desen A — Post-exploitation temizliği (Linux, sunucu ihlali):**
1. Bir web servisi veya uygulama kullanıcısı (`www-data`, `tomcat`, `hadoop`, `redis`) altında **interaktif kabuk** doğuyor — normalde bu hesaplar shell açmaz. (`www-data` → `/bin/bash` process_creation, parent `nginx`/`java`.)
2. Kısa süre içinde aynı process ağacında **keşif komutları**: `whoami`, `id`, `uname -a`, `crontab -l`, `cat /etc/passwd`.
3. Ardından **indirme**: `curl`/`wget` ile dış IP'den dosya, ya da `chmod +x`.
4. Ve **sonra** `unset HISTFILE` / `> ~/.bash_history` / `chattr +i`.

Bu dördü aynı process soyağacında, birkaç dakika içinde, servis hesabı altında olduğunda — artık "medium keyword match" değil, neredeyse kesin ihlaldir. Cado Security'nin dokümante ettiği Docker/Hadoop/Redis kampanyasının (referanslarda geçen "Spinning YARN") imzası tam olarak budur: servis hesabından interaktif shell + geçmiş manipülasyonu. Tek başına `chattr +i` gürültüdür; bu bağlamda kırmızı alarmdır.

**Desen B — Kimlik hırsızlığı sonrası kapatma (Windows, PowerShell):**
1. Bir kullanıcı/host'ta `(Get-PSReadLineOption).HistorySavePath` **okunuyor** (f4ff7323).
2. Kısa süre sonra aynı oturumda `Set-PSReadlineOption -HistorySaveStyle SaveNothing` (f99276ad) — yani saldırgan geçmişi *önce okuyup credential arıyor, sonra kendi izini kapatıyor.*
3. Bunu çevreleyen: aynı host'ta `net use`, `Invoke-WebRequest`, `-EncodedCommand` ile PowerShell, ya da anormal parent (Office → PowerShell, `w3wp.exe` → PowerShell).
4. Farklı bir hostta, kısa süre sonra aynı kullanıcı hesabıyla oturum (4624 Type 3/10) — lateral movement.

Okuma + sessizleştirme + lateral movement üçlüsü aynı kullanıcı bağlamında zincirlendiğinde, bu credential access → defense evasion → lateral movement geçişidir. Google size "ConsoleHost_history.txt nedir" der; bu zinciri kurmaz.

**Desen C — SYSTEM bağlamında interaktif PowerShell (5b40a734):**
`C:\Windows\System32\config\systemprofile\...\PSReadLine\ConsoleHost_history.txt` dosyasının **oluşması**, SYSTEM hesabının interaktif PowerShell kullandığının parmak izidir. SYSTEM normalde interaktif shell açmaz — bu dosya SYSTEM profilinde belirdiyse, ya bir servis/scheduled task PowerShell'i interaktif çağırıyor (kötü ama bazen meşru) ya da biri PsExec/named pipe ile SYSTEM'e yükselip elle komut çalıştırıyor. Bunu `PsExec` servis kurulumu (7045 System log), anormal named pipe, veya Mimikatz benzeri araç imzalarıyla birleştirdiğinizde yüksek güvenli tespit çıkar. `5b40a734` bunu `level: high` işaretlemiş — haklı olarak, çünkü bu dosyanın o konumda oluşması *tek başına bile* anomalidir.

Zincirleme mantığı şu: geçmiş temizleme bir **defense evasion** aksiyonudur ve evasion tanım gereği *başka bir kötü şeyin üstünü örtmek için* yapılır. O yüzden korelasyon motorunuzu şöyle kurun: "geçmiş manipülasyonu" olayını gördüğünüz an, aynı host + aynı kullanıcı + ±10 dakika penceresinde execution/credential-access/discovery ATT&CK tekniklerini sorgulayın. Yalnız gelen evasion = düşük öncelik; kalabalık gelen evasion = incident.

---

## 4. False positive gerçeği ve triage yargısı

Bu alarmları meşru üretenler gerçek ortamda çoktur ve onları tanımadan triage yapamazsınız:

- **Yedekleme ve DLP/AV yazılımları:** Bir yedek ajanı ya da antivirüs tam disk taraması `ConsoleHost_history.txt` ve `.bash_history` dosyalarını okur. `f4ff7323` bu yüzden meşru okumalarla dolar. Ayırt edici: okuyan process kim? `MsMpEng.exe`, yedek ajanı, indexleme servisi = gürültü. `powershell.exe` interaktif oturumda, anormal parent'la = incele.
- **Konfigürasyon yönetimi (SCCM/MECM, Ansible, Puppet, Chef, Salt):** Bunlar rutin olarak kullanıcı profillerini temizler, geçici dosyaları siler, bazen shell geçmişini de sıfırlar. Ansible bir playbook'ta `lineinfile`/`file: state=absent` ile `.bash_history`'ye dokunabilir. Ayırt edici: kaynak host bir yönetim sunucusu mu, komut bir otomasyon hesabı altında ve *tüm filoda aynı anda* mı çalışıyor? Filo genelinde eşzamanlı = otomasyon, tek host'ta tek seferlik = şüpheli.
- **Vulnerability scanner'lar (Nessus, Qualys) kimlik doğrulamalı tarama:** Uzaktan komut çalıştırıp temizlik yaparlar; command line'da `history` ve dosya işlemleri görünebilir. Ayırt edici: kaynak IP scanner'ın bilinen IP'si mi, tarama penceresiyle örtüşüyor mu?
- **Geliştirici/DevOps davranışı:** İnsanlar geçmişlerine yanlışlıkla parola yazınca `history -d` / `history -c` yaparlar; `HISTCONTROL=ignorespace` kullanırlar; container imajları build sırasında `rm ~/.bash_history` içerir (temiz imaj için standart). CI/CD runner'larında bu çok yaygındır.
- **PSReadLine'ın kendi rotasyonu:** Dosya boyut sınırına gelince kırpılır/yeniden yazılır — file_delete telemetrisinde silme gibi görünebilir.

Kıdemli analistin triage yargısı şu sırayla ilerler. **Önce hesap ve bağlam:** Bu bir servis hesabı mı (`www-data`, `svc_*`), yoksa gerçek bir kullanıcı/otomasyon hesabı mı? Servis hesabından interaktif shell + geçmiş temizleme, çok yüksek önceliktir çünkü servis hesapları shell açmamalıdır. **Sonra parent process ve soyağacı:** `nginx → bash → chattr` doğal değildir; `sshd → bash → history -c` bir sysadmin olabilir. **Sonra eşzamanlılık:** Aynı komut filoda 500 hostta aynı dakikada mı koştu (otomasyon), yoksa tek hostta bir kez mi (insan/saldırgan)? **Sonra komşu olaylar:** ±10 dk içinde discovery/download/credential var mı? **En son string'in kendisi.** Yani kıdemli analist alarmın *tetikleyicisine* değil, alarmın *etrafına* bakar. Çoklu alarm geldiğinde ilk baktığı şey her zaman "en anormal bağlam hangisinde" — servis hesabı, anormal parent, ve komşu execution olayı olan alarm önce açılır; izole keyword eşleşmesi kuyruğun sonuna gider.

Pratik tuning: `f4ff7323` ve benzeri okuma kurallarını, bilinen tarama/yedek/AV process ve hesaplarını *allowlist* ederek düşürün; ama allowlist'i **process adı + imza + üst süreç** üçlüsüyle yapın, sadece process adıyla değil — çünkü saldırgan `MsMpEng.exe` adında bir binary bırakabilir. İmza doğrulaması olmayan bir allowlist, saldırgana davetiyedir.

---

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

Kural dokümanlarının yazmadığı gerçek atlatma yolları ve her birine ikinci-derece tespit:

**Kaçınma 1 — Hiç yazdırmama (silme değil, en baştan kapatma).** Saldırgan oturumun ilk komutu olarak `export HISTFILE=/dev/null` veya `set +o history` yapar; sonrasında hiçbir komut geçmişe girmez, silinecek bir şey de yoktur. Silme kuralları hiç tetiklenmez.
*Karşı-tespit:* `.bash_history`'nin son değişiklik zamanı (mtime) ile kullanıcının son oturum zamanı arasındaki uyumsuzluk. Kullanıcı 2 saat aktif SSH oturumu geçirdiyse ama `.bash_history` mtime'ı hiç güncellenmediyse ya da dosya sıfır boyuttaysa, bu bir anomalidir. Bunu process telemetrisiyle değil, dosya durumu telemetrisiyle (periyodik osquery sorgusu: `SELECT * FROM file WHERE path LIKE '/home/%/.bash_history' AND size = 0`) yakalarsınız. Ayrıca `HISTFILE`/`HISTSIZE` ortam değişkeni atamalarını yakalayabilen bir EDR (komut satırını değil, `execve` env'ini gören) altın değerindedir.

**Kaçınma 2 — Symlink ile çöpe yönlendirme.** `ln -sf /dev/null ~/.bash_history`. Dosya "var" görünür, kabuk yazar, ama `/dev/null`'a gider. Silme yok, truncate yok.
*Karşı-tespit:* `.bash_history`'nin symlink olup olmadığını denetleyin (osquery: `file` tablosunda `type`, ya da `SELECT * FROM file WHERE path='...' AND type='symbolic'`). Bir geçmiş dosyasının symlink olması neredeyse her zaman kötü niyetlidir. Ayrıca `ln -sf ... history` komutunun kendisi bir execve'dir ve yakalanabilir — keyword listenize `ln -s*history` ekleyin.

**Kaçınma 3 — chattr yerine bind mount / namespace.** Gelişmiş saldırgan `mount --bind /dev/null ~/.bash_history` yapar; bu `chattr +i` string'ini içermez ve daha sinsidir.
*Karşı-tespit:* auditd ile `mount` syscall izleme (`-a always,exit -F arch=b64 -S mount`), ve `.bash_history` üzerinde bind mount'un `/proc/mounts`'ta görünmesi — periyodik bütünlük kontrolü.

**Kaçınma 4 — Dosyayı düzenlemek, silmek değil.** `sed -i` ile sadece kendi komutlarını çıkarmak, ya da geçmişi okuyup temizleyip geri yazmak. Toplu silme kuralları tetiklenmez çünkü dosya var, dolu ve "normal" görünüyor.
*Karşı-tespit:* Bu neredeyse process telemetrisinden görünmez. Gerçek savunma: geçmişi **merkeze göndermek.** `.bash_history`'ye güvenmeyin; `auditd` execve loglarını ya da `PROMPT_COMMAND` ile her komutu syslog'a (ve oradan SIEM'e) *anlık* akıtın. Saldırgan lokal dosyayı düzenleyebilir ama zaten SIEM'e gitmiş loga dokunamaz. Detection engineering'in gerçek dersi budur: geçmiş temizlemeye karşı en iyi tespit, geçmişi *saldırganın ulaşamayacağı yere kopyalamaktır* — böylece temizleme aksiyonu tespiti bozmak yerine *kendisi bir sinyale dönüşür.*

**Kaçınma 5 — Windows: PSReadLine'ı bypass eden yürütme.** Saldırgan hiç interaktif PowerShell açmaz; `-EncodedCommand`, `powershell -c`, WMI, ya da .NET runspace / `System.Management.Automation` DLL'ini doğrudan yükleyerek (unmanaged PowerShell, örn. PowerShell without powershell.exe) çalışır. PSReadLine sadece **interaktif konsol** geçmişini tutar; non-interaktif çağrılar `ConsoleHost_history.txt`'ye hiç yazılmaz. Yani silinecek geçmiş baştan yoktur.
*Karşı-tespit:* Burada geçmiş dosyası tamamen yanlış katmandır. **ScriptBlock Logging (Event ID 4104)** ve **Module Logging (4103)** açık olmalı — bunlar PSReadLine'dan bağımsız, PowerShell engine seviyesinde loglar ve `-EncodedCommand`'ı decode edilmiş halde yakalar. `f99276ad` zaten `ps_module` logsource kullanıyor, bu doğru katman. Ayrıca AMSI. Eğer sadece geçmiş dosyasına bakıyorsanız, ciddi saldırganı hiç görmezsiniz.

**Kaçınma 6 — Timestomp ile mtime maskeleme.** Saldırgan `.bash_history`'yi düzenledikten sonra `touch -r` ile mtime'ı eski haline döndürür, böylece Kaçınma 1'in karşı-tespitini (mtime anomalisi) bozar.
*Karşı-tespit:* mtime'a değil, **merkezi loga ve inode/ctime'a** güvenin. `ctime` (change time) `touch` ile kolayca değiştirilemez (yalnızca kök seviyede debugfs vb. ile). ctime ile mtime arasındaki tutarsızlık timestomp göstergesidir.

Buradaki genel ilke: her atlatma, tespiti *bir katman aşağıya* iter. Saldırgan dosyayı silmezse → dosya durumuna bak; dosya durumunu maskelerse → merkezi loga bak; interaktif shell'i atlarsa → engine loglamasına (4104/scriptblock, auditd execve) bak. Detection engineer'ın işi, saldırganı en dibe, *aşamayacağı* katmana (kendi kontrolündeki, sunucudan bağımsız telemetriye) itmektir.

---

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** Yukarıdaki Sigma kurallarının hepsi farklı logsource kullanıyor ve bunları backend'e çevirirken en sık yapılan hata yanlış alana map etmektir. `fdc88d25` (Linux) *keyword* bazlı — Splunk'ta bunu `_raw`'da mı yoksa parse edilmiş `CommandLine`/`process.command_line` alanında mı aradığınız her şeyi değiştirir. auditd `execve` olayları komutu `a0`, `a1`, `a2` argüman alanlarına *parçalar*; `cat /dev/null > ~/.bash_history` tek string değil, ayrı ayrı argümanlardır ve redirection (`>`) kabuk operatörü olduğu için execve argümanında **hiç görünmez** — `>` kabuk tarafından işlenir, `cat`'e argüman olarak geçmez! Bu yüzden `cat /dev/null >*sh_history` keyword'ü ham auditd execve'de asla eşleşmez. Ya kabuk seviyesi loglama (Sysmon for Linux'un birleştirdiği command line, ya da `execve`'yi yeniden birleştiren bir parser) gerekir ya da bu kural sadece EDR'ın normalize ettiği tam command line üzerinde çalışır. Bunu bilmeden kuralı deploy edip "çalışıyor" sanmak, en tehlikeli sessiz başarısızlıktır.

**Varsayılan loglanmayanlar — audit policy ve Sysmon zorunlulukları.** Windows'ta `ff301988` (file_delete) için Sysmon **Event ID 23 (FileDelete)** gerekir ve varsayılan/popüler config'lerde (örn. SwiftOnSecurity) bu ya kapalıdır ya da yalnızca belirli uzantılara (`.exe`, `.dll`, `.ps1`) kısıtlıdır — `.txt` genelde listede değildir. Yani kuralı yazarsınız, hiç tetiklenmez, çünkü telemetri hiç gelmez. `5b40a734` ve `5b40a734`'ün baktığı `file_event` için Sysmon **Event ID 11 (FileCreate)** ve `systemprofile` yolunun config'de kapsanması gerekir. PowerShell tarafında `f99276ad`'nin `ps_module` logsource'u **Module Logging (4103)** demektir ve bu grup politikasıyla (`Turn on Module Logging`, `*` modülleri) açık olmalı; `f4ff7323`/`ConsoleHost_history.txt` erişimini görmek için ise ya ScriptBlock Logging (4104) ya da dosya erişim denetimi (SACL + 4663) gerekir — 4663 çok gürültülüdür ve nadiren açıktır. Kısacası: bu kuralların yarısı, altyapı açılmadan **ölü kuraldır.** Deploy etmeden önce sorulacak soru "kural doğru mu" değil, "bu kuralın beslendiği event gerçekten toplanıyor mu."

**Linux tarafında en kritik gerçek:** `history -c`, `unset HISTFILE`, `export HISTFILESIZE=0` shell built-in olduğu için **hiçbir process telemetrisinde görünmez.** Bunları yakalamanın tek yolu ya `.bash_history` dosyasına auditd watch koymak (`auditctl -w /root/.bash_history -p wa -k histfile_tamper`) — ki bu dosyaya *yazma/değişiklik* denetimi verir, built-in'in kendisini değil — ya da her kullanıcının shell'ini `PROMPT_COMMAND` / `pam_tty_audit` / `auditd` ile session-level komut loglamaya zorlamaktır. Çoğu kurumsal Linux filosunda bunların hiçbiri yoktur; bu yüzden Linux geçmiş temizlemenin büyük kısmı sessizce başarılıdır.

**Splunk vs Sentinel vs Elastic farkları.** Splunk'ta bu kuralları `tstats` ile data model üzerinde (Endpoint.Processes) çalıştırmak hızlıdır ama data model'e CIM uyumlu normalize edilmiş command line gerekir; ham log'da `| search` yaparsanız yavaş ama esnektir (redirection karakterlerini yakalamak için ham log bazen daha iyidir). Sentinel'de `DeviceProcessEvents` (MDE) tablosu command line'ı birleştirilmiş verir — auditd'nin argüman parçalama sorunu MDE'de yoktur, çünkü Defender komutu tek string olarak sunar; ama Sentinel'de KQL `contains` operatörü büyük hacimde pahalıdır, `has` kullanın. Elastic'te ECS `process.command_line` ve `process.args` ayrı alanlardır — `process.args` dizisinde arama yaparsanız redirection'ı yine kaçırırsınız, `process.command_line` (varsa) tam string tutar ama Auditbeat bunu her zaman doldurmaz. Üç platformda da altta yatan aynı gerçek: **command line'ın nasıl toplandığı** (parçalanmış mı, birleşik mi, redirection dahil mi) kuralın çalışıp çalışmayacağını belirler, kuralın mantığı değil.

**Tuning gerçeği.** Bu aile kurallarını canlıya alırken doğru sıra: (1) önce telemetriyi doğrula (event gerçekten geliyor mu — bir test host'ta `chattr +i ~/.bash_history` çalıştırıp SIEM'de aranıyor mu bak), (2) bilinen otomasyonu (SCCM, Ansible, yedek, scanner) hesap + imza + parent üçlüsüyle allowlist et, (3) `f4ff7323` gibi okuma kurallarını tek başına alarm yapma — onları risk-skorlu/korelasyonlu bir kuralın *girdisi* yap (Sentinel'de Fusion/analytics rule, Splunk'ta Risk-Based Alerting notable), (4) silme/kapatma olaylarını her zaman ±10 dk discovery/execution penceresiyle zenginleştir. Tek bir "geçmiş temizlendi" alarmını P1 yapmak, SOC'u yakar; onu bir risk objesine puan ekleyen sinyal yapmak ve eşik aşıldığında incident açmak, hem gürültüyü keser hem gerçek ihlali yakalar. Kıdemli detection engineer'ın buradaki son sözü şudur: **geçmiş temizleme bir sonuç değil, bir işarettir — onu tek başına kovalamak yerine, işaret ettiği asıl olayı çevreleyen telemetriyle avlarsınız.**
