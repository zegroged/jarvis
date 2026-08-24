# Ağ Programlama: Soket API, Non-blocking I/O ve Olay Bildirim Mekanizmaları (epoll/io_uring)

## Giriş: Bu Konu Neden Kritik

Modern yazılımın neredeyse tamamı ağ üzerinden konuşur; ama çoğu geliştirici bu iletişimi yüksek seviye kütüphaneler (HTTP client, ORM, RPC framework) arkasından görür ve altındaki mekanizmayı hiç görmez. Bu, iki ayrı yeteneği köreltir: (1) performans mühendisliği — bir sunucunun neden 10.000 eşzamanlı bağlantıda çöktüğünü, neden CPU'nun %90'ının "sistem" zamanında harcandığını anlayamama; (2) güvenlik mühendisliği — özel TCP client/server yazamama, ham paket seviyesinde neyin mümkün olduğunu (ve neyin tespit edilebilir olduğunu) kavrayamama. Soket API, thread-per-connection modelinin neden ölçeklenmediğini, non-blocking I/O'nun bunu nasıl çözdüğünü ve epoll/io_uring gibi mekanizmaların neden var olduğunu anlamak, hem "neden yavaş" hem "neden savunmasız" sorularının ortak kökenidir.

Bu makale bir saldırı kılavuzu değildir. Amaç, düşük seviye ağ I/O'sunun çalışma mantığını öğrenip bunu **performans tasarımı** ve **savunma/tespit** perspektifinden okumaktır.

## Soket API: Temel Soyutlama

### Soket nedir, kök neden ne

İşletim sistemi çekirdeği, ağ kartından gelen paketleri TCP/IP yığınında işler ve bir bağlantıyı temsil eden veri yapısını (TCB — Transmission Control Block, ya da UDP için basit bir endpoint kaydı) tutar. Uygulama programı bu çekirdek durumuna doğrudan erişemez; POSIX soket API'si (`socket()`, `bind()`, `listen()`, `accept()`, `connect()`, `send()`/`recv()`, `close()`) bu duruma erişmek için bir **dosya tanımlayıcısı (file descriptor)** soyutlaması sunar. Unix felsefesinin "her şey bir dosyadır" ilkesi burada da geçerlidir: bir soket, `read()`/`write()` ile de kullanılabilen bir fd'dir.

Kök neden şudur: ağ I/O'su doğası gereği **asenkron ve öngörülemez gecikmelidir** — bir `recv()` çağrısı karşı taraf hiç veri göndermezse süresiz bekleyebilir. Çekirdek bu belirsizliği bir kuyruk (receive buffer) ve bir bildirim mekanizmasıyla yönetir; soket API bu kuyruğa erişim ve bildirim alma sözleşmesidir.

### TCP soket yaşam döngüsü

Sunucu tarafı: `socket()` → `bind()` (adres/port ata) → `listen()` (backlog kuyruğu oluştur, SYN'leri kabul etmeye başla) → `accept()` (tamamlanmış üç yollu el sıkışmadan yeni bir bağlantı fd'si çek). İstemci tarafı: `socket()` → `connect()` (SYN gönder, SYN-ACK bekle, ACK gönder).

Kritik ayrıntı: `listen()` çağrıldığında çekirdek **iki kuyruk** tutar — SYN alınmış ama el sıkışma tamamlanmamış bağlantılar için "yarı açık" kuyruk (SYN queue) ve el sıkışması tamamlanmış ama henüz `accept()` edilmemiş bağlantılar için "tamamlanmış" kuyruk (accept queue). Bu ayrım, hem performans hem güvenlik açısından önemlidir: SYN queue'nun taşması **SYN flood** saldırısının hedefidir (savunma: SYN cookies — çekirdek durumu tutmadan, ACK'teki bilgiden bağlantı parametrelerini yeniden türetir); accept queue'nun taşması ise uygulamanın `accept()` çağırmakta yavaş kaldığının (backpressure biriktiğinin) işaretidir.

### UDP: bağlantısız model

