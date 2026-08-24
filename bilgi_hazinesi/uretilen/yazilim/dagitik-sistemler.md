# Dağıtık Sistem Temelleri

Dağıtık sistem, birden fazla bağımsız bilgisayarın (node) bir ağ üzerinden mesajlaşarak tek bir tutarlı hizmet gibi davranmaya çalıştığı sistemdir. Kullanıcı tek bir uygulama görür; arka planda ise onlarca, bazen binlerce makine koordine olmaktadır. Bu koordinasyonun zorluğu, dağıtık sistemleri tek makinedeki programlamadan kökten ayıran şeydir. Tek bir makinede belleğe yazdığınızda o yazma ya olur ya olmaz; ortada bir belirsizlik yoktur. Dağıtık sistemde ise bir node'a "şunu yap" dediğinizde üç sonuç mümkündür: yapılmıştır, yapılmamıştır ya da **yapılıp yapılmadığını bilemezsiniz**. Bu üçüncü durum, yani belirsizlik, tüm alanın temel gerilimidir.

Bu makale beş temel eksen üzerinden ilerliyor: node'ların bir değer üzerinde anlaşması (consensus), zamanın ölçülmesi ve sıralanması (saat), sistemin bir kısmının çökmesi (kısmi hata / partial failure), bir işlemin tekrarlansa da aynı sonucu vermesi (idempotency) ve bir mesajın tam olarak bir kez işlendiğinin garanti edilmesi (exactly-once). Bunlar birbirinden bağımsız konular değildir; aksine hepsi aynı kök nedenden, yani **güvenilmez ağ ve bağımsız hata modelinden** doğar.

## Kök Neden: Neden Dağıtık Sistem Zordur

Dağıtık sistemin zorluğunu anlamak için önce üç fiziksel gerçeği kabul etmek gerekir.

Birincisi, **ağ güvenilmezdir**. Mesajlar kaybolabilir, gecikebilir, sırası bozulabilir veya çoğaltılabilir (duplicate). Daha kötüsü, bir mesajın gecikmesiyle tamamen kaybolması arasındaki farkı gönderen taraf ayırt edemez. Bir istek gönderip yanıt alamadığınızda, isteğin karşıya hiç ulaşmadığını mı yoksa ulaşıp işlendiğini ama yanıtın yolda kaybolduğunu mu bilemezsiniz. Bu ayırt edilemezlik, idempotency ve exactly-once tartışmalarının tam kalbindedir.

İkincisi, **saatler senkron değildir**. Her makinenin kendi kristal osilatörü vardır ve bu osilatörler farklı hızlarda kayar (clock drift / saat kayması). İki makinenin duvar saati (wall clock) aynı anı gösterdiğinde bile aralarında milisaniyeler, hatta senkronizasyon bozulduğunda saniyeler fark olabilir.

Üçüncüsü ve en önemlisi, **kısmi hata (partial failure) vardır**. Tek makinede program ya çalışır ya çöker; ikisi arasında bir durum yoktur. Dağıtık sistemde ise sistemin bir bölümü çökerken diğer bölümü hâlâ sağlıklı çalışıyor olabilir ve çalışan taraf, çöken tarafın çöktüğünü hemen anlayamaz. Anlayamamasının nedeni birinci gerçekle aynıdır: sessizlik, hem çökmüş bir node'un hem de sadece ağ üzerinden ulaşılamayan ama aslında çalışan bir node'un ortak işaretidir.

Bu üç gerçeğin birleşimi, dağıtık sistemlerin en ünlü teorik sonucuna götürür: **FLP imkânsızlık sonucu**. Kabaca ifadesiyle, mesajların keyfi olarak gecikebildiği asenkron bir sistemde, tek bir node bile çökebiliyorsa, deterministik bir consensus algoritması her zaman ve garantili şekilde sonuçlanamaz. Pratikte bu "consensus imkânsız" demek değildir; "hem her koşulda güvenli hem de her koşulda ilerlemeyi garanti eden mükemmel bir algoritma yoktur, bir yerde ödün vermelisiniz" demektir. Gerçek sistemler bu ödünü zaman aşımı (timeout) ve rastgelelik ekleyerek verir.

## Saatler ve Zaman: Neden "Ne Zaman" Sorusu Tehlikelidir

