# Web Uygulamalarında Race Condition

## Tanım

Race condition (yarış durumu), bir sistemin doğruluğunun birden çok işlemin **zamanlamasına** ya da **sırasına** bağlı hale geldiği ve bu zamanlamanın saldırgan tarafından bozulabildiği bir güvenlik açığı sınıfıdır. Tek başına çalıştırıldığında kusursuz görünen bir kod, aynı anda (concurrent) çalışan iki veya daha fazla kopyası bir paylaşılan kaynağa (veritabanı satırı, bakiye, kupon sayacı, dosya, oturum durumu) eş zamanlı eriştiğinde beklenmedik ve genellikle tehlikeli bir sonuç üretir.

Web bağlamında race condition'ın özel bir tehlikesi vardır: HTTP sunucuları doğaları gereği **eşzamanlıdır**. Bir endpoint saniyede yüzlerce isteği paralel thread'ler, process'ler veya event loop üzerinde işler. Yani saldırganın yarışı tetiklemek için özel bir yetki, bellek erişimi ya da düşük seviyeli araca ihtiyacı yoktur; sadece **aynı isteği aynı anda birden fazla göndermesi** yeterlidir. Bu, race condition'ı web'de düşük maliyetli ama yüksek etkili bir sınıf yapar.

Bu makalede dört ana örüntüye odaklanıyoruz: **TOCTOU** (Time-of-Check to Time-of-Use), **limit-overrun** (limit aşımı), **çift harcama** (double spending) ve bunların hepsini keskinleştiren **tek-paket saldırısı** (single-packet attack).

## Kök Neden: Neden Böyle Oluyor?

### Kontrol ve kullanım arasındaki boşluk

Race condition'ların büyük çoğunluğunun kalbinde tek bir yapısal hata yatar: **bir koşulu kontrol etme anı ile o koşula dayanarak eylem yapma anı arasında bir zaman boşluğu vardır ve bu boşlukta durum değişebilir.** Bu boşluğa literatürde **TOCTOU penceresi** denir.

Tipik kırılgan akış şöyledir:

1. Uygulama bir koşulu okur ("kullanıcının bakiyesi yeterli mi?", "bu kupon daha önce kullanılmış mı?", "bu kullanıcı adı boşta mı?").
2. Koşul sağlanır (`check` geçer).
3. Uygulama eyleme geçer (`use`): parayı çeker, kuponu uygular, hesabı oluşturur.

Sıralı (sequential) dünyada bu mantık kusursuzdur. Ancak iki istek `1` ile `3` adımları arasında iç içe geçerse, **ikisi de aynı eski durumu okur**, ikisi de kontrolü geçer ve ikisi de eyleme geçer. Bakiyesi 100 TL olan bir kullanıcı, iki 100 TL'lik çekimi aynı anda gönderirse, her iki istek de "yeterli bakiye var" görür ve 200 TL çekilir.

### Atomiklik eksikliği (atomicity)

Sorunun teknik adı **atomiklik eksikliği**dir. Bir işlem "atomik" ise, dışarıdan bakıldığında ya tamamen olur ya da hiç olmaz; ortasında başka bir işlem araya giremez. Kırılgan kod, mantıksal olarak tek bir bütün olması gereken "kontrol et + güncelle" işlemini **atomik olmayan** iki ayrı adıma böler. Araya giren pencere, saldırının tüm alanıdır.

### Web'de neden bu kadar kolay tetiklenir?

Geleneksel yerel (local) race condition'larda saldırganın thread zamanlamasını hassas biçimde ayarlaması gerekir. Web'de ise iki zorluk vardır ve saldırgan tarafı bu ikisini yenmeye çalışır:

- **Ağ jitter'ı (network jitter):** İstekler farklı zamanlarda sunucuya varır. Birkaç milisaniyelik farklar bile pencereyi kaçırmaya yeter.
- **Sunucu tarafı sıralama:** Sunucu istekleri sırayla kabul edebilir.

İşte tek-paket saldırısı tam olarak bu jitter problemini çözmek için doğdu; ona birazdan geleceğiz. Önce dört örüntüyü ayrı ayrı inceleyelim.

## Örüntü 1: TOCTOU (Time-of-Check to Time-of-Use)

TOCTOU, race condition'ın en genel ve en temel biçimidir; diğer üçü aslında onun özel görünümleridir. İsmi tam olarak sorunu tarif eder: **kontrol zamanı** (time of check) ile **kullanım zamanı** (time of use) arasındaki tutarsızlık.

Klasik web örneği bir **para çekme** akışıdır:

```python
# KIRILGAN kod — sadece örnek amaçlı
def para_cek(kullanici_id, miktar):
    bakiye = db.query("SELECT bakiye FROM hesaplar WHERE id = ?", kullanici_id)
    if bakiye >= miktar:                 # <-- CHECK (kontrol)
        yeni = bakiye - miktar
        db.execute("UPDATE hesaplar SET bakiye = ? WHERE id = ?", yeni, kullanici_id)  # <-- USE (kullanım)
        return "Basarili"
    return "Yetersiz bakiye"
```

Burada `SELECT` ile `UPDATE` arasında hiçbir kilit (lock) yok. İki istek aynı anda geldiğinde ikisi de aynı `bakiye` değerini okur, ikisi de `UPDATE` çalıştırır ve ikinci `UPDATE` birincinin sonucunu **ezerek** hatalı bir bakiye bırakır. Bu, aynı zamanda bir **lost update** (kayıp güncelleme) problemidir.

TOCTOU sadece parayla sınırlı değildir. Yaygın web varyantları:

- **Yetki kontrolü ile eylem arası:** "Bu dosyaya erişim iznin var mı?" kontrol edilir, ama okuma anına kadar dosyanın sahipliği/yolu değişebilir (özellikle dosya yükleme ve sembolik link senaryolarında).
- **Kullanıcı adı / e-posta benzersizliği:** "Bu kullanıcı adı boşta mı?" kontrol edilir, iki kayıt isteği aynı anda gelir, ikisi de boşta görür, iki hesap aynı adla oluşur.
- **Ödeme durumu:** "Sipariş ödendi mi?" ile "kargoyu tetikle" arasındaki boşluk.

## Örüntü 2: Limit-Overrun (Limit Aşımı)

Limit-overrun, bir sayısal sınırın **eşzamanlı isteklerle aşılması**dır. Uygulama bir kaynağın kaç kez kullanılabileceğine dair bir sınır koyar, ama sınır kontrolü atomik değildir.

Gerçek dünyadan tipik senaryolar:

- **Tek kullanımlık indirim kuponu / hediye kodu:** Kupon "kullanıldı mı?" diye kontrol edilir, henüz kullanılmamış görünür, ve saldırgan aynı kuponu 50 kez paralel uygular. Kontrol ile "kullanıldı olarak işaretle" arası atomik olmadığından **tek kupon onlarca kez** geçerli olur.
- **Kampanya / stok limiti:** "Kişi başı 1 adet" ya da "toplam 100 adet" gibi sınırlar. Saldırgan sınırı katlayarak aşar.
- **Rate limit / OTP deneme sayısı:** "5 yanlış denemeden sonra kilitle" mantığı. Deneme sayacı okuma ve artırma atomik değilse, saldırgan yüzlerce OTP tahminini limit devreye girmeden gönderebilir. Bu, race condition'ın **kimlik doğrulamayı** doğrudan zayıflatan biçimidir.
- **Davet / referans bakiyesi:** "1 davet hakkın var" limitinin aşılıp çok sayıda ödül toplanması.

Limit-overrun'ın etkisi genellikle **doğrudan finansal**dır ve bug bounty programlarında sık raporlanan bir sınıftır, çünkü kanıtı nettir: sınır sayısal olarak aşılmıştır.

## Örüntü 3: Çift Harcama (Double Spending)

Çift harcama terimi kripto para dünyasından gelir ama web'de çok daha geneldir: **aynı değer biriminin (bakiye, puan, hediye kartı, jeton) birden fazla kez harcanması.** Limit-overrun'ın "bakiye" üzerine uygulanmış özel halidir ve TOCTOU'nun para bağlamındaki görünümüdür.

Somut örnek — bir cüzdan uygulamasında **para transferi**:

Kullanıcının 100 TL bakiyesi var. İki farklı alıcıya, ikisi de 100 TL, transfer isteğini **aynı anda** gönderir. Her iki istek de bakiyeyi 100 TL okur, her ikisi de "yeterli" der, ve sistem toplam 200 TL transfer eder. Saldırgan 100 TL'lik varlıktan 200 TL üretmiştir.

Aynı örüntü şuralarda görülür:

- **Hediye kartı / bakiye yükleme:** Aynı kodun bakiyesini iki hesaba birden yükleme.
- **Puan/mil harcama:** Aynı puanı iki ödüle çevirme.
- **Sipariş iadesi:** Aynı siparişi paralel iki `refund` isteğiyle iki kez iade ettirme.
- **Sepet/indirim istifleme:** Aynı tek-kullanımlık indirimi paralel sepetlere uygulama.

