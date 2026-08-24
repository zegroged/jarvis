# SQL Injection Sonrası Veritabanı-Spesifik Sızma Teknikleri

## Giriş: Neden Ayrı Bir Konu?

Genel `SQL Injection` (SQLi) anlatımları çoğunlukla `' OR 1=1--` gibi kimlik doğrulama atlatma veya `UNION SELECT` ile veri çekme aşamasında durur. Ancak bir saldırganın SQLi ile ulaşabileceği asıl derinlik, veritabanı motorunun (`DBMS`) kendine özgü fonksiyonlarında saklıdır. `MSSQL`, `PostgreSQL`, `Oracle` ve `MySQL`; standart `SQL`'in çok ötesinde, işletim sistemi ile etkileşime giren, dosya sistemine erişen ve komut çalıştırabilen genişletilmiş yetenekler sunar.

Bu makale, bir SQLi açığının nasıl `data breach`'ten `Remote Code Execution` (RCE) veya tam sunucu ele geçirmeye (`full compromise`) dönüştüğünü DBMS mercekleriyle inceler. Amaç saldırı reçetesi vermek değil; **mekanizmayı anlamak**, böylece bu tekniklerin **tespit** (`detection`) ve **savunma** (`hardening`) yüzeyini doğru kurabilmektir. Bir sistemi savunmak için, saldırganın hangi kapıları zorladığını bilmek zorunludur.

## Temel Kavram: Sızma Aşamasının Ön Koşulu

DBMS-spesifik ileri teknikler kendiliğinden ortaya çıkmaz. İki şeye bağlıdırlar:

1. **Enjeksiyon noktası ile veritabanı yetkileri (`privileges`).** SQLi'nin çalıştığı bağlantının (`connection`) hangi kullanıcı olarak açıldığı belirleyicidir. Uygulama veritabanına `sa`, `postgres`, `SYS`/`SYSTEM` veya `root` gibi yüksek yetkili bir hesapla bağlanıyorsa, ileri teknikler kapıda hazır bekler. En yaygın ve en kritik güvenlik hatası tam olarak budur: uygulamanın **en düşük yetkili** (`least privilege`) bir hesap yerine yönetici hesabıyla bağlanması.

2. **Enjeksiyonun türü.** Klasik (`in-band`/`UNION`-based) enjeksiyonda çıktıyı doğrudan görürsünüz. Ancak birçok gerçek dünya açığı **Blind** veya **Out-of-band (OOB)** kategorisindedir; buralarda motor-spesifik fonksiyonlar sadece istismar için değil, veriyi *kaçırmak* için de kullanılır.

Bu iki eksen (yetki ve enjeksiyon kanalı) tüm bölümün arka planını oluşturur.

## Blind ve Out-of-band SQL Injection

### Blind SQLi: Çıktısız Sorgulama

`Blind SQLi`'de sorgu sonucu HTTP yanıtında görünmez. Saldırgan, veritabanının davranışını bir *yan kanal* (`side channel`) üzerinden çıkarır. İki temel varyant:

- **Boolean-based:** Enjekte edilen koşulun `TRUE`/`FALSE` oluşuna göre sayfa içeriği değişir (örneğin "Kullanıcı bulundu" / "bulunamadı"). Saldırgan `AND SUBSTRING(password,1,1)='a'` gibi koşullarla veriyi karakter karakter, ikili arama (`binary search`) ile tahmin eder.

- **Time-based:** Yanıt içeriği hiç değişmese bile, koşul doğruysa motor bekletilir. Buradaki fonksiyonlar tamamen DBMS'e özgüdür:
  - `MSSQL`: `WAITFOR DELAY '0:0:5'`
  - `MySQL`: `SLEEP(5)` veya `BENCHMARK(...)`
  - `PostgreSQL`: `pg_sleep(5)`
  - `Oracle`: `DBMS_LOCK.SLEEP(5)` (yetki gerektirir) veya yoğun bir sorguyla suni gecikme.

Gecikmeyi gören saldırgan, "koşul doğruydu" bilgisini kazanır. Bu, DBMS tespitinin (`fingerprinting`) de temelidir: hangi `sleep` sözdizimi çalışıyorsa motor odur.

### Out-of-band SQLi: Veriyi Dışarı Sızdırma

