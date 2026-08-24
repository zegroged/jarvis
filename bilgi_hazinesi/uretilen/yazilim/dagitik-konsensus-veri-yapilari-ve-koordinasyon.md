# Dağıtık Konsensüs Veri Yapıları ve Koordinasyon Servisleri (ZooKeeper, etcd, Chubby)

## Giriş: Neden Bu Konu Kritik

Dağıtık bir sistemde birden fazla makine aynı gerçekliği paylaşmak zorundadır: "Şu an lider hangi düğüm?", "Bu kaynağın kilidi kimde?", "Konfigürasyon değeri nedir?", "Hangi servis örnekleri şu an sağlıklı ve canlı?" Bu soruların hepsi aslında tek bir problemin farklı yüzleridir: **birden fazla bağımsız süreç, ağ gecikmeleri ve kısmi hatalar altında tek bir doğru üzerinde nasıl anlaşır?** Buna dağıtık konsensüs denir ve teorik olarak FLP imkânsızlık sonucu (asenkron sistemde, tek bir süreç bile çökebiliyorsa, deterministik konsensüsün garanti edilemeyeceğini söyler) yüzünden "çözülemez" görünür. Pratikte ise Paxos ve Raft gibi algoritmalar, zaman aşımları ve rastgelelik ekleyerek pratik sistemlerde çalışan çözümler üretir.

Bu makalenin konusu olan Chubby (Google), ZooKeeper (Apache, Yahoo kökenli) ve etcd (CoreOS, şimdi CNCF), bu teoriyi **ürünleştiren** koordinasyon servisleridir. Önemleri abartı değildir: Kubernetes'in tüm cluster durumu etcd üzerinde tutulur; Hadoop ekosistemi (HDFS NameNode HA, HBase, Kafka'nın eski sürümleri) ZooKeeper'a dayanır; Google'ın iç altyapısının büyük kısmı (GFS master seçimi, Bigtable) Chubby'ye dayanır. Bir mühendis olarak bu servislerin iç mantığını bilmemek, üzerine kurulu her şeyin (service discovery, dağıtık kilitleme, lider seçimi, konfigürasyon dağıtımı) "kara kutu" kalması demektir — hem doğru kullanamazsınız hem de arıza anında ne olduğunu anlayamazsınız.

## Problem Tanımı: Tam Olarak Ne Çözülüyor

Bu servislerin çözdüğü problem sınıfı şudur: küçük miktarda veriyi (genelde birkaç KB — megabaytlarca değil), yüksek tutarlılıkla (strong consistency), yüksek erişilebilirlikle saklamak ve üzerine **koordinasyon primitifleri** (lider seçimi, dağıtık kilit, watch/bildirim mekanizması) inşa etmek. Bunlar bir veritabanı değildir; büyük veri saklamak için tasarlanmamıştır. Amaç "az veri, çok yüksek güvenilirlik" dengesidir.

Kritik bir kavram ayrımı: **CAP teoremi** bağlamında bu sistemler CP'dir (Consistency + Partition tolerance), AP değildir. Yani ağ bölünmesi (network partition) olduğunda azınlıkta kalan taraf, tutarlılığı korumak için erişilebilirlikten feragat eder — yazma isteklerini reddeder veya hiç cevap vermez. Bu, kasıtlı bir tasarım kararıdır: lider seçimi ve dağıtık kilit gibi kullanım senaryolarında "yanlış ama hızlı cevap" felakettir (iki düğüm kendini lider sanabilir — "split brain"), "yavaş ama doğru cevap" kabul edilebilirdir.

## Kök Neden / Çalışma Mantığı

### Neden Basit Bir "Çoğunluk Oylaması" Yetmiyor

Naif yaklaşım şudur: "N düğüm var, bir değeri yazmak için çoğunluğun onayını al." Bu doğru yönde bir adımdır (quorum tabanlı yazma), ama tek başına yetmez çünkü şu sorulara cevap vermez:
- Aynı anda iki düğüm de "ben öneriyorum" derse ne olur (çakışan öneriler)?
- Bir düğüm önce onay verip sonra çöker ve yeniden başladığında ne hatırlar?
- Öneriler farklı sırayla farklı düğümlere ulaşırsa, herkes aynı sırayı nasıl görür?

