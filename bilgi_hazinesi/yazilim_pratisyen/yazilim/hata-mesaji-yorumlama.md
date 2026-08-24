# Hata Mesajı ve Stack Trace Yorumlama

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Bir sistem çöktüğünde, bir istek 500 döndüğünde ya da müşteri "bir şeyler ters gitti" ekranıyla karşılaştığında, elimizde çoğu zaman tek bir şey vardır: bir hata mesajı ve ona eşlik eden bir stack trace. Bu, olay yerinde bıraktığı izlerdir. İşin özü aslında bir dedektiflik işidir; kod yazmak değil, kanıt okumaktır. Ve sahada gördüğüm en büyük beceri farkı da tam burada ortaya çıkar: iki mühendise aynı 200 satırlık stack trace'i verirsiniz, biri 30 saniyede kök nedene iner, diğeri iki saat log'un içinde kaybolur. Fark zekâ değildir; okuma disiplini ve zihinsel modeldir.

Hata yorumlama, hata ayıklamanın (debugging) ön aşamasıdır. Debugger'ı açıp breakpoint koymadan önce, elinizdeki metinden mümkün olan en fazla bilgiyi çıkarmak zorundasınız. Çünkü üretimde çoğu zaman debugger'ınız yoktur. Elinizde sadece dün gece 03:14'te üretilmiş bir log satırı, bir Sentry kaydı ya da bir kullanıcının ekran görüntüsü vardır. O tek kanıttan ne kadar çok şey okuyabilirseniz, o kadar hızlı ve o kadar az reprodüksiyon denemesiyle çözersiniz.

Bu metin, o okuma disiplinini anlatır: bir stack trace önünüze düştüğünde profesyonelin kafasında ne olup bittiğini, hangi sırayla baktığını, neyi görmezden geldiğini ve aceminin nerede yoldan çıktığını.

Bir noktanın altını çizeyim: hata yorumlama, "hata çözme"nin en görünmez ama en belirleyici parçasıdır. Ölçtüğüm ekiplerde bir üretim olayının çözüm süresinin çoğu, düzeltmeyi yazmakta değil, *doğru yeri bulmakta* geçer. Kod değişikliğinin kendisi çoğu zaman üç satırdır ve iki dakika sürer; ondan önceki iki saat, "nerede" ve "neden" sorularına harcanır. Dolayısıyla bu beceriye yatırım, en yüksek getirili mühendislik yatırımlarından biridir; çünkü her olayı kısaltır, her nöbeti daha az acılı yapar.

## 2. Metodoloji ve karar ağacı: profesyonel nasıl ilerler

### Önce sınıflandır: bu ne tür bir hata?

Deneyimli birinin ilk yaptığı şey, hatayı okumadan önce kategorize etmektir. Çünkü kategori, arama stratejisini belirler. Kabaca beş aile vardır ve her biri farklı bir refleks tetikler:

- **Sözdizimi / derleme / tip hataları**: kod daha çalışmadan yakalanır. Bunlar en kolayıdır; derleyici size tam satırı ve genelde tam sebebi söyler. Deterministiktir, her seferinde aynı yerde patlar.
- **Çalışma zamanı istisnaları (null referans, index out of bounds, tip dönüşümü)**: kod çalışırken belirli bir veriyle patlar. Kod doğru görünür ama beklenmedik girdi gelmiştir.
- **Mantık hataları**: hiçbir istisna fırlamaz, sistem "çalışır" ama yanlış sonuç üretir. Bunların stack trace'i yoktur ve bu yüzden en sinsi olanlardır.
- **Kaynak / altyapı hataları**: bağlantı zaman aşımı, bellek yetmezliği (OOM), disk dolu, dosya tanıtıcısı tükenmesi, ağ hatası. Bunlar kodunuzda değil, kodunuzun içinde yaşadığı dünyada başlar.
- **Eşzamanlılık / zamanlama hataları**: race condition, deadlock, yalnızca yükte ortaya çıkan hatalar. Reprodüksiyonu en zor aile budur.

Bu sınıflandırma refleksi neden bu kadar önemli? Çünkü " connection timeout" gördüğümde koddaki fonksiyonu incelemeye başlamam; ağa, kaynak havuzuna (connection pool), karşı servisin sağlığına bakarım. "NullPointerException" gördüğümde ise doğrudan koda, o null'ın nereden geldiğine giderim. Yanlış aileye girerseniz, doğru araçla yanlış yerde kazarsınız.