Ne içerik ne zamanlama kanalı güvenilir olduğunda, saldırgan veritabanını **kendi kontrolündeki bir sunucuya ağ isteği** yaptırmaya zorlar. Veri, o isteğin içine (örneğin bir DNS alt alan adı olarak) gömülür. `DNS exfiltration` özellikle güçlüdür çünkü DNS trafiği neredeyse her yerde dışarı çıkabilir ve çoğu güvenlik duvarı onu engellemez.

Kavramsal olarak, motorlar dış kaynağa erişim için şu tür yeteneklere sahiptir:

- `MSSQL`: `xp_dirtree` veya `xp_fileexist` gibi prosedürler bir `UNC` yoluna (`\\attacker.com\...`) erişmeye çalışarak DNS/SMB isteği tetikler.
- `Oracle`: `UTL_HTTP`, `UTL_INADDR` (DNS çözümlemesi), `DBMS_LDAP` gibi ağ paketleri dışarı istek yapabilir. Modern sürümlerde bunlar `ACL` (`Access Control List`) ile kısıtlanmıştır.
- `PostgreSQL` / `MySQL`: doğrudan OOB desteği motor çekirdeğinde sınırlıdır; genellikle dosya/uzantı ya da eklenti mekanizmaları üzerinden dolaylı yollar aranır.

**Savunma açısından kritik ders:** OOB, çıktısı görünmeyen "sessiz" enjeksiyonları bile sömürülebilir kılar. Bu yüzden veritabanı sunucusunun **giden (`egress`) ağ trafiği** sıkı denetlenmelidir. Bir veritabanı sunucusunun rastgele internet adreslerine DNS/HTTP isteği yapmak için hiçbir meşru gerekçesi yoktur.

## MSSQL: `xp_cmdshell` ve Genişletilmiş Prosedürler

### Mekanizma

`Microsoft SQL Server`'ın en bilinen sızma vektörü `xp_cmdshell` adlı genişletilmiş saklı prosedürdür (`extended stored procedure`). Bu prosedür, verilen bir dizeyi doğrudan işletim sistemi komut kabuğunda (`cmd.exe`) çalıştırır ve çıktısını satır satır döndürür. Yani SQLi ile bu prosedüre erişebilen saldırgan, veritabanı hizmetinin (`service account`) yetkileriyle **işletim sistemi komutu** çalıştırabilir — bu, tam anlamıyla RCE'dir.

Modern SQL Server sürümlerinde `xp_cmdshell` **varsayılan olarak devre dışıdır**. Etkinleştirmek için `sp_configure` üzerinden `advanced options` ve ardından `xp_cmdshell` ayarının açılması gerekir. Yeterli yetkiye (`sysadmin`) sahip bir enjeksiyon, bu ayarı çalışma anında açabilir. İşte bu yüzden "kapalı olması" tek başına yeterli savunma değildir; asıl mesele **enjeksiyonun `sysadmin` yetkisiyle çalışmamasıdır**.

### Diğer MSSQL Vektörleri

- **`OLE Automation` prosedürleri** (`sp_OACreate`, `sp_OAMethod`): `COM` nesneleri oluşturarak dosya yazma veya komut çalıştırma benzeri yeteneklere dolaylı erişim.
- **`CLR` integration:** `.NET` derlemelerini (`assembly`) veritabanına yükleyip çalıştırma. Yanlış yapılandırıldığında güçlü bir RCE yüzeyi açar.
- **Linked servers:** Başka veritabanı sunucularına köprü; yanal hareket (`lateral movement`) için kullanılır.

### Tespit ve Savunma

- `xp_cmdshell` ve `OLE Automation` **kapalı** tutulmalı; açılma girişimi (`sp_configure` çağrısı) bir alarm olarak izlenmelidir.
- Uygulama, `sysadmin` olmayan, yalnızca gerekli tablolara erişimi olan bir `login` ile bağlanmalıdır.
- SQL Server hizmetini `LocalSystem` yerine düşük yetkili bir servis hesabıyla çalıştırmak, RCE'nin etkisini sınırlar.
- Sorgu denetimi (`SQL Server Audit`) ile hassas prosedür çağrıları loglanmalıdır.

## PostgreSQL: `COPY ... PROGRAM`, `lo_import` ve Uzantılar

### `COPY ... FROM PROGRAM`