Paxos (Lamport) ve Raft (Ongaro & Ousterhout) bu soruları çözen algoritmalardır. İkisi de temelde aynı fikri uygular: **her karar bir "dönem/terim" (epoch/term) numarasıyla damgalanır, sadece çoğunluğun kabul ettiği ve en yüksek terime sahip öneri kazanır.** Terim numarası, eski/gecikmiş mesajların yanlışlıkla yeni kararları geçersiz kılmasını engeller — "en son konuşan kazanır" değil, "en yetkili (en yüksek terimli) konuşan kazanır" mantığı işler.

### Raft'ın Somut Mantığı (etcd'nin Temeli)

Raft, Paxos'un anlaşılabilirlik açısından zayıf yönünü hedef alarak tasarlanmıştır (Paxos doğru ama açıklaması/implementasyonu zordur). Üç rol vardır: Leader, Follower, Candidate.

1. **Lider seçimi**: Her follower bir "election timeout" (rastgele, örn. 150-300ms aralığı) bekler. Bu sürede lider'den heartbeat gelmezse, follower kendini Candidate ilan eder, terim numarasını bir artırır, kendine oy verir ve diğerlerinden oy ister (RequestVote RPC). Çoğunluk oyu alan candidate, o terim için Leader olur.
2. **Neden rastgele zaman aşımı**: Eğer tüm düğümler aynı anda timeout olursa, hepsi aynı anda candidate olur, oylar bölünür, kimse çoğunluk alamaz, tekrar dener — sonsuz döngü riski. Rastgelelik bu çakışma olasılığını pratik olarak sıfıra indirir. Bu, FLP imkânsızlığını "aşmanın" pratik yoludur: saf asenkron modelde garanti yoktur ama rastgele zamanlamayla neredeyse her zaman ilerleme (liveness) sağlanır.
3. **Log replikasyonu**: Lider seçildikten sonra tüm yazma istekleri lidere gider. Lider, her isteği kendi log'una ekler, follower'lara AppendEntries RPC ile gönderir. Çoğunluk "kabul ettim" derse, girdi **commit** edilmiş sayılır ve state machine'e uygulanır. Bu "commit önce çoğunluğa yaz, sonra uygula" sırası, bir çökme anında hiçbir onaylanmış (committed) verinin kaybolmamasını garanti eder.
4. **Terim numarası ve log tutarlılığı**: Her log girdisi hangi terimde yazıldığını taşır. Bir follower'ın log'u lider ile uyuşmazsa (örneğin follower geçici olarak koptu ve geride kaldı), lider onun log'unu geriye doğru düzeltir (üzerine yazar) — bu yüzden Raft'ta "en uzun log kazanır" değil, "en yüksek terimli, çoğunluk tarafından onaylı log kazanır" ilkesi geçerlidir.

Bu mekanizmanın kritik sonucu: **linearizability** (doğrusallaştırılabilirlik) — sistem dışarıdan bakıldığında sanki tek bir makineymiş gibi davranır; bir yazma commit olduktan sonra yapılan her okuma o yazmayı (veya sonrasını) görür.

### ZooKeeper'ın Yaklaşımı: ZAB (ZooKeeper Atomic Broadcast)

ZooKeeper, Raft'tan önce (Google Chubby'den ilham alarak) geliştirilmiş, kendi konsensüs protokolü olan ZAB'ı kullanır. Mantık olarak Raft'a çok benzer (lider seçimi, terim/epoch benzeri "zxid" — ZooKeeper transaction id — kullanımı, çoğunluk onayı ile commit) ama iki fazlı bir yayın modeliyle çalışır: normal operasyonda lider, sıralı (FIFO) atomik yayın yapar; lider değişiminde bir kurtarma (recovery) fazı devreye girer ve son commit edilen durumun kaybolmadığından emin olunur.

ZooKeeper'ın veri modeli, dosya sistemine benzer hiyerarşik bir isim uzayıdır (znode ağacı). Üç önemli znode tipi:
- **Persistent**: İstemci kaybolsa da kalır.
- **Ephemeral**: Sadece oluşturan istemcinin session'ı canlı olduğu sürece var olur — bağlantı/session kopunca otomatik silinir. Bu, "canlılık göstergesi" (liveness indicator) olarak lider seçimi ve service discovery'de kullanılır.
- **Sequential**: İsme otomatik artan bir sayı eklenir — sıralı kilit kuyruğu (lock queue) inşa etmek için kullanılır.

