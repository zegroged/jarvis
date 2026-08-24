# Kod İnceleme (Code Review) Yargısı — Saha Notları

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Kod incelemenin görünen amacı "hata yakalamak"tır ama sahada 15 yıl geçirdikten sonra şunu söyleyebilirim: hata yakalamak code review'ün en zayıf tarafıdır. İnsan gözü, üç kere iç içe geçmiş bir döngüde off-by-one hatasını çoğu zaman kaçırır; onu testler ve statik analiz daha iyi yakalar. Code review'ün asıl çözdüğü problem başka: **bilgi yayılımı, tasarım hizası ve kod tabanının uzun vadeli okunabilirliğinin korunması.**

Somut olarak dört şeyi çözer:

1. **Tasarım kararlarının erken yakalanması.** Bir fonksiyonun yanlış katmanda durması, bir sorumluluğun yanlış servise verilmesi — bunlar bir kere merge olduktan sonra sökülmesi haftalar süren şeylerdir. Review, bu kararı henüz ucuzken yakalar.
2. **Bus factor / bilgi tekelinin kırılması.** İncelemeyi yapan kişi, o kodu artık bir miktar sahiplenir. Altı ay sonra o modülde bir şey patladığında, "hiç kimse bilmiyor" durumuna düşmezsiniz.
3. **Standart ve kültürün taşınması.** Yeni birine "biz burada hataları nasıl ele alıyoruz, log'u nasıl yazıyoruz" bilgisini doküman değil, review yorumları öğretir.
4. **İkinci bir zihin modelinin devreye girmesi.** Yazan kişi kendi varsayımlarına kör olur. İnceleyen kişi o varsayımları görmediği için "burada input null olabilir mi?" diye sorar — ve çoğu prod olayı tam olarak bu tip görülmeyen varsayımlardan çıkar.

Ne zaman devreye girer? Klasik cevap "her PR'da". Gerçek cevap daha ince: **riskle orantılı.** Bir feature flag arkasındaki, geri alınması bir satırlık config değişikliği olan deneysel koda harcadığınız inceleme enerjisiyle; ödeme akışına, kimlik doğrulamaya, veri migrasyonuna, silme işlemine dokunan koda harcadığınız enerji aynı olamaz. Acemi her PR'ı aynı özenle (ya da aynı özensizlikle) inceler. Pro, enerjisini **blast radius**'a (bir şey patlarsa etki alanı) göre dağıtır.

## 2. Metodoloji ve karar ağacı — asıl değer

Kıdemli bir mühendisin PR açtığında kafasında dönen sıra kabaca şudur. Ben bunu yıllar içinde bir refleks haline getirdim; adım adım açıyorum.

### Adım 0: Kodu okumadan önce bağlamı oku

Diff'e dalmadan önce PR açıklamasını, bağlı issue'yu ve "bu neden yapılıyor?" sorusunun cevabını ararım. **Niyeti bilmeden kodu inceleyemezsiniz.** Çünkü review'ün ilk sorusu "kod doğru mu?" değil, "bu kod doğru problemi mi çözüyor?" sorusudur. En pahalı hata, mükemmel yazılmış ama yanlış şeyi yapan koddur. Acemi doğrudan satırlara bakar, pro önce "bu değişiklik gerçekten gerekli mi, yoksa mevcut bir mekanizma bunu zaten yapıyor mu?" diye sorar.

Eğer açıklama yoksa veya "bug fix" gibi tek kelimeyse, ilk yorumum kod hakkında değil, açıklama hakkında olur. Bağlamı yazana geri yükletirim — çünkü altı ay sonra `git blame` yapan kişi de o bağlama muhtaç olacak.

### Adım 1: Boyut ve şekil kontrolü

Diff'in büyüklüğüne bakarım. **800 satırlık bir PR'ı kimse düzgün inceleyemez** — bu bir yalan, herkes "LGTM" der ve göz gezdirir. Araştırmalar da bunu doğruluyor: 200-400 satırdan sonra kusur yakalama oranı çöker. Büyük bir PR gördüğümde ilk yargım koda değil sürece dairedir: "Bu bölünebilir mi?" Bölünemiyorsa (örneğin otomatik bir refactor, bir kütüphane sürüm yükseltmesi), o zaman "gürültü" ile "sinyal"i ayırırım — mekanik değişiklikleri hızlı geçer, elle yazılmış mantığa yoğunlaşırım.

