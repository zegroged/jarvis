# Dağıtık Kilitleme ve Liderlik Seçimi (Distributed Locking, Leader Election, Fencing Tokens)

## Giriş ve Problem Tanımı

Tek bir makinede çalışan bir programda "aynı anda yalnızca bir iş parçacığı (thread) şu kaynağa dokunsun" demek kolaydır: işletim sistemi ve dil çalışma zamanı (runtime) size `mutex`, `semaphore` ya da atomik komutlar sunar. Bu mekanizmalar paylaşılan belleğe ve tek bir saate dayanır.

Dağıtık sistemlerde ise bu güvenli zemin ortadan kalkar. Farklı makinelerde çalışan onlarca süreç (process), aralarında paylaşılmış bir bellek olmadan, ağ üzerinden haberleşerek şu iki ihtiyacı karşılamak zorundadır:

- **Distributed lock (dağıtık kilit):** "Bu kritik bölüme ya da bu kaynağa aynı anda en fazla bir düğüm (node) girsin." Örnek: aynı faturayı iki kez işlememek, aynı dosyayı iki worker'ın aynı anda yeniden yazmaması.
- **Leader election (liderlik seçimi):** "Bir küme (cluster) içinde belirli bir görevi yalnızca tek bir düğüm üstlensin; o düğüm çökerse başkası devralsın." Örnek: bir cron job'u kümede tek düğümün çalıştırması, bir replikasyon lideri seçimi.

Bu iki problem aslında aynı madalyonun iki yüzüdür: liderlik, "süreli ve devredilebilir tekil sahiplik" demektir; dağıtık kilit de öyle. İkisinin de kalbindeki tehlike **split-brain** (beyin bölünmesi) durumudur: sistemin aynı anda iki düğümü de "lider/kilit sahibi benim" sanmasıdır. Bu makale mekanizmaları, kök nedenleri, doğru kullanım desenlerini ve en sık yapılan hataları savunma odağıyla anlatır.

## Neden Bu Kadar Zor? Kök Nedenler

Dağıtık kilidin zorluğu tesadüf değildir; dört temel gerçekten kaynaklanır.

### 1. Ağ güvenilmezdir (asenkron ağ)

Mesajlar kaybolabilir, gecikebilir, sırası değişebilir ya da geç kopyalanıp tekrar gelebilir. Bir düğüm başka bir düğümden yanıt alamadığında iki olasılığı ayırt edemez: karşı taraf **çöktü mü**, yoksa sadece **yavaş mı** (ya da ağ mı koptu)? Bu ayırt edilemezlik, dağıtık sistemlerin en temel sorunudur.

### 2. Süreçler istediğiniz zaman duraklayabilir

Bir süreç, tam kilidi aldıktan sonra ama kritik işi yapmadan önce durabilir:

- **Stop-the-world GC duraklaması:** JVM ya da başka bir çalışma zamanı, çöp toplama için süreci saniyelerce dondurabilir.
- **İşletim sistemi zamanlaması:** Aşırı yüklü bir makinede süreç CPU'dan uzun süre çekilebilir.
- **Sanal makine askıya alması (VM pause), disk I/O beklemesi, sayfa hatası (page fault).**

Sonuç: süreç "sadece 10 milisaniye sürer" sandığı bir aralıkta 30 saniye durabilir. Bu sırada kilidin kira süresi (lease) dolar, kilit başkasına verilir, ama duraklamış süreç uyandığında hâlâ "kilit bende" zannederek işini yapmaya çalışır.

### 3. Saatler güvenilmezdir (clock skew ve drift)

Farklı makinelerin saatleri birbirinden kayar (skew) ve farklı hızlarda ilerler (drift). NTP düzeltmesi saati ileri ya da **geri** sıçratabilir. Monotonik olmayan bir saate dayanarak "kira süresi doldu mu" kararı vermek tehlikelidir. Kira süreleri, mümkünse duvar saatine (wall clock) değil, monotonik saate göre ölçülmelidir.