UDP'de `connect()` isteğe bağlıdır ve gerçek bir el sıkışma başlatmaz — sadece varsayılan hedef adresi kaydeder. Her `sendto()`/`recvfrom()` bağımsız bir datagramdır; sıra garantisi, teslim garantisi, akış kontrolü yoktur. Bu, DNS, QUIC'in temeli, oyun ağı protokolleri gibi düşük gecikme gerektiren ve uygulamanın kendi güvenilirlik katmanını kurmayı tercih ettiği senaryolarda tercih edilir.

## Blocking I/O'nun Ölçeklenme Problemi

### Thread-per-connection modeli ve neden çöker

En basit sunucu modeli: her yeni bağlantı için bir thread/process ayır, o thread `recv()`'de bloklanarak veri bekler. Bu model küçük ölçekte doğru çalışır ama kök neden şudur: **thread'ler pahalıdır**. Her thread bir çekirdek yığını (genelde 1-8 MB sanal adres alanı, gerçekte daha az fiziksel commit ama yine de context switch maliyeti taşır) tüketir; binlerce eşzamanlı boşta-bekleyen bağlantı, çoğu zaman hiçbir iş yapmayan binlerce thread'i zamanlayıcıda tutmak anlamına gelir. Bu, C10K problemi olarak bilinir (aynı anda 10.000 bağlantıyı verimli yönetememe).

Semptomlar: yüksek context-switch oranı, cache thrashing (her switch'te CPU cache'i soğur), bellek baskısı, zamanlayıcı overhead'i. Sonuç: CPU kullanıcı kodunda değil, çekirdek zamanlayıcısında ve context switch'te harcanır — "sistem zamanı yüksek ama iş yapılmıyor" belirtisi budur.

### Neden non-blocking I/O gerekli

Çözüm iki eksende ilerler: (1) bir thread'in aynı anda **çok sayıda** soketi yönetmesini sağlamak, (2) bir soket hazır olmadığında thread'i bloklamak yerine ona haber vermek. Bunun için soket, `fcntl(fd, F_SETFL, O_NONBLOCK)` ile non-blocking moda alınır. Bu modda `recv()`/`send()`/`accept()` veri hazır değilse hemen `EAGAIN`/`EWOULDBLOCK` hatasıyla döner, bloklamaz.

Ama tek başına non-blocking mod yetmez: thread artık "hangi soket hazır?" sorusunu bilmeden sürekli her fd'yi sırayla deneyip (**busy-polling/spinning**) CPU'yu boşa yakabilir. Bu yüzden non-blocking I/O, mutlaka bir **olay bildirim (event notification)** mekanizmasıyla eşleşmelidir: "bana hangi fd'lerin hazır olduğunu söyle, ben de sadece onları işleyeyim."

## Olay Bildirim Mekanizmaları: select → poll → epoll → io_uring

