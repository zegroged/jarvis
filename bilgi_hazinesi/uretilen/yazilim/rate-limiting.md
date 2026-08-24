# Rate Limiting (Hız Sınırlama)

## Tanım

Rate limiting, bir istemcinin (client) veya kaynağın belirli bir zaman penceresi içinde bir sisteme yapabileceği istek (request) sayısını sınırlayan bir denetim mekanizmasıdır. Amaç basit görünse de arkasındaki gerekçeler katmanlıdır: bir servisi aşırı yükten korumak, kapasiteyi kullanıcılar arasında **adil** biçimde paylaştırmak, kötü niyetli trafiği (brute-force, scraping, DoS) yavaşlatmak ve maliyeti öngörülebilir kılmak.

Rate limiting'i "kaç istek geçebilir" sorusuyla; onun yakın akrabası olan **throttling** kavramını ise "geçen isteklerin hızı nasıl düzenlenir" sorusuyla ayırt etmek faydalıdır. Pratikte ikisi iç içe geçer: sınıra ulaşıldığında sistem isteği ya reddeder (genellikle HTTP `429 Too Many Requests` ile), ya kuyruğa alır (throttle), ya da geciktirir.

Bu makale, rate limiting'in kalbindeki iki temel algoritmaya — **token bucket** ve **leaky bucket** — ve bunların dağıtık (distributed) sistemlerde nasıl doğru uygulanacağına, adil kullanım (fair use) garantilerinin nasıl kurulacağına odaklanır.

## Kök Neden: Neden Rate Limiting'e İhtiyaç Var?

Rate limiting bir "güzellik" değil, bir zorunluluktur; çünkü hiçbir sistemin kapasitesi sonsuz değildir. Bunu anlamak için birkaç kök nedeni ayrıştıralım.

**Sonlu kaynaklar ve kuyruk teorisi.** Bir sunucunun aynı anda işleyebileceği bağlantı (connection), CPU çekirdeği, bellek ve veritabanı bağlantı havuzu (connection pool) sonludur. Little's Law'a göre bir sistemdeki ortalama iş miktarı (L), varış hızı (λ) ile ortalama işlem süresinin (W) çarpımıdır: `L = λ × W`. Varış hızı λ kontrolsüz büyüdüğünde, sistemdeki iş birikir, kuyruklar uzar, gecikme (latency) katlanır ve sonunda sistem tamamen çöker. Rate limiting, tam olarak bu λ'yı sınırlayarak sistemi kararlı (stable) çalışma bölgesinde tutar.

**Kaskad çöküşü (cascading failure) ve gürültülü komşu.** Paylaşımlı bir sistemde tek bir istemci — bir hatalı retry döngüsü yüzünden ya da kötü niyetle — tüm kapasiteyi yutabilir. Buna "noisy neighbor" (gürültülü komşu) problemi denir. Rate limiting olmadan, bir müşterinin kontrolsüz trafiği diğer tüm müşterilerin servisini bozar. Dolayısıyla rate limiting aynı zamanda bir **izolasyon** (isolation) aracıdır.

**Öngörülemeyen maliyet.** Bulut çağında her istek gerçek para demektir: hesaplama, bant genişliği, üçüncü parti API çağrıları. Rate limiting, maliyeti öngörülebilir bir tavana bağlar.

**Güvenlik.** Şifre deneme (brute-force), OTP tahmin etme, credential stuffing gibi saldırıların hepsi "çok sayıda deneme" gerektirir. Denemeleri saniyede birkaçla sınırlamak, saldırının ekonomisini bozar.

Özetle rate limiting, kontrolsüz talebin karşısına bilinçli bir **backpressure** (geri basınç) mekanizması koyar: "artık kabul edemiyorum, yavaşla" der.

## Temel Algoritmalar

Rate limiting'in nasıl uygulandığı, seçilen algoritmaya bağlıdır. Dört klasik yaklaşımı, en zayıftan en güçlüye doğru inceleyelim; ana odağımız token ve leaky bucket olacak.