`PostgreSQL`'de `COPY` normalde tablo ile dosya arasında veri taşır. Ancak `COPY ... FROM PROGRAM 'komut'` sözdizimi, bir işletim sistemi komutunu çalıştırıp çıktısını tabloya aktarır. Bu, süper kullanıcı (`superuser`) veya `pg_execute_server_program` gibi özel bir role sahip bağlantıda **doğrudan RCE** anlamına gelir. Komut, PostgreSQL sunucu sürecinin işletim sistemi kullanıcısı (`postgres`) yetkileriyle çalışır.

Bu yeteneğin kök nedeni tasarımdır: `COPY PROGRAM`, veritabanı yöneticisinin toplu veri işlemleri için meşru bir aracıdır. Sorun, bu ayrıcalığın uygulamanın bağlandığı hesaba sızmasıdır.

### `lo_import` / `lo_export` ve `pg_read_file`

- **Large Object fonksiyonları** (`lo_import`, `lo_export`): sunucu dosya sistemindeki dosyaları veritabanına okuma veya veritabanından dosyaya yazma. Yetkili bir bağlamda, bir web dizinine dosya yazarak (`web shell`) dolaylı RCE'ye zemin hazırlayabilir.
- **`pg_read_file` / `pg_read_binary_file`:** sunucu dosya sisteminden okuma; yapılandırma dosyaları, gizli anahtarlar gibi hassas içeriğin sızdırılması.

### Uzantılar ve UDF

Saldırgan yeterli yetkiye sahipse, kötü amaçlı bir paylaşımlı kütüphaneyi (`shared library`) yükleyip `CREATE FUNCTION` ile bir `User Defined Function` (UDF) tanımlayarak kod çalıştırabilir. Bu, motorun eklenebilirlik (`extensibility`) modelinin kötüye kullanımıdır.

### Tespit ve Savunma

- Uygulama hesabı **kesinlikle** `superuser` olmamalı ve `pg_execute_server_program`, `pg_read_server_files`, `pg_write_server_files` gibi güçlü rollere sahip olmamalıdır.
- `COPY ... PROGRAM`, `lo_import`/`lo_export`, `CREATE FUNCTION` gibi ifadelerin uygulama trafiğinde görülmesi neredeyse her zaman bir saldırı göstergesidir; bunlar loglanıp uyarı üretmelidir.
- PostgreSQL sürecini kısıtlı bir OS kullanıcısı ve mümkünse konteyner/`namespace` izolasyonu içinde çalıştırmak yatay etkiyi azaltır.

## Oracle: PL/SQL Injection ve Ağ Paketleri

### Farklı Bir Model

`Oracle`, çoklu ifade (`stacked queries`) yürütmeyi klasik JDBC/OCI arayüzünde genellikle desteklemez; bu yüzden "`; DROP TABLE`" tarzı zincirleme Oracle'da çoğu zaman doğrudan çalışmaz. Buna karşılık Oracle'ın asıl zenginliği **`PL/SQL`** — sunucu tarafı prosedürel dilidir. Sızma teknikleri bu dilin ve yerleşik paketlerin (`built-in packages`) çevresinde döner.

### `PL/SQL` Injection ve Definer's Rights

Oracle'da saklı prosedürler varsayılan olarak **tanımlayanın yetkisiyle** (`definer's rights`, `AUTHID DEFINER`) çalışır. Dinamik SQL kullanan (`EXECUTE IMMEDIATE`) ve girdisini güvensiz biçimde birleştiren bir prosedür varsa, düşük yetkili bir kullanıcı buraya enjeksiyon yaparak prosedürün sahibinin (çoğunlukla `SYS`) yetkileriyle kod çalıştırabilir. Bu, **privilege escalation** için Oracle'a özgü klasik bir kalıptır. Yerleşik paketlerdeki bu tür açıklar tarihsel olarak birçok yamayla kapatılmıştır — bu yüzden **güncel `Critical Patch Update` (CPU) yamaları** Oracle'da savunmanın belkemiğidir.

### Ağ ve Dosya Paketleri

- **`UTL_HTTP`, `UTL_TCP`, `UTL_INADDR`:** dışarıya HTTP/TCP isteği ve DNS çözümlemesi — OOB exfiltration ve SSRF benzeri davranış.
- **`UTL_FILE`:** sunucu dosya sistemine okuma/yazma (yapılandırılmış `directory` nesneleriyle sınırlı).
- **`DBMS_SCHEDULER` / eski `DBMS_JOB`:** zamanlanmış iş olarak OS komutu çalıştırma potansiyeli — yapılandırmaya bağlı olarak RCE yüzeyi.
- **Java stored procedures:** Oracle içindeki JVM üzerinden OS etkileşimi.

Modern Oracle'da ağ paketleri **`ACL`** ile kısıtlanır: bir kullanıcının `UTL_HTTP` ile hangi hedeflere erişebileceği açıkça yetkilendirilmelidir. ACL'lerin gevşek yapılandırılması yaygın bir zafiyettir.

### Tespit ve Savunma

- **Yama yönetimi** Oracle'da diğer motorlardan daha kritiktir; yerleşik paket açıkları CPU'larla kapatılır.
- `PUBLIC` rolünden gereksiz paket `EXECUTE` yetkileri (`UTL_HTTP`, `DBMS_SCHEDULER` vb.) geri alınmalıdır (`REVOKE`).
- Ağ ACL'leri en dar biçimde tanımlanmalıdır.
- Uygulama şemasının gereksiz sistem yetkileri olmamalı; `definer's rights` prosedürler denetlenmelidir.

