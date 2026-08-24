# Hata Ayıklama Yargısı: Bilimsel Teşhis

## 1. Problem ve bağlam: bu iş neyi çözer

Hata ayıklama, yazılım mühendisliğinin en yanlış anlaşılan becerisidir. Çoğu insan onu "kodu okuyup hatayı bulmak" sanır. Değil. Hata ayıklama, **eksik bilgiyle karar verme** disiplinidir. Elinde bir belirti var (sistem çöktü, sayı yanlış, istek zaman aşımına uğradı), ve elinde binlerce satır kod, onlarca servis, milyonlarca istek geçmişi var. Bu ikisi arasındaki uçurumu, tahminle değil, **kanıtla** kapatman gerekiyor.

Bu iş ne zaman devreye girer? İki tür durumda. Birincisi: bir şey açıkça bozuk ve tekrar üretilebilir (deterministik bug). Bunlar aslında kolaydır, çünkü doğa seninle konuşur; her seferinde aynı cevabı verir. İkincisi, asıl zor olan: **belirsiz, aralıklı (intermittent), üretimde-olup-lokalde-olmayan** hatalar. Ayda bir çöken servis, %0.3 oranında yanlış tutar hesaplayan finansal sistem, yük altında yavaşlayan API. İşte kıdemli mühendisi acemiden ayıran şey burada ortaya çıkar: acemi tekrar üretilemeyen bir bug karşısında felç olur; kıdemli, belirsizliği daraltmak için bir strateji kurar.

Temel tez şudur: **hata ayıklama bir bilim dalıdır, sanat değil.** Hipotez kurarsın, deney tasarlarsın, ölçersin, hipotezi çürütür ya da desteklersin. Gut-feeling (içgüdü) sadece hangi hipotezi önce test edeceğini seçmene yardım eder; kanıtın yerini asla tutmaz. Bu ayrımı içselleştirmeyen, kariyeri boyunca "shotgun debugging" (rastgele değişiklik yapıp umut etme) yapar.

## 2. Metodoloji ve karar ağacı: asıl değer

Pro bir mühendisin kafasında, çoğu zaman farkında bile olmadığı, bir karar ağacı çalışır. Onu açık edelim.

### Adım 0: Belirtiyi sabitle, güvenilir şekilde tekrar üret

En kritik ve en çok atlanan adım. Bir bug'ı düzeltemezsin eğer onu **isteğine göre çağıramıyorsan**. İlk sorduğum soru asla "neden oluyor?" değildir. İlk sorum: **"Bunu nasıl her seferinde tetiklerim?"**

Neden? Çünkü düzeltmeyi doğrulamanın tek yolu, bug'ı önce üretip sonra üretememektir. Tekrar üretemediğin bir "düzeltme", sadece bir dilek. Aralıklı bug'larda amaç, tekrar üretme olasılığını %0.3'ten %90'a çıkaracak koşulları bulmaktır: hangi kullanıcı, hangi veri, hangi zamanlama, hangi eşzamanlılık seviyesi? Bir bug'ı üretilebilir kılmak, çözümün yarısıdır.

Takas: Bazen tekrar üretmek günler alır. O zaman paralel yürütürsün — bir yandan tekrar üretmeye çalışırken, bir yandan gözlemlenebilirlik (logging, tracing) ekleyip bir sonraki doğal oluşumu yakalamayı beklersin.

Pratik bir teknik: **minimal tekrar üretim (minimal repro).** Elindeki karmaşık senaryoyu, bug hâlâ tetiklenirken parça parça kırparsın. Yüz satırlık isteği ellilik, sonra onluk, sonra iki satırlık bir çekirdeğe indirirsin. Her kırpmada sorarsın: "bug hâlâ var mı?" Var olduğu en küçük hâl, sana kök nedeni neredeyse çıplak gösterir — gürültü gitmiş, sadece sinyal kalmıştır. Acemi tüm sistemi ayakta tutup içinde debug etmeye çalışır; pro problemi bir kibrit çöpü boyutuna küçültür.

### Adım 1: Değişeni bul — "En son ne değişti?"