### Fiziksel saatler neden yeterli değil

Sezgisel yaklaşım şudur: her olaya bir zaman damgası (timestamp) koyalım, sonra zaman damgalarına göre sıralayalım. Bu yaklaşım dağıtık sistemde sessizce bozulur. Node A bir olay üretip `t=100` damgası koyar, node B başka bir olay üretip `t=95` damgası koyar. B'nin olayı gerçekte A'nınkinden sonra gerçekleşmiş olabilir; sadece B'nin saati geride olduğu için daha küçük bir sayı yazılmıştır. Zaman damgalarına körü körüne güvenip "küçük olan önce oldu" derseniz, nedensellik ihlal edilir.

Bunun kök nedeni saatlerin birbirinden bağımsız kayması ve NTP (Network Time Protocol) gibi senkronizasyon protokollerinin de kendi belirsizliğini taşımasıdır. NTP, saatleri birbirine yaklaştırır ama sıfır fark garantisi vermez; ağ gecikmesinin asimetrik olması bir kalıntı hata bırakır. Daha da tehlikelisi, NTP saati **geriye** de ayarlayabilir. Kodunuz "iki `now()` çağrısı arasındaki fark her zaman pozitiftir" varsayarsa, saat geri gittiği anda negatif süre ölçer ve mantığınız çöker.

### Monotonik saat ile duvar saatini ayırmak

Doğru pratik, iki farklı saat kavramını ayırmaktır. **Duvar saati (wall clock)** "şu an takvimde hangi an" sorusunu yanıtlar; loglama, son kullanma tarihi gibi insanla ilgili şeyler için uygundur ama geriye atlayabilir. **Monotonik saat (monotonic clock)** ise yalnızca ileri gider ve iki ölçüm arasındaki geçen süreyi vermek için tasarlanmıştır; takvimle ilişkisi yoktur ama asla geri gitmez. Kural nettir: **süre ölçmek için monotonik saat kullanın, bir anı adlandırmak için duvar saati.** Timeout hesabını duvar saatiyle yapmak yaygın ve sinsi bir hatadır.

### Mantıksal saatler: Lamport ve vektör saatleri

Zaman probleminin dağıtık sistemlere özgü çözümü, fiziksel zamandan tamamen vazgeçip **mantıksal saat (logical clock)** kullanmaktır. Buradaki içgörü şudur: çoğu zaman gerçekten kaçta olduğu umurumuzda değildir; sadece **hangi olayın hangisinden önce gelebileceğini** bilmek isteriz.

**Lamport saati** basit bir sayaçtır. Her node bir sayaç tutar. Bir olay olunca sayacı artırır. Bir mesaj gönderirken kendi sayaç değerini mesaja iliştirir. Bir mesaj alırken, kendi sayacını `max(kendi_sayaç, gelen_sayaç) + 1` yapar. Bu kural sayesinde, eğer olay A gerçekten olay B'nin nedeniyse (A'dan B'ye bir bilgi akışı varsa), A'nın Lamport zamanı B'ninkinden küçük olur. Ancak tersi doğru değildir: Lamport zamanı küçük olan olay illa nedensel olarak önce gelmiş olmayabilir; ilgisiz (concurrent) da olabilirler. Yani Lamport saati nedenselliği **korur** ama nedensellikle eşzamanlılığı **ayırt edemez**.

Bu ayrımı yapabilmek için **vektör saati (vector clock)** kullanılır. Her node, tüm node'ların sayaçlarından oluşan bir vektör tutar. İki vektörü karşılaştırarak "A kesinlikle B'den önce oldu", "B kesinlikle A'dan önce oldu" ya da "bunlar eşzamanlı, birbirinden habersiz" sonuçlarından hangisinin geçerli olduğunu tam olarak söyleyebilirsiniz. Bedeli, node sayısıyla büyüyen bir vektör taşımaktır. Vektör saatleri, birden çok yazmanın çakıştığı durumları tespit etmek için (örneğin bir anahtara iki farklı node'un aynı anda farklı değer yazması) sıkça kullanılır.

## Kısmi Hata (Partial Failure): Sessizliğin İki Anlamı

### Neden en zorlu problem budur