### Stack trace'i doğru sırayla oku

Acemi stack trace'i yukarıdan aşağı, baştan sona okur ve ilk satıra takılır. Profesyonel farklı okur. Şu üç şeyi bu sırayla arar:

**Birincisi: gerçek istisna türü ve mesajı.** Genellikle en üsttedir (dil ve runtime'a göre değişir; Java/Python'da en dıştaki başlık, ama Python'da "asıl" olan en alttaki `raise`). Ama dikkat: mesajın kendisi bazen yalan söyler. "Connection refused" mesajı bağlantının reddedildiğini söyler ama *neden* reddedildiğini söylemez; asıl neden yanlış port, çökmüş servis ya da güvenlik duvarı olabilir.

**İkincisi: "senin kodun" hangi satırda.** Bir stack trace'in %80'i framework, kütüphane ve runtime çağrılarıdır. Bunlar gürültüdür. Profesyonelin gözü otomatik olarak kendi paket/namespace'ini tarar. Trace'te aşağı doğru inerken kendi kodunuzun göründüğü *ilk* satır, çoğu zaman altın satırdır; kontrolün sizden framework'e geçtiği ya da tam tersi noktadır.

**Üçüncüsü: neden zinciri (caused by / chained exceptions).** Modern runtime'lar istisnaları sarmalar. Java'da `Caused by:`, .NET'te `InnerException`, Python'da `During handling of the above exception, another exception occurred`. Buradaki kritik yargı şudur: **en dıştaki istisna semptomdur, en içteki `Caused by` genellikle hastalıktır.** Acemi en üstteki `ServiceException`'ı okur ve genel bir hata sanır; profesyonel dört `Caused by` aşağı iner ve en dipteki `SQLException: connection pool exhausted` satırını bulur. Asıl hikâye orada.

### "Şu belirtiyi görünce şu yöne giderim" refleksleri

Yıllar içinde oluşan örüntü tanıma budur. Birkaç somut örnek:

- **Null/undefined hatası, üretimde ama testte yok** → veri kaynaklı. Bir alan beklediğim gibi dolu gelmemiş. Testte hep dolu geliyordu çünkü test verisi temizdi. Gerçek veride bir null var. Yön: girdinin sınırına bak, veritabanı/API sınırına.
- **"Works on my machine" ama CI'da patlıyor** → ortam farkı. Sıralamaya bağlı test, zaman dilimi, dosya sistemi büyük/küçük harf duyarlılığı (Windows vs Linux), ya da açıkça deklare edilmemiş bir bağımlılık. Yön: ortam değişkenlerini ve versiyonları karşılaştır.
- **İlk N istekte çalışıyor, sonra yavaşlıyor ve patlıyor** → kaynak sızıntısı. Kapatılmayan bağlantı, büyüyen cache, temizlenmeyen thread. Yön: bellek/handle sayısını zaman içinde izle.
- **Aralıklı, tekrar üretilemeyen hata** → eşzamanlılık ya da dış bağımlılık. Yön: doğrudan debugger'a gitme, önce log'a zaman damgası ve korelasyon kimliği ekle, örüntüyü ara.
- **Stack trace'te hiç senin kodun yok, tamamen framework** → yanlış konfigürasyon ya da başlatma (bootstrap) hatası. Yön: koda değil, config'e ve dependency injection kurulumuna bak.

### Temel takas: ne kadar okuyup ne zaman denemeye geçmeli

Burada bir denge vardır. Bir uçta "analiz felci" var: stack trace'i saatlerce inceleyip hiç kod çalıştırmamak. Diğer uçta "shotgun debugging" var: hiç düşünmeden rastgele değişiklik yapıp "acaba bu düzeltti mi" diye tekrar tekrar denemek. Profesyonelin yaklaşımı hipotez odaklıdır: trace'ten *bir* hipotez üret ("bu null, X endpoint'inden gelen boş yanıttan kaynaklanıyor"), sonra o hipotezi *doğrulayacak en ucuz* deneyi yap. Hipotezsiz deneme, kumar oynamaktır ve üretimde en tehlikeli alışkanlıktır çünkü çoğu zaman semptomu maskeleyip kök nedeni gömer.

Pratikte kullandığım bir yön bulucu daha var: **hatanın deterministik mi yoksa olasılıksal mı olduğunu erken belirle.** "Her seferinde aynı girdiyle aynı yerde patlıyor mu, yoksa bazen mi?" sorusunun cevabı tüm stratejiyi çevirir. Deterministikse hayat kolaydır; girdiyi sabitler, debugger'ı açar, adım adım yürür ve kök nedeni doğrudan görürsünüz. Olasılıksalsa (aralıklı, "bazen") debugger büyük olasılıkla yardımcı olmayacaktır; çünkü sorun ya zamanlamaya (race), ya dış bir bağımlılığa, ya da yalnızca belirli ve nadir bir veri kombinasyonuna bağlıdır. O durumda silahınız debugger değil, log ve metriktir: hatayı yakalamak için ağ kurar, örüntü çıkana kadar beklersiniz. Acemi, aralıklı bir hatayı da deterministik bir hata gibi debugger'a bağlamaya çalışıp saatlerce boşa kürek çeker; kıdemli, "bu tekrar üretilemez, o zaman gözlemlenebilirlik kuracağım" der ve doğru araca geçer.

Bir başka kritik ayrım: **hata sınırda mı doğuyor, çekirdekte mi?** Sistemlerin çoğu hata, dış dünyayla temas noktalarında doğar — kullanıcı girdisi, ağ yanıtı, dosya, veritabanı, üçüncü parti API. İç çekirdek mantığı (saf hesaplama) genellikle daha az patlar çünkü girdisi zaten temizlenmiştir. Bu yüzden bir stack trace'i okurken refleksim, hatanın bir "sınır" fonksiyonundan mı (parse, deserialize, fetch, read) yoksa saf iş mantığından mı geldiğini işaretlemektir. Sınırdaysa, ilk şüphelim beklenmedik dış veridir, kendi mantığım değil.

## 3. Somut örnek üzerinden yürüyüş

Gerçek bir senaryoyu, dilinden bağımsız ama somut biçimde ele alalım. Bir web servisi, gün içinde sorunsuz çalışıyor; ama akşam trafiği artınca aralıklı olarak 500 dönmeye başlıyor. Log'da şuna benzer bir trace var (Java benzeri, ama mantık her dilde aynı):

```
com.acme.api.OrderController.getOrder(OrderController.java:42)
  -> com.acme.service.OrderService.fetch(OrderService.java:88)
  -> com.acme.repo.OrderRepository.findById(OrderRepository.java:120)

org.springframework.dao.DataAccessResourceFailureException:
    Unable to acquire JDBC Connection
  Caused by: java.sql.SQLTransientConnectionException:
      HikariPool-1 - Connection is not available,
      request timed out after 30000ms
    Caused by: (havuz tükendi)
```

**Adım 1 — Sınıflandır.** Mesajda "Connection is not available", "request timed out", "Pool" geçiyor. Bu koddaki bir mantık hatası değil; kaynak/altyapı ailesinden. Refleksim: `OrderController.getOrder` fonksiyonunun içine bakmaya *başlamıyorum*. Sorun, iş mantığında değil, bağlantı havuzunda.

**Adım 2 — Neden zincirini in.** En dıştaki `DataAccessResourceFailureException` semptom. Bir alttaki `Connection is not available ... timed out after 30000ms` asıl olay. Havuz bir bağlantı vermek için 30 saniye bekledi ve bulamadı. Yani havuzdaki tüm bağlantılar meşgul ve serbest kalmıyor.

**Adım 3 — Hipotez üret.** İki olasılık var. (a) Trafik gerçekten havuz kapasitesini aştı, basitçe boyut yetersiz. (b) Bağlantılar sızıyor; bir yerde `connection` açılıp geri havuza bırakılmıyor, dolayısıyla trafik artınca havuz kalıcı olarak tükeniyor. (b) çok daha olası çünkü "akşam artınca patlıyor, gündüz düzeliyor" örüntüsü klasik sızıntı imzasıdır: yavaşça birikir, yük altında tükenir.

**Adım 4 — Kanıtla doğrula.** Havuz metriklerine bakarım (HikariCP bunları yayınlar): aktif bağlantı sayısı zamanla monoton artıyor mu, yoksa yük ile inip çıkıyor mu? Monoton artış = sızıntı. Sonra kodda bağlantıyı manuel yöneten yerleri ararım. Ve tipik suçluyu buluruz:

```java
// HATALI: istisna durumunda bağlantı asla kapanmıyor
Connection conn = dataSource.getConnection();
Statement st = conn.createStatement();
ResultSet rs = st.executeQuery(sql);   // burası fırlatırsa...
process(rs);
conn.close();                           // ...buraya hiç gelinmez
```

İşte kök neden. `executeQuery` bir istisna fırlattığında `conn.close()` satırına asla ulaşılmıyor. Her hatalı sorgu bir bağlantıyı havuzdan kalıcı olarak çalıyor. Gündüz düşük trafikte fark edilmiyor; akşam yüzlerce hatalı istek olunca havuz tükeniyor. Dikkat edin: log'daki asıl hata mesajı ("pool timeout") sızıntının *sonucuydu*, sebebi değil. Eğer sadece semptoma bakıp havuz boyutunu büyütseydik, sorunu birkaç saat ertelemekten başka bir şey yapmazdık — bu, sahada en sık yapılan yanlış "düzeltme"dir.

**Düzeltilmiş hali:**

```java
// DOĞRU: try-with-resources, hata olsa da olmasa da kapatır
try (Connection conn = dataSource.getConnection();
     Statement st = conn.createStatement();
     ResultSet rs = st.executeQuery(sql)) {
    process(rs);
}   // conn, st, rs otomatik ve garanti kapanır
```

Aynı desen her dilde vardır: Python'da `with`, C#'ta `using`, Go'da `defer conn.Close()`. Kaynak yönetiminde altın kural: kaynağı açan satırın hemen yanında kapanışını garanti altına al.

Bu senaryoda bir başka pro refleksini daha vurgulayayım: "akşam patlıyor, sabah düzeliyor" ifadesinin kendisi bir teşhistir. Zaman içinde kötüleşip belirli bir eşikte çöken ve sonra (yeniden başlatma ya da düşük trafikle) toparlanan her şey, birikimli bir kaynak sorununun imzasıdır — bağlantı, bellek, thread, dosya tanıtıcısı, disk. Anlık patlayıp anlık düzelen şey ise genellikle dış bağımlılık dalgalanmasıdır. Sürekli ve sabit patlayan şey, deterministik bir kod ya da config hatasıdır. Hatanın *zaman içindeki şekli*, stack trace'in metninden bazen daha çok şey söyler; bu yüzden "ne zaman başladı, giderek mi kötüleşti, ne tetikledi" sorularını daima sorarım.

İkinci bir somut örnek, mantık hatası ailesinden — çünkü bunların stack trace'i yoktur ve en çok kafa karıştıran türdür. Bir raporlama servisi, aydan aya toplam geliri yanlış hesaplıyor; hiç istisna fırlatmıyor, sadece rakam tutmuyor. Burada okuyacak bir trace olmadığı için strateji değişir. Yön: girdi ve çıktıyı sabitleyip aradaki dönüşümü daraltmak. Bilinen bir girdi (örneğin tek bir siparişin verisi) alıp beklenen çıktıyı elle hesaplarım, sonra kodun ürettiğiyle karşılaştırırım. Fark nerede başlıyorsa, hata orada. Çoğu zaman suçlu şudur:

```
// HATALI: kayan nokta ile para hesabı
double toplam = 0.0;
for (Order o : orders) toplam += o.price;   // 0.1 + 0.2 = 0.30000000000000004
```

Para, kayan noktayla (float/double) tutulduğunda küçük yuvarlama hataları binlerce toplamda birikir ve rapor "10.000,01" yerine "9.999,98" der. Hiçbir hata mesajı yoktur; sadece güven sarsılır. Düzeltme, para için ondalık/tamsayı (kuruş cinsinden `long` ya da `BigDecimal`/`decimal`) kullanmaktır. Bu örneğin dersi: her hatanın stack trace'i yoktur; en sinsi hatalar sessizce yanlış çalışanlardır ve onları yakalamanın yolu trace okumak değil, beklenen ile gerçek arasındaki farkı sistematik daraltmaktır.

Bu örneğin dersi şudur: **hata mesajı size olayın bittiği yeri gösterir, başladığı yeri değil.** "Pool timeout" bir gösterge lambasıydı; asıl arıza 40 satır öteki bir eksik `finally` bloğuydu. Profesyonelin işi, gösterge lambasından arızaya geri yürümektir.

## 4. Acemi vs profesyonel: tuzaklar ve gözden kaçanlar

**En üstteki satıra takılmak.** Acemi, stack trace'in en üstteki (ya da Python'da en son) satırını okur ve "tamam, hata OrderController satır 42'de" der. Oysa satır 42 sadece istisnanın *kabardığı* yerdir, doğduğu yer değil. Profesyonel `Caused by` zincirini sonuna kadar iner. Kural: neden zincirinin en dibi genellikle gerçeğe en yakın yerdir.