**Watch mekanizması**: İstemci bir znode üzerine "watch" koyar; o znode değişince (veya silinince) istemciye tek seferlik bir bildirim gider. Bu, polling yerine event-driven koordinasyon sağlar. Kritik tuzak: watch'lar **tek seferliktir (one-time trigger)** — bildirim aldıktan sonra tekrar izlemek istiyorsanız watch'ı yeniden kurmanız gerekir; bu arada bir olay kaçırma (miss) riski vardır, bu yüzden doğru kullanım "watch kur → tekrar oku → duruma göre karar ver" döngüsüdür, sadece bildirime güvenip son durumu okumadan aksiyon almak hatadır.

### Chubby: Kavramın Öncüsü

Google'ın 2006 makalesinde tanımlanan Chubby, ZooKeeper'a ilham veren sistemdir. Temel fikirleri: küçük dosya benzeri nesneler + kilitler (advisory lock — zorunlu değil, tavsiye niteliğinde; istemcinin kilide "saygı göstermesi" beklenir, OS seviyesinde zorlanmaz), oturum (session) ve "lease" (kiralama) kavramı. Chubby'nin en önemli katkısı, konsensüsü **istemciler için görünmez kılmak**: istemci Paxos'un iç detaylarını bilmeden basit bir dosya/kilit API'siyle konuşur, arka planda 5 replikadan oluşan bir Paxos grubu çalışır (genelde 1 lider + 4 follower, çoğunluk = 3).

### Lease Kavramı: Neden Sadece "Kilit Aldım" Yetmez

Bir düğüm kilit/liderlik aldıktan sonra ağdan kopabilir (GC duraklaması, ağ gecikmesi, disk I/O donması) ama process'i canlı kalabilir. Bu durumda "ben hâlâ liderim" sanarak yazmaya devam edebilir — bu arada sistem yeni bir lider seçmiş olabilir. Buna **"zombi lider" / split-brain** denir. Çözüm **lease (kiralama)** mantığıdır: liderlik/kilit süresiz değil, süreli verilir (örn. 10 saniye) ve düğüm bunu periyodik yenilemek (renew) zorundadır. Yenileyemezse (örn. GC pause yüzünden) lease süresi dolar, başka biri liderliği alabilir.

Burada kritik ve sık atlanan nokta: **saat senkronizasyonu varsayımı**. Lease mekanizması, lideri seçen taraf ile liderliği elinde tutan tarafın saat hızlarının (clock drift) makul sınırlar içinde olduğunu varsayar. Bir düğümde aşırı GC duraklaması (Java'da "stop-the-world" GC) lease süresinden uzun sürerse, düğüm lease'in dolduğunu fark etmeden "ben hâlâ liderim" sanarak eski verilerle yazmaya devam edebilir. Bu yüzden gerçek dünya kullanımında **fencing token** (aşağıda) ek bir güvenlik katmanı olarak şarttır — sadece lease'e güvenmek yeterli değildir.

## Doğru Kullanım Kalıpları

### 1. Lider Seçimi (Leader Election)

Doğru desen (ZooKeeper örneğiyle): Her aday, `/election` altında **ephemeral + sequential** bir znode oluşturur (örn. `/election/node-0000000007`). En küçük sıra numaralı düğüm liderdir. Diğer her düğüm, kendinden bir küçük sıra numaralı düğümü izler (watch), tüm düğümleri değil — bu, "herding effect" (bir düğüm düşünce herkesin aynı anda tetiklenip yeniden oylaşması) problemini önler; sadece bir sonraki sıradaki düğüm harekete geçer.

etcd'de benzer iş, `Lease` + `Compare-And-Swap` (veya resmi `concurrency` paketindeki `Election` API'si) ile yapılır: bir anahtara lease'li yaz, lease süresi boyunca keepalive gönder, kaybedersen anahtar otomatik silinir.

### 2. Dağıtık Kilit (Distributed Lock)