Sistem dün çalışıyordu, bugün çalışmıyor. Fizik yasaları değişmedi. **Bir şey değişti.** Kıdemli refleksi: `git log`, son deploy'lar, config değişiklikleri, altyapı güncellemeleri, bağımlılık sürüm yükseltmeleri, hatta veri. "Kod değişmedi" diyen kişiye asla inanma — çevre değişti, trafik desenı değişti, bir upstream servis davranışını değiştirdi.

Burada `git bisect` altın değerindedir. "Çalışıyordu" commit'i ile "bozuk" commit'i arasında ikili arama yaparak, hatayı getiren tam değişikliği logaritmik zamanda bulursun. 500 commit varsa, 9 denemede bulursun. Acemi 500 commit'i gözle okumaya çalışır.

### Adım 2: Yarıya böl — ikili arama zihniyeti

Hata ayıklamanın kalbi budur. Sistem bir boru hattıdır: A → B → C → D → çıktı. Çıktı yanlış. Nerede bozuldu? Baştan başlamazsın. **Ortadan başlarsın.** B ile C arasındaki veriyi kontrol et. Doğruysa, hata C-D arasında; değilse A-B arasında. Her ölçüm, arama uzayını yarıya indirir.

Bu, dağıtık sistemlerde de geçerlidir: istek client → load balancer → API gateway → servis → veritabanı yolunu izler. Trace'e bakıp "veri hangi noktada bozuldu / gecikme hangi hop'ta oluştu" diye ortadan bölersin. Bir milyar satırlık log içinde boğulmanın alternatifi budur.

### Adım 3: Katmanı belirle — nerede aramalı?

Belirtiye göre yön seçme mantığı. İşte pratisyen sezgileri:

- **"Lokalde çalışıyor, üretimde çalışmıyor"** → Kodda değil, **çevrede** ara. Config farkı, ortam değişkeni, veri ölçeği, ağ, izinler, saat dilimi, locale. Kod ikisinde de aynı; fark ortamdadır.
- **"Bazen çalışıyor, bazen çalışmıyor"** → **Durum (state), eşzamanlılık veya zamanlama.** Race condition, önbellek, paylaşılan mutable state, sıralı olmayan mesajlar, bağlantı havuzu tükenmesi. Deterministik olmayan her şeyin arkasında ya rastgelelik, ya zaman, ya eşzamanlılık vardır.
- **"Belli bir kullanıcıda/kayıtta çalışmıyor"** → **Veri.** Null, boş string, Unicode, çok uzun alan, negatif sayı, geçmiş tarih, o kullanıcıya özel bir edge-case. "Kötü veriyi" bul, kopyala, lokalde besle.
- **"İlk istek yavaş, sonrakiler hızlı"** → Soğuk başlangıç, lazy loading, JIT, bağlantı kurulumu, önbellek ısınması.
- **"Zamanla yavaşlıyor / bellek büyüyor"** → Kaynak sızıntısı (bellek, dosya tanıtıcısı, bağlantı, thread). Doğrusal büyüme sızıntının imzasıdır.
- **"Gece yarısı / ay sonu / yılbaşı çöküyor"** → Zaman/tarih sınırları, saat dilimi, cron çakışması, batch işleri.

### Adım 4: Hipotezi yaz, sonra çürütmeye çalış

Kritik disiplin: hipotezi **düzeltmeye** değil, **çürütmeye** çalış. "Sanırım sorun önbellekte" dediğinde, acemi hemen önbelleği temizler ve umut eder. Pro şöyle sorar: "Eğer sorun önbellek olsaydı, başka ne doğru olurdu? Onu ölçebilir miyim?" Confirmation bias (doğrulama önyargısı) hata ayıklamanın en büyük düşmanıdır — beynin, ilk teorine uyan kanıtları görür, çelişenleri görmezden gelir.

Altın kural: **bir seferde tek değişken.** İki şeyi aynı anda değiştirip düzelirse, hangisinin düzelttiğini asla bilemezsin. Ve muhtemelen yanlış olanı "öğrenirsin".

### Adım 5: Kök nedene in — "5 kere neden?"

