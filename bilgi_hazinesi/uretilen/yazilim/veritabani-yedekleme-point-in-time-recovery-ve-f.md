# Veritabanı Yedekleme, Point-in-Time Recovery ve Felaket Kurtarma (DB-Spesifik)

## Giriş: Neden Genel "Backup" Yetmez?

Çoğu ekip "yedek alıyoruz" der ve rahatlar. Ama bir `DROP TABLE` kazasından ya da ransomware saldırısından sonra o rahatlık paramparça olur. Genel dosya yedekleme (file-level backup) ile veritabanı yedekleme birbirinden derin biçimde ayrılır: bir veritabanı, sürekli değişen, transaction'lar hâlinde tutarlılık (consistency) garantisi veren canlı bir sistemdir. Dolayısıyla veritabanına özgü kavramlar (transaction log, checkpoint, WAL, binlog, point-in-time recovery) olmadan alınan yedekler ya bozuk (corrupt/inconsistent) çıkar ya da felaket anında saatlerce veri kaybettirir.

Bu makale mekanizmayı anlamayı, kurtarmayı planlamayı ve yedeklerin kendisini tehdit modeline sokmayı hedefler. Amaç kavramsaldır: nasıl çalışır, ne zaman ne seçilir, nerede tuzak vardır.

## Temel Kavramlar: RPO ve RTO

Her felaket kurtarma (disaster recovery, DR) tartışması iki metrikle başlar:

- **RPO (Recovery Point Objective):** Kabul edilebilir maksimum veri kaybı süresi. "En fazla ne kadarlık veriyi kaybetmeye razıyız?" sorusunun cevabı. RPO 15 dakika ise, felaket anında son 15 dakikadan eski her transaction geri gelebilmeli.
- **RTO (Recovery Time Objective):** Sistemin tekrar ayağa kalkması için kabul edilebilir maksimum süre. "Ne kadar süre kapalı kalabiliriz?" sorusunun cevabı.

Bu ikisi bağımsız hedeflerdir ve maliyeti belirler. RPO'yu sıfıra yaklaştırmak (senkron replikasyon, sürekli log gönderimi) pahalıdır; RTO'yu düşürmek (hazır bekleyen standby, otomatik failover) ayrı bir yatırımdır.

### RPO/RTO Hesaplama Mantığı

RPO'yu belirleyen tek şey yedek/log alma sıklığıdır. Eğer transaction log'unuzu her 5 dakikada bir uzak depoya atıyorsanız, kötü senaryoda son gönderimden sonra biriken 5 dakikalık veri kaybolur — yani gerçekleşen RPO ~5 dakikadır. Point-in-time recovery kullanıyorsanız RPO, log'un ne kadar sık ve güvenli biçimde saklandığına iner; teoride saniyeler mertebesine kadar düşürülebilir.

RTO ise şunların toplamıdır: felaketi fark etme süresi + karar süresi + full backup'ı geri yükleme (restore) süresi + üzerine log'ları oynatma (replay) süresi + doğrulama süresi. Kritik nokta: **1 TB'lık bir yedeği geri yüklemek dakikalar değil saatler alabilir.** RTO'yu gerçekçi hesaplamak için restore hızını (ör. depolama okuma/yazma bant genişliği) gerçek ortamda ölçmek gerekir; tahminle değil.

Bir örnek: Full backup 800 GB, restore hızınız pratikte ~200 MB/s ise, tek başına kopyalama ~1 saat 7 dakika sürer. Buna log replay ve doğrulama eklenince RTO rahatça 2 saati bulur. "Yedeğimiz var" demek RTO'yu bilmek demek değildir; **restore'u test etmeden RTO bir temenndidir.**

## Yedek Türleri: Full, Incremental, Differential

### Full Backup (Tam Yedek)

Veritabanının o andaki bütününün kopyası. Tek başına geri yüklenebilir — başka hiçbir yedeğe bağımlı değildir. Avantajı basitlik ve hızlı restore; dezavantajı boyut ve alma süresi. Büyük sistemlerde her gün full almak depolama ve I/O açısından pahalıdır.