**Hata mesajını harfiyen doğru sanmak.** Mesajlar programcılar tarafından yazılır ve programcılar yanılır. "File not found" bazen dosyanın var olduğu ama izin hatası olduğu anlamına gelir; işletim sistemi güvenlik gerekçesiyle "yok" der. "Invalid credentials" bazen kimlik doğrulama servisinin çökmesidir, yanlış şifre değil. Mesajı bir ipucu olarak al, kesin gerçek olarak değil.

**Gürültüyü sinyalden ayıramamak.** Yeni başlayan, 200 satırlık trace'in her satırını eşit ciddiyetle okumaya çalışır ve boğulur. Kıdemli, framework/runtime satırlarını saniyeler içinde tarayıp atlar, sadece kendi kodunun geçtiği ve `Caused by` başlıklarına odaklanır. Bu bir "görme" becerisidir ve pratikle otomatikleşir.

**Semptomu düzeltip kök nedeni gömmek.** Klasik: `NullPointerException` alıyorum, bir `if (x != null)` ekliyorum, hata kayboluyor. Ama x neden null'dı? O sorunun cevabı hâlâ orada; sadece artık sessizce yanlış davranıyor. En tehlikeli "düzeltme" türü, hatayı ortadan kaldıran değil, onu görünmez kılan düzeltmedir. Bir istisnayı yakalayıp yutmak (`catch (Exception e) {}`) bu suçun en ağır biçimidir; üretimde saatlerce süren gizemli davranışların kaynağı çoğu zaman yıllar önce birinin yuttuğu bir istisnadır.

