# Mikroservis vs Monolit: Takaslar, Dağıtık Vergi ve "Monolith-First" Yaklaşımı

## Giriş: Neyi tartışıyoruz?

Yazılım mimarisinde "mikroservis mi, monolit mi?" sorusu son on yılın en çok yanlış anlaşılan tartışmalarından biridir. Çoğu zaman bu, teknik bir tercihten çok bir moda savaşı gibi sunulur: monolit "eski ve kötü", mikroservis "modern ve doğru" olarak kodlanır. Bu çerçeveleme baştan yanlıştır. Doğru soru "hangisi üstün?" değil, "bu takımın, bu problemin ve bu ölçeğin altında hangi mimari daha az toplam maliyet üretir?" sorusudur.

Bu makale kavramı tanımlayarak başlayacak, ardından işin **kök nedenine** inecek: mikroservise geçildiğinde neden karmaşıklık ortadan kalkmaz da sadece **yer değiştirir**? Somut örneklerle "dağıtık vergi" (distributed tax) kavramını, servis sınırlarının (bounded context) nasıl çizilmesi gerektiğini, "monolith-first" ilkesinin neden ciddiye alınması gerektiğini ve sahada en sık yapılan hataları ele alacağız.

---

## Tanımlar: İki mimarinin ne olduğu ve ne olmadığı

### Monolit nedir?

**Monolit**, bir uygulamanın tüm işlevlerinin tek bir dağıtım biriminde (deployable unit) toplandığı mimaridir. Tek bir kod tabanı derlenir/paketlenir ve tek bir süreç (process) olarak çalışır; modüller birbirini bellek içi fonksiyon çağrılarıyla (in-process call) kullanır.

Burada kritik bir yanlış anlamayı düzeltmek gerekir: **monolit, "spagetti kod" demek değildir.** İyi tasarlanmış bir monolit, içinde net modül sınırları olan, katmanlı ve modüler bir yapı olabilir. Buna genellikle **modular monolith** (modüler monolit) denir. Monolit "kötü kod", mikroservis "iyi kod" anlamına gelmez; bunlar birbirinden bağımsız eksenlerdir. Kötü sınırlanmış bir monolit kadar, yanlış bölünmüş bir mikroservis ağı da felakettir.

### Mikroservis nedir?

**Mikroservis mimarisi**, uygulamanın birbirinden bağımsız olarak dağıtılabilen (independently deployable), her biri kendi süreci içinde çalışan ve genellikle kendi verisine sahip küçük servislere bölündüğü mimaridir. Servisler birbirleriyle ağ üzerinden (HTTP/gRPC gibi senkron protokoller veya mesaj kuyrukları gibi asenkron mekanizmalarla) konuşur.

Tanımdaki en önemli iki kelime **"bağımsız dağıtılabilir"** ve **"ağ üzerinden"**dir. Bir sistemi 20 parçaya bölüp hepsini hâlâ birlikte deploy etmek zorundaysanız, mikroservisin maliyetini ödeyip faydasını alamıyorsunuz demektir; buna **distributed monolith** (dağıtık monolit) denir ve iki dünyanın da en kötüsüdür.

---

## Kök neden: Karmaşıklık yok olmaz, yer değiştirir

Bu tartışmanın kalbindeki tek en önemli fikir şudur: **Mikroservise geçmek karmaşıklığı azaltmaz; onu kod düzeyinden operasyon ve ağ düzeyine taşır.**

### Neden böyle oluyor?

Monolitte iki modül birbirini çağırdığında bu bir **fonksiyon çağrısıdır**. Bu çağrı:

- Neredeyse anında (nanosaniyeler) gerçekleşir,
- Ya çalışır ya derleme zamanı hatası verir,
- Aynı bellek adres alanında olduğu için serializasyon gerektirmez,
- Ya tümüyle olur ya hiç olmaz; kısmi başarısızlık (partial failure) diye bir kavram yoktur.

