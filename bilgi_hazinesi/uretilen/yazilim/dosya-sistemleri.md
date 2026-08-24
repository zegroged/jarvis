# Dosya Sistemleri: inode, İzinler, Journaling ve Sembolik Link

## Giriş ve Kapsam

Dosya sistemi, ham blok cihazının (disk, SSD, USB) üzerinde yer alan yapısız bayt dizisini; dizinler, dosyalar, meta veriler ve erişim kuralları içeren düzenli bir soyutlamaya dönüştüren yazılım katmanıdır. Kullanıcı `cat rapor.txt` yazdığında arka planda gerçekleşen şey aslında bir dizi dolaylı adres çözümlemesidir: isimden inode'a, inode'dan veri bloklarına. Bu makale, Unix/Linux geleneğindeki dört temel kavramı derinlemesine ele alır: **inode** (dosyanın kimliği ve meta verisi), **izinler** (kimin ne yapabileceği), **journaling** (çökme sonrası tutarlılık) ve **sembolik link** (isim düzeyinde yönlendirme). Bu dört kavram birbirinden bağımsız değildir; bir sembolik linkin neden ayrı bir inode'a ihtiyaç duyduğunu ya da journaling'in neden meta veriyi veriden ayrı ele aldığını anlamak, dördünün nasıl iç içe geçtiğini görmeyi gerektirir.

## inode: Dosyanın Gerçek Kimliği

### Tanım

**inode** (index node), bir dosyanın adı ve içeriği dışındaki her şeyini tutan sabit boyutlu bir meta veri kaydıdır. Yaygın bir yanılgının aksine, bir dosyanın adı inode içinde saklanmaz. inode şunları barındırır: dosya tipi (normal dosya, dizin, symlink, aygıt dosyası vb.), sahip kullanıcı (UID) ve grup (GID), izin bitleri, boyut, zaman damgaları (genellikle erişim/atime, değişiklik/mtime, meta veri değişikliği/ctime), **link sayısı** (hard link count) ve en önemlisi verinin durduğu disk bloklarını gösteren adres işaretçileri.

### Kök Neden: Neden İsim inode'dan Ayrıldı?

Bu ayrım keyfi değildir; doğrudan bir tasarım problemine verilmiş bir cevaptır. Eğer dosya adı ile meta veri tek bir yapıda birleşik olsaydı, aynı içeriğe iki farklı isimle erişmek (hard link) imkânsız olurdu ve dosyayı yeniden adlandırmak, tüm meta veriyi ve hatta veri işaretçilerini yeniden yazmayı gerektirebilirdi. Unix tasarımcıları ismi ve kimliği ayırarak **dizin** kavramını, "isim → inode numarası" eşlemelerini tutan basit bir tablo hâline getirdi. Böylece bir dizin, aslında sadece bir eşleme listesidir. Bu ayrımın en somut sonucu şudur: bir dizine yazma iznine sahip olmak, o dizindeki bir dosyayı **silmek** için yeterlidir, çünkü silme işlemi aslında dosyanın içeriğine değil, dizindeki isim girişine dokunur.

### İşaretçilerin Yapısı ve Büyük Dosya Problemi

inode sabit boyutlu olduğu için, keyfi büyüklükteki bir dosyanın tüm bloklarını doğrudan listeleyemez. Klasik Unix dosya sistemleri bunu **çok seviyeli dolaylı işaretçi** (indirect pointer) yapısıyla çözer: inode içinde birkaç doğrudan (direct) işaretçi bulunur; bunlar küçük dosyalar için yeterlidir. Dosya büyüdükçe tek dolaylı (single indirect), çift dolaylı (double indirect) ve üç dolaylı (triple indirect) işaretçiler devreye girer. Tek dolaylı işaretçi, veri bloklarını değil, veri bloklarının adreslerini içeren bir bloğu gösterir. Bu tasarımın zarafeti şudur: küçük dosyalar için hiçbir dolaylı okuma maliyeti yokken, çok büyük dosyalar da temsil edilebilir. Modern dosya sistemleri (ör. ext4, XFS, Btrfs) bu klasik bağlantılı blok modelinin yerine büyük ölçüde **extent** yaklaşımını kullanır: tek tek blok adresleri yerine "şu bloktan başlayarak N ardışık blok" biçiminde aralıklar tutulur. Extent'ler, ardışık yerleşim yaygın olduğunda meta veriyi ciddi biçimde küçültür ve büyük dosyalarda ardışık okumayı hızlandırır.