Belirti düzeldi diye durma. "Null pointer" bir belirtidir, kök neden değil. Neden null geldi? Çünkü API boş döndü. Neden boş döndü? Çünkü upstream timeout oldu ve biz bunu yakalamadık. Neden yakalamadık? Çünkü hata yolunu hiç test etmedik. **İşte gerçek bug bu.** Belirtiyi yamayan, aynı sınıftan on bug daha görür. Kök nedeni düzelten, bir sınıfı birden kapatır.

Bir uyarı: "5 neden" mekanik bir ritüel değildir. Amaç, **düzeltebileceğin ve tekrarı önleyebileceğin** bir seviyeye inmektir. Bazen üçüncü nedende durursun (orası aksiyon alınabilir), bazen yedinci nedene kadar gidersin. Kök nedenin iki yüzü vardır: teknik kök neden (kodda ne yanlıştı) ve süreç kök nedeni (bu bug neden yakalanmadan üretime gitti — hangi test eksikti, hangi review adımı atlandı). Kıdemli olay-sonrası incelemesi (postmortem) her ikisini de kapsar; sadece kodu değil, onu kaçıran sistemi de düzeltir. Ve postmortem **suçlamasız (blameless)** olmalıdır — "kim yaptı" sorusu insanları savunmaya iter ve gerçeği gizler; "sistem buna nasıl izin verdi" sorusu ise öğrenmeyi açar.

## 3. Gerçek senaryo üzerinden yürüyüş

Somut bir üretim senaryosu. Bir e-ticaret ödeme servisi, günde bir-iki kez, rastgele görünen anlarda 30 saniye takılıp timeout veriyor. Lokalde asla olmuyor. Loglar temiz. Klasik kâbus.

### Hatalı kod (basitleştirilmiş, dilden bağımsız mantık)

```
işlev ödemeİşle(sipariş):
    bağlantı = havuzdanBağlantıAl()      // veritabanı bağlantı havuzu, boyut 10
    sonuç = ödemeSağlayıcıyaÇağır(sipariş) // dış HTTP çağrısı, timeout yok
    bağlantıyıKaydet(bağlantı, sonuç)
    havuzaBağlantıİadeEt(bağlantı)
    dönüş sonuç
```

Gözle bakınca temiz görünüyor. İşte "çalışır gibi görünüp üretimde patlayan" kod tam olarak budur.

### Teşhis yürüyüşü

**Adım 0 — Tekrar üret:** Lokalde olmuyor çünkü lokalde tek istek gönderiyoruz. Hipotez: eşzamanlılıkla ilgili ("bazen oluyor" → state/concurrency dalı). Yük testi aracıyla 50 eşzamanlı istek gönderiyoruz. Bingo — birkaç saniye içinde sistem takılıyor. Tekrar üretim sağlandı; işin yarısı bitti.

**Adım 2 — Ortadan böl:** Zincir: bağlantı al → sağlayıcıya çağrı → kaydet → iade. Nerede takılıyor? Gözlemlenebilirlik ekliyoruz: her adımın başına/sonuna zaman damgası. Ölçüm gösteriyor ki thread'ler `havuzdanBağlantıAl()` satırında bekliyor. Havuz tükenmiş.

**Adım 3 — Neden tükendi?** Havuzda 10 bağlantı var. Ama `ödemeSağlayıcıyaÇağır` bazen çok yavaş (sağlayıcı ara sıra 30 sn takılıyor) ve **timeout yok**. Kritik hata şu: bağlantıyı ta en başta alıyoruz ve tüm yavaş HTTP çağrısı boyunca elimizde tutuyoruz. 10 istek aynı anda yavaş sağlayıcıya takılırsa, 10 bağlantının hepsi kilitlenir, 11. istekten itibaren herkes havuz için sonsuza dek bekler. Domino etkisiyle tüm servis ölür.

**Kök neden (5 neden):** Timeout takıldı → çünkü dış çağrının timeout'u yok → çünkü bağlantı, gerekmediği halde ağ çağrısı boyunca tutuluyor → çünkü kaynak yaşam süresi mümkün olan en dar aralığa çekilmemiş. İki ayrı kusur birleşmiş: sınırsız bekleme + kaynağı gereğinden uzun tutma.

### Düzeltilmiş kod