### Adım 2: Katmanları soymak — dıştan içe okuma sırası

Kodu yazıldığı sırayla değil, **risk sırasıyla** okurum:

1. **Genel akış / arayüz:** Fonksiyon imzaları, public API, veri tipleri. Buradaki bir hata en pahalıdır çünkü çağıran her yeri etkiler.
2. **Sınır koşulları:** null/boş/negatif/çok büyük girdiler. "Bu liste boşsa ne olur?" "Bu sayı taşarsa?" "Bu string'e emoji gelirse?"
3. **Hata yolları:** Mutlu yol (happy path) her zaman çalışır; sorunlar hata yollarında saklanır. Try-catch içinde ne yutuluyor? Exception'lar nereye gidiyor? Yarıda kalan işlem sistemi tutarsız bırakıyor mu?
4. **Eşzamanlılık ve durum:** Paylaşılan bir state var mı? İki istek aynı anda gelirse? Bu en son ve en dikkatli baktığım katmandır çünkü en zor görünen buradadır.

### Adım 3: "Belirti görünce nereye giderim" — teşhis refleksleri

Yıllar içinde kod okurken belirli desenler alarm çaldırır. İşte gerçek karar ağacım:

- **Bir yorum satırı "// TODO: geçici" ya da "// hack" görürsem** → o satır bir sürü teknik borcun kapısıdır; gerçekten geçici mi yoksa iki yıl kalacak mı diye sorarım.
- **`catch` bloğu boşsa ya da sadece log'luyorsa** → "Bu hata gerçekten yutulabilir mi? Yoksa çağıran bunu bilmeli mi?" Yutulan exception'lar prod'da en çok saç yolduran şeydir çünkü sistem sessizce yanlış davranır.
- **Bir zaman aşımı (timeout) değeri görmezsem, ağ çağrısında** → "Bu çağrı sonsuza kadar asılı kalabilir." Dış servise yapılan her çağrıda timeout ararım.
- **Yeni bir bağımlılık (dependency) eklenmişse** → "Bunu gerçekten eklemek şart mı? Bu satırlık iş için 2MB'lık kütüphane mi?" ve "bu kütüphanenin bakımı yapılıyor mu, lisansı uygun mu?"
- **Bir döngü içinde veritabanı ya da ağ çağrısı görürsem** → N+1 alarmı. Bu, testte 10 kayıtla mükemmel çalışıp prod'da 100.000 kayıtla sistemi dize getiren bir numaralı desendir.
- **String birleştirmeyle sorgu/komut kuruluyorsa** → injection alarmı. İstisnasız.
- **Bir boolean parametre görürsem, `doThing(true, false)` gibi** → çağıran tarafta okunması imkânsız; enum ya da ayrı fonksiyon öneririm.
- **Bir sayının birimi belirsizse** (`timeout = 30` — saniye mi? milisaniye?) → birim ya isimde ya tipte olmalı.

### Adım 4: Takaslar ve "ne zaman geçireyim" kararı

Burası acemiyi profesyonelden ayıran yer. Her gördüğüm kusur "engelleyici" değildir. Kafamda üç kova var:

- **Engelleyici (blocking):** Doğruluk hatası, güvenlik açığı, veri kaybı riski, geri alınamaz bir tasarım hatası. Bunlar merge'ü durdurur.
- **Öneri (should):** Daha iyi bir yaklaşım var ama mevcut hali de çalışır ve güvenli. Tartışırım ama yazan direnirse ve gerekçesi mantıklıysa bırakırım.
- **Zevk/stil (nit):** Değişken adı, biçim. Bunları "nit:" diye işaretlerim ki yazan bunların isteğe bağlı olduğunu bilsin. **Bir PR'ı yalnızca stil için bloklamak, kültürel bir suçtur.**

En önemli takas: **mükemmeliyetçilik vs. teslim hızı.** Kod hiçbir zaman "mükemmel" olmaz. Sorum "bu mükemmel mi?" değil, "bu, mevcut kod tabanının ortalama kalitesini yükseltiyor mu, düşürüyor mu?" olur. Yükseltiyorsa ve güvenliyse, ufak kusurlarla bile geçer, kalanı takip issue'suna yazarım. Sürekli bloklayan review'cı, ekibi kendisini es geçmeye iter — ki bu review'ün ölümüdür.