Kısmi hatanın zorluğu, daha önce değindiğimiz **ayırt edilemezlik** ilkesinden gelir. Bir node'a istek gönderdiniz, yanıt gelmedi. Olası nedenler: node çökmüş olabilir; node çalışıyor ama aşırı yüklendiği için yavaş yanıt veriyor olabilir; isteğiniz ağda kaybolmuş olabilir; node isteği aldı, işledi, ama yanıtı yolda kayboldu olabilir. Bu senaryoların **hiçbirini** dışarıdan kesin olarak ayırt edemezsiniz. Elinizdeki tek işaret sessizliktir ve sessizlik hepsinin ortak sonucudur.

Bu yüzden dağıtık sistemlerde "öldü mü sağ mı" sorusu asla kesin cevaplanamaz; yalnızca **şüphe** üretilebilir. Hata tespiti (failure detection) pratikte bir zaman aşımı meselesine indirgenir: "Şu kadar süredir cevap yok, o hâlde node'u ölü **sayıyorum**." Buradaki kelime "sayıyorum"dur, "biliyorum" değil.

### Timeout ikilemi

Timeout süresini seçmek gerçek bir ödünleşmedir. Çok kısa seçerseniz, aslında sağlıklı ama o an biraz yavaş olan bir node'u yanlışlıkla ölü ilan edersiniz (false positive). Bu, gereksiz failover'lara, çift işleme ve kararsızlığa yol açar. Çok uzun seçerseniz, gerçekten ölmüş bir node'u fark etmeniz uzun sürer ve sistem o süre boyunca yanıt veremez. Mükemmel bir timeout değeri yoktur; ağ koşulları değiştikçe doğru değer de değişir. Bu yüzden olgun sistemler sabit timeout yerine adaptif (ölçülen gecikmeye göre ayarlanan) mekanizmalar kullanır.

### Split-brain: kısmi hatanın en tehlikeli sonucu

Kısmi hatanın en yıkıcı biçimi **split-brain**'dir. Bir ağ bölünmesi (network partition) sistemi iki gruba ayırır. Her iki grup da diğerini "ölmüş" sanar ve her ikisi de "ben artık liderim, kararları ben veriyorum" der. Sonuçta iki lider aynı anda çelişen kararlar alır; bir banka bakiyesini iki farklı tarafta iki farklı şekilde günceller. Ağ tekrar birleştiğinde ortada uzlaştırılamaz iki gerçek vardır.

Split-brain'e karşı temel savunma **quorum** (çoğunluk) mantığıdır: bir karar ancak node'ların çoğunluğu onayladığında geçerli sayılır. Beş node'luk bir kümede karar için en az üç onay gerekir. Ağ 2'ye 3 bölündüğünde, üçlü taraf çoğunluğu sağlar ve çalışmaya devam eder; ikili taraf çoğunluğu sağlayamaz ve kendini durdurur. İki taraf da çoğunluk **olamayacağı** için iki lider aynı anda var olamaz. Quorum, split-brain'i "imkânsız kılmaz" ama iki tarafın da aynı anda yazma yapmasını imkânsız kılar; bu da yeterlidir. Bu yüzden küme boyutları genellikle tek sayı seçilir (3, 5, 7): çift sayıda node'la tam ortadan bölünme çoğunluğu belirsizleştirir.

## Consensus: Birden Fazla Node Nasıl Anlaşır

### Problem ve neden zor