Aynı iki modülü iki ayrı servise böldüğünüzde, o fonksiyon çağrısı bir **ağ çağrısına (remote call)** dönüşür. Ve ağ çağrısı bambaşka bir canavardır. Onlarca yıl önce formüle edilen **"Distributed Computing'in Yanılgıları" (Fallacies of Distributed Computing)** tam olarak bunu anlatır. Geliştiriciler dağıtık sistemleri tasarlarken sessizce şu yanlış varsayımları yaparlar:

1. Ağ güvenilirdir (reliable),
2. Gecikme (latency) sıfırdır,
3. Bant genişliği sonsuzdur,
4. Ağ güvenlidir (secure),
5. Topoloji değişmez,
6. Tek bir yönetici vardır,
7. Taşıma maliyeti (transport cost) sıfırdır,
8. Ağ homojendir.

Bunların **hepsi yanlıştır.** Ağ paket düşürür, gecikme değişkendir, çağrı zaman aşımına uğrayabilir, karşı taraf yanıt vermeden ölebilir. Monolitte var olmayan tüm bu problemler, servisleri böldüğünüz anda sizin problemleriniz haline gelir. İşte bu yüzden karmaşıklık "yok olmaz, yer değiştirir": derleyicinin sizin için hallettiği tip güvenliği, atomik çağrı ve determinizm garantilerini kaybeder; yerine **retry, timeout, circuit breaker, idempotency, dağıtık izleme (distributed tracing)** ve **eventual consistency** ile uğraşmaya başlarsınız.

---

## Dağıtık vergi (Distributed Tax): Somut olarak neyi ödüyorsunuz?

"Dağıtık vergi" terimi, mikroservise geçtiğinizde **iş mantığıyla hiç ilgisi olmayan** ama zorunlu olarak ödemeniz gereken sabit maliyetleri anlatır. Bu bir metafor değil; her kalemi tek tek sayılabilir bir maliyettir.

### 1. Ağ ve serializasyon maliyeti

Bellek içi bir çağrı bedavaydı. Şimdi her servis sınırında veri **serialize** edilip (JSON/Protobuf) ağdan geçip karşı tarafta **deserialize** edilmek zorunda. Bir kullanıcı isteği monolitte 3 fonksiyon çağrısıyla bitiyorken, mikroserviste 3 ayrı ağ turuna (round-trip) dönüşebilir. Her turun kendi gecikmesi vardır ve bunlar **toplanır**. Bir sayfa 10 servise çağrı yapıyorsa, en yavaş servisin kuyruğu (tail latency) tüm sayfanın hızını belirler.

### 2. Kısmi başarısızlık ve dayanıklılık (resilience) maliyeti

Monolitte "A modülü B modülünü çağırdı ve B çöktü" senaryosunda uygulama zaten tek parça olduğu için ikisi birlikte durur. Mikroserviste B servisi ayakta ama **yavaş** olabilir. Bu, monolitteki bir çökmeden çok daha sinsidir: A servisi B'yi beklerken thread'lerini tüketir, kuyruğu dolar ve **A da çöker**. Bir servisin yavaşlığı zincirleme tüm sistemi kilitler; buna **cascading failure** denir.

Bunu önlemek için artık yazmak zorunda olduğunuz kod:

- **Timeout**: Bir çağrı sonsuza kadar bekleyemez.
- **Retry** (ve akıllı retry: exponential backoff + jitter): Ama dikkatli olmazsanız retry'lar çöken servisi daha da ezer (retry storm).
- **Circuit breaker**: Karşı servis sürekli hata veriyorsa bir süre çağırmayı bırakıp hızlı hata dönmek.
- **Bulkhead**: Bir servise giden çağrıları izole etmek ki o servis çökünce tüm thread havuzunu tüketmesin.

Bu kodların **hiçbiri iş değeri üretmez**. Sadece dağıtık olmanın vergisidir.

### 3. Veri tutarlılığı maliyeti (belki de en pahalısı)

Monolitte "sipariş oluştur ve stoktan düş" işlemi tek bir **veritabanı transaction'ı** içinde atomik yapılabilir: ya ikisi de olur ya hiçbiri (ACID). Her servisin kendi veritabanı olduğunda bu lüksü kaybedersiniz. İki farklı veritabanına yayılan bir işlemi atomik yapamazsınız.