### Fixed Window (Sabit Pencere) Sayacı

En basit yaklaşım: zamanı sabit pencerelere böl (örneğin her dakika), her pencerede bir sayaç tut, sayaç limiti aşınca reddet, pencere değişince sayacı sıfırla.

Basitliği cazip olsa da ciddi bir kusuru vardır: **pencere kenarı patlaması** (boundary burst). Limit dakikada 100 ise, bir istemci pencerenin son saniyesinde 100, bir sonraki pencerenin ilk saniyesinde 100 istek gönderebilir. Sonuç: yaklaşık iki saniyelik bir aralıkta 200 istek — nominal limitin iki katı. Sistemi korumak istediğimiz "en kötü an" tam da budur. Bu yüzden fixed window, dağıtık ve yüksek trafikli sistemlerde tek başına yetersiz kalır.

### Sliding Window (Kayan Pencere) Log ve Sayaç

Kayan pencere, kenar patlamasını çözmeye çalışır. **Sliding window log** her isteğin zaman damgasını (timestamp) saklar ve "son N saniyedeki" istek sayısını kesin olarak hesaplar. Doğrudur ama bellek maliyeti yüksektir: her istemci için tüm zaman damgalarını tutmak gerekir.

**Sliding window counter** ise bir yaklaşım (approximation) sunar: mevcut ve önceki pencerenin sayaçlarını, geçen sürenin ağırlığıyla harmanlar. Örneğin şu anki pencerenin %25'i geçtiyse, efektif oran ≈ `önceki_pencere_sayaci × 0.75 + mevcut_pencere_sayaci` gibi bir formülle hesaplanır. Belleği azdır, kenar patlamasını büyük ölçüde yumuşatır; bu yüzden pratikte çok yaygındır. Kusuru, oranların pencere içinde düzgün dağıldığını varsaymasıdır — bu her zaman doğru değildir.

### Token Bucket (Jeton Kovası)

Token bucket, esnekliği ve doğruluğu dengeleyen, en çok sevilen algoritmadır. Zihinsel modeli şudur: elinizde sabit kapasiteli bir kova (bucket) var. Bu kovaya sabit bir hızla (refill rate) jetonlar (token) damlar. Her gelen istek bir (veya isteğin ağırlığına göre birkaç) jeton harcar. Kovada jeton varsa istek geçer ve jeton düşülür; jeton yoksa istek reddedilir veya bekletilir.

İki parametre her şeyi belirler:

- **Kapasite (burst boyutu):** Kovanın alabileceği maksimum jeton. Bu, izin verilen ani patlamanın (burst) büyüklüğüdür.
- **Doldurma hızı (refill rate):** Birim zamanda eklenen jeton sayısı. Bu, uzun vadeli **ortalama** hızı belirler.

Token bucket'ın zarafeti bu ayrımdadır: **ortalama hızı sınırlar ama makul patlamalara izin verir.** Bir kullanıcı bir süre sessiz kaldıysa kova dolar; sonra kısa bir anda biriken jetonları harcayıp bir burst yapabilir. Bu, gerçek dünya trafiğine çok uygundur — insanlar ve istemciler nadiren düzgün aralıklarla istek gönderir; kümeler (clusters) halinde gönderir.

Uygulama açısından güzel yanı, jetonları arka planda gerçekten "damlatmanıza" gerek olmamasıdır. Bunun yerine **lazy (tembel) hesaplama** yaparsınız: her istek geldiğinde, son güncellemeden bu yana geçen süreye bakıp `eklenmesi_gereken_jeton = geçen_süre × refill_rate` kadar jetonu (kapasiteyi aşmadan) eklersiniz, sonra harcamayı denersiniz. Yani sadece iki değer saklanır: mevcut jeton sayısı ve son güncelleme zamanı. Bu, dağıtık ortamda son derece verimlidir.