Bu evrim, aynı problemin (çok sayıda fd'yi verimli izleme) giderek daha ölçeklenebilir çözümlerini temsil eder.

### select()

En eski API. Çağırana üç fd_set (read/write/exception) verilir, çekirdek her seferinde **tüm set'i baştan sona tarar** ve hangilerinin hazır olduğunu işaretler. İki temel sınırlama: (1) fd_set sabit boyutludur (genelde `FD_SETSIZE=1024`), bu da bağlantı sayısını sert şekilde sınırlar; (2) her çağrıda kullanıcı alanı → çekirdek alanı arasında **tüm fd listesi kopyalanır** ve çekirdek O(n) tarama yapar — n binlerce olduğunda bu maliyet baskındır.

### poll()

`select()`'in sabit boyut sınırını kaldırır (dinamik `pollfd` dizisi), ama temel algoritmik sorun aynıdır: her çağrıda **tüm liste** kullanıcı-çekirdek arasında kopyalanır ve O(n) taranır. n bağlantı sayısı arttıkça (C10K senaryosu) bu O(n) maliyet her olay döngüsü turunda tekrar ödenir — toplamda O(n) çağrı sıklığıyla çarpıldığında pratikte O(n²) davranışa yaklaşır.

### epoll (Linux)

Kök fikir: **durumu çekirdekte tut, her seferinde yeniden gönderme**. `epoll_create()` bir epoll örneği (fd) oluşturur; `epoll_ctl()` ile fd'ler bu örneğe bir kez eklenir/çıkarılır/güncellenir; `epoll_wait()` sadece **hazır olan** fd'lerin listesini döndürür. İzlenen fd seti çekirdekte (kırmızı-siyah ağaç benzeri bir yapıda) kalıcı olarak tutulur, her `epoll_wait()` çağrısında yeniden gönderilmez. Bu, O(1)'e yakın amortize maliyet sağlar — hazır fd sayısı m ise maliyet O(m), izlenen toplam fd sayısı n'den bağımsızdır.

İki mod: **level-triggered (LT)** — soket hazır olduğu sürece her `epoll_wait()` onu bildirir (veri okunmazsa tekrar tekrar bildirir, unutmaya karşı güvenlidir, varsayılan ve daha kolay doğru kullanılır); **edge-triggered (ET)** — sadece durum **değiştiğinde** bir kez bildirir (`EPOLLET` bayrağı). ET modunda kritik kural: bildirim geldiğinde soketten **`EAGAIN` alana kadar döngüyle okumak/yazmak** zorunludur; aksi halde buffer'da kalan veri bir daha asla bildirilmeyebilir ve bağlantı "askıda" kalır — bu, ET kullanan kodlarda en yaygın hatadır.

BSD/macOS dünyasında eşdeğeri **kqueue**'dur; kavramsal olarak aynı çözümü sunar (kalıcı çekirdek tarafı ilgi listesi + değişen olayların bildirimi), ayrıca dosya sistemi olayları, sinyaller, timer'lar gibi soket-dışı olayları da tek bir arayüzde birleştirir.

### io_uring (Linux, daha yeni)

epoll hâlâ bir sınırı aşamaz: gerçek `read()`/`write()` sistem çağrıları, "hazır" bildirimi alındıktan **sonra** ayrıca yapılmalıdır — her G/Ç işlemi hâlâ ayrı bir sistem çağrısı ve kullanıcı/çekirdek geçişi (context switch, ring buffer'a kopyalama değil) maliyeti taşır. io_uring, kök nedeni doğrudan hedefler: kullanıcı alanı ve çekirdek arasında **paylaşımlı halka buffer'lar (submission queue - SQ ve completion queue - CQ)** kurar. Uygulama bir G/Ç isteğini SQ'ya yazar (sistem çağrısı gerekmeden, paylaşımlı bellek üzerinden), çekirdek işi tamamlayınca sonucu CQ'ya yazar; `io_uring_enter()` sistem çağrısı sadece toplu senkronizasyon/uyandırma için gerekir, mümkünse o da atlanabilir (polling modları). Bu, hem "hazır mı?" bildirimini hem de gerçek veri transferini **tek bir asenkron model** altında birleştirir ve sistem çağrısı başına maliyeti (özellikle yüksek IOPS senaryolarında, ağ ve disk I/O'sunu ortak çatı altında) ciddi biçimde azaltır. Bedelı: daha karmaşık programlama modeli ve (ilk sürümlerinde) bazı güvenlik/izolasyon tartışmaları — bu yüzden bazı sıkı-güvenlikli ortamlar (konteyner sandbox'ları) io_uring'i varsayılan olarak kısıtlar/devre dışı bırakır, çünkü çekirdek arayüzü seccomp gibi sistem-çağrısı-filtreleme mekanizmalarını kısmen atlatabilir.

## Backpressure ve Buffer Yönetimi

### Kök neden: hız uyumsuzluğu

Backpressure, üretici (gönderen taraf ya da hızlı istemci) ile tüketici (alıcı taraf ya da yavaş işleyen sunucu) arasındaki hız farkının yönetilmesidir. TCP bunu protokol seviyesinde **akış kontrolü (flow control)** ile çözer: alıcı, kendi receive buffer'ında ne kadar boş yer olduğunu **window size** alanıyla gönderene bildirir; gönderen bu pencereyi aşamaz. Alıcı uygulama veriyi okumazsa (yavaşsa ya da tıkanmışsa) buffer dolar, window sıfıra iner ("zero window"), gönderen durur. Bu, çekirdek seviyesinde otomatik ama uygulama seviyesinde **görünmez** bir mekanizmadır — uygulama kendi buffer'larını da yönetmezse bu koruma tek başına yetmez.

### Uygulama seviyesinde buffer yönetimi tuzakları

1. **Sınırsız kuyruklama:** Non-blocking `send()` `EAGAIN` döndüğünde (çekirdek gönderim buffer'ı dolu), naif kod veriyi kendi kullanıcı-alanı kuyruğuna sınırsız biriktirir. Yavaş bir istemci varsa bu kuyruk sınırsız büyür → bellek tükenmesi. Doğru yaklaşım: kuyruğa üst sınır koymak, sınır aşılınca ya bağlantıyı kesmek ya da üretimi yavaşlatmak (uygulama seviyesi backpressure sinyali).
2. **Kısmi okuma/yazma varsayımı:** `recv()`/`send()` istenen byte sayısının **tamamını** işlemek zorunda değildir; dönüş değeri her zaman kontrol edilmeli ve kalan veri için döngü kurulmalıdır. Bunu atlamak, mesaj sınırlarının bozulmasına (TCP bir byte akışıdır, mesaj sınırı korumaz) yol açan klasik bir hatadır.
3. **Buffer boyutu ve okuma stratejisi:** Çok küçük okuma buffer'ı → çok fazla sistem çağrısı (throughput düşer); çok büyük → bellek israfı, çok sayıda eşzamanlı bağlantıda toplam bellek patlar (n bağlantı × buffer boyutu). Yaygın çözüm: dinamik boyutlandırma ya da havuzlanmış (pooled) buffer'lar.
4. **Nagle algoritması ve gecikme etkileşimi:** Küçük paketleri biriktirip tek seferde gönderen Nagle algoritması, gecikmeye duyarlı protokollerde (ör. etkileşimli oturumlar) beklenmedik gecikme yaratabilir; `TCP_NODELAY` ile kapatılabilir ama bu durumda küçük paket sayısı artar — throughput/latency ödünleşimi bilinçli yapılmalı.

### Neden önemli: DoS yüzeyi

Backpressure'ı yanlış yönetmek, kasıtlı saldırı olmasa bile bir kendi-kendine-DoS (self-inflicted DoS) yaratır: yavaş istemciler ya da art arda bağlantılar, sınırsız kuyruklar üzerinden sunucu belleğini tüketebilir. Bu aynı zamanda kasıtlı saldırıların da temel vektörüdür (bkz. aşağıdaki Slowloris örneği) — savunma mantığı ikisinde de aynıdır: kaynak tüketimine **sert üst sınır** koymak.

## Saldırı Yüzeyleri ve Tespit/Savunma Perspektifi

Bu bölüm, mekanizmayı anlayan bir savunmacının bakış açısıyla yazılmıştır; amaç saldırı üretmek değil, hangi zayıflığın hangi savunma karşılığı olduğunu netleştirmektir.

### SYN flood

Saldırgan, ACK'i hiç tamamlamadan çok sayıda SYN gönderir; sunucunun SYN queue'su (yarı-açık bağlantı durumu tutan çekirdek belleği) dolar, meşru bağlantılar reddedilir. **Savunma**: SYN cookies (çekirdek, bağlantı durumunu saklamak yerine SYN-ACK'in sıra numarasına kriptografik olarak kodlar; ACK geri geldiğinde bu bilgiden durumu yeniden türetir — böylece "durum tutmadan" el sıkışmayı doğrulama mümkün olur). **Tespit**: SYN/ACK oranındaki ani sapma, `netstat` çıktısında SYN_RECV durumundaki bağlantı sayısının anormal artışı izlenebilir.

### Slowloris tipi yavaş bağlantı tüketimi

Saldırgan, bağlantıları açık tutup veriyi kasıtlı olarak çok yavaş gönderir (ör. HTTP header'ları byte byte); her bağlantı bir thread/kaynak tutar, thread-per-connection modelinde havuz hızla tükenir. **Kök neden**: uygulamanın bağlantı başına zaman aşımı ve eşzamanlı bağlantı sınırı koymaması. **Savunma**: bağlantı/istek başına kesin timeout, tamamlanmamış istekler için ayrı ve düşük kaynak sınırı, ters proxy katmanında (ör. yük dengeleyici) bağlantı biriktirme.

### Ham soket (raw socket) farkındalığı

Raw socket API (`SOCK_RAW`), uygulamanın IP/TCP başlıklarını elle oluşturmasına izin verir (genelde yükseltilmiş yetki gerektirir). Bu yetenek, ağ tanılama araçları (ping, traceroute'un ICMP kullanımı) için meşrudur ama aynı zamanda başlık sahteciliği (spoofing) için de teknik temel sağlar. **Savunma tarafı çıkarımı**: kaynak IP'ye güvenmemek (özellikle UDP tabanlı protokollerde), giriş/çıkış filtrelemesi (BCP38 tipi egress filtering — bir ağın kendi olmayan kaynak adresli paketleri dışarı bırakmaması), ve anormal paket başlığı desenlerini (TTL tutarsızlığı, beklenmeyen bayrak kombinasyonları) izleyen IDS kuralları.

### Non-blocking hatalarının güvenlik yansımaları

`EAGAIN`'i yanlış yorumlayıp veriyi sıfır byte olarak işlemek, kısmi okumaları mesaj sınırı sanmak gibi mantık hataları, protokol ayrıştırıcılarında (parser) bellek bozulması ya da mantık atlaması (request smuggling benzeri sınıf sorunlar HTTP katmanında ortaya çıkar) riskini artırır. Düşük seviye soket kodunun doğruluğu, üstündeki protokol katmanının güvenliğinin ön koşuludur.

## En İyi Pratikler Özeti

- Her zaman non-blocking I/O'yu bir olay bildirim mekanizmasıyla (epoll/kqueue, ya da io_uring'in tamamlama modeliyle) eşleştirin; asla busy-poll yapmayın.
- Edge-triggered modda mutlaka `EAGAIN`'e kadar döngüyle okuyun/yazın.
- Her `send()`/`recv()` dönüş değerini kontrol edin; kısmi işlemleri normal kabul edip döngü kurun.
- Kullanıcı-alanı kuyruklarına (giden veri, bekleyen bağlantı, ayrıştırma tamponu) her zaman üst sınır koyun; sınırsız büyüme bir tasarım hatasıdır.
- Bağlantı başına ve istek başına açık timeout tanımlayın; sonsuz bekleme kabul etmeyin.
- Yüksek eşzamanlılık hedefliyorsanız thread-per-connection yerine olay döngüsü (event loop) + non-blocking I/O ya da hafif eşzamanlılık birimleri (yeşil thread/coroutine üstünde epoll tabanlı zamanlayıcı) kullanın.
- SYN flood, yavaş bağlantı ve kaynak tükenmesi senaryolarına karşı hem çekirdek seviyesi korumaları (SYN cookies, bağlantı sınırları) hem uygulama seviyesi sınırları birlikte devreye alın.
- io_uring gibi yeni ve güçlü çekirdek arayüzlerini üretime almadan önce, çalıştığı ortamın izolasyon/güvenlik varsayımlarıyla (konteyner, sandbox, seccomp politikaları) uyumluluğunu değerlendirin.

## Sonuç

Soket API'den io_uring'e uzanan çizgi, tek bir kök problemin tekrar tekrar çözülmesidir: **çok sayıda yavaş, öngörülemez G/Ç kaynağını, sınırlı işlemci ve bellek kaynağıyla verimli şekilde yönetmek**. select/poll'un O(n) taraması, epoll'un kalıcı ilgi listesiyle O(1)'e yaklaşması, io_uring'in sistem çağrısı maliyetini paylaşımlı halka buffer'larla neredeyse sıfırlaması — hepsi aynı ekonomik baskının (context switch ve kopyalama maliyeti) farklı seviyelerde çözümüdür. Bu mekanizmayı anlamak, hem bir sunucunun neden 10.000 bağlantıda diz çöktüğünü teşhis etmeyi hem de SYN flood, Slowloris gibi kaynak tüketim saldırılarının neden işe yaradığını ve hangi savunmanın (SYN cookies, timeout, kaynak sınırı) hangi katmanda devreye girdiğini kavramayı sağlar. Düşük seviye ağ programlaması, performans mühendisliğiyle ağ güvenliğinin kesiştiği noktadır; biri olmadan diğeri eksik kalır.