Çözüm olarak **saga pattern** gibi desenlere başvurursunuz: her adım kendi başına commit edilir, bir adım başarısız olursa önceki adımları geri almak için **compensating transaction** (telafi işlemi) çalıştırırsınız. Ama bu, "stoktan düştüm ama ödeme başarısız oldu, şimdi stoğu geri eklemem lazım" gibi mantığı **elle** yazmanız demektir. Sistem artık **eventual consistency** ile çalışır: bir an için sipariş var ama stok henüz düşmemiş olabilir. Kullanıcıya ve iş ekibine bu "geçici tutarsızlık" penceresini açıklamak zorunda kalırsınız.

### 4. Operasyon ve gözlemlenebilirlik (observability) maliyeti

Tek bir monolitin logları tek yerdedir. Bir isteğin izini sürmek `grep` kadar kolaydır. 15 servise yayılmış bir istekte, tek bir kullanıcı tıklamasının nereden geçtiğini görmek için:

- **Distributed tracing** (her isteğe bir correlation ID / trace ID takıp servisler arası taşımak),
- Merkezi **log aggregation**,
- Servis başına ayrı **metrik** ve **alerting**,
- **Service discovery**, **load balancing**, muhtemelen bir **service mesh**

kurmak zorundasınız. Ayrıca 15 servisin her biri ayrı deploy pipeline'ı, ayrı sürüm yönetimi, ayrı ölçeklendirme politikası ister. **CI/CD ve platform olgunluğu** artık isteğe bağlı değil, hayatta kalma şartıdır.

### Verginin özeti

Dağıtık vergi şu demektir: mikroservise geçtiğiniz **ilk gün**, henüz hiçbir ölçeklenme faydası almadan, yukarıdaki maliyetlerin hepsini peşin ödemeye başlarsınız. Fayda ise ancak **belirli bir ölçekten ve takım büyüklüğünden sonra** ortaya çıkar. Kritik soru: "Verginin faydayı geçtiği noktaya ulaştım mı?"

---

## Sınır (Bounded Context): Doğru yeri kesmek her şeydir

Mikroservis mimarisinin başarısı veya başarısızlığı neredeyse tamamen **servisleri nereden böldüğünüze** bağlıdır. Yanlış çizilen bir sınır, dağıtık verginin tamamını ödettirir ama hiçbir faydasını vermez.

### Neden sınır bu kadar önemli?

Servisleri bölmenin amacı, birlikte değişen şeyleri birlikte, ayrı değişen şeyleri ayrı tutmaktır. Eğer iki servis her yeni özellikte **birlikte** değişmek ve **birlikte** deploy edilmek zorunda kalıyorsa, o sınır yanlış yerdedir. Bu durumda bağımsız dağıtım faydasını hiç alamazsınız ama ağ çağrısı maliyetini fazlasıyla ödersiniz. İşte bu, **distributed monolith** felaketinin kaynağıdır.

### Domain-Driven Design ve bounded context

Sağlıklı sınır çizmenin en olgun yöntemi **Domain-Driven Design (DDD)** ve onun **bounded context** kavramıdır. Bounded context, belirli bir dilin (ubiquitous language) ve modelin tutarlı olduğu iş alanıdır. Örneğin bir e-ticarette "sipariş", "ödeme", "stok", "kargo" farklı bounded context'lerdir. Bunların her birinin "müşteri" kavramı bile farklı anlamlar taşıyabilir: ödeme için müşteri bir fatura adresidir, kargo için bir teslimat noktasıdır.

**İyi bir servis sınırı, bir bounded context'in etrafından geçer.** Böyle çizildiğinde servisler arası çağrılar seyrek olur (çünkü sıkı ilişkili şeyler aynı servis içinde kaldı) ve servisler gerçekten bağımsız evrilebilir.

### Sınırı teknik katmandan değil, iş yeteneğinden çıkarın

Yaygın ve ölümcül bir hata, servisleri **teknik katmanlara** göre bölmektir: "bir UI servisi, bir business-logic servisi, bir database servisi". Bu, ağ üzerinden çizilmiş bir katmanlı mimaridir ve en kötüsüdür: tek bir kullanıcı özelliği için üç servisin de değişmesi gerekir. Doğru bölme **dikey** (iş yeteneğine göre) olmalıdır, yatay (teknik katmana göre) değil. Her servis kendi UI'dan verisine kadar dikey bir dilimi sahiplenmelidir.