### 4. Kısmi çökme (partial failure)

Tek makinede program ya tamamen çalışır ya tamamen çöker. Dağıtık sistemde bazı düğümler çalışırken bazıları çöker, bazı bağlantılar kopar. Kilit servisinin kendisi de bu kurala tabidir.

Bu dört gerçek yüzünden **"kilidi aldım" ile "kilidi hâlâ ve gerçekten elimde tutuyorum" arasında bir uçurum** vardır. İyi bir tasarım bu uçurumu kapatmaya değil, uçuruma rağmen **doğruluğu korumaya** çalışır. İşte fencing token'ların doğduğu yer burasıdır.

## İki Farklı Kilit Amacı: Verimlilik vs Doğruluk

Kilit istemenizin nedeni doğru mekanizmayı belirler.

- **Verimlilik (efficiency) için kilit:** Aynı işi iki kez yapmamak *işe yarasa iyi olur* ama iki kez yapılırsa felaket olmaz (sadece boşa CPU/masraf). Örnek: pahalı bir hesaplamanın önbelleğini bir kez üretmek. Burada nadir bir yanlış-pozitif kabul edilebilir; tek düğümlü basit bir Redis kilidi yeterli olabilir.
- **Doğruluk (correctness) için kilit:** İki düğüm aynı anda girerse veri bozulur, çift ödeme olur, tutarlılık ihlal edilir. Burada **hiçbir** split-brain kabul edilemez. Bu durumda kilidin tek başına yeterli olmadığını, fencing gerektiğini varsaymalısınız.

Bu ayrımı baştan yapmak, hangi karmaşıklığa katlanacağınızı belirler.

## Redis Tabanlı Kilitler ve Redlock Tartışması

### Tek örnekli (single-instance) basit kilit

En yaygın desen, Redis'te atomik bir "yoksa oluştur" komutuyla anahtar koymaktır:

```
SET kilit_adi <benzersiz_deger> NX PX 30000
```

- `NX`: anahtar yoksa yaz (varsa başarısız). Bu, "kilidi al" adımını **atomik** yapar.
- `PX 30000`: 30 saniyelik son kullanma süresi (kira). Sahip çökerse kilit otomatik serbest kalır, sonsuza kadar takılı kalmaz.
- `<benzersiz_deger>`: her istemcinin ürettiği rastgele/benzersiz jeton. Kilidi **sadece kendi** koyanın açabilmesi için gereklidir.

**Kilidi serbest bırakırken kritik nokta:** Doğrudan `DEL kilit_adi` yapmak yanlıştır. Kira dolmuş, kilit başkasına geçmiş olabilir; siz gecikmeli olarak başkasının kilidini silersiniz. Doğrusu, "değer hâlâ benimse sil" işlemini **atomik** yapmaktır. Bu, tek komutla yapılamadığı için genelde bir Lua script ile "değeri kontrol et, eşitse DEL et" mantığı sunucu tarafında atomik çalıştırılır.

Bu desen basit, hızlı ve verimlilik amaçlı kilitler için iyidir. Ama tek Redis örneği tek bir başarısızlık noktasıdır (single point of failure). Ayrıca Redis'in varsayılan çoğaltması **asenkron**tur: master kilidi kabul edip, replikaya yaymadan çökebilir; yeni master'da kilit yoktur ve başka istemci onu alabilir. Bu, split-brain penceresidir.

### Redlock algoritması

Redlock, bu tek nokta sorununu çözmek için önerilen bir algoritmadır: birbirinden bağımsız N (örneğin 5) Redis örneğinde aynı kilidi almaya çalışırsınız, çoğunluktan (N/2+1) belirli bir süre içinde kilidi alabilirseniz kilidi kazanmış sayılırsınız; alınan süreden ağ gidiş-geliş gecikmesini düşerek geçerli kira süresini hesaplarsınız.