### inode Tükenmesi: Klasik Bir Sürpriz

Pek çok klasik dosya sisteminde inode sayısı, dosya sistemi oluşturulurken (mkfs anında) sabitlenir. Bu, diskte yer olmasına rağmen yeni dosya oluşturamama gibi kafa karıştırıcı bir duruma yol açabilir: `df` boş alan gösterirken `df -i` inode'ların bittiğini gösterir. Bu tipik olarak milyonlarca çok küçük dosya (mail spool'ları, cache dizinleri, oturum dosyaları) üreten sistemlerde görülür. Kök neden, alan ile inode havuzunun ayrı ayrı tahsis edilmesidir. Btrfs gibi bazı modern sistemler inode'ları dinamik tahsis ederek bu sınırı kaldırır.

### Hard Link ve Link Sayısı

Bir **hard link**, aynı inode'a işaret eden ikinci bir isim girişidir. Bu yüzden hard link'lerin "aslı" ve "kopyası" ayrımı yoktur; ikisi de eşdeğer isimlerdir. inode içindeki link sayacı, kaç dizin girişinin bu inode'a işaret ettiğini tutar. Bir dosya `unlink` edildiğinde sistem içeriği hemen silmez; sadece sayacı bir azaltır. Veri blokları ve inode ancak sayaç **sıfıra** düştüğünde serbest bırakılır. Buradan çok önemli bir davranış çıkar: bir programın hâlâ açık tuttuğu bir dosya silinse bile, açık dosya tanıtıcısı (file descriptor) bir referans saydığı için içerik erişilebilir kalır; süreç kapanınca alan geri döner. Log dosyalarının silinmesine rağmen diskin dolu görünmeye devam etmesinin klasik nedeni budur.

## İzinler: Kim, Neyi, Nasıl?

### Klasik Model

Unix izin modeli üç aktör sınıfı tanımlar: **owner** (sahip/user), **group** (grup) ve **others** (diğerleri). Her sınıf için üç temel hak vardır: okuma (r), yazma (w), çalıştırma (x). Bunlar `rwxr-xr--` biçiminde on karakterlik bir dizgede (ilk karakter dosya tipi) gösterilir ve sekizlik (octal) sayılarla da ifade edilir: r=4, w=2, x=1. Böylece `755`, sahibe tam hak (rwx=7), gruba ve diğerlerine okuma+çalıştırma (r-x=5) verir.

### Kök Neden: Dizinlerde x Bitinin Anlamı Neden Farklı?

En sık kafa karıştıran nokta, aynı bitlerin dosyalarda ve dizinlerde farklı anlam taşımasıdır. Bir dosyada `x` çalıştırılabilirlik demektir. Bir **dizinde** ise `x`, o dizine "girme" ya da daha doğru ifadeyle içindeki bir isme göre inode çözümleme (traverse) iznidir. `r` ise dizindeki isimleri **listeleyebilme** iznidir. Bunun pratik sonucu şaşırtıcıdır: bir dizinde `x` olup `r` olmazsa, içindeki dosyaların adlarını göremezsiniz ama adını tam olarak bildiğiniz bir dosyaya erişebilirsiniz. Tersine `r` olup `x` olmazsa, isimleri listeleyebilir ama hiçbirine gerçekten ulaşamazsınız. Bu ayrım, isim çözümleme (path resolution) mantığından doğar: bir yola erişmek için yol üzerindeki **her** dizinde traverse (x) izni gerekir.

### Özel Bitler: setuid, setgid ve sticky

Üç temel bitin ötesinde üç özel bit vardır ve bunların kök nedeni pratik bir güvenlik/yönetim ihtiyacıdır.