Çift harcamanın tehlikeli yanı, **denetim kayıtlarında bile hemen fark edilmeyebilmesi**dir; her işlem tek başına meşru görünür, sorun yalnızca toplamda ortaya çıkar.

## Tek-Paket Saldırısı (Single-Packet Attack)

Yukarıdaki üç örüntünün hepsi teoride açıktır ama pratikte tetiklemek zordur, çünkü **ağ jitter'ı** yüzünden istekler tam olarak aynı anda sunucuya varmaz. Birkaç milisaniyelik varış farkı bile TOCTOU penceresini kaçırmaya yeter. Saldırganın esas mücadelesi budur.

Bu problemi çözmek için önce **son-bayt senkronizasyonu (last-byte sync)** tekniği yaygınlaştı: saldırgan çok sayıda isteğin *neredeyse tamamını* önceden gönderir, her birinin sadece son birkaç baytını tutar, sonra tüm son baytları tek seferde salıverir. Böylece istekler sunucuya çok daha eş zamanlı ulaşır. Ancak bu teknik hâlâ TCP katmanındaki jitter'a ve isteklerin farklı TCP paketlerine düşmesine bağımlıdır.

**Tek-paket saldırısı**, bu fikri bir adım öteye taşır ve HTTP/2'nin (ve genel olarak çoklama yapan protokollerin) bir özelliğinden yararlanır: HTTP/2, tek bir TCP bağlantısı üzerinde **birden fazla isteği paralel stream'ler halinde çoklar (multiplexing)**. Bu sayede saldırgan, çok sayıda tam isteği tek bir TCP paketine sığdıracak biçimde hazırlayıp gönderebilir. İstekler sunucuya **aynı ağ paketiyle** vardığında, aralarındaki varış farkı neredeyse sıfıra iner ve ağ jitter'ı büyük ölçüde denklemden çıkar.

Sonuç: TOCTOU penceresi çok dar (mikrosaniyeler mertebesinde) olsa bile, tek-paket saldırısı onu güvenilir biçimde vurabilir. Bu teknik, daha önce "teorik olarak var ama pratikte tetiklenemez" denen birçok race condition'ı **istismar edilebilir** hale getirdiği için önemlidir; race condition'ın modern web güvenliğinde yeniden ciddiye alınmasının başlıca sebebidir.

> Dürüstlük notu: Bu tekniği kavramsal düzeyde anlatıyorum. Belirli bir aracın tam bayrağını, sürüm numarasını veya sabit paket boyutu eşiğini burada uydurmuyorum; pratik uygulamada güncel dokümantasyona bakılmalıdır. Kavram net olarak şudur: HTTP/2 multiplexing sayesinde birden çok isteği aynı ağ paketiyle eş zamanlı gönderip varış farkını yok etmek.

## İstismar / Sömürü Mantığı

Bir saldırganın race condition avlarken izlediği düşünce zinciri şöyledir. Savunmayı doğru kurmak için bu zihniyeti anlamak şarttır.

**1. Aday endpoint'leri belirleme.** Saldırgan, "bir şeyi bir kez yapabilirsin" mantığı taşıyan tüm akışlara odaklanır: kupon uygulama, para çekme/transfer, oy verme, davet kullanma, hesap oluşturma, OTP doğrulama, iade talebi. Değer üreten veya sınır uygulayan her yer adaydır.

**2. Durum değişikliğini gözlemleme.** İstek tek başına gönderilir; hangi kaynağın değiştiği (bakiye, sayaç, bayrak) tespit edilir. Race, ancak paylaşılan bir durumu değiştiren isteklerde vardır; salt okuma yapan endpoint'ler ilgi çekmez.

**3. Eş zamanlı gönderim.** Aynı istek (ya da mantıksal olarak çelişen iki farklı istek) 20-100 kopya halinde, mümkün olan en yüksek eş zamanlılıkla, tercihen tek-paket tekniğiyle gönderilir.

**4. Anomaliyi ölçme.** Beklenen sonuç: bakiye yanlış, kupon birden çok kez geçerli, limit aşılmış, birden fazla hesap oluşmuş. Saldırgan başarıyı **sayısal kanıtla** doğrular.

**5. Tekrarlanabilirlik.** Race condition olasılıksaldır; her denemede tetiklenmeyebilir. Saldırgan denemeyi tekrarlar; tek-paket tekniği başarı oranını dramatik biçimde yükseltir.