**Redlock etrafındaki ünlü tartışma:** Bu algoritmanın **doğruluk (correctness) amaçlı kilitler için güvenli olup olmadığı** ciddi biçimde eleştirilmiştir (bu eleştiri dağıtık sistemler literatüründe iyi bilinir). Temel itirazlar:

1. **Zamanlama varsayımlarına bağımlılık:** Redlock'un güvenliği, süreçlerin ve saatlerin "makul" davranmasına dayanır. Ama yukarıda saydığımız GC duraklaması, saat sıçraması ve zamanlama gecikmeleri bu varsayımları bozar. Sınırlı gecikme (bounded delay) varsaymayan asenkron bir modelde Redlock'un doğruluğu garanti edilmez.
2. **Fencing sağlamaması:** Redlock, sıralı ve monoton artan bir jeton üretmez. Dolayısıyla aşağıda anlatacağımız fencing korumasını kendi başına vermez. Duraklamış eski bir sahip uyanıp yazma yaparsa, kilit servisi bunu durduramaz.

Pratik sonuç: **Verimlilik** amaçlı kilitlerde tek örnekli Redis (ya da Redlock) genelde yeterlidir ve pragmatik bir tercihtir. **Doğruluk** kritikse, ya güçlü tutarlılık sağlayan bir uzlaşma (consensus) sistemine geçin ya da mutlaka **fencing token** ile paylaşılan kaynağı koruyun. Kilit servisinin tek başına doğruluğu garanti ettiğini varsaymayın.

## ZooKeeper / etcd Tabanlı Kilitler ve Liderlik

ZooKeeper, etcd ve Consul gibi sistemler, altlarında bir uzlaşma protokolü (ZooKeeper'da ZAB, etcd'de Raft) çalıştırır. Bu protokoller, çoğunluk (quorum) ile linearizable (doğrusallaştırılabilir) bir tutarlılık sunar. Bu, kilit için güçlü bir zemindir.

### ZooKeeper'da tipik kilit / liderlik deseni

ZooKeeper'ın iki özelliği bu problemi zarif çözer:

- **Ephemeral node (geçici düğüm):** Bir istemci bir ephemeral znode oluşturur. İstemcinin oturumu (session) koparsa (çökme, ağ kesintisi, uzun duraklama) ZooKeeper bu düğümü **otomatik siler**. Böylece "sahip yaşıyor mu" sorusu, ayrı bir kira/kalp atışı (heartbeat) mekanizmasına gerek kalmadan oturum canlılığına bağlanır.
- **Sequential node (sıralı düğüm):** Oluşturulan düğüme monoton artan bir sıra numarası eklenir.

Kilit/liderlik deseni şöyledir: her aday `/kilit/lock-` ön ekiyle bir **ephemeral sequential** düğüm yaratır. En küçük sıra numarasına sahip aday kilidi/liderliği kazanır. Diğerleri, yalnızca kendilerinden **bir küçük** düğümü izler (watch); o düğüm silinince tekrar değerlendirme yapılır. Böylece herkesin herkesi izlediği "sürü etkisi" (herd effect) önlenir.

Bu desenin gücü: sahip çökünce ephemeral düğüm silinir ve devir otomatik olur. Zayıflığı: **oturum ifadesi (session expiry) hâlâ zamanlamaya bağlıdır.** Uzun bir GC duraklaması, istemcinin kalp atışını kaçırmasına ve ZooKeeper'ın oturumu ölü ilan edip düğümü silmesine yol açabilir; ama duraklamış istemci uyandığında hâlâ "lider benim" sanabilir. Yani **linearizable bir kilit servisi bile, istemci tarafındaki duraklamaları çözmez.** Bu yüzden burada da fencing gerekir.

## Fencing Token: Split-Brain'e Karşı Asıl Savunma

### Fikir