**setuid**: Çalıştırılabilir bir dosyada ayarlandığında, program çalıştıran kullanıcının değil, dosyanın **sahibinin** yetkisiyle çalışır. Klasik örnek `passwd` komutudur: sıradan bir kullanıcı parolasını değiştirmek için parola veritabanına yazmalıdır, ama bu dosya root'a aittir. setuid sayesinde program root yetkisiyle çalışır. Bu güç, setuid'i tarihsel olarak en büyük **privilege escalation** (yetki yükseltme) kaynaklarından biri yapmıştır; kötü yazılmış bir setuid programı, saldırgana root verebilir.

**setgid**: Dizinlerde kullanıldığında özellikle güçlüdür: bu dizin içinde oluşturulan yeni dosyalar, oluşturanın birincil grubunu değil, **dizinin grubunu** miras alır. Ekiplerin paylaşımlı klasörlerde ortak grup sahipliğini korumasının pratik yolu budur.

**sticky bit**: Bir dizinde ayarlandığında, o dizindeki bir dosyayı yalnızca dosyanın sahibi (veya dizin sahibi/root) silebilir. Bunun kanonik örneği `/tmp` dizinidir: herkes yazabilir ama kimse başkasının dosyasını silemez. Sticky bit olmasaydı, dünyaya açık yazılabilir bir dizinde herkes herkesin dosyasını silebilirdi.

### İzinlerin Ötesi: umask, ACL ve MAC

Yeni bir dosya oluşturulduğunda hangi izinlerle başlayacağını **umask** belirler. umask, oluşturma sırasında maskelenecek (kaldırılacak) bitleri tutar; örneğin `022` umask'ı, gruptan ve diğerlerinden yazma iznini otomatik kaldırır. Bu bir "izin verme" değil, "izinleri kırpma" mekanizmasıdır. Klasik owner/group/other modeli her senaryoya yetmez; örneğin "şu üç kullanıcıya okuma, ama bir dördüncüye yazma" gibi ince ayarlar için **ACL** (Access Control List) kullanılır; `setfacl`/`getfacl` ile yönetilir. Bunun da ötesinde SELinux/AppArmor gibi **MAC** (Mandatory Access Control) sistemleri, dosya izinlerinden bağımsız, çekirdek düzeyinde zorlanan ek bir politika katmanı ekler; burada erişim kararı yalnızca dosyanın izinlerine değil, sürecin güvenlik etiketine (context) de bağlıdır.

## Journaling: Çökme Sonrası Tutarlılık

### Problem: Atomik Olmayan Güncellemeler

Journaling'i anlamak için önce çözdüğü sorunu görmek gerekir. Diske bir dosya eklemek tek bir işlem değildir; en az birkaç ayrı yazma içerir: yeni veri bloklarını yazmak, inode'u güncellemek, dizin girişini eklemek ve boş blok/inode haritasını (bitmap) güncellemek. Disk (veya işletim sistemi) bu yazmaları farklı sıralarda ve farklı zamanlarda gerçekleştirebilir. Tam bu işlemlerin ortasında elektrik kesilirse dosya sistemi **tutarsız** bir durumda kalır: örneğin bitmap bloğun kullanıldığını söylerken hiçbir inode ona sahip çıkmıyor olabilir (alan sızıntısı), ya da iki inode aynı bloğu paylaşıyor olabilir (veri bozulması). Journaling'in yokluğunda tek çare, önyükleme sırasında `fsck` ile tüm dosya sistemini baştan sona tarayıp tutarlılığı yeniden kurmaktır; bu, terabaytlık disklerde saatler sürebilir.

### Kök Neden ve Çalışma Mantığı

Journaling'in temel fikri **veritabanlarındaki write-ahead logging** ile aynıdır: gerçek değişikliği yapmadan önce, "ne yapmayı planladığımı" ayrı bir alana (journal/log) atomik olarak yaz. Mantık şöyle işler:

1. Yapılacak değişiklikler önce journal'a bir **transaction** olarak yazılır.
2. Transaction'ın tamamının journal'a ulaştığını işaretleyen bir **commit** kaydı yazılır.
3. Ancak bundan sonra değişiklikler gerçek konumlarına (in-place) uygulanır; buna **checkpoint** denir.
4. Değişiklikler kalıcı olarak yerine oturunca journal girdisi serbest bırakılır.