### Incremental Backup (Artımlı Yedek)

Yalnızca **bir önceki yedekten (full ya da incremental) bu yana değişen** blokları/verileri saklar. En küçük ve en hızlı alınan yedek türüdür. Ama restore zinciri uzundur: full + tüm ara incremental'ları sırayla oynatmak gerekir. Zincirdeki tek bir bozuk incremental, sonraki tüm kurtarmayı riske atar.

### Differential Backup (Fark Yedeği)

Yalnızca **son full backup'tan bu yana** değişenleri saklar. Zamanla büyür (bir sonraki full'e kadar her differential daha şişer), ama restore sadece iki adımdır: full + son differential. Incremental'a göre daha çok yer kaplar ama restore daha basit ve daha az kırılgandır.

### Karşılaştırma Özeti

| Tür | Alma boyutu/süresi | Restore karmaşıklığı | Kırılganlık |
|---|---|---|---|
| Full | Büyük / yavaş | En basit | Düşük |
| Incremental | En küçük / en hızlı | Uzun zincir | Yüksek (zincir kopabilir) |
| Differential | Orta, büyüyen | 2 adım | Orta |

Pratikte tipik strateji karma olur: haftada bir full, günlük differential ya da incremental, ve **transaction log'ların sürekli arşivlenmesi.** Asıl kurtarma gücü bu son maddeden gelir.

## Point-in-Time Recovery (PITR): İşin Kalbi

### Tanım

Point-in-time recovery, veritabanını **geçmişteki herhangi bir ana** (ör. "dün saat 14:32:07"ye) geri getirebilme yeteneğidir. Bir full backup'a geri dönmekle karıştırılmamalı: full backup sizi yedeğin alındığı ana götürür; PITR ise o andan sonraki transaction'ları **istediğiniz saniyeye kadar** yeniden oynatır.

### Çalışma Mantığı: Transaction Log

Modern veritabanları her değişikliği önce bir **transaction log**'una yazar (write-ahead logging, WAL prensibi): "Veriyi diske kalıcı yazmadan önce, ne yapacağını log'a yaz." PostgreSQL'de buna **WAL (Write-Ahead Log)**, MySQL/InnoDB'de **binary log (binlog)** ve ayrıca **redo log**, Oracle'da **redo log** ve **archived redo log**, SQL Server'da **transaction log** denir. İsimler farklı, prensip aynıdır.

PITR şöyle çalışır:

1. Belli bir andaki **temel (base) full backup** alınır.
2. O andan itibaren tüm transaction log'lar **sürekli arşivlenir** (log shipping / continuous archiving).
3. Kurtarma anında: önce base backup restore edilir, sonra arşivlenmiş log'lar **hedef zamana kadar sırayla oynatılır (replay).**

Bu, WAL'in aynı zamanda crash recovery mekanizması olmasından kaynaklanır. Veritabanı normalde çöktüğünde de log'u oynatarak (redo) tutarlı hâle gelir; PITR bunu daha uzak bir geçmişten, kontrollü biçimde yapar.

### Neden Bu Kadar Kritik?

Diyelim ki bir geliştirici saat 14:32'de yanlışlıkla `DELETE FROM orders` çalıştırdı (WHERE'i unutarak). Sadece full backup'ınız varsa, en son yedeğe (ör. gece yarısı) dönersiniz ve o günün tüm çalışmasını kaybedersiniz. PITR ile ise base backup'ı restore edip log'ları **14:31:59'a kadar** oynatır, felaketli komuttan bir saniye önce durursunuz. Kayıp: neredeyse sıfır.

Aynı mantık ransomware sonrası da geçerlidir: eğer log arşiviniz sağlamsa, şifrelemenin/bozulmanın başladığı andan hemen önceye dönebilirsiniz.

### Doğru Kullanım ve Tuzaklar