**"Bende çalışıyor" tuzağı.** Kendi makinesinde çalışan kod, üretimde ortam farkları yüzünden patlar: farklı zaman dilimi, farklı yerel ayar (locale — ondalık ayırıcı `.` mi `,` mı), farklı dosya sistemi, farklı bağımlılık versiyonu, farklı bellek limiti, farklı CPU çekirdek sayısı. Acemi "kodum doğru, ortam bozuk" diye savunmaya geçer; profesyonel "kodum ortam farklarına dayanıklı değilmiş" diye kabul eder ve farkı bulur.

**Log seviyesini yanlış okumak.** Bir `WARN` satırı gördüğünde paniğe kapılmak ya da bir `ERROR` satırını görmezden gelmek. Profesyonel, log seviyelerinin gürültü/sinyal oranını bilir: bazı sistemler her şeyi `ERROR` basar (o zaman ERROR gürültüdür), bazıları gerçek felaketi `WARN` altında saklar. Kendi sisteminin log kültürünü tanımak gerekir.

**Zaman damgası ve korelasyonu ihmal etmek.** Tek bir hata satırı çoğu zaman yeterli değildir. Aynı istek boyunca ne olduğunu görmek için korelasyon kimliği (correlation/trace ID) ile o isteğin tüm log satırlarını yan yana koymak gerekir. Acemi tek satıra bakar; profesyonel o satırın etrafındaki ±5 saniyeyi ve aynı trace ID'li tüm kayıtları okur. Hatanın hikâyesi tek karede değil, film şeridindedir.