## 3. Gerçek kod üzerinden yürüyüş: zafiyetli → teşhis → düzeltilmiş

Somut bir senaryo. Bir e-ticaret sisteminde "kullanıcının siparişlerini getir ve toplam harcamayı hesapla" endpoint'i. PR olarak şu geldi (dili önemli değil, mantık evrensel; Python'a benzer bir sözde-kodla veriyorum):

```python
def get_user_orders(user_id):
    user = db.query("SELECT * FROM users WHERE id = " + user_id)
    orders = db.query("SELECT * FROM orders WHERE user_id = " + user_id)

    total = 0
    for order in orders:
        items = db.query("SELECT * FROM items WHERE order_id = " + order.id)
        for item in items:
            total += item.price * item.quantity

    return {
        "user": user,
        "orders": orders,
        "total_spent": total
    }
```

Testte çalışıyor. CI yeşil. Acemi "LGTM" der. Şimdi bir profesyonelin kafasından geçenleri sırayla açayım.

**Teşhis 1 — SQL Injection (engelleyici).** `"... WHERE id = " + user_id` klasik injection. `user_id` bir HTTP parametresinden geliyorsa, saldırgan `1 OR 1=1` ya da çok daha kötüsünü gönderebilir. Bu, en yüksek öncelikli bulgu. Testte görünmez çünkü test "kibar" girdi verir. Prod'da ilk gün taranır.

**Teşhis 2 — N+1 sorgu problemi (engelleyici, performans).** Döngünün içinde her sipariş için ayrı bir `items` sorgusu var. 5 siparişli test kullanıcısında 6 sorgu, sorun yok. Ama sadık bir müşterinin 2.000 siparişi varsa, tek endpoint çağrısı 2.001 veritabanı sorgusu üretir. Bu, veritabanı bağlantı havuzunu tüketir ve **tek bir kullanıcının profil sayfası tüm sistemi yavaşlatır.** Bu deseni yıllar içinde onlarca kez prod incident raporunda gördüm.

**Teşhis 3 — Parasal hesaplamada float (engelleyici, doğruluk).** `item.price * item.quantity` eğer `price` bir kayan noktalı sayıysa, `0.1 + 0.2 = 0.30000000000000004` klasiği devreye girer. Binlerce kalemde bu yuvarlama hataları birikir ve muhasebe tutmaz. Para her zaman tam sayı kuruş ya da decimal tipiyle tutulmalı.

**Teşhis 4 — Yetkilendirme kontrolü yok (engelleyici, güvenlik).** `user_id`'yi alıp doğrudan sorguluyoruz. Peki isteği yapan kişi bu kullanıcı mı? Yoksa herhangi biri başkasının `user_id`'sini gönderip onun tüm sipariş geçmişini görebilir mi? Bu **IDOR (Insecure Direct Object Reference)** açığı; kimlik doğrulama (authentication) ile yetkilendirmenin (authorization) karıştırılmasıdır. Testte asla görünmez çünkü test tek kullanıcıyla koşar.

**Teşhis 5 — `SELECT *` ve hassas veri sızıntısı (öneri/engelleyici).** `users` tablosundan `SELECT *` çekip tüm objeyi döndürüyoruz. İçinde `password_hash`, `email`, belki `reset_token` var mı? Response'a ne sızıyor? `SELECT *` hem bunu görünmez kılar hem de tabloya kolon eklendiğinde sessizce yeni alan sızdırır.

**Teşhis 6 — Boş/yok kullanıcı durumu (öneri).** Kullanıcı yoksa `user` boş döner ama kod devam eder ve `total_spent: 0` ile 200 OK verir. Muhtemelen 404 dönmeli. Sessiz başarısızlık, çağıran tarafta gizli hataya yol açar.

Düzeltilmiş hali (mantığı gösteriyorum, sözde-kod):