### Conway Yasası'nı görmezden gelemezsiniz

**Conway Yasası**, bir organizasyonun ürettiği sistem tasarımının o organizasyonun iletişim yapısını yansıtacağını söyler. Bu bir gözlem değil, neredeyse bir doğa yasası gibi çalışır. Pratik sonucu şudur: servis sınırlarınız, takım sınırlarınızla uyumlu değilse çatışma çıkar. Bu yüzden birçok başarılı organizasyon **"inverse Conway maneuver"** uygular: istedikleri mimariyi elde etmek için önce **takım yapısını** o mimariye göre kurarlar. "Her servisin sahibi tek bir takımdır ve o takım servisi baştan sona sahiplenir" ilkesi, mikroservisin çalışması için organizasyonel ön koşuldur.

---

## Monolith-First: Neden çoğu proje monolitle başlamalı?

Sektörde ciddiye alınması gereken bir ilke vardır: **yeni bir sistem kurarken monolitle başlayın, mikroservise ancak gerçek bir ihtiyaç kanıtlandığında geçin.** Bu, "korkaklık" değil, mühendislik disiplinidir.

### Kök neden: Sınırları en başta doğru çizemezsiniz

Yeni bir üründe, iş alanını (domain) henüz tam anlamamışsınızdır. Bounded context'lerin nerede olduğunu ancak sistem büyüdükçe, gerçek kullanım desenleri ortaya çıktıkça öğrenirsiniz. Mikroservise en baştan geçerseniz, servis sınırlarını **en az bildiğiniz anda** betona dökmüş olursunuz.

Sorun şu: **Monolit içinde yanlış çizilmiş bir modül sınırını düzeltmek kolaydır** — bir refactor, birkaç fonksiyonu taşımak. Ama **mikroservisler arasında yanlış çizilmiş bir sınırı düzeltmek çok pahalıdır**: iki servisi birleştirmek veya sorumluluğu bir servisten diğerine taşımak, veritabanı migrasyonu, API değişikliği, koordineli deploy ve veri taşıma gerektirir. Yani mikroservis, sınır hatalarını **cezalandırır**; monolit **affeder**. En çok hata yapacağınız dönemde, en affedici mimaride olmak istersiniz.

### Doğru yol: Modüler monolit → gerektiğinde çıkarma (extraction)

Pratik ve olgun yaklaşım şudur:

1. **Modüler monolitle başlayın.** Kod tek deploy birimidir ama içinde **net modül sınırları** vardır. Modüller birbirine sadece açık arayüzlerle bağlanır, birbirlerinin veritabanı tablolarına doğrudan uzanmaz.
2. **Sınırları modül düzeyinde disiplinle koruyun.** Böylece ileride bir modülü servise çıkarmak istediğinizde, sınır zaten çizilmiş olur.
3. **Gerçek bir sinyal geldiğinde çıkarın.** O sinyal genellikle şudur: bir modül diğerlerinden **farklı hızda** ölçeklenmek zorunda, farklı bir takım tarafından **bağımsız** deploy edilmek istiyor, ya da farklı bir teknoloji/dayanıklılık profili gerektiriyor.

Bu, "büyük patlama" (big bang) yeniden yazımından çok daha güvenlidir. Genellikle en yüksek yükü çeken veya en bağımsız olan bir-iki servisi önce çıkarır, çoğunluğu monolitte tutarsınız. Netflix veya Amazon gibi devlerin mikroservise geçişini örnek almadan önce şunu hatırlayın: onlar bu geçişi **büyük ve olgun monolitleri ölçeklerken** yaptılar, sıfırdan başlarken değil.

### Ne zaman monolith-first'ü atlamak mantıklıdır?

Dürüst olmak gerekirse istisnalar vardır. Eğer:

- Takımınız zaten mikroservis operasyonunda **olgunsa** (güçlü platform, CI/CD, observability altyapısı hazır),
- Domain'i çok iyi biliyorsanız (örneğin daha önce benzer bir sistemi kurdunuz),
- Ölçek gereksinimi **baştan kesin ve büyükse**,

o zaman doğrudan servislerle başlamak savunulabilir. Ama bu, kuralın kendisi değil, bilinçli bir istisnadır. Varsayılan tercih monolith-first olmalı; aksini yapmak için gerekçeniz olmalıdır.

---

## Somut karşılaştırma: Aynı senaryo iki mimaride

Bir e-ticaret sitesinde "sipariş ver" akışını düşünelim: kullanıcı sepeti onaylar, stok kontrol edilir, ödeme alınır, sipariş kaydedilir, kargo tetiklenir.

**Monolitte:** Bunların hepsi tek bir transaction içinde çağrılabilir. Ödeme başarısız olursa transaction geri alınır (rollback), stok hiç düşmemiş gibi olur, tutarlılık ACID garantisiyle sağlanır. Loglar tek yerdedir, hata ayıklama basittir. Dezavantaj: Kara Cuma'da ödeme servisi çok yüklendiğinde, sadece ödeme kısmını ölçeklendiremezsiniz; **tüm** monoliti ölçeklendirmek zorundasınız. Ayrıca 200 kişilik bir mühendislik ekibi aynı kod tabanına aynı anda commit atmaya çalışırken merge ve deploy koordinasyonu kâbusa döner.

**Mikroserviste:** Ödeme servisi ayrı ölçeklenir, ayrı deploy edilir; ödeme takımı stok takımından bağımsız çalışır. Ama artık "stok düştü, ödeme başarısız" durumunda ACID rollback yok; saga ve compensating transaction yazmak zorundasınız. Bir siparişin izini sürmek için distributed tracing gerekir. Tek bir yavaş servis tüm akışı kilitleyebilir, bu yüzden circuit breaker ve timeout şart.

**Sonuç:** Küçük bir ekip ve orta ölçekte, monolit belirgin şekilde daha ucuz ve hızlıdır. Ekip 100+ mühendise, trafik farklı bileşenlerde farklı ölçeklenme profillerine ulaştığında, mikroservisin bağımsız deploy ve ölçekleme faydası dağıtık vergiyi haklı çıkarmaya başlar. Kırılım noktası **ekip büyüklüğü ve organizasyonel karmaşıklıktadır**, çoğu zaman ham trafikte değil.

---

## Yaygın hatalar ve tuzaklar

**1. Mikroservisi ölçek için değil, moda için seçmek.** "Herkes yapıyor" bir mimari gerekçe değildir. Faydayı somut olarak adlandıramıyorsanız (hangi servis, neden bağımsız ölçeklenmeli/deploy edilmeli), muhtemelen sadece vergi ödüyorsunuz.

**2. Distributed monolith yaratmak.** Servislere böldünüz ama hepsi hâlâ birbirine sıkı bağlı, birlikte deploy edilmek zorunda ve birbirinin veritabanına dokunuyor. Bu, her iki dünyanın en kötüsüdür: monolitin katılığı + mikroservisin ağ maliyeti.

**3. Paylaşılan veritabanı.** Birden çok servisin aynı veritabanına/tablolara doğrudan erişmesi, en yaygın gizli bağımlılıktır. Servisler bağımsız gibi görünür ama şema değiştiğinde hepsi birden kırılır. Kural: **her servis kendi verisinin tek sahibidir**, dışarıya sadece API'sıyla açılır.

**4. Sınırları çok küçük çizmek (nano-servisler).** Her fonksiyonu bir servise dönüştürmek, ağ çağrısı sayısını patlatır. "Mikro" küçüklük demek değil, **bağımsız değişebilirlik** demektir. Doğru büyüklük, bir bounded context kadardır.

**5. Kısmi başarısızlığı görmezden gelmek.** "Karşı servis hep ayakta olur" varsayımı. Timeout, retry ve circuit breaker olmadan yazılan servisler, ilk yavaşlamada zincirleme çöker.