Bu bilgi savunma amaçlıdır: kendi sistemlerinizi test ederken tam olarak bu adımları izlemeniz, kırılganlığı üretimde birinin bulmasından önce ortaya çıkarır.

## Savunma: Doğru Çözümler

Race condition'a karşı savunmanın altın kuralı tektir: **"kontrol et ve eyleme geç" işlemini atomik yap.** Bunu başarmanın birkaç doğru yolu vardır ve doğru araç, verinin nerede tutulduğuna bağlıdır.

### 1. Veritabanı düzeyinde atomiklik

En sağlam savunma katmanı çoğunlukla veritabanıdır, çünkü paylaşılan durum genelde oradadır.

- **Koşulu güncelleme cümlesine gömmek.** Kontrolü ayrı bir `SELECT` yerine `UPDATE`'in `WHERE` koşuluna koyun. Örneğin bakiye düşerken:

  ```sql
  UPDATE hesaplar
  SET bakiye = bakiye - :miktar
  WHERE id = :id AND bakiye >= :miktar;
  ```

  Ardından etkilenen satır sayısını kontrol edin: 0 ise işlem yetersiz bakiyeden reddedilmiştir. Burada kontrol ve güncelleme **tek bir atomik cümlededir**; araya girecek pencere yoktur. Bu, çift harcamaya karşı en temiz çözümlerden biridir.

- **Kilitleme (locking).** İlgili satırı işlem süresince kilitleyin (ör. `SELECT ... FOR UPDATE` gibi bir satır kilidi). Kilit tutulduğu sürece ikinci istek bekler; kontrol ve kullanım seri hale gelir. Kilit kapsamını dar tutun, aksi halde performans ve deadlock riski doğar.

- **Benzersizlik kısıtları (unique constraints).** Kullanıcı adı, e-posta, kupon-kullanıcı çifti gibi alanlarda veritabanı seviyesinde `UNIQUE` kısıtı tanımlayın. İki paralel kayıt yarışsa bile veritabanı ikincisini **reddeder**; uygulama mantığındaki kontrol atlansa dahi kısıt son savunma hattı olur.

- **Uygun izolasyon seviyesi (isolation level) ve iyimser kilitleme (optimistic locking).** Bir `version` sütunu tutup güncellerken `WHERE version = :okunan_version` koşulu koymak, araya giren güncellemeyi tespit edip işlemi tekrarlatmayı sağlar. Serializable izolasyon en güçlü garantidir ama maliyeti yüksektir; bilinçli seçilmelidir.

### 2. İdempotanlık (idempotency)

Özellikle ödeme ve para transferi gibi akışlarda **idempotency key** kullanın. İstemci her işlem için benzersiz bir anahtar üretir; sunucu aynı anahtarla gelen ikinci isteği yeni bir işlem olarak değil, ilk isteğin tekrarı olarak ele alır. Böylece aynı iade/transfer paralel de gönderilse yalnızca bir kez uygulanır. Bu, çift harcamaya karşı çok etkili ve saldırgana bağımlı olmayan bir savunmadır.

### 3. Atomik sayaçlar ve dağıtık kilitler

Limit-overrun'a karşı, sayaç işlemlerini atomik yapan araçlar kullanın. Örneğin bir in-memory veri deposunda atomik artırma (`INCR` benzeri) operasyonları, "önce oku sonra yaz" penceresini kapatır. Birden çok sunucu (çok instance'lı mimari) söz konusuysa **dağıtık kilit (distributed lock)** gerekir; tek bir sunucudaki dil-içi kilit (mutex) yeterli değildir, çünkü yarış farklı process'ler arasında olur.

### 4. Sunucu tarafında serileştirme

Bazı hassas akışlarda, aynı kullanıcı/kaynak için isteklerin sunucu tarafında **kuyruklanarak sırayla** işlenmesi tasarımsal olarak seçilebilir. Bu, eşzamanlılığı belirli bir kaynak için bilinçli olarak feda eder ama en yüksek güvenlik garantisini verir.

## Yaygın Hatalar

Race condition savunmasında en sık görülen ve en tehlikeli yanılgılar:

- **Uygulama katmanı kontrolüne güvenmek.** `if bakiye >= miktar` kontrolünü uygulama kodunda yapıp güncellemeyi ayrı çalıştırmak klasik hatadır. Kontrol, güncellemeyle **aynı atomik işlemde** olmalıdır.
- **Tek instance mutex'in yeterli olduğunu sanmak.** Uygulama sunucusu yatayda ölçeklenince (birden çok kopya), tek process içindeki kilit hiçbir şey korumaz. Kilit paylaşılan katmanda (veritabanı veya dağıtık kilit servisi) olmalıdır.
- **Frontend / istemci tarafı kısıtlamayı savunma sanmak.** Butonu devre dışı bırakmak, tek istek göndermek gibi istemci önlemleri saldırgan için hiç yoktur; saldırgan HTTP isteklerini doğrudan üretir.
- **"Bu race pratikte tetiklenemez" varsayımı.** Tek-paket saldırısı öncesi geçerli sanılan bu varsayım artık tehlikelidir. Dar bir pencere bile güvenilir biçimde vurulabilir; teorik açığı görmezden gelmeyin.
- **Sadece rate limit koymak.** Rate limit, çok sayıda isteği yavaşlatır ama eş zamanlı **birkaç** isteğin yarattığı race'i engellemez. Rate limit bir savunma katmanıdır, atomiklik değildir.
- **İzolasyon seviyesini varsayılan bırakıp güvenli sanmak.** Çoğu veritabanının varsayılan izolasyonu (ör. read committed türü) lost update'i tek başına engellemez. Hassas akışlar bilinçli kilit veya atomik cümle gerektirir.
- **Testleri sıralı yapmak.** Fonksiyonel testler isteği tek tek gönderir ve her zaman geçer. Race, yalnızca **eş zamanlı** testle ortaya çıkar; test paketine paralel/yarış testleri eklenmelidir.

## En İyi Pratikler

Bunları bir kontrol listesi olarak düşünün:

1. **Değer üreten veya sınır uygulayan her akışı race açısından tehdit modelleyin.** "Bu iki kez aynı anda çalışırsa ne olur?" sorusunu her endpoint için sorun. Bu tek soru açıkların çoğunu erkenden yakalar.

2. **Kritik değişiklikleri veritabanının atomiklik garantilerine dayandırın.** Koşulu `UPDATE ... WHERE`'e gömün, benzersizlik kısıtları koyun, gerektiğinde satır kilidi veya serializable izolasyon kullanın. Güvenliği uygulama kodunun zamanlamasına değil, veritabanının garantilerine yaslayın.

3. **Ödeme, transfer ve iade akışlarını idempotent yapın.** Her mali işlem için idempotency key benimseyin; bu hem race'e hem ağ tekrarına karşı korur.

4. **Dağıtık mimaride dağıtık kilit veya atomik sayaç kullanın**; asla tek-instance mutex'e güvenmeyin.

5. **Savunmayı katmanlayın (defense in depth).** Uygulama kontrolü + veritabanı kısıtı + idempotency birlikte kullanılınca, biri atlansa diğeri yakalar. Tek bir savunma noktasına bağımlı kalmayın.

6. **Eş zamanlılık testleri yazın.** CI hattına, aynı kritik isteği paralel gönderip sonucun tutarlı kaldığını doğrulayan testler ekleyin. Mümkünse kendi sistemlerinizi tek-paket / son-bayt sync teknikleriyle proaktif test edin.

7. **Kilit kapsamını dar, işlem süresini kısa tutun.** Uzun tutulan kilitler deadlock ve performans sorunu üretir; atomikliği en küçük gerekli kapsamda sağlayın.

8. **Loglama ve anomali tespiti ekleyin.** Aynı kaynağa çok kısa sürede gelen çok sayıda çelişkili işlem, bir race istismarının işareti olabilir; bunu izleyin.

## Sonuç

Race condition, web'de küçük bir zamanlama boşluğunun büyük finansal ve güvenlik sonuçlarına dönüştüğü, sinsi ama sistematik olarak önlenebilir bir açık sınıfıdır. Kök nedeni her zaman aynıdır: **kontrol ile kullanım arasındaki atomik olmayan pencere.** TOCTOU bu boşluğun genel adı, limit-overrun ve çift harcama onun para ve sayaç bağlamındaki keskin görünümleri, tek-paket saldırısı ise bu görünümleri pratikte güvenilir biçimde istismar edilebilir kılan modern tekniktir.

Savunma da tek bir ilkeye indirgenir: **mantıksal olarak bölünmez olması gereken işlemi teknik olarak da bölünmez (atomik) yapın** ve bunu uygulama kodunun zamanlamasına değil, veritabanı kısıtlarına, idempotency anahtarlarına ve dağıtık kilitlere dayandırın. "Bu iki kez aynı anda olursa ne olur?" sorusunu bir refleks haline getiren bir ekip, race condition'ların ezici çoğunluğunu daha kod yazılırken kapatır.