Kavramsal bir taslak:

```
istek_geldiginde(istemci, maliyet=1):
    simdi        = su_anki_zaman()
    gecen        = simdi - istemci.son_guncelleme
    istemci.jeton = min(kapasite, istemci.jeton + gecen * refill_rate)
    istemci.son_guncelleme = simdi
    eger istemci.jeton >= maliyet:
        istemci.jeton -= maliyet
        return IZIN_VER
    else:
        return REDDET   # HTTP 429
```

### Leaky Bucket (Sızdıran Kova)

Leaky bucket ilk bakışta token bucket'a benzer ama felsefesi terstir. Burada kova, gelen istekleri tutan bir **kuyruktur** (queue). İstekler kovaya damlar (varış düzensiz olabilir), ama kovanın dibindeki delikten **sabit bir hızla** sızar — yani işlenir. Kova dolarsa (kapasite aşılırsa), taşan istekler düşürülür (drop).

Kritik fark şudur:

- **Token bucket çıkışı düzensizdir (bursty).** Jeton varsa patlamaya izin verir. Ortalamayı sınırlar, anlık hızı değil.
- **Leaky bucket çıkışı pürüzsüzdür (smooth).** Ne kadar düzensiz gelirse gelsin, çıkış sabit hızdadır. Anlık hızı da sınırlar; trafiği "şekillendirir" (traffic shaping).

Bu yüzden leaky bucket, çıkış tarafında hız garantisi isteyen senaryolarda idealdir: örneğin arkadaki bir servisin saniyede en fazla X istek kaldırabildiği ve **kesinlikle** aşmak istemediğiniz durumlarda. Ağ ekipmanlarında ve trafik şekillendirmede (traffic shaping) klasik tercihtir.

Bedeli ise **gecikmedir (latency).** İstekler kuyrukta bekler; ani bir yük geldiğinde patlama emilmez, sıraya girer. Kullanıcı açısından bu, "reddedilmedim ama yanıtım geç geldi" demektir. Ayrıca kuyruk bellek tüketir ve kuyruk dolduğunda yine düşürme başlar.

### Token mu, Leaky mi?

Sezgisel karar: **Patlamalara nazik olmak ve düşük gecikme istiyorsan token bucket.** API'lerin çoğu bunu seçer, çünkü kullanıcı deneyimi açısından kısa patlamalara izin vermek makuldür ve isteği hemen ya kabul ya reddetmek (kuyrukta bekletmek yerine) daha öngörülebilirdir. **Çıkış hızını kesinlikle sabit tutman gereken, arkadaki kırılgan bir kaynağı koruduğun durumlarda leaky bucket.** İkisi birlikte de kullanılabilir: kenarda (edge) token bucket ile kabul et, arka uçta leaky bucket ile pürüzsüzleştir.

## Dağıtık Rate Limiting

Buraya kadar anlatılanlar tek bir sunucu için geçerlidir. Gerçek sistemler ise onlarca, yüzlerce sunucudan oluşur ve asıl zorluk buradadır. Sorunu netleştirelim: limit "dakikada 100 istek" ise, bu 100 tüm cluster geneli için mi, yoksa her sunucu için ayrı ayrı mı?

### Neden Naif Yaklaşım Bozulur?

Her sunucunun kendi yerel (local) sayacını tutması cazip görünür — hızlıdır, koordinasyon gerektirmez. Ama 10 sunucunuz ve global "dakikada 100" limitiniz varsa, her sunucuya 10 pay verirsiniz. Sorun şu ki, load balancer trafiği eşit dağıtmaz; bir istemci sürekli aynı sunucuya düşerse 10'da reddedilir, oysa global limit 100'dü. Tersine, trafik dağıldığında toplam 10 × 10 = 100'ü aşan efektif limitler ortaya çıkabilir. Yani **yerel sayaçlar ne adildir ne de doğrudur.** Dağıtık rate limiting'in kök problemi, **paylaşılan durumun (shared state) tutarlılığıdır.**