**6. Senkron çağrı zincirleri kurmak.** A→B→C→D şeklinde uzun senkron çağrı zincirleri, gecikmeleri toplar ve tek bir halkanın çökmesini tüm zincirin çökmesine çevirir. Mümkün olduğunca asenkron (event-driven) iletişim tercih edilmeli, senkron zincirler kısa tutulmalıdır.

**7. Observability'yi sonraya bırakmak.** Distributed tracing ve merkezi log olmadan üretime çıkan bir mikroservis ağı, ilk ciddi hatada kör uçuşa döner. Bu altyapı, ilk servisten önce hazır olmalıdır.

**8. Organizasyonu hazırlamadan mimariyi değiştirmek.** Conway Yasası'nı görmezden gelmek. Tek bir servisin birden çok takıma dağıldığı ya da tek takımın onlarca servise baktığı yapılarda mimari işlemez.

---

## En iyi pratikler

- **Varsayılan olarak modüler monolitle başlayın.** Net modül sınırları koyun, modüller arası erişimi açık arayüzlerle sınırlayın, doğrudan tablo erişimini yasaklayın. Sınırları en başta koda gömün ki gerektiğinde çıkarma ucuz olsun.

- **Sınırları iş yeteneğine (bounded context) göre çizin, teknik katmana göre değil.** Dikey dilimler, yatay katmanlar değil. Birlikte değişenler birlikte kalsın.

- **Bir servis çıkarma kararını somut bir sinyale bağlayın:** bağımsız ölçekleme ihtiyacı, bağımsız deploy hızı, ayrı takım sahipliği veya farklı dayanıklılık profili. Sinyal yoksa çıkarmayın.

- **Her servisin verisi kendine ait olsun.** Paylaşılan veritabanı yasak. Servisler arası veri paylaşımı API veya event üzerinden.

- **Dayanıklılığı baştan tasarlayın:** timeout, retry (backoff + jitter), circuit breaker, bulkhead. Kısmi başarısızlığı bir istisna değil, normal durum olarak varsayın.

- **Mümkünse asenkron ve event-driven iletişim tercih edin;** senkron çağrı zincirlerini kısa tutun. Böylece servisler zamansal olarak (temporal coupling) birbirine bağımlı olmaz.

- **Observability'yi mimarinin bir parçası yapın:** distributed tracing (correlation/trace ID), merkezi log, servis başına metrik ve alert. Bunlar opsiyonel değil, ön koşul.

- **Tutarlılık modelini bilinçli seçin.** Servis sınırı geçen işlemlerde ACID yerine saga/eventual consistency olduğunu kabul edin ve iş ekibiyle bu "geçici tutarsızlık" penceresini konuşun.

- **Organizasyonu mimariye hizalayın (Conway).** Her servisin net bir sahibi olsun. Mimari kararını takım yapısından bağımsız vermeyin.

- **Geri dönüşü mümkün kılın.** İyi bir modüler monolit, hem servise çıkmayı hem de aşırı bölünmüş bir yapıdan geri konsolidasyonu kolaylaştırır. Mimariyi tek yönlü bir kapı gibi görmeyin.

---

## Sonuç

Mikroservis ile monolit arasındaki seçim, "modern vs eski" değil, **bir maliyet-fayda takasıdır**. Mikroservis, karmaşıklığı yok etmez; onu koddan operasyona taşır ve karşılığında **dağıtık vergi** ödetir: ağ gecikmesi, kısmi başarısızlık yönetimi, dağıtık veri tutarlılığı ve ağır operasyonel yük. Bu verginin faydaya dönüşmesi ancak yeterli **ölçek** ve özellikle yeterli **organizasyonel karmaşıklıkta** gerçekleşir.

Bu yüzden pratik kural nettir: iş alanını en az bildiğiniz başlangıçta, sınır hatalarını affeden **modüler monolitle** başlayın; sınırları disiplinle koruyun; ve mikroservise **moda için değil, kanıtlanmış bir ihtiyaç için** geçin. Doğru çizilmiş bir sınır her şeydir — yanlış sınır, iki mimarinin de en kötüsünü verir. En iyi mimari, en gösterişli olan değil, takımınızın bu problemi bu ölçekte **en az toplam maliyetle** çözmesini sağlayan mimaridir.