## MySQL: `FILE` Yetkisi ile Dosya Okuma/Yazma

### Mekanizma

`MySQL`/`MariaDB`'de OS komut çalıştırma, diğer motorlar kadar doğrudan değildir; asıl vektör **dosya sistemi erişimidir** ve merkezinde `FILE` yetkisi vardır.

- **`LOAD_FILE('/yol/dosya')`:** `FILE` yetkisine sahip bir kullanıcı, sunucudaki bir dosyanın içeriğini okuyabilir. `UNION SELECT LOAD_FILE('/etc/passwd')` klasik örnektir. Yapılandırma dosyaları, uygulama kaynak kodu veya anahtarlar bu yolla sızdırılabilir.

- **`INTO OUTFILE` / `INTO DUMPFILE`:** sorgu sonucunu sunucu dosya sistemine **yazma**. Saldırgan bir web kök dizinine (`document root`) `.php` gibi çalıştırılabilir bir dosya yazabilirse (`web shell`), sonraki HTTP isteğiyle bu dosya çalışır ve RCE elde edilir. Bu, "veri yazma"nın "kod çalıştırma"ya dönüştüğü noktadır.

### Sınırlayıcı Faktörler

MySQL'de bu yeteneği kısıtlayan üç önemli mekanizma vardır:

1. **`FILE` yetkisi:** varsayılan uygulama kullanıcısında bulunmamalıdır; bulunması ciddi bir yanlış yapılandırmadır.
2. **`secure_file_priv` değişkeni:** `LOAD_FILE` ve `OUTFILE`'ın hangi dizinle sınırlı olduğunu belirler. Boş bırakılırsa sınırsız; belirli bir dizine ayarlanırsa sadece orası; `NULL` yapılırsa dosya işlemleri tamamen kapatılır. **`NULL` en güvenli değerdir.**
3. **OS dosya izinleri:** MySQL süreci hedef dosyayı okuyabilmeli/yazabilmelidir. `OUTFILE` mevcut dosyanın üzerine yazamaz; bu da web shell yerleştirmeyi kısıtlar.

UDF tabanlı komut çalıştırma da mümkündür ancak `plugin` dizinine yazma ve yükleme yetkisi gerektirdiğinden pratikte çok daha zordur ve kolay engellenir.

### Tespit ve Savunma

- Uygulama kullanıcısından `FILE` yetkisini kaldırın; `GRANT`'leri düzenli denetleyin.
- `secure_file_priv`'i `NULL` veya en azından uygulama dizinlerinden ve web kökünden uzak dar bir yola ayarlayın.
- Web kök dizinine veritabanı sürecinin **yazma izni olmamalıdır**; bu tek başına birçok web shell senaryosunu bloke eder.
- `LOAD_FILE`, `INTO OUTFILE`, `INTO DUMPFILE` ifadeleri uygulama trafiğinde alarm konusu olmalıdır.

## Motorlar Arası Ortak Örüntü ve Doğru Savunma

Farklı motorlar farklı fonksiyonlar sunsa da sızma zinciri hep aynı iskelete oturur:

**SQLi noktası → yüksek yetkili bağlantı → motor-spesifik güçlü fonksiyon → dosya erişimi veya komut çalıştırma → kalıcılık / yanal hareket.**