**Reprodüksiyon olmadan düzeltme yazmak.** "Sanırım şu satır sorunlu" deyip düzeltip deploy etmek. Eğer hatayı güvenilir biçimde tekrar üretemiyorsan, düzelttiğini de doğrulayamazsın. Profesyonelin kuralı: önce hatayı isteyerek tekrar üretebilecek en küçük senaryoyu bul (yeşil-kırmızı), sonra düzelt, sonra o senaryonun artık geçtiğini gör. Reprodüksiyon olmadan yapılan "düzeltme", çoğu zaman zaten çalışan bir şeyi bozup asıl hatayı olduğu yerde bırakır.

## 5. Araçlar ve saha notları

Doğru araç, hatanın ailesine göre değişir. Hepsini aynı anda kullanmazsınız; belirtiye göre birini seçersiniz.

**Debugger (adım adım yürütme, breakpoint, watch).** Deterministik, yerelde tekrar üretilebilen hatalar için birinci sınıf araçtır. Değişken değerlerini gerçek zamanlı görürsünüz. Ama sınırı var: aralıklı üretim hataları, race condition'lar ve dağıtık sistem sorunları için çoğu zaman işe yaramaz — çünkü breakpoint koymanız zamanlamayı değiştirir (heisenbug) ya da üretimde debugger bağlayamazsınız. Saha tüyosu: koşullu breakpoint (yalnızca `id == 12345` iken dur) binlerce iterasyon içinde tek bir kötü veriyi yakalamanın en hızlı yoludur; acemi döngüde 5000 kez F5'e basar, kıdemli koşul yazar.