```python
def get_user_orders(requesting_user, target_user_id):
    # Yetkilendirme: sadece kendi verisini ya da admin görebilir
    if requesting_user.id != target_user_id and not requesting_user.is_admin:
        raise ForbiddenError()

    # Parametreli sorgu: injection kapalı
    user = db.query(
        "SELECT id, name, email FROM users WHERE id = ?",
        [target_user_id]
    )
    if user is None:
        raise NotFoundError()

    # Tek sorguda toplam: N+1 yok, para tam sayı (kuruş) olarak
    row = db.query(
        """
        SELECT COALESCE(SUM(i.price_cents * i.quantity), 0) AS total_cents
        FROM orders o
        JOIN items i ON i.order_id = o.id
        WHERE o.user_id = ?
        """,
        [target_user_id]
    )

    return {
        "user": user,
        "total_spent_cents": row.total_cents
    }
```

Dikkat edin: düzeltme kodu **daha kısa** oldu. İyi review çoğu zaman kod ekletmez, kod sildirir. Ve bu altı bulgunun hiçbiri "compile olmuyor" ya da "test kırmızı" değildi — hepsi yeşil CI'dan geçerdi. Code review'ün değeri tam olarak buradadır.

Bir de review yorumlarının **tonu** önemli. "Bunu neden böyle yaptın?" yerine "Burada 2.000 siparişli bir kullanıcıda N+1 riski var gibi; JOIN ile tek sorguya çekebilir miyiz?" Birincisi savunmaya iter, ikincisi problemi ve gerekçeyi birlikte verir. Yorumu koda değil probleme yönelt; kişiye değil koda. "Sen" değil "bu kod" ya da "biz".

## 4. Acemi vs. pro: tuzaklar ve gözden kaçanlar

**Acemi diff'e bakar, pro sisteme bakar.** Yeni review'cı yalnızca eklenen kırmızı-yeşil satırları okur. Kıdemli, "bu değişiklik dosyanın geri kalanıyla, hatta değişmemiş kodla nasıl etkileşiyor?" diye sorar. En sinsi hatalar, değişen satırda değil, o değişikliğin bozduğu **değişmemiş** varsayımda saklanır. Diff aracı size sadece değişeni gösterir; asıl tehlike bazen ekranın dışındadır.

**Acemi "kod çalışıyor mu" sorar, pro "bu kod nasıl bozulur" sorar.** Mutlu yol herkesin gördüğüdür. Profesyonel refleks olarak kötümser okur: "Bu satır bir milyon kez, saniyede bin kez, yarısı hatalı girdiyle çağrılırsa?"

**"İşe yarar gibi görünüp prod'da patlayan" klasik tuzaklar:**

- **Testte küçük veriyle çalışan, prod'da ölçekte çöken kod.** N+1, belleğe tüm tabloyu yükleme, O(n²) döngü. Test 10 satırla koşar, prod 10 milyonla. CI asla yakalamaz.
- **Zaman ve zaman dilimi.** "Şimdi"yi kullanan, yerel saat varsayan, yaz saati geçişini düşünmeyen kod. Gece yarısı ya da 29 Şubat'ta patlar.
- **Yutulmuş hatalar.** `catch` içinde sessizce devam eden kod. Sistem "başarılı" der ama arka planda veri kaybeder. Aylarca fark edilmez.
- **Geriye dönük uyumluluk kırılması.** Bir API alanını yeniden adlandırmak diff'te temiz görünür ama o alanı kullanan eski mobil istemciler sahada patlar. Review'cı "bu alanı kim tüketiyor?" diye sormalı.
- **Veritabanı migrasyonları.** "Kolon ekle" masum görünür ama büyük tabloda kilit alıp tabloyu dakikalarca yazmaya kapatabilir. Geri alma planı var mı? Migration ileriye ve geriye uyumlu mu?
- **Feature flag ve dağıtım sırası.** Kod deploy oldu ama flag açık değil, ya da tam tersi. Kısmi dağıtımda eski ve yeni kod aynı anda çalışırken tutarlı mı?

**Aceminin kaçırdığı ama pro'nun otomatik gördüğü şeyler:**

- Bir şey **eklenmesi** kadar bir şeyin **eklenmemiş** olması da önemlidir: yeni endpoint eklendi ama test yok, log yok, metrik yok, rate limit yok. Diff'te olmayanı görmek ustalıktır.
- **Geri alınabilirlik (revertability).** "Bu prod'da yanlış giderse, saat 3'te ne kadar hızlı geri alabiliriz?" Geri alması zor değişiklikler daha çok inceleme hak eder.
- **Gözlemlenebilirlik.** Bu kod prod'da yanlış davranırsa, bunu nereden anlarız? Log/metrik yoksa, hata sessizce yaşar.