Bu zincirin her halkası ayrı bir savunma katmanıdır (`defense in depth`):

1. **Enjeksiyonu kökten önle.** Tek gerçek çözüm **parametreli sorgular** (`prepared statements` / `parameterized queries`) ve girdinin veriden ayrı taşınmasıdır. String birleştirme ile SQL kurmak tüm bu tekniklerin kapısını açar. `stored procedure` kullanmak bile içeride dinamik SQL varsa korumaz.

2. **En düşük yetki (`least privilege`).** Uygulama hesabı asla `sa`/`root`/`superuser`/`SYS` olmamalı; `FILE`, `xp_cmdshell`, `COPY PROGRAM`, tehlikeli paket `EXECUTE` gibi yetkilerden arındırılmalıdır. Bu ilke, enjeksiyon gerçekleşse bile ileri tekniklerin çoğunu etkisiz kılar. **Tek en yüksek getirili savunma budur.**

3. **Yüzey daraltma (`hardening`).** Tehlikeli özellikleri kapatın: `xp_cmdshell`, `OLE Automation`, gereksiz ağ paketleri, `secure_file_priv=NULL`. Kapalı ama açılabilir olmak yetmez; yetkiyle birlikte düşünün.

4. **Egress kontrolü.** OOB tekniklerinin can damarı giden ağ trafiğidir. Veritabanı sunucusu keyfi DNS/HTTP çıkışı yapamamalıdır.

5. **Yama.** Özellikle Oracle'da yerleşik paket açıkları ve `definer's rights` istismarı yamalarla kapanır; güncel kalmak zorunludur.

6. **Tespit / izleme.** Uygulamadan asla gelmemesi gereken ifadeler (`xp_cmdshell`, `COPY PROGRAM`, `LOAD_FILE`, `UTL_HTTP`, `sp_configure`) birer yüksek-güven `IDS`/`SIEM` imzasıdır. Time-based enjeksiyon için anormal `sleep` çağrıları ve olağandışı sorgu süreleri izlenebilir.

## Yaygın Hatalar ve Tuzaklar

- **"WAF var, güvendeyiz" yanılgısı.** `Web Application Firewall`, imza kaçırma (`obfuscation`, yorum enjeksiyonu, kodlama) ile atlatılabilir; kök çözüm parametreli sorgudur.
- **Uygulamanın yönetici hesabıyla bağlanması.** Kolaylık uğruna verilen `superuser`/`root` hakkı, tek bir SQLi'yi tam sunucu ele geçirmeye çevirir.
- **"Kapalı = güvenli" sanmak.** `xp_cmdshell` kapalı olsa da yeterli yetki onu açabilir. Yetki modelini ihmal etmeyin.
- **Blind/OOB'yi hafife almak.** Çıktısı görünmeyen enjeksiyon "zararsız" değildir; time-based ve DNS exfiltration ile tüm veri sızdırılabilir.
- **Sadece in-band savunma.** Egress trafiğini denetlemeyen bir mimari, OOB kanalını açık bırakır.
- **`secure_file_priv`'i boş bırakmak.** Boş değer sınırsız dosya erişimi demektir; `NULL` tercih edilmelidir.
- **Oracle'da yama ertelemek.** Yerleşik paket zafiyetleri güncellenmediğinde `PL/SQL` privilege escalation kalıcı bir risktir.

## Sonuç

SQL Injection'ın gerçek tehlikesi, veri sızdırmanın ötesinde **veritabanı motorunun işletim sistemi ile kurduğu köprüde** yatar. `MSSQL`'in `xp_cmdshell`'i, `PostgreSQL`'in `COPY PROGRAM`'ı, `Oracle`'ın `PL/SQL` paketleri ve `MySQL`'in `FILE` yetkisi; hepsi meşru yönetim araçlarının, yanlış yetki modeliyle birleşince nasıl RCE'ye dönüştüğünü gösterir. Savunmanın özü tek bir cümlede toplanır: **enjeksiyonu parametreli sorguyla kökten önle, uygulamayı en düşük yetkiyle bağla, tehlikeli özellikleri kapat, çıkış trafiğini ve şüpheli ifadeleri izle.** Bu katmanların her biri, saldırının bir halkasını koparır; birlikte uygulandığında zinciri tümüyle çökertir.
