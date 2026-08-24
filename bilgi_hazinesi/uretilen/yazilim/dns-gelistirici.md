# DNS (Geliştirici Bakışı): Kayıt Türleri, Çözümleme, Cache ve TTL

## Tanım: DNS Aslında Ne Yapar?

DNS (Domain Name System), insanların hatırlayabileceği alan adlarını (`ornek.com`) makinelerin konuşabileceği adreslere (`93.184.216.34` gibi bir IPv4 ya da `2606:...` gibi bir IPv6) çeviren, hiyerarşik ve dağıtık bir isim çözümleme sistemidir. Ancak bir geliştirici için DNS'i "telefon rehberi" benzetmesiyle bırakmak yetersizdir. DNS aslında **dağıtık, gevşek tutarlı (eventually consistent), yoğun cache'lenen bir anahtar-değer veritabanıdır**. Anahtarı `(isim, sınıf, tür)` üçlüsüdür; değeri ise bir dizi kayıttır.

Bu tanımı en baştan doğru oturtmak önemli, çünkü DNS ile ilgili yaşanan üretim (production) sorunlarının büyük kısmı, DNS'i anlık ve tutarlı (strongly consistent) bir sistem sanmaktan doğar. Bir kayıt değiştirdiğinizde değişikliğin dünya genelinde "hemen" görünür olmasını beklerseniz, TTL ve cache katmanlarının gerçekliğiyle çarpışırsınız. DNS'in tasarımı bilinçli olarak tutarlılıktan feragat edip **ölçeklenebilirlik ve dayanıklılık** kazanır.

## Kök Neden: Neden Hiyerarşik ve Dağıtık Bir Sistem?

DNS'in neden böyle çalıştığını anlamak için tek merkezi bir sunucuda tutulan devasa bir isim tablosunu hayal edin. Böyle bir sistem üç noktada çöker: ölçek (dünyadaki tüm sorguları tek makine karşılayamaz), gecikme (herkes tek noktaya gider), ve yönetim (her ismin sahibi kendi kaydını değiştirmek için merkezi otoriteye başvurmak zorunda kalır). DNS bu üç problemi de **yetki devri (delegation)** ile çözer.

İsim uzayı sağdan sola bir ağaçtır. En sağda görünmez bir kök (`.`) vardır. Onun altında TLD'ler (`com`, `net`, `org`, ülke kodları gibi) yer alır. Onun altında ikinci seviye alan adları (`ornek.com`), onun altında alt alan adları (`api.ornek.com`) gelir. Her seviye, bir alt seviyenin sorumluluğunu başka sunuculara **devreder**. Kök sunucular "`com` işlerini şu TLD sunucularına sor" der; `com` sunucuları "`ornek.com` işlerini şu authoritative sunuculara sor" der. Böylece hiçbir sunucunun her şeyi bilmesi gerekmez ve her alan sahibi kendi bölgesini (zone) bağımsız yönetir.

Burada iki kavramı ayırmak kritik: **zone** ve **domain**. Domain isim uzayındaki bir düğüm ve altındaki her şeydir. Zone ise tek bir authoritative sunucunun fiilen yönetim sorumluluğunu üstlendiği kesittir; bir zone, alt alanları başka bir zone'a devrettiği (delegation) noktada biter. Yani `ornek.com` zone'u, `alt.ornek.com`'u ayrı bir zone'a devretmişse orada sona erer.

## Kayıt Türleri (Record Types)

DNS'te asıl "veri", **resource record** (RR) denilen kayıtlardır. Her kayıt en azından bir isim, bir tür (type), bir sınıf (neredeyse her zaman `IN` — Internet), bir TTL ve türe özgü bir veri (RDATA) içerir. Geliştiricinin günlük hayatta karşılaştığı türleri, neden var olduklarıyla birlikte gözden geçirelim.

### A ve AAAA — Adres Kayıtları