Aynı sequential znode / lease'li anahtar deseni kilit için de kullanılır. **Kritik tuzak — fencing token olmadan kilit kullanmak**: Bir istemci kilidi alır, iş yapmaya başlar, ama GC duraklaması yüzünden lease'i süresinde yenileyemez, kilit başka bir istemciye geçer, ilk istemci "uyanınca" hâlâ kilidi elinde sandığı için işine devam eder — artık iki istemci aynı kaynağa aynı anda yazıyordur. Doğru çözüm: kilit her verildiğinde monoton artan bir **fencing token** (sayaç) üretilir; korunan kaynağa (örn. bir depolama servisine) yazarken bu token gönderilir, kaynak sadece **en yüksek gördüğü token'dan büyük veya eşit** istekleri kabul eder, daha düşük token'lı gecikmiş isteği reddeder. Bu, Martin Kleppmann'ın dağıtık kilit tartışmalarında vurguladığı temel bir güvenlik önlemidir.

### 3. Konfigürasyon Yönetimi ve Service Discovery

Servis örnekleri başlarken kendi adreslerini ephemeral bir anahtar olarak yazar (`/services/orders/instance-3 -> 10.0.1.5:8080`); process ölünce (veya bağlantı kopunca) bu kayıt otomatik silinir — sağlık kontrolü (health check) ile "canlılık"ı senkron tutmak için ek bir mekanizmaya gerek kalmaz. Konfigürasyon değerleri watch ile izlenir; değer değişince ilgilenen tüm servisler bildirim alıp yeni değeri çeker.

**Kubernetes + etcd** somut örneği: Kubernetes API server, cluster'ın tüm durumunu (Pod, Deployment, Service tanımları) etcd'de saklar. `kubectl apply` bir kaynağı günceller → API server bunu etcd'ye yazar (Raft üzerinden çoğunluk onayı ile commit) → controller'lar etcd'yi izleyen "watch" API'si üzerinden değişikliği görür → gerçek durumu istenen duruma getirir (reconciliation loop). etcd çökerse veya çoğunluk kaybedilirse, cluster'da hiçbir yeni değişiklik kabul edilmez (var olan Pod'lar çalışmaya devam eder ama kontrol düzlemi "dondurulur").

## Yaygın Hatalar ve Tuzaklar

**Hata 1 — Bu sistemleri genel amaçlı veritabanı gibi kullanmak.** ZooKeeper/etcd, büyük veri (MB/GB seviyesinde blob, yüksek yazma hacmi) için tasarlanmamıştır. Her yazma çoğunluğa disk'e commit edilene kadar bloklar; yüksek verim (throughput) değil, yüksek tutarlılık ve düşük veri hacmi hedeflenir. Kubernetes'te "çok fazla obje / çok büyük obje" etcd performans sorunlarının klasik nedenidir — bu, gerçek prodüksiyon cluster'larında sıkça karşılaşılan bir operasyonel sorundur.

**Hata 2 — Tek düğümle (single node) "geçici olarak" prod'a çıkmak.** Konsensüs, çoğunluk (quorum) gerektirir; 1 düğümlü kurulum hem tek arıza noktasıdır hem de "dağıtık konsensüs" avantajının hiçbirini sağlamaz. Standart dağıtımlar 3 veya 5 düğümdür (çift sayı önerilmez: 4 düğümde çoğunluk için gereken sayı 3 iken 3 düğümde de çoğunluk 2'dir — çift sayı ekstra dayanıklılık kazandırmadan sadece maliyet ve gecikme ekler; 2f+1 formülü ile f arıza toleransı hesaplanır).

**Hata 3 — "Split brain" senaryosunu yalnızca lease'e güvenerek çözmeye çalışmak.** Yukarıda anlatıldığı gibi fencing token olmadan lease tek başına yeterli güvenlik sağlamaz.

**Hata 4 — Watch'ın "kesintisiz stream" olduğunu varsaymak.** ZooKeeper watch'ları tek seferliktir; ardışık iki olay arasında bağlantı koparsa (session timeout), istemci bazı olayları tamamen kaçırabilir. Doğru pratik: watch tetiklendiğinde her zaman güncel durumu tekrar oku, sadece "bir şey değişti" bilgisine güvenip önceki bilinen duruma göre delta uygulama.

**Hata 5 — Session timeout ayarını yanlış kalibre etmek.** Çok kısa timeout, geçici ağ gecikmelerinde gereksiz yere lider/kilit kaybına (gereksiz failover, "thrashing") yol açar. Çok uzun timeout, gerçek bir arızanın fark edilmesini ve yeni liderin seçilmesini geciktirir — kullanılabilirlik kaybı. Bu, GC duraklama sürelerinizi, ağ RTT'nizi bilerek deneysel kalibre edilmesi gereken bir parametredir; "varsayılanı bırak" kararı üretim ortamına özgü olmayabilir.