Kritik nokta commit kaydıdır. Çökme, commit yazılmadan önce olursa, yeniden başlatmada dosya sistemi eksik transaction'ı görür ve onu **yok sayar** (rollback): sanki hiç başlamamış gibi. Commit yazıldıktan sonra ama checkpoint tamamlanmadan olursa, dosya sistemi journal'daki tamamlanmış transaction'ı **yeniden oynatır** (replay): değişiklikleri baştan uygular. Her iki durumda da sonuç **tutarlı**dır. Böylece fsck ile tüm diski taramak yerine, yalnızca küçük journal'ı işlemek yeterli olur; kurtarma saniyeler sürer.

### Journaling Modları: Neyi Koruyoruz?

Burada önemli bir ince ayrım vardır. Journaling'in tuttuğu şey ne kadar olmalı? Her yazmayı iki kez (bir journal'a, bir yerine) yapmak veri güvenliğini artırır ama performansı yarıya indirir. ext türü dosya sistemlerinde tipik olarak üç mod bulunur:

- **journal (data=journal)**: Hem meta veri hem de veri journal'a yazılır. En güvenli, en yavaş. Her şey iki kez yazılır.
- **ordered (data=ordered)**: Yalnızca meta veri journal'a yazılır, ancak ilgili veri blokları **meta veri commit edilmeden önce** yerine yazılmış olmak zorundadır. Bu, meta verinin var olmayan/eski veriye işaret etmesini engeller. Yaygın varsayılan budur.
- **writeback (data=writeback)**: Yalnızca meta veri journal'lanır ve veri ile meta veri arasında sıralama garantisi yoktur. En hızlı ama çökme sonrası bir dosyanın meta verisi güncelken içeriğinin eski/çöp olması mümkündür.

Buradaki kritik doğruluk mesajı şudur: **çoğu journaling dosya sistemi, çökme sonrası dosya sisteminin yapısal tutarlılığını garanti eder; ama tek tek dosyaların içeriğinin en son yazdığınız hâlde olacağını garanti etmez.** Uygulama düzeyinde veri kalıcılığı istiyorsanız hâlâ `fsync` çağırmanız gerekir. Journaling, "diskim çökmeden bozulmasın" derdine çözümdür; "az önce yazdığım her byte kesin diskte olsun" derdine değil.

### Alternatif Yaklaşımlar

Journaling tek çözüm değildir. **Copy-on-write** (CoW) tabanlı dosya sistemleri (Btrfs, ZFS) farklı bir yol izler: bir bloğu asla yerinde değiştirmezler, yeni bir kopyasını yazıp sonra üst düzey işaretçiyi atomik olarak yeni kopyaya çevirirler. Böylece eski durum, yeni durum tam hazır olana kadar bozulmadan durur; ayrı bir journal'a gerek kalmaz ve anlık görüntü (snapshot) alma neredeyse bedava hâle gelir. Bir diğer yaklaşım **soft updates**'tir; burada yazma sırası dikkatle düzenlenerek diskin her an kurtarılabilir bir durumda kalması sağlanır.

## Sembolik Link: İsim Düzeyinde Yönlendirme

### Tanım ve Hard Link'ten Farkı

Bir **sembolik link** (symlink, soft link), içeriği başka bir yolun metinsel adresi olan özel bir dosyadır. Hard link aynı inode'a ikinci bir isim verirken, symlink **kendi inode'una** sahip ayrı bir dosyadır ve içinde hedefin yol dizgesini tutar. Bu temel fark, davranıştaki neredeyse tüm farkların kaynağıdır.

### Kök Neden: Neden Symlink'e İhtiyaç Var?