`A` kaydı bir ismi bir IPv4 adresine, `AAAA` kaydı ise bir IPv6 adresine bağlar. Bunlar çözümlemenin nihai hedefi olan "yaprak" kayıtlardır. Bir isim için birden çok `A` kaydı bulunabilir; bu durumda çözücü (resolver) genellikle sırayı değiştirerek (round-robin benzeri) döner ve istemci basit bir yük dağılımı elde eder. Fakat bunun gerçek bir load balancer olmadığını unutmayın: DNS sağlık kontrolü yapmaz, sadece adres listesi döner. Sıra dönüşü de cache tarafından bozulabilir.

### CNAME — Takma Ad Kaydı

`CNAME` (Canonical Name) bir ismi başka bir isme yönlendirir: "`www.ornek.com` aslında `ornek.com`'dur" gibi. Çözücü bir `CNAME` gördüğünde hedef isim için çözümlemeyi yeniden başlatır. `CNAME`'in en önemli ve sık ihlal edilen kuralı şudur: **bir isimde `CNAME` varsa, o isimde başka tür kayıt bulunamaz.** Bu yüzden zone tepesinde (apex/root, yani çıplak `ornek.com`) `CNAME` kullanamazsınız, çünkü apex'te zorunlu olarak `SOA` ve `NS` kayıtları bulunur. Bu kısıt, "apex'i bir CDN'e CNAME'lemek istiyorum ama olmuyor" şikayetinin kök nedenidir. Sağlayıcılar bu boşluğu `ALIAS`/`ANAME` gibi standart olmayan, sunucu tarafında çözümlenen özel kayıtlarla doldurur.

### MX — Mail Yönlendirme

`MX` (Mail Exchanger) kaydı, bir alan adına gelen e-postanın hangi sunuculara teslim edileceğini ve hangi öncelikle denemesi gerektiğini belirtir. Düşük öncelik değeri daha yüksek tercih anlamına gelir. `MX` kaydının hedefi bir isim olmalıdır, doğrudan IP olmamalı ve `CNAME`'e işaret etmemelidir; hedefin kendi `A`/`AAAA` kaydı olması beklenir.

### TXT — Serbest Metin ve Doğrulama

`TXT` kayıtları başlangıçta serbest metin için tasarlanmıştı, ama pratikte bir sürü protokolün taşıyıcısı oldu: alan sahipliği doğrulaması (`... verification=`), SPF, DKIM anahtarları, DMARC politikaları hep `TXT` (veya alt isimlerdeki `TXT`) üzerinden taşınır. Bir `TXT` kaydının RDATA'sı, her biri sınırlı uzunlukta olan bir veya daha fazla metin parçasından oluşur; uzun değerler (örneğin DKIM açık anahtarları) birden fazla parçaya bölünür ve okunurken birleştirilir.

### NS ve SOA — Zone'un İskeleti