**Hata 6 — Okuma tutarlılığı seviyesini karıştırmak.** etcd ve ZooKeeper, performans için "lineárizable read" (lidere gidip quorum onayı ile okuma) yerine daha ucuz "yerel/stale read" seçenekleri de sunabilir (örn. ZooKeeper'da varsayılan okuma, sadece bağlı olunan sunucunun yerel durumunu döner — `sync()` çağrısı olmadan en güncel yazmayı görmeyebilirsiniz). Bir mühendisin hangi okumanın "kesin güncel" hangi okumanın "muhtemelen güncel" olduğunu bilmemesi, ince ve nadir görülen ama ciddi tutarlılık hatalarına yol açar.

## Tespit ve Savunma Perspektifi

Bir savunmacı/operasyon mühendisi açısından izlenmesi gereken sinyaller:

- **Sık lider değişimi (leader churn)**: Loglarda beklenmedik sıklıkta "new leader elected" görülüyorsa, bu genelde ağ instabilitesi, aşırı yüklü disk I/O (commit gecikmesi) veya GC duraklamalarının belirtisidir. Kök nedeni bulmadan sadece timeout'u artırmak, semptomu gizler.
- **Quorum kaybı uyarıları**: Çoğunluk sağlanamıyorsa (örn. 3 düğümden 2'si erişilemez durumda), sistem yazmaları reddeder. Bu, CP tasarımın beklenen davranışıdır — "neden yazamıyorum" panikleyip zorla tek düğümü lider yapmaya çalışmak (manuel müdahale ile quorum'u bypass etmek) veri bütünlüğünü bozabilir; doğru tepki, ağ/altyapı sorununu çözüp çoğunluğu geri getirmektir.
- **Ephemeral node/lease üzerinden "hayalet" kayıtlar**: Bir servis örneği çökmüş ama service discovery kaydı hâlâ görünüyorsa, bu session timeout'un veya health check mekanizmasının yanlış yapılandırıldığına işaret eder — trafiğin ölü örneğe yönlendirilmesi (kısmi kesinti) riski.
- **Yetkilendirme (ACL) denetimi**: ZooKeeper ve etcd'ye erişim genelde sistemin "tüm gerçeği" olduğu için, bu servislere yetkisiz erişim tüm cluster'ı (örn. Kubernetes API server'ın arkasındaki etcd) tehlikeye atabilir. etcd verisi varsayılan olarak şifrelenmeden diskte durabilir (encryption-at-rest ayrıca yapılandırılmalıdır) ve ağ trafiği TLS ile korunmalıdır — bu servisleri "iç ağda olduğu için güvenli" varsaymak, savunma derinliği (defense in depth) ilkesini ihlal eder.
- **Değişiklik denetim izi (audit log)**: Kritik konfigürasyon anahtarlarındaki değişiklikler izlenmelidir; bu servisler genelde "gerçeğin tek kaynağı" olduğundan, buradaki yetkisiz veya yanlışlıkla yapılan bir değişiklik, üzerine kurulu tüm sistemi (örn. tüm Kubernetes cluster'ı) etkiler.

## Sonuç

ZooKeeper, etcd ve Chubby, konsensüs teorisinin (Paxos/Raft/ZAB) somut, kullanılabilir API'lere dönüştürülmüş halidir. Kök mantık her zaman aynıdır: terimli/epoch'lu liderlik, çoğunluk onaylı commit, lease tabanlı canlılık kontrolü ve watch tabanlı bildirim. Bir mühendis olarak bu kavramları anlamak; sadece bu araçları doğru kullanmayı değil, üzerlerine kurulu Kubernetes, Kafka, HBase gibi sistemlerin arıza modlarını da anlamayı sağlar. En önemli çıkarım şudur: bu sistemler **tutarlılığı erişilebilirliğin önüne koyar** — bu bilinçli tercih anlaşılmadan yapılan her "hızlı düzeltme" (timeout artırma, tek düğümle çalıştırma, fencing olmadan kilit kullanma), sistemin sağladığı temel garantiyi sessizce ortadan kaldırabilir.
