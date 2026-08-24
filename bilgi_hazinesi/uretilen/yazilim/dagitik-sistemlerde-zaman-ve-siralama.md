# Dağıtık Sistemlerde Zaman ve Sıralama: Logical Clocks, Vector Clocks, Lamport Timestamps, Hybrid Logical Clocks, TrueTime/Spanner

## Giriş: Neden "zaman" dağıtık sistemlerde bir problem?

Tek makinede çalışan bir programda zaman basittir: tek bir CPU saati vardır, olaylar tek bir sırayla gerçekleşir, "A önce mi oldu, B mi önce oldu" sorusunun her zaman net bir cevabı vardır. Dağıtık bir sistemde bu varsayım çöker. Her düğümün (node) kendi fiziksel saati vardır, bu saatler senkron değildir, ağ gecikmeleri değişkendir (jitter), mesajlar sıra dışı gelebilir, düğümler çökebilir ve yeniden başlayabilir. Sonuç: "şu an saat kaç" sorusu bile düğümden düğüme farklı cevaplanır, "hangi olay önce oldu" sorusu ise çoğu zaman **tanımsızdır** — çünkü olaylar arasında hiçbir nedensel (causal) ilişki yoksa, evrensel bir sıralama fiziksel olarak anlamsızdır (bu, dağıtık sistemlerin özel görelilik ile şaşırtıcı bir benzerliğidir).

Bu makalenin amacı: neden fiziksel saatlerin (wall-clock, NTP) tek başına yetmediğini, bunun yerine "mantıksal zaman" (logical time) kavramının nasıl icat edildiğini, bu kavramın evrimini (Lamport → Vector → Hybrid Logical Clock → TrueTime) ve bunların consensus, replikasyon, tutarlılık modelleri gibi gerçek mimari problemlerde nasıl kullanıldığını derinlemesine anlamak.

## Kök Problem: Saat senkronizasyonunun fiziksel sınırları

### Neden NTP yetmez?

NTP (Network Time Protocol) düğümlerin saatlerini birbirine yaklaştırır, ama şu nedenlerle **kesinlik garantisi** veremez:

- **Ağ gecikmesi asimetriktir**: NTP, round-trip time'ın yarısını tek yönlü gecikme sanar; gidiş ve dönüş yolları farklı gecikmeye sahipse hata oluşur.
- **Saat sürüklenmesi (clock drift)**: Fiziksel kristal osilatörler mükemmel değildir; saat senkronize edildikten sonra bile zamanla kayar (tipik olarak günde milisaniyeler mertebesinde, donanıma bağlı).
- **Sıçramalar (leap seconds), sanallaştırma (VM saatleri hipervizör tarafından duraklatılabilir), NTP sunucusu erişilemezliği** gibi pratik arızalar.

Sonuç: iki farklı makinedeki `System.currentTimeMillis()` (veya benzeri) değerlerini karşılaştırarak "hangi olay önce oldu" demek **yanlış** olabilir — aradaki fark, gerçek olay sırasından değil, saat hatasından kaynaklanıyor olabilir. Bu, dağıtık sistem hatalarının en sinsi kaynaklarından biridir: kod çalışır, testler geçer, ama üretimde saat kayması olan bir düğüm sessizce yanlış sıralama üretir.

### Nedensellik (causality): asıl aranan şey

Dağıtık sistemlerde genelde ihtiyaç duyulan şey "gerçek zamanda kim önce oldu" değil, **nedensel sıralamadır**: eğer olay A, olay B'yi *etkileme potansiyeline* sahipse (örneğin A bir mesaj gönderdi, B o mesajı aldıktan sonra oldu), o zaman A→B ilişkisi korunmalıdır. Birbirini etkilemeyen olaylar (concurrent/eşzamanlı olaylar) için ise sıralama önemsizdir ve zorla bir sıra dayatmak gereksiz koordinasyon maliyeti yaratır.

Bu ayrım — **happens-before ilişkisi** — Leslie Lamport'un 1978 tarihli "Time, Clocks, and the Ordering of Events in a Distributed System" makalesinde formelleştirilmiştir ve tüm bu alanın temelidir.

## Lamport Timestamps (Lamport Saatleri)

### Tanım ve çalışma mantığı

Lamport saati, her düğümde tutulan basit bir sayaçtır (`C`). Kurallar:

1. Bir düğüm yerel bir olay gerçekleştirdiğinde: `C = C + 1`.
2. Bir düğüm mesaj gönderirken: `C = C + 1`, mesaja `C` değerini ekler.
3. Bir düğüm mesaj aldığında: `C = max(C_yerel, C_mesaj) + 1`.