### Merkezi Depo (Genellikle Redis)

En yaygın çözüm, sayaçları/kovaları paylaşılan hızlı bir veri deposunda (çoğunlukla Redis) tutmaktır. Tüm sunucular aynı Redis anahtarına (key) danışır. Bu, global tutarlılık sağlar ama iki tehlike doğurur:

**1. Race condition (yarış durumu).** İki sunucu aynı anda "oku, kontrol et, yaz" yaparsa, ikisi de sayacı limitin altında görüp geçebilir; sonuç limitin aşılmasıdır. Çözüm, işlemi **atomik (atomic)** yapmaktır. Redis'te bunun standart yolu, tüm oku-hesapla-yaz mantığını tek bir sunucu tarafı (server-side) script'i içinde çalıştırmaktır (Redis'in gömülü Lua script motoru bu işi atomik olarak yürütür). Böylece "check ve decrement" bölünmez tek bir adım olur. Basit sayaçlar için `INCR` ve `EXPIRE` komut kombinasyonu da kullanılır; token bucket gibi durum içeren (stateful) mantık için script yaklaşımı tercih edilir.

**2. Gecikme ve tek nokta bağımlılığı.** Her istek için ağ üzerinden Redis'e gitmek gecikme ekler ve Redis'i kritik bir bağımlılık haline getirir. Redis yavaşlarsa veya düşerse ne olacak? Bu, tasarımın en önemli sorusudur (aşağıda "fail-open/fail-closed" başlığına bakın).

### Yerel + Merkezi Melez: Sliding/Token Bucket Kombinasyonu ve Yaklaşık Sayım

Saf merkezi yaklaşımın gecikmesini azaltmak için melez desenler kullanılır. Bir yaygın teknik, her sunucunun merkezi bütçeden **jeton paketi** (batch) çekmesidir: sunucu Redis'ten bir kerede N jeton "kiralar", yerelde harcar, bitince tekrar çeker. Bu, Redis'e gidiş sayısını N kat azaltır. Karşılığında bir miktar kesinlikten ödün verirsiniz — kiralanmış ama harcanmamış jetonlar kısa süreliğine "kayıp" görünebilir. Bu, dağıtık sistemlerin klasik ödünleşmesidir: **kesinlik (accuracy) ve performans/kullanılabilirlik arasında denge.** Çoğu üretim sistemi, mükemmel kesinlik yerine "yeterince yakın" ve düşük gecikmeli bir çözümü seçer; çünkü rate limiting'in amacı muhasebe değil korumadır.

### Gossip ve Yaklaşık Yaklaşımlar

Çok büyük ölçekte, bazı sistemler merkezi depoyu tamamen atlar ve sunucular sayımlarını birbirlerine periyodik olarak yayar (gossip protokolü). Bu, tam tutarlılık sağlamaz ama global durum hakkında "yeterince iyi" bir tahmin verir ve merkezi darboğazı ortadan kaldırır. Yaklaşık veri yapıları (örneğin sayım için probabilistik yapılar) bu bağlamda bellek tasarrufu için kullanılabilir. Bu yaklaşımlar, kesinliğin kritik olmadığı, ölçeğin ise çok büyük olduğu durumlara uygundur.

### Saat Kayması (Clock Skew) Problemi

Dağıtık rate limiting'in sinsi bir tuzağı, sunucu saatlerinin senkron olmamasıdır. Zaman pencerelerini veya jeton doldurmayı yerel saate göre hesaplayan bir sistemde, saatler birkaç yüz milisaniye kayarsa limitler tutarsızlaşır. Bu yüzden mümkün olduğunda **tek bir otoritatif zaman kaynağı** (örneğin merkezi deponun kendi zamanı) kullanılmalı; script içinde zaman hesaplaması yapılıyorsa deponun sunucu zamanı referans alınmalıdır. NTP ile saat senkronizasyonu şarttır ama tek başına yeterli güvence değildir.

## Adil Kullanım (Fair Use)

Rate limiting'in en incelikli boyutu adalettir. "Toplam trafiği sınırladım" demek yetmez; **kimin ne kadar pay aldığı** kritiktir. Kötü tasarlanmış bir limit, birkaç ağır kullanıcının tüm bütçeyi tüketip diğerlerini aç bırakmasına (starvation) yol açabilir.

### Doğru Anahtarlama (Keying): Sınırı Neye Göre Uyguluyoruz?

Adaletin ilk adımı, limitin **hangi boyuta** uygulandığını doğru seçmektir. Yaygın anahtarlar:

- **IP adresine göre:** Basittir ama tehlikelidir. Kurumsal NAT veya mobil operatör arkasında binlerce meşru kullanıcı tek bir IP paylaşabilir; onları haksızca cezalandırırsınız. Tersine, saldırgan IP havuzu döndürerek limiti aşabilir.
- **Kullanıcı/hesap kimliğine göre:** Kimliği doğrulanmış (authenticated) trafik için en adil yöntemdir. Her kullanıcı kendi kotasını alır.
- **API anahtarına (API key) göre:** Servisler arası (B2B) senaryolarda standarttır; her müşteriye plan seviyesine göre limit tanınır.
- **Uç noktaya (endpoint) göre:** Pahalı bir işlemi (örneğin rapor üretimi) ucuz bir işlemden (örneğin sağlık kontrolü) farklı sınırlamak mantıklıdır. Bu, isteğin "ağırlığını" (weight/cost) jeton maliyetine yansıtmakla birleştirilebilir.

Genellikle bu boyutlar katmanlanır: hem kullanıcı başına hem global, hem uç nokta başına limitler aynı anda uygulanır ve en kısıtlayıcı olan kazanır.

### Katmanlı Kotalar ve Öncelik

Adil kullanım çoğu zaman "eşit" değil, "orantılı" demektir. Ücretli bir müşteri, ücretsiz bir kullanıcıdan daha yüksek limit hak eder. Burada iki desen öne çıkar:

**Weighted fair queuing (ağırlıklı adil kuyruklama):** Her müşteri sınıfına kapasiteden bir pay ayrılır; bir sınıf payını kullanmıyorsa, boşta kalan kapasite geçici olarak başka sınıflara ödünç verilebilir (work-conserving davranış). Böylece hem izolasyon hem verimlilik sağlanır.

**Ayrılmış ve paylaşımlı kapasite:** Kapasitenin bir kısmı her müşteriye garantilenir (rezerve), kalanı ilk gelen ilk alır mantığıyla paylaşılır. Bu, garantili taban ile esnek tavanı birleştirir.

### Starvation ve Ağır Kullanıcı Problemi

Adaletin en büyük düşmanı starvation'dır: bir kullanıcının sürekli reddedilmesi. Global bir limitte tek başına baskın bir kullanıcı, saf FIFO'da diğerlerinin önünü sürekli kesebilir. Bunu önlemek için **kullanıcı başına** izolasyon (her kullanıcının kendi kovası) ve gerektiğinde adil kuyruklama gereklidir. Kritik ilke: **global bir sınır, kullanıcı başına sınırların yerini tutmaz.** İkisi birlikte kurulmalıdır — global sınır sistemi korur, kullanıcı başına sınır adaleti korur.

## Doğru Kullanım, Tuzaklar ve Yaygın Hatalar

### İstemciyle Doğru İletişim

Rate limiting sadece reddetmek değildir; **iyi iletişim kurmaktır.** Standart pratikler:

- Sınır aşıldığında `429 Too Many Requests` durum kodu döndürün.
- **`Retry-After`** başlığıyla istemciye ne kadar bekleyeceğini söyleyin. Bu, iyi davranan istemcilerin gereksiz yere tekrar denemesini önler.
- Mevcut kotayı bildiren başlıklar ekleyin (yaygın gelenek `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` benzeri alanlardır; not: bu başlık isimleri fiilen standartlaşmış geleneklerdir, farklı servisler farklı adlandırabilir). Böylece istemci limite yaklaştığını önceden görüp kendini ayarlayabilir.

Bu şeffaflık, ekosistemin sağlığı için kritiktir: istemci ne zaman duracağını bilirse, hem kendini hem sizi korur.

### Retry Storm ve Thundering Herd

En yaygın ve en yıkıcı hatalardan biri, **istemci tarafında yanlış retry** davranışıdır. Bir istemci 429 aldığında hemen ve sabit aralıklarla tekrar denerse, üstelik binlerce istemci aynı anda bunu yaparsa, sistem toparlanamaz — buna **retry storm** veya **thundering herd** denir. Sınır tam da yükü azaltmalıyken, yanlış retry yükü artırır.

Doğru çözüm istemci tarafındadır ama sunucu bunu teşvik etmelidir: **exponential backoff** (üstel geri çekilme) ve **jitter** (rastgele sapma). Backoff, her başarısız denemede bekleme süresini katlar (1s, 2s, 4s...); jitter ise bu süreye rastgelelik ekler ki tüm istemciler aynı anda tekrar denemesin. Jitter olmadan backoff yeterli değildir, çünkü senkronize istemciler yine dalga dalga gelir. `Retry-After` başlığı vermek, sunucunun bu doğru davranışı istemciye önermesinin yoludur.

### Fail-Open mu, Fail-Closed mı?

Dağıtık rate limiting merkezi bir depoya bağlıysa, o depo düştüğünde ne yapmalı? İki seçenek var ve bu bir tasarım kararıdır:

- **Fail-open:** Depo erişilemezse isteklere izin ver. Kullanılabilirliği (availability) korur ama koruma katmanını geçici olarak kaldırır — tam da yük anında bu tehlikeli olabilir.
- **Fail-closed:** Depo erişilemezse reddet. Korumayı korur ama kendi rate limiter'ınız yüzünden servisinizi kapatmış olabilirsiniz.

Doğru yanıt bağlama bağlıdır. Güvenlik kritik uç noktalarda (login gibi) fail-closed daha güvenlidir; genel API trafiğinde çoğu sistem fail-open'ı tercih eder ama bunu **yerel bir yedek limitle** (local fallback) birleştirir: merkezi depo düşerse her sunucu tutucu bir yerel limitle çalışmaya devam eder. Böylece "ya hep ya hiç" tuzağından kaçılır.

### Sık Yapılan Diğer Hatalar

- **Yalnızca fixed window kullanmak:** Kenar patlaması yüzünden gerçek koruma sağlamaz. En azından sliding window counter veya token bucket'a geçin.
- **Race condition'ı görmezden gelmek:** Dağıtık sayaçta atomik olmayan oku-yaz, sessizce limiti aşar. Atomik script veya atomik komutlar şarttır.
- **Sadece global limit koymak:** Adaleti öldürür; tek bir ağır kullanıcı herkesi etkiler. Kullanıcı başına izolasyon ekleyin.
- **İç trafiği (retry, sağlık kontrolü, cron) sınıra dahil etmemek veya yanlış dahil etmek:** Sağlık kontrollerini sınırlarsanız monitoring bozulur; retry'ları saymazsanız gerçek yükü göremezsiniz. Sınıflandırma bilinçli yapılmalıdır.
- **Zaman penceresini yerel saate güvenerek hesaplamak:** Clock skew tutarsızlık yaratır.
- **Sınıra ulaşıldığında sessizce düşürmek:** İstemci neden başarısız olduğunu bilmezse hatalı davranır. Net `429` ve `Retry-After` verin.
- **Limitleri sabit kodlamak (hard-code):** Trafik desenleri değişir; limitler yapılandırılabilir (configurable) olmalı, ideali dinamik ayarlanabilmelidir.

## En İyi Pratikler

Bir arada değerlendirildiğinde, sağlam bir rate limiting tasarımı şu ilkelere dayanır:

**Katmanlı savunma.** Tek bir limit her şeyi çözmez. Global (sistemi korur), kullanıcı/API anahtarı başına (adaleti korur) ve uç nokta başına (pahalı işlemleri korur) limitleri birlikte uygulayın. Kenarda (edge/gateway) kaba bir limit, arka uçta ince ayarlı limitler koyun.

**Algoritmayı amaca göre seçin.** API'lerin çoğunda token bucket doğru varsayılandır: patlamalara nazik, düşük gecikmeli, uygulaması verimli. Çıkış hızını kesinlikle sabitlemeniz gereken, arkadaki kaynağı koruduğunuz yerlerde leaky bucket kullanın. Basit ve yaklaşık bir çözüm yeterliyse sliding window counter idealdir.

**Dağıtık durumu atomik yönetin.** Merkezi bir depo (yaygınca Redis) kullanıyorsanız, kontrol-ve-güncelleme mantığını atomik script içine alın. Gecikmeyi düşürmek için jeton kiralama (batch) gibi melez desenler düşünün ve kesinlik/performans ödünleşmesini bilinçli yapın.

**Zamanı otoritatif bir kaynaktan alın.** Clock skew'i önlemek için pencere ve doldurma hesaplarını merkezi deponun zamanına dayandırın; NTP senkronizasyonunu ihmal etmeyin.

**Nazikçe başarısız olun.** Fail-open/fail-closed kararını bilinçli verin ve merkezi depo düştüğünde yerel bir yedek limitle çalışmaya devam edin. Güvenlik uç noktalarında daha tutucu (fail-closed) olun.

**İstemciye net konuşun.** `429`, `Retry-After` ve kota başlıklarıyla şeffaf olun. İyi davranan istemcileri exponential backoff ve jitter'a teşvik edin; retry storm'u tasarımınızla önleyin.

**Ölçün ve gözlemleyin.** Kaç isteğin reddedildiğini, hangi anahtarların sürekli limite takıldığını izleyin. Sürekli reddedilen meşru kullanıcılar, limitin yanlış ayarlandığının işaretidir; sürekli limite dayanan bir kullanıcı, ya kötü niyetlidir ya da daha yüksek plana ihtiyacı vardır. Rate limiting metrikleri, kapasite planlaması için de değerli sinyaldir.

**Adaleti açıkça tasarlayın.** "Toplamı sınırladım" demek yetmez. Kullanıcı başına izolasyon, katmanlı kotalar ve gerektiğinde ağırlıklı adil kuyruklama ile starvation'ı önleyin. Boşta kalan kapasitenin ödünç verilebildiği work-conserving tasarımlar hem adil hem verimlidir.

## Kapanış

Rate limiting yüzeyde "bir sayaç ve bir eşik" kadar basit görünür; derinlemesine bakıldığında ise kuyruk teorisi, dağıtık sistemlerde tutarlılık, atomiklik, saat senkronizasyonu, hata modu tasarımı ve adalet mühendisliğinin kesiştiği zengin bir alandır. Token bucket ve leaky bucket, bu alanın iki temel yapı taşıdır: biri patlamalara nazik ortalama hızı, diğeri pürüzsüz sabit çıkışı temsil eder. Doğru uygulanmış bir rate limiter, kullanıcı fark etmeden sistemi ayakta tutar; yanlış uygulanmışı ise korumaya çalıştığı sistemin kendisini çökertebilir. Bu yüzden rate limiting, "koydum ve unuttum" değil, sürekli ölçülüp ayarlanan yaşayan bir mühendislik kararıdır.