```
işlev ödemeİşle(sipariş):
    // Ağ çağrısı için veritabanı bağlantısı TUTMA
    sonuç = ödemeSağlayıcıyaÇağır(sipariş, timeout=5sn) // sınır koy
    
    bağlantı = havuzdanBağlantıAl(bekleTimeout=2sn) // havuz beklemesine de sınır
    dene:
        bağlantıyıKaydet(bağlantı, sonuç)
    nihayet:
        havuzaBağlantıİadeEt(bağlantı) // hata olsa bile iade et
    dönüş sonuç
```

İki değişiklik, tek kök neden ailesi: (1) kaynağı sadece gerçekten gerektiği anda al ve mümkün olan en kısa süre tut; (2) her bekleme noktasına sınır koy. Bir de `nihayet` (finally) bloğu — bağlantı, exception fırlasa bile havuza döner; yoksa yavaş bir sızıntı bug'ı daha yaratmış olurduk.

Dikkat: Belirti "timeout" idi. Acemi çözümü: "timeout süresini artıralım, 30 saniyeden 60'a çıkaralım." Bu, yangına benzin dökmektir — havuz daha da uzun kilitli kalır. Belirtiyi tedavi etmek, çoğu zaman hastalığı kötüleştirir.

Bu senaryonun bir de gizli dersi var: **hata izole kaldığı sürece küçüktür; sistem onu yaydığında felaket olur.** Tek bir yavaş sağlayıcı çağrısı başlı başına zararsızdı — kullanıcı biraz bekler, geçer. Onu üretim kesintisine çeviren şey, o yavaşlığın paylaşılan bir kaynağı (bağlantı havuzu) kilitleyip tüm servise bulaştırmasıydı. Buna "cascading failure" (zincirleme çöküş) denir. Kıdemli mühendisin bir bug'a bakarken sorduğu ekstra soru şudur: "Bu hata **yayılıyor mu**, yoksa kendi köşesinde mi kalıyor?" Bulkhead (bölme), timeout, circuit breaker (devre kesici) gibi desenler hep aynı amaca hizmet eder: bir bileşenin arızasını o bileşende hapsetmek. Teşhis ederken de aynı gözle bakarsın — belirti nerede patladı ile hata nerede doğdu çoğu zaman farklı yerlerdir; patlama noktası sadece en zayıf halkadır.

## 4. Acemi vs pro: tuzaklar

**Acemi rastgele değiştirir, pro ölçer.** Acemi "şunu deneyeyim, olmadı, bunu deneyeyim" döngüsüne girer (shotgun debugging). Her denemede kodu değiştirir, çalıştırır, umut eder. Sorun düzelince neden düzeldiğini bilmez — belki de düzeltmedi, sadece zamanlama değişti. Pro her değişiklikten önce bir tahmin (prediction) yazar: "Bu değişikliği yaparsam, şu metriğin şöyle değişmesini bekliyorum." Sonra ölçer. Tahmin tutmadıysa, modeli yanlış demektir — bu bir başarısızlık değil, öğrenmedir.

**Acemi ilk teoriye âşık olur.** İlk akla gelen açıklamayı bulur ve onu doğrulayan her şeye sarılır, çürüten kanıtı görmezden gelir. Pro, en sevdiği hipotezi bile aktif olarak öldürmeye çalışır. "Yanılıyorsam bunu nasıl anlarım?" sorusu, kıdemin imzasıdır.

**Acemi loglara/hata mesajına yüzeysel bakar.** Stack trace'in en üst satırını okur, gerisini atlar. Oysa asıl bilgi çoğu zaman "Caused by:" zincirinin en altındadır — gerçek kök istisna oradadır. Ya da mesajı okur ama **tam olarak ne dediğine** dikkat etmez. "Connection refused" ile "Connection timeout" tamamen farklı iki dünyadır: biri "kimse dinlemiyor" (yanlış port/adres, servis çökük), diğeri "dinliyor ama cevap vermiyor" (ağ, güvenlik duvarı, aşırı yük). Bu ayrımı atlamak, günlerce yanlış yerde aramaya yol açar.

**Acemi "düzeldi" der ve gider.** Bir kez çalıştı diye biter sanır — özellikle aralıklı bug'larda felakettir. Aralıklı bir bug'ın "düzeldiğini" bir kez çalışarak kanıtlayamazsın; onu **eskiden güvenilir şekilde bozan** koşulu bulup, o koşulda artık bozulmadığını göstermelisin. Yoksa sadece kumar oynadın.

