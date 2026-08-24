# ACID ve Transaction'lar

## Transaction Nedir?

Bir **transaction** (işlem/hareket), veritabanı üzerinde yapılan bir veya birden fazla işlemin *tek bir mantıksal bütün* olarak ele alındığı çalışma birimidir. Buradaki kritik fikir "mantıksal bütünlük"tür: transaction içindeki işlemlerin ya *hepsi* başarıyla ve kalıcı olarak uygulanır, ya da *hiçbiri* uygulanmamış gibi davranılır. Arada bir yer, yani "yarısı yapıldı" durumu, dışarıdan bakan hiçbir gözlemci için var olmamalıdır.

Klasik örnek para transferidir. A hesabından B hesabına 100 lira göndermek aslında iki ayrı yazma işlemidir:

```sql
UPDATE hesaplar SET bakiye = bakiye - 100 WHERE id = 'A';
UPDATE hesaplar SET bakiye = bakiye + 100 WHERE id = 'B';
```

Eğer birinci `UPDATE` çalıştıktan sonra sistem çöker ve ikincisi hiç çalışmazsa, A'dan para eksilmiş ama B'ye hiç ulaşmamış olur. 100 lira buharlaşır. Transaction kavramı tam olarak bu felaketi önlemek için vardır: bu iki ifadeyi `BEGIN` ve `COMMIT` arasına alarak, veritabanına "bunlar bir bütündür, ya ikisini de yap ya da hiçbirini yapma" demiş oluruz.

**ACID**, bir transaction sisteminin güvenilir sayılabilmesi için sağlaması gereken dört temel garantinin baş harflerinden oluşan bir kısaltmadır: **A**tomicity (atomiklik), **C**onsistency (tutarlılık), **I**solation (izolasyon), **D**urability (kalıcılık). Bu dört özellik birlikte, "eş zamanlı erişimin ve arıza (crash, güç kesintisi, disk hatası) risklerinin olduğu bir dünyada verimin tutarlı kalması" problemine verilen mühendislik cevabıdır.

## Kök Neden: ACID Neden Var?

ACID özelliklerini ezberlemek yerine *hangi problemlere* cevap olduklarını anlamak çok daha kalıcıdır. İki temel gerçeklik ACID'yi doğurur:

1. **Donanım ve süreçler her an çökebilir.** Bir yazma işleminin ortasında elektrik kesilebilir, disk yazması yarıda kalabilir, işletim sistemi süreci öldürebilir. Veritabanı bu ihtimallere rağmen tutarlı kalmak zorundadır.
2. **Aynı veriye aynı anda birçok istemci erişir.** İki kullanıcı aynı ürünün son stok adedini almaya çalışabilir; iki thread aynı satırı güncelleyebilir. Bu eş zamanlılık (concurrency) kontrol altına alınmazsa **race condition**'lar ortaya çıkar ve veri bozulur.

Atomicity ve Durability daha çok *arıza* sorununu; Isolation ise daha çok *eş zamanlılık* sorununu çözer. Consistency ise bu üçünün ve uygulama kurallarının bir sonucudur. Şimdi her birini kök nedeniyle inceleyelim.

## Atomicity (Atomiklik)

### Tanım

Atomiklik, bir transaction'ın **bölünemez** olması demektir. Yunanca "atomos" (bölünemez) kelimesinden gelir. Transaction içindeki tüm işlemler tek bir birim olarak ya tamamen gerçekleşir (`COMMIT`) ya da tamamen geri alınır (`ROLLBACK`). Kısmi başarı diye bir şey yoktur.

### Çalışma Mantığı: Neden Böyle Olur?

Atomiklik sihirle değil, veritabanının değişiklikleri uygulamadan *önce* nasıl kaydettiğiyle sağlanır. Buradaki temel mekanizma genellikle **WAL (Write-Ahead Logging)** yani "önce loga yaz" prensibidir.

Fikir şudur: veritabanı bir veri sayfasını (data page) diskteki asıl yerinde değiştirmeden önce, "ne değiştireceğim" bilgisini ayrı bir *log* dosyasına yazar. Bu log kaydı diske kalıcı olarak yazıldıktan sonra asıl değişiklik yapılabilir. Böyle olunca iki senaryo da güvenli hale gelir:

- Transaction `COMMIT` edilmeden çökme olursa, veritabanı yeniden başladığında log'a bakar ve tamamlanmamış transaction'ların yaptığı değişiklikleri **geri alır (undo/rollback)**. Sanki hiç olmamış gibi.
- Transaction `COMMIT` edildikten sonra ama değişiklikler asıl diske tam yazılmadan çökme olursa, log'daki bilgiyi kullanarak değişiklikleri **yeniden uygular (redo)**.

Bu ikili yeteneğe (undo + redo) sahip olmak, atomikliğin ve az sonra göreceğimiz kalıcılığın temelidir. PostgreSQL, MySQL/InnoDB, SQLite gibi sistemlerin hepsi bir tür WAL veya redo/undo log kullanır.

### Somut Örnek ve Tuzaklar

Para transferini düşünün. `bakiye - 100` çalıştı, sonra sistem çöktü. Atomiklik sayesinde yeniden başlatmada bu değişiklik geri alınır ve A hesabı eski bakiyesine döner. Uygulama transferi tekrar deneyebilir.

**Yaygın tuzak:** Birçok geliştirici hata durumunda `ROLLBACK` çağırmayı unutur. Bir `try/catch` bloğunda transaction başlatıp exception fırlatınca, `finally` bloğunda bağlantı düzgün kapanmazsa transaction "asılı" kalabilir ve kilitleri tutmaya devam edebilir. Doğru desen şudur:

```python
conn.begin()
try:
    islem_1()
    islem_2()
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

Bir başka incelik: **atomiklik uygulama seviyesinde başlar.** Veritabanı sadece açtığınız transaction bloğunu atomik yapar. İki ayrı transaction'da yaptığınız iki işlem veritabanı için ilişkisizdir; onları tek `BEGIN`/`COMMIT` içine almazsanız atomiklik garantisi *o iki işlemi kapsamaz*.

## Consistency (Tutarlılık)

### Tanım

Tutarlılık, bir transaction'ın veritabanını *geçerli bir durumdan başka bir geçerli duruma* taşıması demektir. Yani transaction bittiğinde tüm tanımlı kurallar, kısıtlar (constraints) ve invariant'lar sağlanmış olmalıdır. Örneğin bir sütun `NOT NULL` ise, bir yabancı anahtar (foreign key) bir ana tabloya işaret etmek zorundaysa, bir `CHECK` kısıtı bakiyenin negatif olmasını yasaklıyorsa, transaction sonunda bunların hepsi geçerli olmalıdır.

### Çalışma Mantığı ve Sık Karıştırılan Nokta

Burada ACID literatüründeki en çok yanlış anlaşılan noktaya dikkat çekmek gerekir. ACID'deki "C" aslında diğer üçünden farklı bir kategoridedir. Atomicity, Isolation ve Durability tamamen *veritabanı motorunun* sorumluluğundadır. Tutarlılık ise **veritabanı ile uygulamanın ortak sorumluluğudur.**

Veritabanı size şu araçları verir: `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE`, `NOT NULL`, `CHECK` kısıtları ve tetikleyiciler (trigger). Bir transaction bu kuralları ihlal edecek bir duruma yol açarsa, veritabanı transaction'ı reddeder ve geri alır. Bu ölçüde tutarlılık motorun işidir.

Ancak "para transferinde toplam para miktarı korunmalıdır" gibi bir iş kuralını veritabanı *kendiliğinden bilmez*. Bu invariant'ı doğru kodlamak, yani her iki `UPDATE`'i aynı transaction'a koymak, uygulamanın sorumluluğudur. Veritabanı sadece "bu transaction bittiğinde tanımlı kısıtlar sağlanıyor mu?" diye kontrol eder; "senin iş mantığın anlamlı mı?" diye kontrol edemez. Dolayısıyla tutarlılık, doğru tanımlanmış kısıtlar + doğru yazılmış transaction sınırlarının bir sonucudur.

Diğer üç özelliğin de tutarlılığa hizmet ettiğini görmek önemlidir: atomiklik yarım kalmış değişikliklerin geçersiz durum bırakmasını, izolasyon eş zamanlı transaction'ların birbirini bozmasını, kalıcılık ise onaylanmış tutarlı durumun kaybolmasını önler.

## Durability (Kalıcılık)

### Tanım

Kalıcılık, bir transaction `COMMIT` edildikten sonra yaptığı değişikliklerin **kalıcı olarak** saklandığını garanti eder. `COMMIT` başarıyla döndükten sonra sistem çökse, elektrik kesilse, sunucu yeniden başlasa bile o veri kaybolmaz. İstemciye "tamamlandı" dendiği anda, o söz tutulmuş kabul edilir.

### Çalışma Mantığı: fsync ve WAL

Kalıcılığın kalbinde işletim sisteminin dosya sistemi davranışı yatar. Bir programın diske yazması aslında hemen fiziksel diske gitmez; önce işletim sisteminin **page cache**'inde (RAM'de) bekler. Bu hızlıdır ama kalıcı değildir. Tam bu noktada güç kesilirse veri gider.

Veritabanı bunu çözmek için kritik anlarda **fsync** (veya benzeri) sistem çağrısını kullanır. `fsync`, işletim sistemine "bu veriyi RAM cache'inde bırakma, gerçekten fiziksel diske yaz ve bana yazdığını teyit et" der. Bir `COMMIT`'in gerçek anlamı çoğu zaman "WAL log kaydı fsync ile diske kalıcı yazıldı" demektir.

Buradaki zekice optimizasyon şudur: asıl veri sayfalarını (rasgele konumlardaki data page'leri) diske yazmak yavaştır çünkü rasgele erişim (random I/O) gerektirir. Oysa WAL log dosyasına yazmak *ardışık (sequential)* bir yazmadır ve çok daha hızlıdır. Bu yüzden veritabanı `COMMIT` anında sadece log'u fsync eder; asıl data page'leri arka planda tembel tembel (checkpoint sırasında) diske yazılır. Çökme olursa log yeterlidir, çünkü redo ile eksik yazmalar tamamlanabilir.

### Tuzak: Katmanların Yalan Söylemesi

Kalıcılığın en sinsi tuzağı, katmanlardan birinin "yazdım" diye yalan söylemesidir. Bazı disk denetleyicileri veya SSD'ler kendi yazma önbelleklerine (write cache) sahiptir ve `fsync` çağrısını gerçekten fiziksel medyaya yazmadan başarılı döndürebilir. Bu durumda veritabanı kalıcılık garantisini sağladığını sanırken, ani güç kesintisinde önbellekteki onaylanmış veri kaybolur. Ciddi kurulumlarda güç koruması (BBU/kondansatörlü SSD) veya disk write cache'inin kapatılması bu yüzden önemlidir.

Ayrıca kalıcılık genellikle *tek makine* bağlamında tanımlanır. Dağıtık sistemlerde "dayanıklılık", veriyi birden çok düğüme replikleyip yeterli sayıda düğüm onaylayınca `COMMIT` dönmek şeklinde genişletilir; tek diskin fiziksel arızasına karşı da koruma sağlanmış olur.

## Isolation (İzolasyon) ve İzolasyon Seviyeleri

### Tanım

İzolasyon, aynı anda çalışan birden fazla transaction'ın birbirinden ne ölçüde *habersiz* olduğunu tanımlar. Teorik olarak mükemmel izolasyon, transaction'ların sanki *tek tek, sırayla* (seri olarak) çalışıyormuş gibi bir sonuç üretmesidir. Buna **serializability** denir.

Ancak mükemmel izolasyon pahalıdır: her transaction'ı gerçekten sıraya koyarsanız performans çöker. Bu yüzden veritabanları performans ile doğruluk arasında bir denge kurmak için farklı **izolasyon seviyeleri** sunar. Bir seviyeyi anlamanın yolu, o seviyenin *hangi anormalliklere (anomaly) izin verdiğini* bilmektir.

### Kök Neden: İzolasyon Neden Kademelidir?

Eğer her transaction başkasını hiç etkilemeden çalışsaydı izolasyona gerek olmazdı. Sorun, transaction'ların aynı veriyi paylaşmasıdır. Tam izolasyon için sistem ya çok fazla **lock** (kilit) tutmalı ya da çok fazla sürüm saklayıp çakışmaları tespit etmelidir; her ikisi de eş zamanlılığı düşürür. SQL standardı bu yüzden dört seviye tanımlar ve her seviye "hangi tür yan etkileri tolere ediyorsun?" sorusuna cevaptır. Uygulama, doğruluk ihtiyacına göre bu takası bilinçli yapmalıdır.

### İzolasyon Anomalileri (Yan Etkiler)

Seviyeleri anlamadan önce engellemeye çalıştıkları üç klasik anomaliyi tanımlayalım:

- **Dirty read (kirli okuma):** Bir transaction, başka bir transaction'ın henüz `COMMIT` etmediği (belki de geri alınacak) değişikliğini okur. Diğer transaction rollback yaparsa, ilki hiç var olmamış bir veriyi okumuş olur.
- **Non-repeatable read (tekrarlanamayan okuma):** Bir transaction aynı satırı iki kez okur ve iki okuma arasında başka bir transaction o satırı değiştirip commit ettiği için farklı değerler görür. Aynı sorgu, aynı transaction içinde farklı cevap verir.
- **Phantom read (hayalet okuma):** Bir transaction bir koşula uyan satırları okur (örneğin "fiyatı 100'den küçük ürünler"), sonra başka bir transaction bu koşula uyan *yeni bir satır ekler*. İlk transaction sorguyu tekrarladığında daha önce olmayan "hayalet" satırlar belirir. Non-repeatable read'den farkı, mevcut bir satırın değişmesi değil, kümenin üye sayısının değişmesidir.

### SQL Standardındaki Dört Seviye

Standart, izolasyon seviyelerini yukarıdaki anomalilere *izin verip vermemesiyle* tanımlar:

| Seviye | Dirty Read | Non-repeatable Read | Phantom Read |
|---|---|---|---|
| **READ UNCOMMITTED** | Olabilir | Olabilir | Olabilir |
| **READ COMMITTED** | Önlenir | Olabilir | Olabilir |
| **REPEATABLE READ** | Önlenir | Önlenir | Olabilir |
| **SERIALIZABLE** | Önlenir | Önlenir | Önlenir |

**READ UNCOMMITTED**, en gevşek seviyedir; başka transaction'ların commit etmemiş verisini bile okuyabilir. Pratikte çok nadir gerektiği için çoğu sistemde önerilmez.

**READ COMMITTED**, yalnızca commit edilmiş veriyi okumayı garanti eder. Bu, birçok veritabanının (örneğin PostgreSQL, Oracle) *varsayılan* seviyesidir. Kirli okumayı engeller ama aynı transaction içinde iki farklı okuma farklı sonuç verebilir.

**REPEATABLE READ**, bir transaction başladığında gördüğü satırların o transaction boyunca değişmeden kalmasını garanti eder. Aynı satırı iki kez okursanız aynı değeri görürsünüz. Standart tanıma göre bu seviyede hayalet okumalar hâlâ mümkündür (ancak pratikte bazı sistemler bunu da engeller; aşağıya bakınız).

**SERIALIZABLE**, en katı seviyedir. Sonuç, transaction'ların bir sıralamada seri çalışmasıyla elde edilecek sonuca eşdeğer olmak zorundadır. Tüm anomaliler engellenir. Doğruluk en yüksek, performans ve eş zamanlılık en düşüktür.

### Önemli Uyarı: Standart ile Gerçek Uygulamalar Ayrışır

Burada uzman seviyesinde bilinmesi gereken kritik bir gerçek var: **izolasyon seviyelerinin isimleri her veritabanında aynı davranışı garanti etmez.** SQL standardı seviyeleri anomalilerle tanımlar ama motorlar bunları farklı iç mekanizmalarla (kilit tabanlı veya sürüm tabanlı) uygular. Sonuç olarak aynı isimli seviye, farklı sistemlerde farklı davranır. Somut ve iyi bilinen örnekler:

- Birçok **MVCC** (Multi-Version Concurrency Control) tabanlı sistemde `REPEATABLE READ`, standardın izin verdiği bazı hayalet durumlarını da engelleyecek şekilde daha güçlü davranır. MVCC'de her transaction verinin tutarlı bir *snapshot*'ını gördüğü için, bu genelde "snapshot isolation" olarak adlandırılan bir davranışa yakındır.
- **Snapshot isolation**, dirty/non-repeatable/phantom read'lerin çoğunu engellese de kendine özgü bir anomaliye, **write skew**'e açık olabilir. Write skew, iki transaction farklı satırları okuyup birbirinin varsayımını bozacak şekilde yazdığında ortaya çıkar; her ikisi kendi başına geçerli görünür ama birlikte bir invariant'ı ihlal ederler. Snapshot isolation standart seviyeler tablosundaki anomalilerle tam örtüşmez; bu yüzden isimlere değil davranışa güvenmek gerekir.

Bu yüzden pratik kural şudur: kullandığınız spesifik veritabanının dokümantasyonunda, seçtiğiniz izolasyon seviyesinin *tam olarak hangi garantileri* verdiğini okuyun. "REPEATABLE READ yazıyor, o zaman standarttaki gibidir" varsayımı sizi hataya götürür.

### İzolasyon Nasıl Uygulanır: Kilit Tabanlı vs MVCC

İzolasyonu sağlamanın iki büyük yaklaşımı vardır ve bunları bilmek davranışları öngörmeyi kolaylaştırır:

- **Pesimist (kilit tabanlı):** Bir satır okunurken/yazılırken üzerine kilit konur, diğer transaction'lar beklemek zorunda kalır. Doğruluğu sağlar ama beklemeye ve **deadlock**'lara (iki transaction karşılıklı birbirinin kilidini bekler) yol açabilir.
- **İyimser / MVCC (sürüm tabanlı):** Veri her değiştiğinde eski sürüm saklanır. Okuyucular yazıcıları bloklamaz; her okuyucu kendi snapshot'ını görür. Bu, okuma ağırlıklı iş yüklerinde çok daha yüksek eş zamanlılık sağlar. Ancak çakışma commit anında tespit edilir ve bir transaction "seri hale getirilemedi" hatasıyla reddedilebilir; uygulamanın bu durumda transaction'ı *yeniden denemesi* gerekir. PostgreSQL, Oracle ve modern InnoDB büyük ölçüde MVCC kullanır.

## Yaygın Hatalar

**1. Transaction'ı çok uzun tutmak.** Bir transaction açıp içinde ağ çağrısı, kullanıcı girdisi beklemek veya uzun hesaplama yapmak, tutulan kilitlerin uzun süre elde kalmasına, dolayısıyla diğer transaction'ların bloklanmasına ve deadlock riskine yol açar. Transaction'lar kısa ve odaklı olmalıdır; harici I/O transaction dışına alınmalıdır.

**2. Retry mantığını unutmak.** Özellikle `SERIALIZABLE` veya MVCC tabanlı yüksek izolasyonda, veritabanı çakışan bir transaction'ı reddedebilir. Uygulama bu "serialization failure" hatasını yakalayıp transaction'ı yeniden denemek üzere tasarlanmalıdır. Bunu yapmayan kodlar, yük altında beklenmedik hatalarla karşılaşır.

**3. İzolasyon seviyesini iş kuralına göre değil, körü körüne seçmek.** Varsayılan `READ COMMITTED` birçok senaryoda yeterlidir ama "önce oku, karar ver, sonra yaz" (read-modify-write) desenlerinde yetersiz kalabilir. Örneğin stok kontrolünde "stok var mı diye bak, varsa düş" işlemi READ COMMITTED altında iki eş zamanlı istemcide aynı son ürünü iki kez satabilir. Bu gibi durumlarda ya daha yüksek izolasyon ya da açık kilitleme (`SELECT ... FOR UPDATE`) gerekir.

**4. Uygulama seviyesinde "tutarlılık" varsaymak.** Veritabanı invariant'larınızı bilmez. Kritik iş kurallarını `CHECK`, `UNIQUE`, `FOREIGN KEY` gibi kısıtlara mümkün olduğunca gömmek, kuralları sadece uygulama kodunda tutmaktan çok daha güvenlidir; çünkü aynı veritabanına birden çok uygulama veya betik erişebilir.

**5. Kalıcılığı test etmemek.** "COMMIT döndü, o hâlde veri güvende" varsayımı, disk write cache'i açıkken yanlış olabilir. Ciddi sistemlerde ani güç kesintisi senaryoları test edilmeli, fsync davranışı ve donanım write cache ayarları doğrulanmalıdır.

**6. Otomatik commit modunu fark etmemek.** Birçok istemci kütüphanesi varsayılan olarak "autocommit" modundadır; yani her ifade kendi transaction'ında çalışır. Birden çok ifadeyi atomik yapmak istediğinizde açıkça bir transaction başlatmanız gerekir. Bunu unutmak, atomik sandığınız işlemlerin aslında ayrı ayrı commit edilmesine yol açar.

## En İyi Pratikler

- **Transaction sınırlarını iş mantığına göre çizin.** Bir "mantıksal bütün" oluşturan tüm işlemleri (ve *yalnızca* onları) aynı transaction'a koyun. Alakasız işlemleri aynı transaction'a doldurmak gereksiz kilit ve çakışma yaratır.
- **Transaction'ları kısa tutun; harici bağımlılıkları dışarı alın.** Kullanıcı etkileşimi, üçüncü parti API çağrısı gibi yavaş ve öngörülemez işleri transaction dışında yapın.
- **İzolasyon seviyesini bilinçli seçin.** Varsayılanla başlayın, ama read-modify-write, envanter, muhasebe gibi doğruluğu kritik akışlarda daha yüksek seviye veya açık kilitleme kullanmayı değerlendirin. Seçtiğiniz seviyenin *kendi veritabanınızdaki* tam davranışını dokümandan teyit edin.
- **Serialization/deadlock hataları için idempotent retry yazın.** Yüksek izolasyon veya MVCC kullanıyorsanız, sınırlı sayıda ve giderek artan bekleme süreli (exponential backoff) yeniden deneme mantığı ekleyin.
- **İş invariant'larını veritabanı kısıtlarına gömün.** `NOT NULL`, `UNIQUE`, `FOREIGN KEY`, `CHECK` kısıtları tutarlılığın son savunma hattıdır ve tüm erişim yollarını korur.
- **Hata durumunda rollback'i garanti edin.** Transaction'ı `try/except/finally` gibi bir yapıyla sarıp, herhangi bir hatada mutlaka geri alınmasını ve bağlantının serbest bırakılmasını sağlayın.
- **Kalıcılık zincirinin tümünü doğrulayın.** Sadece veritabanı ayarına değil, altındaki dosya sistemi, disk denetleyici ve depolama donanımının fsync'e dürüst cevap verdiğine güvenin ve mümkünse test edin.

## Özet

ACID, "arıza ve eş zamanlılık dünyasında verinin güvenilir kalması" probleminin dört boyutlu cevabıdır. **Atomiklik** (WAL/undo sayesinde ya hep ya hiç), **Tutarlılık** (kısıtlar + doğru transaction sınırları), **İzolasyon** (kilit veya MVCC ile eş zamanlı transaction'ların birbirini bozmaması) ve **Kalıcılık** (fsync ile commit edilen verinin kaybolmaması). Bu özelliklerden en incelikli olanı izolasyondur; çünkü seviyeleri bir doğruluk-performans takasıdır ve isimleri her veritabanında aynı garantiyi vermez. Uzman yaklaşım, bu garantileri ezberlemek değil, altlarındaki mekanizmaları ve kullandığınız spesifik motorun gerçek davranışını anlamaktır.