Consensus, birden çok node'un tek bir değer üzerinde anlaşmasını sağlama problemidir. "Bir sonraki lider kim", "bu işlem commit mi edilecek", "loga sırayla hangi kayıt yazılacak" gibi soruların cevabı tüm node'larda **aynı** olmalıdır. Doğru bir consensus algoritması dört özelliği sağlamalıdır: anlaşma (tüm sağlıklı node'lar aynı değeri seçer), bütünlük (sadece önerilen bir değer seçilebilir), geçerlilik (seçilen değer anlamsız olamaz) ve sonlanma (er ya da geç bir karara varılır). FLP sonucu tam olarak bu dördüncü özelliğin, hata varlığında garantilenemeyeceğini söyler; gerçek algoritmalar sonlanmayı "büyük olasılıkla ve pratikte" sağlayacak biçimde tasarlanır.

### Paxos ve Raft: aynı hedefe iki yol

Alanın klasik çözümü **Paxos**'tur. Paxos doğrudur ve yıllarca standart kabul edilmiştir, ancak anlaşılması ve doğru uygulanması meşhur biçimde zordur. Bu zorluğa tepki olarak tasarlanan **Raft**, aynı garantileri daha anlaşılır bir yapıyla sunmayı amaçlar ve bu yüzden bugün yeni sistemlerde çok yaygındır.

Raft'ın çalışma mantığı şu sezgiye dayanır: koordinasyonu tek bir lidere yıkarsanız problem sadeleşir. Raft üç mekanizmadan oluşur. **Lider seçimi (leader election):** node'lar başlangıçta takipçidir (follower); belirli bir süre liderden haber alamayan bir node aday (candidate) olur ve oy ister; çoğunluğun oyunu alan lider olur. Her seçim bir **terim (term)** numarasıyla etiketlenir; bu numara mantıksal bir saat gibi davranır ve eski bir liderin geri dönüp karışıklık çıkarmasını engeller, çünkü daha büyük terimli mesaj her zaman kazanır. **Log replikasyonu:** tüm yazmalar liderden geçer; lider kaydı takipçilere gönderir ve çoğunluk kaydı diske yazdığını onaylayınca kayıt "commit" edilmiş sayılır. **Güvenlik:** yalnızca en güncel loga sahip node lider olabilir; bu kural, commit edilmiş bir kaydın asla kaybolmamasını garanti eder.

Buradaki quorum bağlantısı kritiktir. Bir kayıt çoğunluk tarafından yazıldığında commit sayıldığı için, ve yeni lider olmak da çoğunluk oyu gerektirdiği için, iki çoğunluk kümesi **matematiksel olarak** en az bir ortak node'da kesişir. O ortak node commit edilmiş kaydı taşıdığından, yeni lider onu görmek zorunda kalır ve kayıt kaybolmaz. Consensus'un tüm güvenliği bu kesişim özelliğine dayanır.

### Consensus'un maliyeti ve doğru kullanımı

Consensus ucuz değildir: her karar için birden çok tur mesajlaşma ve disk yazımı gerekir, bu da gecikme ekler. Bu yüzden doğru pratik, **her şeyi consensus'tan geçirmemektir**. Consensus'u sadece gerçekten global anlaşma gerektiren kritik metadata için (lider kimliği, konfigürasyon, kilit sahipliği, shard atamaları) kullanın; yüksek hacimli veri yolunu ise mümkün olduğunca consensus dışında tutun. Yaygın mimari, küçük ve kritik durumu bir consensus servisine emanet edip (koordinasyon servisi rolü), asıl iş yükünü onun verdiği kararlara dayandırmaktır.

## Idempotency: Tekrarı Zararsız Kılmak

### Tanım ve kök neden

Bir işlem **idempotent** ise, onu bir kez de çalıştırsanız beş kez de çalıştırsanız sistemin son durumu aynıdır. "Bakiyeyi 100 yap" idempotenttir; kaç kez uygularsanız uygulayın bakiye 100 olur. "Bakiyeye 100 ekle" idempotent **değildir**; tekrarlanırsa bakiye şişer.

Idempotency neden bu kadar merkezi? Çünkü ağın güvenilmezliğini hatırlayın: bir istek gönderip yanıt alamadığınızda, isteğin işlenip işlenmediğini bilemezsiniz. Elinizde tek makul seçenek **yeniden denemektir (retry)**. Ama yeniden deneme, isteğin belki de zaten işlenmiş olma ihtimalini taşır. Yani güvenilmez ağda retry kaçınılmazdır ve retry ancak işlem idempotent ise güvenlidir. Idempotency, "en az bir kez teslimat" (at-least-once delivery) gerçekliğiyle baş etmenin temel aracıdır. Bu yüzden pratikte söylenen şudur: **ağ en az bir kez teslim eder, uygulama idempotency ile bunu tam bir kez etkisine çevirir.**

### Idempotency nasıl inşa edilir

En yaygın ve sağlam yöntem **idempotency anahtarı (idempotency key)** kullanmaktır. İstemci her isteğe benzersiz bir kimlik (genellikle bir UUID) iliştirir. Sunucu bu anahtarı işlemeden önce bir kayıt tablosunda arar. Anahtar daha önce görülmüşse, işlemi tekrar çalıştırmaz; sadece ilk sefer ürettiği yanıtı geri döner. Görülmemişse işlemi çalıştırır, sonucu anahtarla birlikte kaydeder. Kritik nokta şudur: anahtarın kontrol edilmesi, işin yapılması ve sonucun kaydedilmesi **atomik** olmalıdır; aksi hâlde iki eşzamanlı retry ikisi de "bu anahtarı görmedim" deyip işi iki kez çalıştırabilir. Bu atomikliği çoğu zaman veritabanının benzersizlik kısıtı (unique constraint) veya transaction'ı sağlar.

İkinci yaklaşım, işlemi doğası gereği idempotent tasarlamaktır. Örneğin "sipariş durumunu KARGOLANDI yap" gibi mutlak durum atamaları, "durumu bir ileri götür" gibi görece işlemlere tercih edilir. Bir başka örnek, deduplication için içerik tabanlı kimlik kullanmaktır: kaydın içeriğinden türetilen bir hash'i anahtar yaparsanız, aynı içerik iki kez gelse bile tek kayıt oluşur.

### Yaygın tuzaklar

Idempotency'nin en sinsi hatası, **yan etkileri (side effect) unutmaktır**. Ana veritabanı yazması idempotent olabilir ama aynı işlem bir e-posta gönderiyorsa, retry ikinci bir e-posta yollayabilir. Idempotency'yi işlemin tamamı için, dış dünyaya olan tüm etkileri kapsayacak şekilde düşünmek gerekir. İkinci tuzak, idempotency kayıtlarının **süresiz saklanmasıdır**; anahtar tablosu sonsuza dek büyürse sorun olur, bu yüzden anahtarlara makul bir yaşam süresi verilir ama bu süre olası retry penceresinden uzun olmalıdır. Üçüncü tuzak, kısmi başarıdır: işlem yarısına kadar ilerleyip çökerse, retry'ın tutarlı bir noktadan devam edebilmesi için işin kendisinin de idempotent adımlardan oluşması gerekir.

## Exactly-Once: En Çok Yanlış Anlaşılan Kavram

### Neden saf exactly-once bir efsanedir

Mesajlaşmada üç teslimat garantisinden söz edilir. **En fazla bir kez (at-most-once):** mesaj ya bir kez teslim edilir ya hiç; kayıp mümkündür ama duplicate yoktur. **En az bir kez (at-least-once):** mesaj mutlaka teslim edilir ama birden fazla kez teslim edilebilir. **Tam bir kez (exactly-once):** ne kayıp ne duplicate.

Kritik gerçek şudur: **mesaj teslimatı düzeyinde saf exactly-once fiziksel olarak imkânsıza yakındır.** Nedeni yine ayırt edilemezliktir. Gönderen bir mesaj yollar, alan işler ve onay (ack) döner, ama ack yolda kaybolur. Gönderen ack görmediği için yeniden gönderir. Alan mesajı ikinci kez alır. Gönderen "hiç göndermeyeyim mi tekrar göndereyim mi" ikilemindedir ve her iki seçim de ya kayba ya duplicate'e yol açar. Kaybı önlemek için tekrar göndermek zorundadır, dolayısıyla ağ katmanı en fazla **at-least-once** verebilir.

### Gerçekte kastedilen: exactly-once işleme

O hâlde "exactly-once" diyen sistemler ne yapar? İşin sırrı şudur: teslimatı at-least-once bırakırlar (mesaj birden çok kez gelebilir), ama **işlemenin etkisini** tam bir kez olacak şekilde tasarlarlar. Yani exactly-once **delivery** değil, exactly-once **processing** (effectively-once) hedeflenir. Bunu sağlayan iki temel teknik vardır ve ikisi de daha önce anlattığımız kavramlardır.

Birincisi **idempotent tüketicidir (idempotent consumer):** mesajın bir kimliği vardır, tüketici işlediği kimlikleri kaydeder, aynı kimliği ikinci görüşünde atlar. Duplicate gelir ama etki tektir. İkincisi **atomik commit / transactional outbox** yaklaşımıdır: mesajı işleme ile "bu mesajı işledim" işaretini koyma aynı transaction içinde, atomik olarak yapılır; böylece "işledim ama işaretlemeden çöktüm" ya da "işaretledim ama işlemeden çöktüm" gibi tutarsız ara durumlar oluşamaz.

Bu bakışla exactly-once, ayrı bir sihir değil, **at-least-once teslimat artı idempotent işleme**nin birleşiminden doğan bir sonuçtur. Bir sistem "exactly-once destekliyoruz" dediğinde, doğru okuma "duplicate'leri sizin adınıza etkisizleştiren bir mekanizma sağlıyoruz"dur; mesajların hiç çoğalmadığı değil.

### İki ordu problemi ve sınırlar

Bu imkânsızlığın teorik kökeni **iki ordu problemidir (Two Generals' Problem)**. İki general güvenilmez bir vadi üzerinden haberci göndererek ortak bir saldırı anında anlaşmaya çalışır. Her mesaj kaybolabildiği için, hiçbir general diğerinin son mesajı aldığından **kesin** emin olamaz; teyidin teyidinin teyidi sonsuza gider. Sonuç: güvenilmez bir kanal üzerinden iki tarafın bir eylem üzerinde **kesin** ortak bilgiye (common knowledge) ulaşması imkânsızdır. Exactly-once'ın neden teslimat katmanında çözülemeyip uygulama katmanında (idempotency ve atomiklik ile) ele alınması gerektiğinin özü budur.

## En İyi Pratikler ve Kapanış

Bütün bu kavramlar tek bir zihinsel modele oturur: **dağıtık sistemde belirsizliği ortadan kaldıramazsınız, onunla yaşamayı tasarlarsınız.** Bu modelden çıkan pratik ilkeler şunlardır.

Ağın güvenilmez olduğunu varsayın; her uzak çağrı başarısız olabilirmiş gibi, timeout ve retry ile tasarlayın. Retry yaptığınız her yerde, çağırdığınız işlemin idempotent olduğundan emin olun; retry ile idempotency birbirinden ayrılamaz bir ikilidir. Retry'lerinizi sabit aralıkla değil, üstel geri çekilme (exponential backoff) ve rastgelelik (jitter) ile yapın; aksi hâlde binlerce istemci aynı anda yeniden deneyip sistemi ikinci bir çöküşe sürükler (thundering herd).

Zamanı hiçbir zaman doğruluk garantisi olarak kullanmayın. Süre ölçmek için monotonik saat kullanın, olayları sıralamak için mantıksal saat (Lamport veya vektör) kullanın, duvar saatini yalnızca insanların okuyacağı zaman damgaları için bırakın. "İki node'un saatinin aynı olduğu" varsayımına dayanan hiçbir güvenlik mantığı kurmayın.

Kritik kararları çoğunluk (quorum) üzerine kurun ve split-brain'i quorum ile engelleyin; küme boyutunu tek sayı seçin. Global anlaşma gerektiren her şeyi olgun bir consensus mekanizmasına (Raft/Paxos temelli) devredin, ama consensus'u gereksiz yere sıcak veri yoluna sokup gecikme ödemeyin. Kendi consensus algoritmanızı sıfırdan yazmaya kalkmayın; bu, doğru yapılması yıllar alan ve küçük bir hatanın sessizce veri kaybına yol açtığı bir alandır.

Son olarak, "exactly-once garanti ediyoruz" ifadesini gördüğünüzde altında ne olduğunu sorun. Neredeyse her zaman altında "at-least-once teslimat + idempotent işleme" vardır ve bu tamamen sağlıklıdır. Yanlış olan, saf exactly-once teslimata güvenip idempotency'yi atlamaktır; o zaman ilk ağ hıçkırığında sessiz duplicate'ler sisteminize sızar.

Dağıtık sistem mühendisliği, sihirli bir garanti bulmak değil, hangi belirsizliğin nerede tolere edileceğini bilinçli seçmektir. Consensus, saatler, kısmi hata, idempotency ve exactly-once; hepsi aynı temel gerçeğin, yani güvenilmez ağ ve bağımsız hata modelinin farklı yüzleridir. Bu birliği görmek, bu beş kavramı ayrı ayrı ezberlemekten çok daha güçlü bir anlayış verir.