Hard link güçlü ama iki temel kısıtı vardır. Birincisi, hard link'ler **dosya sistemi sınırını aşamaz**: inode numaraları yalnızca kendi dosya sistemleri içinde anlamlıdır, dolayısıyla farklı bir bölümdeki/diskteki dosyaya hard link kurulamaz. İkincisi, geleneksel olarak **dizinlere hard link kurulmasına izin verilmez**, çünkü bu, dosya sistemi ağacında döngüler yaratıp path resolution'ı sonsuz döngüye sokabilir ve `..` semantiğini bozabilir. Symlink her ikisini de çözer: sadece bir metin dizgesi tuttuğu için hedefin hangi dosya sistemi, hangi disk hatta var olup olmadığı umurunda değildir. Bu esneklik, symlink'i sistem yönetiminin temel aracı yapar: kütüphane sürüm yönlendirmeleri (`libfoo.so → libfoo.so.1.2.3`), `/etc/alternatives` mekanizması, aktif yapılandırma seçimi hep symlink üzerine kuruludur.

### Çözümleme Anı ve Kırık Linkler

Symlink'in en kritik özelliği, hedefin **erişim anında** çözümlenmesidir. Symlink oluşturulurken hedefin var olup olmadığı kontrol edilmez; siz hedefe erişmeye çalıştığınızda çekirdek yol dizgesini okur ve o anda çözer. Bu, iki önemli sonuç doğurur. Birincisi, hedef sonradan silinir veya taşınırsa, symlink **dangling** (kırık/sallanan) hâle gelir; kendisi hâlâ vardır ama gösterdiği yer yoktur. İkincisi, symlink **göreli** (relative) bir yol tutuyorsa, çözümleme link'in bulunduğu dizine göre yapılır; bu yüzden symlink'i başka bir yere kopyalamak/taşımak onu kırabilir. Genel bir kural olarak, taşınması olası yapılarda symlink'i mutlak (absolute) yolla değil, hedefe **göreli** kurmak daha dayanıklı olur; çünkü tüm ağaç birlikte taşındığında göreli yol korunur.

### Symlink ve Güvenlik: TOCTOU

Symlink'ler klasik bir güvenlik açığı sınıfının merkezindedir: **TOCTOU** (Time-of-Check to Time-of-Use). Bir program bir yolun güvenli olduğunu kontrol edip (check) sonra ona yazarsa (use), aradaki minik zaman aralığında bir saldırgan o yolu bir symlink'e çevirerek yazmayı hassas bir hedefe (ör. `/etc/passwd`) yönlendirebilir. Bu bir **race condition**'dır. Özellikle `/tmp` gibi dünyaya açık yazılabilir dizinlerde tahmin edilebilir isimlerle geçici dosya oluşturan programlar bu saldırıya açıktır. Doğru savunma, "kontrol et sonra kullan" desenini kırmaktır: dosyayı atomik olarak `O_CREAT | O_EXCL` bayraklarıyla açmak (varsa hata ver), symlink'i takip etmeyen `O_NOFOLLOW` gibi seçenekleri kullanmak, `mkstemp` benzeri güvenli geçici dosya API'lerine güvenmek ve mümkünse yol adı yerine açık dosya tanıtıcıları üzerinden çalışmak (`openat` ailesi).

## Yaygın Hatalar ve Tuzaklar

**Symlink ile dosya izinlerini yönetmeye çalışmak.** Symlink'in kendi izin bitleri çoğu sistemde anlamsızdır; erişim kontrolü daima hedef dosyanın izinlerine göre yapılır. `chmod` bir symlink'e uygulandığında genellikle hedefi etkiler, symlink'in kendisini değil. Symlink'in izinlerini "sıkılaştırarak" güvenlik sağladığını sanmak yanlıştır.

**Hard link ile yedekleme sanmak.** Hard link bir kopya değildir; aynı veriyi paylaşan ikinci bir isimdir. İçeriği bir isim üzerinden değiştirirseniz diğer isimden de değişmiş görünür. Yedek zannedilen hard link, veri bozulmasına karşı hiçbir koruma sağlamaz.

**`rm -rf` ile symlink'in ardındaki dizini silmek.** Bir dizine işaret eden symlink'e sondaki eğik çizgiyle (`bir_link/`) davranış işletim sistemine ve komuta göre değişebilir; dikkatsiz bir `rm -rf bir_link/` çağrısı bazı durumlarda linkin işaret ettiği gerçek dizinin içeriğini hedefleyebilir. Yıkıcı işlemlerde symlink'lerin nasıl çözümlendiğini varsaymadan test etmek gerekir.