**Acemi review'cının kendi hataları:**

- **Rubber-stamping:** Büyük PR'a bakmadan "LGTM". En zararlı alışkanlık.
- **Bikeshedding / boyacı kulübesi:** Değişken adı üzerine 20 yorum, ama mimari hatayı görmemek. Enerjiyi önemsize harcamak.
- **Kendi tarzını dayatmak:** "Ben olsam böyle yazardım" — çalışan ve okunur kodu, sırf farklı yazılmış diye reddetmek. Tercih ile hata farklıdır.
- **Ego savaşı:** Yorumu kişisel almak/yapmak. Review bir işbirliğidir, sınav değil.

Ölçek olarak: acemi ya çok yüzeysel (her şeye LGTM) ya çok agresif (her şeyi bloklar) olur. Pro, **kalibre**dir — enerjisini riske göre dağıtır, çoğu şeyi geçirir, az sayıda gerçekten önemli şeyde ısrarcı durur.

## 5. Araçlar ve saha notları

**İnsan yapmamalı olanı makineye ver.** Review zamanınız pahalı ve sınırlı bir kaynak. Onu biçimlendirme, stil ve mekanik kontrollere harcamak israftır. Bunları önce otomatiğe verin:

- **Linter / formatter** (dile göre — ör. ESLint/Prettier, Ruff/Black, gofmt, clippy): Girinti, isimlendirme, kullanılmayan değişken. Bunlar review yorumu olmamalı; CI'da otomatik. Formatı tartışan bir ekip enerjisini boşa harcar.
- **Statik analiz / SAST:** Tip hataları, olası null dereference, basit güvenlik desenleri. İnsan gözünün zayıf olduğu mekanik hataları burada yakalayın.
- **Dependency / güvenlik taraması:** Bağımlılıklardaki bilinen açıkları tarayan araçlar (npm audit, pip-audit, Dependabot gibi mekanizmalar). Yeni bağımlılık eklendiğinde otomatik uyarı.
- **Test kapsamı raporu:** Yüzdeye tapmayın ama "yeni eklenen mantığın hiç testi yok" durumunu görünür kılar.

Bu katman temizlik yapınca, insan review'ü **yalnızca makinenin yapamayacağı işe** odaklanır: tasarım, isimlendirmenin anlamlılığı (aracın kontrol edemediği türden), iş mantığının doğruluğu, güvenlik yargısı.

**Kodu çalıştırarak / adımlayarak inceleme.** Kritik, karmaşık bir PR'da satırları okumak yetmez. O branch'i çekip **debugger** ile sınır koşullarından geçiririm, ya da tartışmalı fonksiyonu bir test ile fiilen koştururum. "Kod okumak" ile "kodun ne yaptığını görmek" farklı şeylerdir; karmaşık mantıkta ikincisi şarttır.

**Performans şüphesinde profiler ve gerçek veri.** "Bu yavaş olabilir" bir histir; kanıt değil. N+1 şüphesi varsa, sorgu log'unu açıp o endpoint'in kaç sorgu attığını sayarım. Bellek şüphesinde profiler. Tahmin yerine ölçüm — ama review aşamasında çoğu zaman ölçemezsiniz, o yüzden **desen tanıma** (döngüde sorgu, tüm tabloyu belleğe alma) ana silahtır.

**Gözlemlenebilirlik gözüyle bakmak.** Review sırasında "bu kod prod'da bir şey yaparken göremeyeceğimiz bir şekilde bozulursa?" diye sorarım. Kritik yollarda log, metrik ve iz (trace) var mı? Yoksa, bunu review'da isterim — çünkü göremediğiniz şeyi düzeltemezsiniz.

**Pratik saha tüyoları:**