Bu üç kural, **happens-before** ilişkisini (yazımda `→` ile gösterilir) koruyacak şekilde sayaçları büyütür: eğer A→B ise, `C(A) < C(B)` garanti edilir.

### Neden işe yarıyor: Kök mantık

Buradaki kritik iç görü şudur: Lamport saati **mutlak zamanı ölçmez**, sadece "bu olaydan önce en az şu kadar olay-zinciri geçti" bilgisini taşır. `max` + `1` kuralı, bir mesajı alan düğümün saatinin, göndericinin saatinden asla geride kalmamasını garanti eder — çünkü geride kalırsa nedensellik ihlal edilir (etki, sebebinden "önce" görünür).

### Kritik sınırlama: Ters yön garantisi YOK

Lamport saatinin en çok yanlış anlaşılan noktası budur: `C(A) < C(B)` olması, A→B anlamına GELMEZ. Yani Lamport saatleri **tek yönlü** bir garanti verir:

- A → B ise, kesinlikle C(A) < C(B).
- Ama C(A) < C(B) ise, A→B olabilir **ya da** A ve B concurrent (eşzamanlı, birbirinden bağımsız) olabilir.

Bu, Lamport saatinin toplam sıralama (total order) üretebilmesini (sayaçlar eşitse düğüm ID'si gibi bir tie-breaker eklenerek) sağlar, ama bu toplam sıra **gerçek nedensellik bilgisini kaybeder**. Bu sınırlama, Vector Clock'ların icadının doğrudan motivasyonudur.

### Kullanım alanları ve tuzaklar

- **Doğru kullanım**: Dağıtık kilitler (Lamport'un orijinal mutual exclusion algoritması), olay günlüklerinde toplam sıralama gerekiyorsa (ör. bazı log-tabanlı replikasyon şemaları) ama nedenselliğin kanıtlanması gerekmiyorsa.
- **Yaygın hata**: Lamport timestamp'lerini karşılaştırarak "A, B'nin nedeni mi" sorusuna cevap aramak. Bu **yanlış sonuç** üretebilir ve bu tip hatalar test ortamında nadiren yakalanır çünkü küçük ölçekte concurrent olaylar azdır; üretimde ölçek büyüyünce sessiz veri tutarsızlıkları (örn. yanlış "son yazan kazanır" kararları) ortaya çıkar.
- **En iyi pratik**: Nedensellik kanıtı gerekiyorsa Vector Clock veya benzeri bir yapı kullanın; Lamport saatini sadece toplam sıralama (tie-break) katmanı olarak kullanın.

## Vector Clocks (Vektör Saatleri)

### Tanım

Vector Clock, tek bir sayaç yerine, sistemdeki **her düğüm için bir sayaç** tutan bir vektördür: `N` düğümlü bir sistemde her düğüm `[C1, C2, ..., CN]` boyutunda bir vektör tutar.

Kurallar:

1. Yerel olayda: düğüm kendi bileşenini artırır (`Ci = Ci + 1`).
2. Mesaj gönderirken: kendi bileşenini artırır, tüm vektörü mesaja ekler.
3. Mesaj alırken: gelen vektörle yerel vektörün **eleman bazında maksimumunu** alır, sonra kendi bileşenini artırır.

### Neden işe yarıyor: İki yönlü garanti

Vector Clock'un gücü şudur: iki vektör arasında tanımlı bir **kısmi sıralama (partial order)** vardır:

- `V(A) ≤ V(B)` (her bileşende A ≤ B) ve `V(A) ≠ V(B)` ise → A → B (A, B'nin nedenidir).
- Ne `V(A) ≤ V(B)` ne `V(B) ≤ V(A)` ise → A ve B **concurrent**'tir (birbirinden bağımsızdır).

Bu, Lamport saatinin eksik bıraktığı şeyi tam olarak sağlar: **nedensellik kanıtlanabilir**, hem de yön belirsizliği olmadan (concurrent olaylar açıkça tespit edilir). Kök neden: her düğümün kendi "katkısını" ayrı ayrı takip ederek, bilginin hangi düğümlerden geçerek yayıldığını tam olarak kodlar.

### Bedeli: Ölçeklenebilirlik problemi

Vector Clock'un maliyeti, vektör boyutunun düğüm sayısıyla doğru orantılı olmasıdır: `N` düğümlü sistemde her mesaj `O(N)` boyutunda meta veri taşır. Binlerce düğümlü sistemlerde (ör. büyük ölçekli key-value store'lar) bu ciddi bir depolama ve ağ bant genişliği maliyetine dönüşür.

### Gerçek dünya kullanımı ve tuzaklar

- **Amazon Dynamo** (ve türevleri Riak, Voldemort) çakışan yazmaları (conflicting writes) tespit etmek için vector clock kullanır: eğer iki versiyon concurrent ise, sistem otomatik birleştirme yapamaz, çakışmayı **uygulamaya** (veya kullanıcıya) bırakır ("sibling" versiyonlar).
- **Yaygın hata**: Düğüm sayısı dinamik olarak değiştiğinde (düğüm ekleme/çıkarma) vektör boyutunun yönetimi karmaşıklaşır; bu genelde "dotted version vectors" gibi varyantlarla çözülür ama doğru tasarlanmazsa vektörler sınırsız büyür (vector clock bloat).
- **En iyi pratik**: Vector clock'u yalnızca gerçekten "kim kimi etkiledi" sorusuna cevap vermeniz gereken yerlerde (çakışma tespiti, nedensel mesajlaşma sıralaması) kullanın; sadece toplam sıra yeterliyse Lamport saati daha ucuzdur.

## Hybrid Logical Clocks (HLC)

### Motivasyon: İki dünyanın en iyisi

Pratikte mühendisler hem şunu isterler: (1) fiziksel zamana yakın, insan tarafından okunabilir zaman damgaları (debug etmek, TTL/expiry hesaplamak, olayları gerçek zamanla ilişkilendirmek için), hem de (2) Lamport saatinin sağladığı nedensellik garantisi (happens-before korunumu). Salt fiziksel saat (NTP) nedenselliği garanti etmez (saat kayması nedeniyle); salt Lamport saati fiziksel zamanla ilişkisizdir (sadece bir sayaç, "gerçek zaman" hakkında hiçbir şey söylemez).

**Hybrid Logical Clock (HLC)**, Kulkarni ve arkadaşlarının çalışmasıyla popülerleşen bir yapıdır: her zaman damgası `(pt, l, c)` üçlüsünden oluşur — `pt` fiziksel saat, `l` "mantıksal maksimum görülen fiziksel zaman", `c` aynı `l` değeri içinde çakışan olayları ayırt eden bir sayaç.

### Çalışma mantığı

Basitleştirilmiş kural seti:

1. Yerel olayda: `l' = max(l, pt_şimdi)`; eğer `l' == l` ise `c' = c + 1`, değilse `c' = 0`.
2. Mesaj gönderirken: yerel HLC güncellenir ve gönderilir.
3. Mesaj alırken: `l' = max(l_yerel, l_mesaj, pt_şimdi)`; `c'` buna göre (üç kaynaktan hangisi eşitse ona göre) artırılır veya sıfırlanır.

Kök mantık: `l` bileşeni, "şimdiye kadar gördüğüm en büyük fiziksel zaman"ı takip eder ve bu değer asla geriye gitmez — tıpkı Lamport saatindeki `max` kuralı gibi ama fiziksel zamana **çapalanmış** olarak. Sonuç: HLC değerleri fiziksel saate yakın kalır (küçük bir sınırlı sapmayla) VE happens-before ilişkisini Lamport saati gibi korur.

### Neden önemli: Pratik kazanımlar

- **Tek boyutlu ve ucuz**: Vector clock gibi `O(N)` değil, sabit boyutlu (fiziksel zaman + sayaç), bu yüzden ölçeklenebilir.
- **Fiziksel zamana yakın**: TTL, snapshot isolation, "şu approximate zamanda ne olmuştu" sorguları için kullanılabilir.
- **Nedensellik korunur**: A→B ise HLC(A) < HLC(B) (Lamport saati gibi tek yönlü garanti; vector clock'un tam kısmi-sıra gücü yoktur).

### Kullanım alanı: CockroachDB

CockroachDB, HLC'yi MVCC (multi-version concurrency control) zaman damgaları ve dağıtık transaction sıralaması için kullanır. Burada kök neden şudur: CockroachDB, Spanner'ın TrueTime'ının donanım desteğine (atomik saat/GPS) sahip olmayan genel amaçlı bulut ortamlarında çalışmak zorundadır; HLC, TrueTime'ın verdiği kesinlik garantisinin bir kısmını, özel donanım gerektirmeden, yazılım seviyesinde yaklaşık olarak taklit etmenin bir yoludur (tam aynı garanti gücünde değildir — bu farkı aşağıda TrueTime bölümünde netleştireceğiz).

### Tuzaklar

- HLC hâlâ Lamport saati gibi **tek yönlü** garanti verir; iki HLC değerini karşılaştırıp kesin nedensellik çıkarımı yapmak (concurrent olayları ayırt etmek) mümkün değildir — bunun için yine vector clock gerekir.
- `pt` bileşeni gerçek saat kaymasından tamamen bağımsız değildir; HLC nedenselliği korur ama "gerçek zamanda kaç saniye fark var" sorusuna Spanner'daki kadar kesin cevap vermez.

## TrueTime ve Google Spanner

### Problem: Küresel ölçekte serializable transaction'lar

Spanner, dünya çapında dağıtılmış, harici olarak tutarlı (external consistency — serializability'nin gerçek zamanla uyumlu hali) transaction'lar sunmak isteyen bir sistemdir. Bunu yapabilmek için, farklı kıtalardaki düğümlerin "şu transaction, bu transaction'dan önce commit oldu" sorusunu **kesin ve doğru** cevaplaması gerekir. Yukarıda tartıştığımız gibi, normal NTP saatleri bunu garanti edemez çünkü **belirsizlik (uncertainty)** ölçülmez, sadece varsayılır.

### TrueTime'ın çözümü: Belirsizliği gizlemek yerine ölçmek

TrueTime'ın temel fikri kavramsal bir sıçramadır: "saat şu an tam olarak X" demek yerine, "saat şu an `[earliest, latest]` aralığında, ve bu aralığın genişliği garanti edilmiş bir üst sınıra sahip" der. API üç fonksiyon sunar (kavramsal olarak): `TT.now()` bir zaman aralığı döndürür, `TT.after(t)` ve `TT.before(t)` belirli bir zamanın kesin olarak geçip geçmediğini sorar.

Bu belirsizlik aralığı, GPS alıcıları ve atomik saatlerden oluşan özel donanım (her Google veri merkezinde) ile küçük tutulur (tipik olarak birkaç milisaniyenin altında), ama **sıfır değildir** — ve TrueTime'ın dehası, bu sıfır olmayan belirsizliği inkar etmek yerine açıkça modellemesidir.

### Commit-wait: Kök mekanizma

Spanner'ın external consistency garantisini sağlayan asıl mekanizma **commit-wait**'tir: bir transaction commit olmadan önce, sistem `TT.now()` aralığının `latest` sınırı geçene kadar **bilerek bekler**. Bu, şu garantiyi sağlar: eğer transaction T1, T2 başlamadan önce commit olduysa (gerçek zamanda), T1'in commit zaman damgası, T2'nin herhangi bir zaman damgasından kesinlikle küçük olacaktır — çünkü T1, kendi belirsizlik aralığının sonuna kadar bekledikten sonra commit olmuştur.

Kök neden/mantık: Belirsizlik aralığı `ε` kadar genişse, commit-wait süresi de `ε` kadar bir gecikme ekler. Yani TrueTime, **doğruluğu, gecikme (latency) ile satın alır** — bu, dağıtık sistemlerdeki klasik "tutarlılık vs. gecikme" değiş tokuşunun somut, ölçülebilir bir örneğidir. `ε` ne kadar küçük tutulabilirse (daha iyi donanım, GPS/atomik saat senkronizasyonu), commit-wait maliyeti o kadar azalır — bu yüzden Spanner özel donanıma yatırım yapar.

### Neden bu, Lamport/Vector/HLC'den farklı bir kategori?

Buradaki kavramsal ayrım önemlidir: Lamport, Vector Clock ve HLC **mantıksal zaman** çözümleridir — fiziksel saat doğruluğuna güvenmezler, sadece mesajlaşma yoluyla nedenselliği çıkarırlar. TrueTime ise tam tersi bir yol izler: **fiziksel saati, ölçülü belirsizlikle, yeterince güvenilir hale getirip** doğrudan gerçek-zamanlı sıralama için kullanır. TrueTime, özel donanım yatırımı gerektirdiği için her sistemin erişebileceği bir çözüm değildir; HLC gibi yaklaşımlar bu yüzden "TrueTime'sız ortamlar için" pratik bir orta yol sunar.

### Yaygın yanlış anlama

Sık yapılan bir hata, TrueTime'ı "Google'ın saatleri mükemmel senkronize ettiği" şeklinde anlamaktır. Gerçekte TrueTime saatleri **mükemmel senkronize etmez**; sadece senkronizasyon hatasının üst sınırını **garanti eder ve dışa açar**, ve sistemin geri kalanı (commit-wait) bu garantiyi kullanarak doğruluğu inşa eder. Belirsizliği yok saymak değil, belirsizliği bir birinci sınıf vatandaş olarak modellemek — asıl kök içgörü budur.

## Bu Kavramların Consensus ve Tutarlılık ile İlişkisi

Bu makalenin başında belirtildiği gibi, zaman ve sıralama kavramları olmadan şu konular tam anlaşılamaz:

- **Consensus (Paxos, Raft)**: Log girdilerinin sırası, terim/epoch numaraları aslında birer mantıksal saat biçimidir (Raft'taki `term` sayacı, Lamport saatine kavramsal olarak yakındır — monoton artan, çakışmaları çözmek için kullanılan bir sayaç).
- **Replikasyon**: Çoklu replika arasında "hangi yazma en son" sorusu, ya vector clock (Dynamo tarzı) ya HLC (CockroachDB tarzı) ya da TrueTime (Spanner tarzı) ile cevaplanır.
- **Tutarlılık modelleri**: Causal consistency doğrudan happens-before ilişkisine (dolayısıyla Lamport/Vector Clock teorisine) dayanır; external/strong consistency ise TrueTime tarzı gerçek-zaman garantilerine ihtiyaç duyar.

## Savunma/Tespit Perspektifi: Bu Mekanizmalar Yanlış Tasarlandığında Ne Olur?

Bir mühendis/savunmacı gözüyle, bu alandaki en kritik "saldırı yüzeyi" kötü niyetli değil, **tasarım hatalarından kaynaklanan sessiz veri bozulmasıdır**:

- **Saat kayması istismarı**: Eğer bir sistem, dağıtık sıralama kararlarını (ör. "son yazan kazanır" — last-write-wins) yalnızca fiziksel wall-clock zaman damgalarına dayandırıyorsa, saati ileri/geri kaydırılabilen bir düğüm (kasıtlı veya arızalı NTP nedeniyle) veri kaybına veya tutarsızlığa yol açabilir. **Tespit**: zaman damgası tabanlı çakışma çözümü kullanan sistemlerde saat sapmasını izleyin (monitoring/alerting); mümkünse HLC veya vector clock'a geçin.
- **Vector clock patlaması (unbounded growth)**: Düğüm sayısı dinamikse ve eski düğüm ID'leri temizlenmiyorsa, vektörler sınırsız büyür — bu bir kaynak tükenmesi (resource exhaustion) riskidir. **Savunma**: dotted version vector gibi sınırlı varyantlar, düzenli garbage collection.
- **Commit-wait'in atlanması**: TrueTime tarzı bir sistemde, mühendisler performans için commit-wait süresini "optimize etmeye" çalışırsa (ör. `ε`'yi olduğundan küçük varsayarsa), external consistency garantisi sessizce bozulur — bu türden hatalar testte görünmez, yalnızca yüksek yük ve gerçek ağ gecikmesi altında ortaya çıkar. **Savunma**: belirsizlik sınırlarını asla varsayılan/sabit değer olarak hardcode etmeyin; gerçek zaman senkronizasyon altyapısından (donanım destekli) alın.
- **Lamport saati ile yanlış nedensellik çıkarımı**: Yukarıda belirtildiği gibi, geliştiricilerin Lamport saatini vector clock gibi kullanmaya çalışması (concurrent olayları ayırt etmeye çalışması) sık görülen bir tasarım hatasıdır ve code review'de özellikle aranmalıdır.

## Sonuç

Dağıtık sistemlerde zaman, tek bir evrensel çizgi değil, **kanıtlanabilir nedensellik** ile **yaklaşık gerçek zaman** arasında bir spektrumdur. Lamport saatleri ucuz ama tek yönlü bir garanti sunar; vector clock'lar tam nedensellik kanıtı sunar ama pahalıdır; HLC ikisinin dengeli bir melezidir; TrueTime ise özel donanımla belirsizliği ölçüp gerçek zamanı doğrudan kullanılabilir kılar. Bu araçlardan hangisinin seçileceği, sistemin ölçeğine, donanım bütçesine ve gereken tutarlılık garantisinin gücüne bağlıdır — ama hangisi seçilirse seçilsin, kök soru hep aynıdır: **"Bu iki olay arasında gerçek bir nedensellik var mı, yoksa sadece saatler mi öyle görünmesine neden oluyor?"**