Fencing token, kilit servisinin her kilit devri (grant) sırasında verdiği **monoton artan** (asla azalmayan) bir sayıdır. Kritik olan, kilidin *ne kadar güvenilir olduğu* değil; **korunan kaynağın bu jetonu kontrol etmesidir.**

Akış şöyledir:

1. İstemci kilit servisinden kilidi alır ve token = 33 alır.
2. İstemci, korunan kaynağa (veritabanı, dosya deposu, satır sunucusu) yazarken bu jetonu da gönderir: "yaz, token=33".
3. Kaynak, gördüğü **en yüksek** jetonu hatırlar. Gelen jeton, daha önce gördüğü en yüksekten **küçükse yazmayı reddeder.**

Şimdi split-brain senaryosunu düşünelim: 33 numaralı jetonu alan istemci uzun bir GC duraklamasına girer, kira dolar, kilit yeni bir istemciye token=34 ile verilir. 34'lü istemci `token=34` ile yazar; kaynak "en yüksek gördüğüm = 34" der. Sonra duraklamış eski istemci uyanır ve `token=33` ile yazmaya çalışır. Kaynak `33 < 34` olduğu için **reddeder.** Split-brain yazması engellenmiş olur.

### Neden bu kadar kritik?

Fencing, doğruluğu **kilit servisinin mükemmelliğine değil, kaynağın basit bir kontrolüne** taşır. Kilit servisi yanlışlıkla iki sahibe kilit verse bile, kaynak sadece en yüksek jetonu kabul ederek doğruluğu korur. Bu yüzden doğruluk kritik sistemlerde fencing, "olsa iyi olur" değil, **olmazsa olmazdır.**

### Fencing token'ı nereden alırsınız?

- **ZooKeeper:** znode'ların `zxid` ya da sıra numarası gibi monoton artan alanları jeton olarak kullanılabilir.
- **etcd:** anahtarların revizyon numarası (revision) monoton artar; jeton olarak uygundur.
- Genelde uzlaşma tabanlı sistemler doğal olarak böyle bir monoton sayı sunar. Redlock'un fencing sağlamaması, doğruluk için başlıca eleştiri noktasıydı.

**Uyarı:** Fencing yalnızca **korunan kaynak jetonu kontrol edebiliyorsa** işe yarar. Yazdığınız sistem (ör. eski bir dosya deposu, jeton kavramı olmayan bir API) reddetme yapamıyorsa, fencing'i tam olarak uygulayamazsınız. Bu durumda kaynağı jeton kontrol edecek şekilde bir katmanla sarmak (ör. koşullu yazma / compare-and-set) gerekir.

## Doğru Kullanım Desenleri