`NS` (Name Server) kayıtları, bir zone'un authoritative sunucularını listeler ve delegation'ı gerçekleştiren mekanizmadır. Hem üst zone'da (delegation'ı gösteren "glue" bağlamında) hem de zone'un kendi içinde bulunurlar. `SOA` (Start of Authority) kaydı ise zone'un yönetim meta verisini taşır: birincil name server, sorumlu e-posta, bir seri numarası (serial) ve secondary sunucuların zone transferini nasıl yenileyeceğini belirleyen `refresh`, `retry`, `expire` zamanlayıcıları ile `minimum` (negatif cevapların TTL'inde rol oynayan) alanı. Serial numarasının artırılması, secondary'lerin "zone değişti, çek" sinyalini almasının temelidir.

### PTR — Ters Çözümleme

`PTR` kaydı, IP'den isme giden ters yönü sağlar ve özel bir isim uzayında (IPv4 için `in-addr.arpa`, IPv6 için `ip6.arpa`) yaşar. Bir sunucunun kendini tanıtırken kullandığı ters DNS, özellikle e-posta teslimatında itibar (reputation) açısından önemlidir; birçok mail sunucusu, gönderenin IP'sinin geçerli bir `PTR`'ye ve o `PTR`'nin de tekrar aynı IP'ye çözülüp çözülmediğine (forward-confirmed reverse DNS) bakar.

### SRV, CAA ve Diğerleri

`SRV` kaydı, bir servisin hangi host ve portta çalıştığını protokol düzeyinde bildirir; öncelik ve ağırlık taşır. `CAA` kaydı ise hangi sertifika otoritelerinin (CA) o alan adı için sertifika düzenleyebileceğini kısıtlar; yanlış sertifika düzenlenmesine karşı bir savunma katmanıdır. Bunların yanında DNSSEC ile gelen imza ve anahtar kayıtları (`RRSIG`, `DNSKEY`, `DS`, `NSEC`/`NSEC3`) vardır; bunlar cevapların authoritative kaynaktan geldiğini kriptografik olarak doğrulamayı sağlar.

## Çözümleme (Resolution): Bir Sorgu Nasıl Cevaplanır?

Çözümlemenin merkezinde iki farklı sunucu rolünü ayırmak yatar ve bu ayrım çok kişi tarafından karıştırılır:

- **Recursive resolver** (özçözücü): İstemci adına işin tamamını üstlenen, gerekirse birçok sunucuya sorup nihai cevabı toparlayan ve cache tutan sunucudur. İşletim sistemi ayarlarınızdaki DNS sunucusu (ISP'ninki ya da kamuya açık çözücüler) genelde budur.
- **Authoritative server** (yetkili sunucu): Belirli bir zone'un gerçek verisini barındıran, "bu alan için doğru cevap bende" diyen sunucudur. Recursive değildir; sadece kendi zone'u hakkında konuşur.

### Adım Adım İteratif Çözümleme

`www.ornek.com`'un A kaydını çözmek istediğinizi düşünelim ve resolver'ın cache'inin boş olduğunu varsayalım. Süreç şöyle işler:

1. Recursive resolver bir kök sunucuya sorar. Kök, `com` için değil ama "`com` işlerini şu TLD sunucularına sor" diye bir yönlendirme (referral) döner.
2. Resolver `com` TLD sunucusuna sorar. O da nihai cevabı bilmez ama "`ornek.com`'un authoritative sunucuları bunlar" diye NS referral'ı verir.
3. Resolver `ornek.com`'un authoritative sunucusuna sorar. Bu sunucu `www.ornek.com` için gerçek `A` kaydını (veya bir `CNAME`'i) döner.
4. Eğer `CNAME` döndüyse resolver hedef isim için 1. adımdan itibaren süreci tekrarlar.

Buradaki önemli kavramsal ayrım şu: resolver ile authoritative arasındaki iletişim **iteratif** (her sunucu ya cevabı ya da bir sonraki durağı verir), istemci ile recursive resolver arasındaki iletişim ise **recursive** (resolver tüm zahmeti üstlenip tek nihai cevabı getirir) yürür.

### Taşıma Katmanı: UDP, TCP ve Şifreli DNS

DNS geleneksel olarak UDP üzerinden ve belirli bir port üzerinden konuşur; UDP'nin bağlantısız yapısı, tek paketlik küçük sorgular için düşük gecikme sağladığından tercih edilmiştir. Fakat cevap belirli bir boyutu aşarsa (özellikle DNSSEC imzaları ya da uzun kayıt listeleri devreye girince) mesaj UDP'ye sığmaz. Bu durumda sunucu cevabı "truncated" (kısaltılmış) işaretler ve istemci sorguyu TCP üzerinden tekrarlar. Yani "DNS sadece UDP'dir" yaygın ama yanlış bir inanıştır; sağlam bir istemci TCP fallback'i de destekler. Modern gizlilik ihtiyaçları ise DNS-over-TLS ve DNS-over-HTTPS gibi şifreli taşıma yöntemlerini getirdi; bunlar sorgu içeriğini yol üzerindeki gözlemcilerden gizler.

### Negatif Cevaplar

Çözümlemenin sadece "bulundu" ile bitmediğini unutmayın. Bir isim gerçekten yoksa authoritative sunucu `NXDOMAIN` döner; isim var ama istenen türde kayıt yoksa boş bir "NODATA" cevabı gelir. Bu negatif cevaplar da cache'lenir; bu yüzden "kaydı yeni ekledim ama hâlâ yok diyor" durumunun bir sebebi, daha önce alınmış bir negatif cevabın cache süresi dolana kadar tutulmasıdır.

## Cache: DNS'in Performansını Ayakta Tutan Katman

DNS'in her sorguyu kökten authoritative'e kadar baştan çözmesi felaket olurdu; kök ve TLD sunucuları anında ezilirdi ve her isim çözümlemesi yüzlerce milisaniye sürerdi. **Cache**, bu maliyeti ortadan kaldıran mekanizmadır ve DNS'in ölçeklenebilirliğinin asıl sırrıdır.

Cache tek bir yerde değil, bir zincir boyunca birçok katmanda bulunur:

- **Uygulama / kütüphane cache'i:** Bazı runtime'lar ve HTTP istemcileri çözümlenmiş adresleri kendi içlerinde tutar. Bu, en sinsi katmandır çünkü işletim sistemi ya da resolver seviyesinde yaptığınız temizlik buraya işlemez.
- **İşletim sistemi / stub resolver cache'i:** OS seviyesinde tutulan çözümlemeler.
- **Recursive resolver cache'i:** Asıl ağır işi yapan katman. Bir kez çözülen kayıt, TTL süresince buradan servis edilir ve tüm istemcilere onların adına hizmet eder.
- **Kayıt sahibinin authoritative sunucusu:** Cache değil, gerçeğin kaynağı.

Cache'in tuttuğu değer sadece nihai `A` kaydı değildir; çözücü, zincir boyunca öğrendiği `NS` referral'larını da cache'ler. Böylece bir sonraki `ornek.com` sorgusunda kökten değil, doğrudan `ornek.com`'un authoritative sunucusundan başlayabilir. İşte bu ara cache'lenme sayesinde kök sunucular, dünyanın tüm trafiğine rağmen görece sakin kalır.

## TTL: Cache'in Ne Kadar Yaşayacağını Kim Söyler?

**TTL (Time To Live)**, her kayda iliştirilen ve "bu değeri kaç saniye cache'te tutabilirsin" diyen bir süredir. TTL, DNS'teki en pratik ve en yanlış anlaşılan ayardır. Doğru mantığı şudur: TTL, tazelik (freshness) ile trafik/gecikme arasındaki bir denge düğmesidir.

- **Uzun TTL:** Kayıtlar uzun süre cache'te kalır. Bu, authoritative sunucuya daha az sorgu, daha hızlı çözümleme ve authoritative bir an için erişilemese bile dayanıklılık demektir. Bedeli, bir değişikliğin yayılmasının yavaş olmasıdır.
- **Kısa TTL:** Değişiklikler hızla görünür olur, ama authoritative sunucuya çok daha sık sorulur ve o sunucu bir sorun yaşarsa etkisi çabuk hissedilir.

TTL ile ilgili anlaşılması gereken kritik nokta, sürenin **cache'e girildiği andan** itibaren geri saydığıdır, sizin kaydı değiştirdiğiniz andan değil. Yani bir resolver kaydı TTL'in ortasında cache'lemişse, sizin değişikliğiniz o resolver'da ancak kalan süre dolduğunda görünür. Dünya genelinde farklı resolver'lar farklı zamanlarda cache'lediği için, bir değişiklik anlık değil, **TTL kadar bir zaman penceresine yayılarak** görünür hale gelir. Bu yüzden planlı bir IP değişikliği (örneğin sunucu göçü) yapacaksanız doğru yöntem şudur: değişiklikten yeterince önce TTL'i düşürürsünüz (ama eski, uzun TTL'li kayıtların cache'lerden temizlenmesi için o eski TTL kadar beklemek gerekir), göç anında kısa TTL sayesinde geçiş hızlı olur, ortalık durulunca TTL'i tekrar yükseltirsiniz.

Negatif cevapların TTL'i ayrı bir konudur ve genelde `SOA` kaydındaki `minimum` alanıyla ilişkilidir. Bir ismin "yok" olduğu bilgisi de belli bir süre cache'lenir; bu, yeni eklenen kayıtların neden hemen görünmediğini açıklayan en sık gözden kaçan sebeplerden biridir.

## Doğru Kullanım ve Tuzaklar

**TTL'in bir garanti değil bir tavsiye olduğunu kabul edin.** Bazı resolver'lar çok kısa TTL'leri kendi alt sınırlarına yükseltir, bazıları çok uzun TTL'leri kendi üst sınırlarına indirir. Yani "TTL'i 30 saniye yaptım, 30 saniyede yayılır" garantisi yoktur. Tasarımınızı, TTL'in yaklaşık bir alt sınır olduğu ama üstünün oynayabileceği varsayımıyla kurun.

**Propagasyon bir "yayılma" değil, cache'lerin süresinin dolmasıdır.** "DNS propagasyonu 48 saat sürüyor" cümlesindeki gerçek mekanizma, verinin bir yerlere itilmesi değil, eski değeri tutan cache'lerin TTL'lerinin tükenmesidir. Bunu doğru modellemek, bekleme süresini doğru tahmin etmenizi sağlar.

**Uygulama katmanı cache'ini hesaba katın.** Sunucu tarafındaki bazı ortamlarda, uzun ömürlü bir süreç bir ismi bir kez çözüp adresi sonsuza dek tutabilir; arkadaki IP değişse bile eski adrese bağlanmayı sürdürür. Bu, resolver'da hiçbir sorun olmamasına rağmen "DNS değişti ama uygulamam hâlâ eski yere gidiyor" tablosunu yaratır. Çözüm, çözümleme sonuçlarının makul aralıklarla yenilendiğinden emin olmaktır.

**CNAME zincirlerini ve apex kısıtını bilin.** Uzun `CNAME` zincirleri her adımı ayrı bir çözümleme turu yaptığından gecikme ekler. Apex'te `CNAME` kullanamama kısıtı gerçektir; sağlayıcıya özgü `ALIAS`/`ANAME` çözümleri kullanışlı olsa da standart olmadıkları için taşınabilirlikleri sınırlıdır.

## Yaygın Hatalar

**"Kaydı ekledim, hemen çalışmalı" beklentisi.** En sık yapılan hata budur. Değişiklikten önce alınmış bir cevap (pozitif ya da negatif) hâlâ cache'te olabilir. Yeni kayıtlarda özellikle negatif cache tuzağı geçerlidir: siz kaydı eklemeden önce birileri o ismi sorup `NXDOMAIN`/NODATA aldıysa, o negatif cevabın TTL'i dolana kadar yeni kaydınız o resolver'da görünmez.

**Tanılamayı yanlış katmanda yapmak.** `ping` ya da tarayıcı ile "çalışıyor mu" bakmak, hangi katmanın hangi değeri döndürdüğünü göstermez. Doğru yöntem, doğrudan **authoritative sunucuya** sorup gerçeğin ne olduğunu, sonra da bir recursive resolver'a sorup cache'in ne dediğini karşılaştırmaktır. Aradaki fark size sorunun cache mi yoksa yanlış yapılandırma mı olduğunu söyler. Sorgu araçları (yaygın olarak `dig` ve `nslookup`) belirli bir sunucuya sorgu yöneltmenize izin verir; hangi sunucuya sorduğunuzu bilerek karşılaştırma yapın.

**TTL'i göç anında düşürmek.** TTL düşürmenin faydası, ancak eski (yüksek) TTL cache'lerden temizlendikten sonra ortaya çıkar. Göçün tam ortasında TTL düşürmek geç kalmış bir hamledir; TTL düşürme, göçten en az eski TTL kadar önce yapılmalıdır.

**Round-robin'i load balancing sanmak.** Birden çok `A` kaydı dönmek yükü kabaca dağıtabilir ama sağlık kontrolü, ağırlıklandırma ya da otururum yapışkanlığı (session stickiness) sağlamaz. Çöken bir sunucunun IP'si listede kalmaya devam eder ve bir kısım istemci ona düşer. Gerçek yük dengeleme ve failover, ayrı bir katmanın (load balancer veya sağlık kontrollü DNS servisi) işidir.

**`MX` ve diğer kayıtları `CNAME`'e işaret ettirmek.** `MX` hedefinin doğrudan adres kaydı olan bir isme işaret etmesi gerekir; bir `CNAME`'e işaret etmek standart dışıdır ve teslimat sorunlarına yol açabilir.

**Aynı isimde çelişen türleri barındırmaya çalışmak.** `CNAME` olan bir isme `A`, `MX` veya `TXT` eklemeye çalışmak kural ihlalidir ve öngörülemeyen davranışa yol açar.

## En İyi Pratikler

**TTL stratejisini niyete göre seçin.** Nadiren değişen, kararlı kayıtlar için uzun TTL kullanın; bu hem performans hem dayanıklılık kazandırır. Değişmesi planlanan ya da failover senaryosuna dahil olan kayıtlarda göçten önce TTL'i düşürüp sonra geri yükseltin. TTL'i "her ihtimale karşı hep kısa tutayım" yaklaşımı, authoritative sunucunuza gereksiz yük bindirir ve o sunucu bir sorun yaşadığında etkisini büyütür.

**Değişikliği iki katmanda doğrulayın.** Bir değişikliği yayınladıktan sonra önce authoritative sunucudan gerçeği teyit edin (değişiklik authoritative'de göründü mü?), sonra dış recursive resolver'lardan cache durumunu izleyin. Bu ikili doğrulama, "sorun bende mi cache'te mi" sorusunu kesin cevaplar.

**Birden çok authoritative sunucu ve coğrafi dağıtım kullanın.** Zone'unuzu tek bir authoritative sunucuya bağımlı bırakmak tek nokta arızası (single point of failure) yaratır. Birden fazla, tercihen farklı ağlarda ve coğrafyalarda dağıtılmış authoritative sunucu, DNS'inizi hem dayanıklı hem de düşük gecikmeli yapar.

**E-posta ve güvenlik kayıtlarını eksiksiz kurun.** Bir alan adı e-posta gönderiyorsa SPF, DKIM ve DMARC'ı doğru `TXT`/kayıt yapılandırmasıyla oturtun; aksi halde e-postalarınız spam'e düşer. Sertifika düzenlemesini kısıtlamak için `CAA`, gizlilik ve bütünlük için imkân varsa DNSSEC değerlendirin. DNSSEC'in cevapların authoritative kaynaktan geldiğini doğruladığını, ama cevap içeriğini şifrelemediğini (o ayrı bir katman olan şifreli taşımanın işi olduğunu) akılda tutun.

**Zone verisini kod gibi yönetin.** Zone dosyalarını versiyon kontrolünde tutmak, değişiklikleri gözden geçirilebilir ve geri alınabilir kılar. Manuel panel düzenlemeleri, tek harflik hataların (yanlış TTL, eksik nokta, çelişen tür) üretime sızmasının başlıca yoludur. `SOA` serial'ını disiplinli artırmak da secondary'lerin senkron kalmasını güvenceye alır.

**Bağımlılıklarınızı DNS üzerinden anlayın.** Modern mimarilerde servis keşfi (service discovery), CDN yönlendirmesi ve failover'ın çoğu DNS'e dayanır. DNS'i "kur ve unut" bir bileşen değil, mimarinizin gecikme, dayanıklılık ve doğruluk özelliklerini doğrudan belirleyen aktif bir katman olarak görün. Bir kesinti (outage) sırasında ilk bakılacak yerlerden biri neredeyse her zaman DNS ve onun cache/TTL davranışıdır.

## Özet

DNS'i doğru kullanmanın anahtarı, onu tutarlı bir veritabanı değil, **TTL ile yönetilen cache katmanları üzerine kurulu, gevşek tutarlı ve dağıtık** bir sistem olarak görmektir. Kayıt türleri verinin ne olduğunu (`A`/`AAAA` adres, `CNAME` takma ad, `MX` posta, `TXT` metin/doğrulama, `NS`/`SOA` zone iskeleti, `PTR` ters yön) tanımlar; çözümleme bu veriyi kökten authoritative'e uzanan yetki devri zinciriyle bulur; cache bu bulmayı ölçeklenebilir kılar; TTL ise cache'in tazeliği ile trafiği arasındaki dengeyi belirler. Bu dört kavramı birlikte düşündüğünüzde, "neden hemen yayılmadı", "neden eski adrese gidiyor", "neden apex'i CNAME'leyemiyorum" gibi soruların cevabı kendiliğinden ortaya çıkar.