**Profiler (CPU, bellek, ayırma).** "Yavaş" ve "bellek şişiyor" sınıfı sorunlar içindir. Bir stack trace vermeyen ama sistemi dizlerinin üstüne çökerten problemler bunlardır. Bellek profiler'ı (heap dump analizi) sızıntının hangi nesne türünde biriktiğini gösterir. CPU profiler'ı zamanın nerede yandığını. Saha tüyosu: performans hatalarında tahmin yürütmeyin, ölçün — "eminim şu döngü yavaştır" diyerek optimize edilen kodun %90'ı yanlış yeri optimize eder. Profiler önce darboğazı gösterir, sonra dokunursunuz.

**Observability (yapılandırılmış log, metrik, dağıtık izleme).** Üretimde debugger'ınız olmadığı için asıl silahınız budur. Üç ayağı vardır: metrikler (ne kadar, ne zaman — havuz doluluğu, hata oranı, gecikme), loglar (ne oldu — yapılandırılmış, korelasyon kimlikli), izler/trace (bir isteğin servisler arası yolculuğu). Saha tüyosu: log'u yapılandırılmış (JSON) yazın ki sonradan sorgulayabilesiniz; düz metin log, ölçekte aranamaz. Ve her isteğe daha girişte bir korelasyon kimliği basın — sorun çıktığında bu kimlik, dağınık log satırlarını tek bir hikâyeye diziler. Bunu önceden yapmayan ekipler, olay anında kör kalır.

**Hata izleme servisleri (Sentry benzeri toplayıcılar).** Aynı hatayı binlerce kez alsanız da gruplandırıp tek bir kayıt gösterir, hangi sürümle geldiğini, kaç kullanıcıyı etkilediğini, hatanın çevresindeki değişken durumunu (breadcrumb) verir. Saha tüyosu: hataları etkilenen kullanıcı sayısına göre önceliklendirin, oluşma sayısına göre değil — 100.000 kez oluşan ama tek bir bot'tan gelen hata, 3 kez oluşan ama ödeme akışını kıran hatadan daha az önemlidir.

**Test araçları (birim ve regresyon testi).** Bir hatayı bulduğunuzda, düzeltmeden *önce* o hatayı yakalayan başarısız bir test yazmak sahada standarttır. Bu, hem düzeltmenizi doğrular hem de aynı hatanın altı ay sonra geri dönmesini (regresyon) engeller. Saha tüyosu: üretim hatası → önce o hatayı tekrar üreten test (kırmızı) → sonra düzeltme (yeşil). Bu, "acaba düzeldi mi" belirsizliğini "kanıtlanmış düzeldi"ye çevirir.

**Basit ama güçlü teknikler.** Her zaman fantezi araç gerekmez. `git bisect`, "hangi commit bozdu" sorusunu ikili aramayla dakikalar içinde cevaplar — 500 commit arasında suçluyu 9 denemede bulur. "En son çalıştığı hali" ile "ilk bozuk hali" arasındaki diff, çoğu zaman kök nedeni doğrudan gösterir. Bir sistem dün çalışıp bugün çalışmıyorsa, ilk sorunuz "kodda ne değişti" değil, "*ne* değişti" olmalı — kod, bağımlılık, config, veri, altyapı ya da karşı servis. Çoğu üretim yangınının sebebi, sizin kodunuzda hiç değişiklik olmamasına rağmen çevrenizde bir şeyin değişmesidir.

**Kapanış saha notu.** Bir stack trace önünüze düştüğünde acele etmeyin. 30 saniye durup mesajı sınıflandırın, neden zincirini dibe kadar okuyun, kendi kodunuzun geçtiği ilk satırı bulun ve bir *hipotez* kurun. Sonra o hipotezi doğrulayacak en ucuz deneyi yapın. Bu disiplin, kariyeriniz boyunca binlerce saat kazandırır — çünkü hata ayıklamanın en pahalı kısmı düzeltmeyi yazmak değil, yanlış yerde kazmaktır.