- **Log zinciri kesintisiz olmalı.** Base backup ile hedef zaman arasındaki hiçbir log dosyası eksik/bozuk olmamalı. Tek bir boşluk, o boşluktan sonrasına ilerlemeyi imkânsız kılar.
- **Base backup ile log'lar birlikte tutarlı olmalı.** Yedek alırken veritabanı "backup mode"a alınır ya da tutarlı bir snapshot alınır; aksi halde base ile log başlangıcı hizalanmaz.
- **Zaman senkronizasyonu (NTP) önemlidir.** "Şu saate kadar oynat" diyorsanız, sunucu saatleri kayıksa hedefi tutturamazsınız. Mümkünse zaman yerine **transaction ID / LSN (log sequence number)** gibi mantıksal işaretçilerle hedeflemek daha kesindir.

## Fiziksel vs Mantıksal Yedek

İki temel yaklaşım vardır ve karıştırılmamalıdır:

- **Fiziksel (physical) yedek:** Veri dosyalarının/blokların birebir kopyası. Hızlı restore, PITR için uygun (log'larla birleşir), ama genelde aynı veritabanı sürümü/mimarisi gerektirir. Büyük sistemlerde tercih edilir.
- **Mantıksal (logical) yedek:** Verinin `INSERT`/`CREATE` ifadeleri ya da taşınabilir bir formatta dışa aktarımı (ör. `pg_dump`, `mysqldump` mantığı). Sürümler/mimariler arası taşınabilir, tek tablo geri yüklemede esnek, ama büyük veritabanlarında restore çok yavaştır ve tek başına PITR sağlamaz.

Genel kural: **PITR ve düşük RTO istiyorsanız fiziksel yedek + log arşivi; taşınabilirlik ve seçici restore istiyorsanız mantıksal yedek.** İkisini birlikte kullanmak yaygındır.

## Yedeklerin Doğrulanması: Test Edilmeyen Yedek = Yedek Değil

En yaygın ve en pahalı hata: yedeklerin hiç geri yüklenerek denenmemesi. Yedek işi "başarılı" raporlasa bile dosya bozuk olabilir, log zinciri kopuk olabilir, ya da restore prosedürü kimsenin bilmediği bir adımı gerektiriyor olabilir.

Doğrulamanın katmanları:

1. **Yedek bütünlüğü (integrity):** Checksum/hash ile dosyanın bozulmadığını kanıtlamak. Birçok veritabanı yedek doğrulama komutları sunar (yedeğin okunabilir ve tutarlı olduğunu denetleyen).
2. **Gerçek restore tatbikatı (restore drill):** Yedeği **izole bir ortama** düzenli aralıklarla geri yükleyip veritabanının açıldığını, satır sayılarının makul olduğunu, uygulamanın bağlanabildiğini doğrulamak. Bu tatbikat aynı zamanda RTO'nuzu gerçek ölçer.
3. **PITR tatbikatı:** Sadece full değil, "geçmiş bir ana dönme" senaryosunu da denemek. Log oynatmanın gerçekten çalıştığını görmeden PITR'e güvenmeyin.

Altın kural: Yedekleme başarısı, restore başarısıyla ölçülür. Diskte duran ama açılmayan bir yedek, olmayan bir yedektir.

## Yedek Şifreleme (Backup Encryption)

Yedekler, üretim veritabanının **tüm hassas verisinin taşınabilir bir kopyasıdır.** Bu yüzden saldırganlar için canlı sistemden bazen daha çekici bir hedeftir: genellikle daha zayıf korunur, farklı depolamada durur ve dışarı sızdırması sessizdir.

İki şifreleme ekseni:

- **At-rest (durağan) şifreleme:** Yedek dosyası depoda şifreli durur. Depolama çalınsa/sızsa bile içerik okunamaz. Bulut nesne depolamalarında sunucu tarafı şifreleme yaygındır ama **anahtar yönetimi kime ait** sorusu kritiktir.
- **In-transit (aktarımdaki) şifreleme:** Yedek uzak depoya taşınırken TLS gibi bir kanalla korunur; ağ üzerinde dinleyen biri okuyamaz.

### Anahtar Yönetimi (Key Management) — En Kritik Nokta

Şifrelemenin gücü anahtarın yönetiminde saklıdır. Yaygın ölümcül hata: **şifreleme anahtarını, şifrelenmiş yedeğin yanında saklamak.** Bu, kilitli kasanın anahtarını kasanın üstüne bantlamak gibidir.

Doğru yaklaşım:

- Anahtarları ayrı bir **key management system (KMS) / secrets manager** içinde tutmak; yedek deposundan erişim ayrımı yapmak.
- Anahtar rotasyonu (key rotation) planlamak, ama **eski yedekleri çözebilmek için eski anahtarları da güvenli biçimde arşivlemek.** Anahtarı kaybederseniz yedek de kaybolur.
- Yedeği şifreleyen kimlik ile yedeği restore/çözecek kimliğin yetkilerini ayırmak (least privilege).

Şifrelemenin ikinci faydası: bütünlük. Bozulan/oynanan bir şifreli yedek, çözme sırasında hata verir; bu bir tür manipülasyon tespitidir.

## Yedek Hırsızlığı Tehdit Modeli (Threat Model)

Yedekleri savunmak için "kim, neyi, nasıl hedefler" diye düşünmek gerekir. Bir tehdit modeli iskeleti:

### Varlık (Asset)
Yedeğin içerdiği veri: müşteri kayıtları, kimlik bilgileri, ödeme verisi, ticari sırlar. Yedek = üretim verisinin tam kopyası.

### Tehdit Aktörleri ve Vektörleri

- **Dış saldırgan — depoya erişim:** Yanlış yapılandırılmış (public/misconfigured) bulut depolama kovaları (bucket) klasik sızıntı kaynağıdır. Yedek kovaları sık sık gözden kaçar çünkü "sadece yedek" diye önemsenmez.
- **Sızmış kimlik bilgisi:** Yedek deposuna erişen servis hesabının anahtarı sızarsa, saldırgan tüm veri tarihçesini indirebilir. Bu yüzden yedek erişimi ayrı, dar yetkili ve loglanan kimliklerle olmalı.
- **İç tehdit (insider):** Yedeklere geniş erişimi olan bir çalışan/yüklenici, canlı sisteme dokunmadan tüm veriyi sessizce dışarı taşıyabilir.
- **Fiziksel/ortam kaybı:** Yanlış imha edilmiş disk, kaybolmuş yedek medyası.

### Savunmalar (Kontroller)

- **En az yetki (least privilege):** Yedeği yazan kimlik onu silememeli/okuyamamalı ayrımı; restore yetkisi ayrı ellerde.
- **Şifreleme + ayrı anahtar yönetimi** (yukarıda).
- **Erişim loglama ve anomali tespiti:** Yedek deposuna kim, ne zaman, ne kadar veri indirdi? Beklenmedik toplu indirme (bulk download) alarm üretmeli. Bu, veri sızıntısını (exfiltration) yakalamanın somut yoludur.
- **Ağ ayrımı:** Yedek deposu, üretim ağından ve internetten mümkün olduğunca izole olmalı.

## Ransomware ve Değiştirilemez Yedekler (Immutable / Air-Gapped)

Modern ransomware sadece üretim verisini şifrelemez; **önce yedekleri yok etmeye çalışır.** Çünkü saldırganlar bilir ki sağlam bir yedek, fidyeyi ödeme baskısını sıfırlar. Bu yüzden yedek stratejisinin ransomware'e özel savunması olmalıdır.

### Immutable Backup (Değiştirilemez Yedek)

Bir kez yazıldıktan sonra belirlenen süre boyunca **silinemeyen ve değiştirilemeyen** yedek. Bu genelde depolama seviyesinde bir "object lock" / WORM (write once, read many) mekanizmasıyla sağlanır. Saldırgan yönetici yetkisi ele geçirse bile, kilit süresi dolmadan bu yedekleri silemez. Ransomware sonrası kurtarmanın en güçlü tek kontrolüdür.

### Air-Gap (Fiziksel/Mantıksal Boşluk)

Yedeğin bir kopyasının, üretim ağına **normalde bağlı olmayan** bir ortamda tutulması. Ağ üzerinden erişilemeyen bir yedek, ağ üzerinden yayılan ransomware tarafından da erişilemez. Modern uygulamada tam fiziksel kopukluk yerine "logical air-gap" (yalnızca yazma penceresinde açılan, ayrı hesap/kimlik alanında duran depo) yaygındır.

### 3-2-1 (ve 3-2-1-1-0) Kuralı

Klasik kural: **3** kopya veri, **2** farklı ortam/medya türü, **1** kopya tesis dışında (off-site). Ransomware çağında buna sık sık **1** immutable/air-gapped kopya ve **0** doğrulama hatası (yani test edilmiş, hatasız restore) eklenir. Bu basit kural, tek bir felaketin (yangın, silme, şifreleme) tüm kopyaları birden yok etmesini önlemek için tasarlanmıştır.

## Yaygın Hatalar (Anti-Patterns)

1. **Restore'u hiç test etmemek.** En sık ve en yıkıcı hata. Yedek "yeşil" görünür, felaket anında açılmaz.
2. **Transaction log'ları arşivlememek.** Sadece gecelik full alıp "yedeğimiz var" sanmak — PITR imkânsızlaşır, RPO gün mertebesine çıkar.
3. **Yedekleri üretimle aynı yerde/hesapta tutmak.** Üretimi silen/şifreleyen olay yedekleri de siler. Off-site ve immutable kopya olmadan tek nokta hatası.
4. **Şifreleme anahtarını yedeğin yanında saklamak.** Şifreleme bu durumda güvenlik değil, sahte bir güven duygusu üretir.
5. **Immutable/air-gap olmaması.** Ransomware yedekleri de silince kurtarma umudu biter.
6. **RTO'yu ölçmemek, tahmin etmek.** Gerçek restore süresi bilinmezse, felaket anındaki "1 saatte döneriz" sözü boştur.
7. **Log zincirini izlememek.** Bir gün log arşivlemesi sessizce bozulur, kimse fark etmez, PITR gerektiğinde boşlukla karşılaşılır. Log sürekliliği izlenmeli ve alarmlanmalı.
8. **Yedek erişimini loglamamak.** Sessiz veri sızıntısı ancak erişim izlenirse yakalanır.

## Kurtarma Sırası: Felaket Anında Zihinsel Model

Bir DB felaketinde kabaca sıra şudur:

1. **Kapsamı belirle:** Ne bozuldu — donanım mı, mantıksal hata mı (yanlış DELETE), yoksa ransomware/kötü niyet mi? Kaynak yanlış anlaşılırsa yanlış yedeğe dönülür.
2. **Hedef zamanı seç:** Mantıksal hatada, felaketten hemen önceki an (PITR hedefi). Ransomware'de, bozulmanın başladığı andan önce — ki bu an tespit loglarından belirlenmeli.
3. **İzole ortama restore et:** Doğrudan üretimin üstüne yazma; önce ayrı bir yerde geri yükle ve doğrula. Bozuk/şifreli bir kaynağı tekrar üretime taşımak felaketi büyütür.
4. **Doğrula:** Satır sayıları, kritik tablolar, uygulama bağlantısı.
5. **Devreye al ve olayı belgele:** Kök nedeni ve kurtarma süresini kayıt altına al — bir sonraki RTO tahminin bu olur.

## Sonuç

Veritabanı yedekleme, "dosya kopyalamak"tan tamamen farklı bir disiplindir. Merkezinde transaction log ve point-in-time recovery yatar: gerçek koruma, full backup'lardan değil, sürekli ve sağlam log arşivinden gelir. RPO ve RTO'yu ölçülebilir hedefler hâline getirmeden, restore'u düzenli tatbik etmeden ve yedekleri şifreleme + immutable + air-gap ile bir tehdit modeli içinde savunmadan, "yedeğimiz var" cümlesi bir güvenlik değil bir temennidir. Özellikle ransomware çağında, silinemeyen ve ağdan izole bir yedek kopyası ile test edilmiş bir kurtarma prosedürü, bir kuruluşun ayakta kalmasıyla iflası arasındaki farktır.