**"Isıtmayla düzelen" bug tuzağı (Heisenbug).** Debugger ekleyince ya da log koyunca bug kaybolur. Acemi "demek düzelmiş" der. Hayır — log/debugger, zamanlamayı değiştirdiği için race condition'ı gizledi. Gözlem, olayı değiştirdi. Bu, %100 bir eşzamanlılık bug'ının işaretidir, çözüldüğünün değil.

**Sonuçla nedeni karıştırma (correlation vs causation).** "CPU %100'e çıktığında sistem yavaşlıyor" — CPU sebep mi, sonuç mu? Belki bir kilit (lock) contention'ı hem yavaşlığa hem boşta dönen CPU'ya yol açıyor. Acemi ilk gördüğü korelasyonu neden sanır. Pro sorar: "Bu ikisinin ortak bir üçüncü nedeni olabilir mi?"

**Ortam farkını küçümseme.** "Bende çalışıyor" cümlesi bir mühendislik özrü değildir. Üretim; farklı veri ölçeği, farklı eşzamanlılık, farklı config, farklı saat dilimi, farklı ağ gecikmesi demektir. Lokalde 100 satırla test edilen sorgu, üretimde 100 milyon satırda tamamen farklı bir plan seçip çöker. Ölçek, davranışı niteliksel olarak değiştirir.

**En son yaptığın değişikliğe körlük.** İnsan zihni, kendi son değişikliğinin masum olduğuna inanmaya meyillidir. "O kısma dokunmadım ki" dersin ve saatlerce başka yerde ararsın — sonra o kısma dokunduğunu fark edersin. Kural: şüpheyi en son değişen şeye, senin en son değiştirdiğin şeye yönelt. İstatistik senin aleyhine değil, lehinedir — bug'ların büyük çoğunluğu yakın zamanda değişen kodda yaşar.

**Aracın çıktısına kör güven.** Debugger'ın gösterdiği değer, optimize edilmiş derlemede yanıltıcı olabilir; log'daki zaman damgası tampon (buffer) gecikmesiyle gerçek sırayı yansıtmayabilir; profiler örnekleme (sampling) yapıyorsa nadir ama kritik yolu kaçırabilir. Pro, aracın da bir model olduğunu ve modellerin yalan söyleyebileceğini bilir. İki bağımsız araç aynı şeyi söylüyorsa güvenin artar; tek bir araca dayalı sonuç her zaman şüpheye açıktır.

**Yanlış katmanda arama inadı.** Bir mühendis bir katmanda (mesela uygulama kodu) uzmansa, bug'ı hep orada arama eğilimindedir — oysa sorun veritabanında, ağda ya da işletim sistemindedir. "Elinde çekiç olana her şey çivi görünür." Belirti hangi katmanı işaret ediyorsa oraya git, en rahat olduğun katmana değil.

## 5. Araçlar ve saha notları

Araç, yargının yerini tutmaz ama yargıyı hızlandırır. Her aracın bir işi vardır; yanlış araçla saatler harcamak yaygındır.

**Debugger (adım adım yürütücü):** Deterministik, tekrar üretilebilir, lokal bug'lar için mükemmel. Breakpoint koy, durumu incele, tek tek ilerle. Ama: eşzamanlılık ve zamanlama bug'larında **işe yaramaz, hatta zararlıdır** — durdurmak zamanlamayı bozar, bug kaçar. Ayrıca üretimde canlı debugger kullanamazsın. Conditional breakpoint (koşullu durak) az bilinen bir cevherdir: "sadece kullanıcı_id == 4172 olduğunda dur" — milyonlarca döngüde tek kötü kaydı yakalamanın yolu.

**Loglama:** En evrensel araç. Ama disiplin ister. İyi log yapılandırılmıştır (structured): serbest metin değil, sorgulanabilir alanlar. Ve bir **korelasyon kimliği (request/trace ID)** taşımalı ki bir isteği tüm servisler boyunca izleyebilesin. Kötü log ya çok az ("bir şeyler oldu") ya çok fazladır (gürültüde sinyal boğulur). Saha kuralı: bir hata dalında (catch bloğu) **her zaman bağlamı logla** — hangi girdi, hangi kullanıcı, hangi durum. Sadece "hata oluştu" loglayan catch bloğu, geleceğin sana attığı bir kötü şakadır.