- **Amacı netleştir:** Verimlilik mi, doğruluk mu? Doğruluksa fencing planla.
- **Kira (lease) + otomatik serbest bırakma:** Kilitler mutlaka son kullanma süresine sahip olmalı ki çöken sahip kilidi sonsuza kadar tutmasın. Ama kira süresini "iş kesin biter" gibi kısa değil, güvenli bir pay bırakacak kadar uzun seç; yine de fencing'e güven, kira süresinin doğruluğu garanti ettiğini varsayma.
- **Sahiplik doğrulaması ile serbest bırakma:** "Değer benimse serbest bırak" işlemini atomik yap (Redis'te Lua ile). Asla körlemesine `DEL` etme.
- **Monoton saat kullan:** Kira süresi ölçümünü mümkünse monotonik saate dayandır, duvar saatine değil.
- **Doğruluk kritikse uzlaşma sistemi kullan:** ZooKeeper/etcd/Consul gibi quorum tabanlı, linearizable sistemleri tercih et.
- **İdempotentlik:** İşlemleri idempotent (tekrarlansa da sonucu değiştirmeyen) yap. Böylece nadir bir çift-çalışma bile zarar vermez. Bu, kilide olan bağımlılığı azaltan en güçlü savunmadır.
- **Liderlik seçiminde tek liderin yeterli olmadığını bil:** Seçilen lider dış dünyaya yazarken yine fencing jetonu taşımalı.

## Yaygın Hatalar ve Tuzaklar

- **Kilit = doğruluk garantisi sanmak.** Kilit servisi mükemmel bile olsa, istemci duraklamaları split-brain açar. Fencing olmadan doğruluk garanti değildir.
- **Redlock'u fencing yerine koymak.** Redlock çoklu örnekle dayanıklılık artırır ama sıralı jeton üretmez; doğruluk için tek başına yeterli varsayılmamalıdır.
- **Kira süresini çok kısa vermek.** GC duraklaması ya da ağ gecikmesi kira süresini aşarsa, sağlıklı bir sahip bile kilidini kaybeder ve iki sahip oluşur. Fencing yoksa bu tehlikelidir.
- **Serbest bırakırken sahipliği kontrol etmemek.** Gecikmeli bir istemcinin, çoktan başkasına ait olan kilidi silmesi klasik hatadır.
- **Asenkron çoğaltmaya güvenmek.** Master kabul edip replikaya yaymadan çökerse kilit "kaybolur" ve çift verilir. Doğruluk için güçlü tutarlılık şart.
- **Duvar saatine dayanmak.** NTP sıçramaları kira mantığını bozar.
- **Herd effect'i görmezden gelmek.** ZooKeeper'da herkesin tek düğümü izlemesi, devir anında binlerce uyanmaya yol açar; her aday yalnızca kendinden bir öncekini izlemeli.
- **Kilit servisini kendisi tek başarısızlık noktası yapmak.** Kilit altyapısının kendi yüksek erişilebilirliğini (HA) tasarlamayı unutmak.
- **İdempotentliği atlamak.** Sistemi kilidin kusursuzluğuna bağımlı kılmak; oysa idempotent tasarım en sağlam güvenlik ağıdır.

## Tespit ve İzleme (Savunma Açısından)

Split-brain'i erken yakalamak için:

- **Reddedilen düşük jeton sayısını izle:** Kaynak, eski (küçük) jeton reddettiğinde bunu logla ve metrik olarak yay. Bu reddetmeler artıyorsa, sık split-brain ya da aşırı duraklama var demektir.
- **Aynı görevin çift çalıştığını gösteren sinyaller:** Aynı kaynağa aynı zamanda iki farklı sahip kimliğinden gelen yazma denemeleri.
- **Kira yenileme başarısızlıkları ve oturum ifadeleri:** ZooKeeper/etcd oturum kayıpları ve yeniden seçim (re-election) sıklığı, altta yatan GC/ağ sorunlarının habercisidir.
- **GC duraklama süreleri ve saat kayması:** Uygulama düğümlerinde uzun GC duraklamalarını ve NTP sıçramalarını izlemek, kök nedeni işaret eder.

## Özet

Dağıtık kilitleme ve liderlik seçimi, ağın güvenilmezliği, süreç duraklamaları, saat kaymaları ve kısmi çökmeler yüzünden zordur. Tek örnekli Redis kilitleri basit ve verimlilik amaçlı işler için pragmatiktir; Redlock dayanıklılığı artırır ama doğruluk için tartışmalıdır ve fencing sağlamaz. ZooKeeper/etcd gibi uzlaşma tabanlı sistemler linearizable ve güçlü bir zemin sunar, yine de istemci tarafı duraklamalarını çözmez. Split-brain'e karşı asıl ve taşınabilir savunma **fencing token**'dır: monoton artan bir jetonu korunan kaynağın kontrol etmesi. Buna idempotent tasarım, kira temelli otomatik serbest bırakma, atomik sahiplik doğrulaması ve iyi izleme eklendiğinde, dağıtık kilit doğruluğu pratikte sağlanabilir hâle gelir.