- **Kendi PR'ınızı önce kendiniz inceleyin.** PR açmadan önce diff'i baştan sona okuyun. Utanç verici hataların yarısını burada yakalar, review'cının zamanına saygı gösterirsiniz.
- **PR'ı küçük tutun.** Bir PR = bir mantıksal değişiklik. Refactor ile feature'ı ayır. Küçük PR daha iyi incelenir, daha hızlı merge olur, daha kolay geri alınır.
- **Yorumlarda "neden"i verin.** "Bunu değiştir" değil, "bunu şu yüzden değiştirmek gerekebilir" — gerekçe, yazana öğretir ve tartışmayı verimli kılar.
- **Ciddiyeti işaretleyin.** "nit:" (isteğe bağlı), "soru:" (anlamak istiyorum), "engelleyici:" — yazan neyin şart neyin zevk olduğunu bilsin.
- **Yorumla değil, konuşarak çözün — gerektiğinde.** Bir PR'da 40 ileri-geri yorum birikmişse, orada bir tasarım anlaşmazlığı vardır ve async yorum bunu çözmez. 10 dakika ekran paylaşımı 3 günlük yorum savaşından iyidir.
- **"Approve ediyorum ama şunlara bak" kullanın.** Ekibi bloklamayın; küçük düzeltmeleri güvene bırakın. Sürekli bekleten review, insanları review'dan kaçırır.
- **Zamanında yapın.** 3 gün bekleyen bir review, yazanın momentumunu ve bağlamını öldürür. Review, kod tazeyken en değerlidir.

**Otomasyonun sınırı ve tehlikesi.** Statik analiz güçlüdür ama iki tuzağı vardır. Birincisi, "yanlış pozitif yorgunluğu": araç 200 uyarı basıyorsa, ekip hepsini görmezden gelmeyi öğrenir ve gerçek uyarı da gürültüde kaybolur. Aracı sıkı ayarlayın, çok kural değil, doğru kural. İkincisi, "araç geçti demek doğru demek değildir": SAST injection görmediyse, injection yok anlamına gelmez — sadece bilinen desenlerde görmedi. İş mantığındaki güvenlik açıklarını (örneğin yetkilendirme eksikliği) hiçbir statik araç anlamaz, çünkü "bu kullanıcı bu veriyi görmeli mi?" sorusunun cevabı iş kuralında saklıdır, kodun şeklinde değil. Bu yüzden yetkilendirme her zaman insan gözü ister.

**Test kodunu da inceleyin — hatta önce onu.** Acemi review'cı test dosyalarını atlar, "test test işte" der. Pro, çoğu zaman testlere üretim kodundan daha dikkatli bakar, çünkü test, kodun ne yapması gerektiğinin sözleşmesidir. Kötü bir test iki türlüdür: hiçbir şeyi doğrulamayan test (assertion'sız, ya da her zaman geçen), ve implementasyonu test eden test (iç detaya bağlı, ufak bir refactor'da kırılan, güven yerine yük olan). "Bu test, kod yanlış olsaydı gerçekten kırmızı olur muydu?" — bu soruyu her testte sorarım. Bir de testin adı ne test ettiğini söylemeli; `test_1` gibi isimler, altı ay sonra kırıldığında kimseye ne olduğunu anlatmaz.

**Git geçmişi ve bağlam araçları.** Bir satırın neden orada olduğunu anlamadığımda `git blame` ve o commit'in mesajına bakarım. Çoğu zaman "gereksiz görünen" bir kontrol, aslında geçmişte bir prod olayının bıraktığı yara izidir. Bir şeyi silmeden önce "bu neden eklenmişti?" sorusunu sormak, aynı hatayı ikinci kez yapmaktan korur. Review'da "bu kontrol gereksiz, kaldır" demeden önce onun bir gerekçesi olup olmadığını kontrol edin.

Son bir yargı: **code review bir kapı bekçiliği değil, bir öğretme ve öğrenme aracıdır.** En iyi review'cılar hata yakalamayı değil, ekibin ortalama seviyesini yükseltmeyi hedefler. Bir junior'ın PR'ında yakaladığınız bir deseni ona açıklarsanız, gelecek 50 PR'da o hatayı görmezsiniz. Ölçeklenen budur. Ve unutmayın — siz de yanılırsınız; bazen yazan haklıdır. "Neden böyle yaptın?" sorusunun cevabı çoğu zaman sizin görmediğiniz bir kısıttır. En kötü review'cı her zaman haklı olduğunu sanandır; en iyisi, öğrenmeye açık olandır.