**Profiler:** Performans bug'ları için. "Yavaş" bir belirtidir; profiler sana zamanın **nereye** gittiğini gösterir. Tahmin etme, profille — mühendisler performans darboğazlarını tahmin etmede notoriously kötüdür. CPU profiler (hesap nerede yanıyor) ile allocation/memory profiler (bellek nerede büyüyor) farklı işler. Flame graph okumayı öğrenmek, performans işinde tek başına bir seviye atlatır: geniş taban = çok zaman harcayan çağrı.

**Dağıtık izleme (distributed tracing):** Mikroservis dünyasında zorunlu. Tek bir isteğin 15 servis arasındaki yolculuğunu, her hop'taki gecikmeyi gösterir. "Hangi servis yavaşladı" sorusunun cevabı trace'tedir. Trace olmadan dağıtık bir gecikme bug'ını çözmek, karanlıkta iğne aramaktır.

**Metrikler ve gösterge panelleri (dashboards):** "Ne zaman başladı, neyle korele?" sorusuna cevap verir. Hata oranındaki sıçramayı bir deploy'la, trafik artışıyla, ya da bir bağımlılığın çöküşüyle zamanda hizalamak, kök nedene giden en hızlı yoldur. USE (Utilization, Saturation, Errors) ve RED (Rate, Errors, Duration) çerçeveleri, neye bakacağını bilmediğinde başlangıç noktandır.

**İkili arama araçları:** `git bisect` (hangi commit), `git blame` (bu satırı kim/ne zaman/neden değiştirdi — commit mesajı çoğu zaman bağlamı verir). Feature flag'ler de bir tür canlı bisect'tir: bir özelliği açıp kapayarak nedeni izole edersin.

**Ağ ve sistem araçları:** `tcpdump`/paket yakalama (gerçekten ne gitti, ne geldi — "gönderdim" ile "gitti" farklıdır), `netstat`/bağlantı sayacı (havuz tükenmesi, TIME_WAIT birikmesi), `strace`/sistem çağrısı izleme (proses gerçekte hangi syscall'da takılı). Bunlar "kod doğru görünüyor ama davranış imkânsız" dediğin anlarda gerçeğe erişimindir — soyutlamaların altındaki fiziksel katmanı görürsün.

**En güçlü "araç": ikili çoğaltma (rubber duck).** Sorunu başka birine (ya da bir ördeğe) yüksek sesle, baştan sona anlatmak. Anlatırken kendi varsayımlarını duyar ve çoğu zaman "dur, burada neden bunun doğru olduğunu varsaydım ki?" dersin. Bug'ların şaşırtıcı bir oranı, kimse cevap vermeden, sadece problemi düzgün ifade etme sırasında çözülür.

### Kapanış saha notu

En derin ders: **belirsizliğe saygı duy ve onu daralt.** Zayıf mühendis, elinde kanıt yokken kesin konuşur ("kesin veritabanıdır"). Güçlü mühendis, ne bildiğini ve ne bilmediğini net ayırır: "Şunu ölçtüm, doğru. Şunu ölçmedim, bilmiyorum. Sıradaki ölçümüm arama uzayını şu kadar daraltacak." Hata ayıklama, kesinlik gösterisi değil, belirsizliği yöntemli biçimde yenmektir. Ve bir bug'ı çözdüğünde bitmez — **onu bir daha yakalayacak bir test yaz.** Yakaladığın her bug, gelecekteki regresyona karşı kalıcı bir bekçiye dönüşmeli. Aksi halde aynı hatayı, altı ay sonra, aynı gecenin bir başka saatinde yeniden çözersin.

Özetle karar akışı: tekrar üret → değişeni bul → ortadan böl → belirtiye göre katmanı seç → hipotezi çürütmeye çalış → tek değişken değiştir → kök nedene in → testle kilitle. Bu döngü, dil, platform ve on yıllar boyunca değişmez. Araçlar değişir; yargı kalır.