**inode/alan karışıklığını gözden kaçırmak.** "Disk dolu" hatası aldığınızda yalnızca `df`'ye bakıp, `df -i` ile inode tükenmesini kontrol etmemek, saatlerce yanlış yerde hata aramaya yol açar.

**Journaling'i veri kalıcılığı garantisi sanmak.** Daha önce vurgulandığı gibi, journaling yapısal tutarlılık sağlar; uygulama verinizin diske indiğini garanti etmez. `fsync` (ya da veritabanları için ilgili dayanıklılık çağrıları) atlanırsa, çökme sonrası "kaydettim sandığım" veri kaybolabilir.

**Açık dosyayı silince alanın geri döneceğini varsaymak.** Bir süreç hâlâ açık tutarken silinen büyük bir log dosyasının alanı, süreç kapanana (veya dosyayı truncate edene) kadar geri gelmez. Diskin dolu görünmesine rağmen `du`'nun bunu göstermemesi bu duruma işarettir.

## En İyi Pratikler

**En az yetki ilkesini izinlere uygulayın.** Dosyalara ve dizinlere ihtiyaç duyulan minimum izni verin. Özellikle dünyaya yazılabilir (`o+w`) izinlerden kaçının; gerçekten gerekliyse sticky bit ile birlikte kullanın. setuid/setgid programları denetim listesinde tutun; her biri potansiyel bir saldırı yüzeyidir ve gereksiz olanların bu bitleri kaldırılmalıdır.

**Geçici dosyaları güvenli oluşturun.** Tahmin edilebilir isimlerle `/tmp` altında dosya açmak yerine `mkstemp` benzeri atomik ve rastgele-isimli API'ler kullanın; symlink saldırılarına karşı `O_EXCL`/`O_NOFOLLOW` seçeneklerini tercih edin. Path yerine file descriptor üzerinden çalışmak race'leri büyük ölçüde kapatır.

**Symlink'lerde göreli yolu bilinçli seçin.** Birlikte taşınacak ağaç yapılarında göreli symlink daha dayanıklıdır; sabit sistem konumlarına (ör. `/usr/lib`) işaret eden linklerde ise mutlak yol daha nettir. Kararı taşınma senaryosuna göre verin, alışkanlıkla değil.

**Doğru journaling modunu iş yüküne göre seçin.** Veri bütünlüğünün kritik olduğu sunucularda `ordered` mod makul bir dengedir; ham performansın öncelikli ve verinin yeniden üretilebilir olduğu (ör. geçici cache) durumlarda `writeback` düşünülebilir. Kritik veriyi asla tek başına dosya sistemi tutarlılığına emanet etmeyin; uygulama düzeyinde `fsync` ve düzenli yedekle destekleyin.

**Bütünlüğü doğrulayın.** Snapshot destekli CoW dosya sistemleri (ZFS, Btrfs) checksum ile sessiz veri bozulmasını (silent corruption / bit rot) tespit edebilir. Uzun ömürlü ve kritik veri depoluyorsanız, journaling'in ötesinde bu checksum ve snapshot yeteneklerini değerlendirin.

## Sonuç

Bu dört kavram tek bir tutarlı fikrin farklı yüzleridir: **isim, kimlik ve içerik arasındaki dolaylılık**. inode, ismi kimlikten ayırarak hard link'i, güvenli silmeyi ve verimli yeniden adlandırmayı mümkün kılar. İzinler, bu kimliğe kimin dokunabileceğini katmanlı bir modelle tanımlar ve dizinlerdeki traverse semantiğiyle path resolution'a bağlanır. Journaling, bu yapıların çökme sırasında yarım kalmamasını, atomik commit fikriyle garanti eder. Sembolik link ise dolaylılığı bir adım öteye taşıyıp ismin kendisini yönlendirilebilir kılar; bu esneklik güçlü olduğu kadar TOCTOU gibi incelikli tehlikeler de doğurur. Bir dosya sistemini gerçekten anlamak, bu dört mekanizmanın nasıl ayrı ayrı çalıştığını değil, birbirlerinin varsayımları üzerine nasıl kurulduğunu görmektir.
