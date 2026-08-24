# Deployment / Rollback Kararı — Sahadan Pratisyen Notları

## 1. Problem / bağlam: bu iş neyi çözer, ne zaman devreye girer

Deployment kararı "kodu prod'a alalım mı" sorusu değildir. Asıl soru şudur: **yeni sürüm canlıya çıktı, bir şeyler tuhaf görünüyor — bekleyeyim mi, ileri mi gideyim, yoksa geri mi döneyim?** Bu karar dakikalar içinde, eksik bilgiyle, genellikle birileri Slack'te "prod yavaşladı" yazarken verilir. Ve yanlış verilirse iki türlü acı çekilir: gereksiz rollback ile aslında sağlam bir sürümü geri alıp gerçek problemi (altyapı, üçüncü parti, veri) gözden kaçırırsın; ya da geç kalınmış rollback ile her geçen dakika daha fazla kullanıcıya, daha fazla bozuk veriye yayılırsın.

Bu konu şu anlarda devreye girer:
- Bir release canlıya alındıktan sonra hata oranı / gecikme / iş metrikleri sapıyor.
- Bir migration çalıştı, geri almak artık "sadece eski kodu koymak" kadar basit değil.
- Gece 03:00, nöbetçisin, ve elinde tek net bilgi "checkout %20 düştü".

Kıdemli mühendisin buradaki değeri, teknik olarak "nasıl deploy edilir"i bilmesi değil. Herkes `kubectl rollout undo` yazmayı bilir. Değer, **hangi durumda ileri, hangi durumda geri gidileceğine dair yargıda** ve daha da önemlisi, **rollback'in mümkün ve güvenli olduğu bir sistemi önceden kurmuş olmakta**. Rollback kararının %80'i, karar anından haftalar önce, deploy'u nasıl tasarladığında verilir.

## 2. Metodoloji ve karar ağacı — asıl değer

### Önce zihinsel model: iki ayrı soru

Acemi "deploy başarılı mı?" diye tek soru sorar. Pro iki soruyu ayırır:

1. **Değişiklik geri alınabilir mi?** (reversibility)
2. **Değişiklik zarar veriyor mu?** (blast radius / etki)

Bu ikisi bağımsızdır ve karar ağacının kökü budur. Geri alınabilir + zararlı = hemen rollback, düşün bile. Geri alınamaz + zararlı = en kötü senaryo, burada "roll forward" (ileri düzeltme) tek yoldur ve panik değil, disiplin gerekir.

### Adım 0 (deploy'dan ÖNCE): geri dönüşü tasarla

Kıdemli mühendis rollback'i olay anında düşünmez. Deploy planında şu soruyu yanıtlamadan çıkmaz: **"Bu yanlış giderse, T+5 dakikada nasıl geri alırım ve o geri alış güvenli mi?"**

Kritik ayrım — geri alınabilirlik seviyeleri:

- **Tam tersinir (stateless kod):** Sadece uygulama kodu değişti, şema/veri dokunulmadı. `rollout undo` yeterli. En rahat durum.
- **İleri-uyumlu şema (expand/contract):** Şema değişti ama eski kod da yeni şemayla çalışabiliyor. Rollback güvenli. Bu, olgun ekiplerin standardıdır.
- **Kırıcı şema değişikliği:** Kolon düşürüldü, tip değişti, NOT NULL eklendi. Eski kod yeni şemada patlar. Rollback artık **veri kaybı riski** taşır. Burada karar bambaşka.
- **Geri dönüşsüz veri işlemi:** Batch bir job veri sildi/dönüştürdü, e-posta gönderildi, ödeme çekildi. "Rollback" diye bir şey yok; sadece telafi (compensation) var.

Bu seviyeyi deploy'dan önce bilmezsen, olay anında öğrenmek zorunda kalırsın — ki bu en pahalı öğrenme anıdır.

### Karar ağacı — belirti gördüğünde

**Belirti geldi (hata oranı, gecikme, iş metriği sapması). Sırayla:**

**1. Zamanlama korelasyonu kur.** İlk refleks "deploy mu yaptı bunu?" değil, **"bu ne zaman başladı ve deploy ne zaman oldu?"** olmalı. Eğer bozulma deploy'dan 40 dakika sonra başladıysa ve deploy anında her şey yolundaydıysa, muhtemelen suçlu deploy değil — trafik artışı, bir üçüncü parti, bir cron job, dolan bir disk olabilir. Acemi burada refleksle rollback yapar, sürümü suçlar, gerçek sebep devam eder ve rollback sonrası da problem sürünce kafası karışır. **Deploy zamanı ile belirti başlangıcı çakışmıyorsa, rollback muhtemelen yanlış koldur.**

**2. Etkiyi ölç, tahmin etme.** "Yavaş görünüyor" karar için yeterli değil. Somut sorular: Hata oranı %0.1'den %kaça çıktı? Hangi endpoint? Tüm kullanıcılar mı, tek bir bölge/tenant/feature flag kohortu mu? Gelir etkileyen bir akış mı (checkout, login) yoksa tali bir şey mi (ayarlar sayfası)? Kıdemli, blast radius'u sayısallaştırmadan büyük karar vermez — ama sayısallaştırmak için 20 dakika beklemek de büyük karardır (aşağıda).

**3. "Durdur zararı" eşiği.** Şu üçünden biri varsa **tartışma bitti, hemen rollback / kill switch:**
   - Veri bozuluyor (yanlış yazılıyor, siliniyor). Her saniye daha fazla temizlenecek veri demek.
   - Gelir/güvenlik akışı komple kırık (kimse ödeme yapamıyor, auth çökük).
   - Hata hızla yayılıyor (kademeli rollout'ta %5'ten %5 hata, %100'e giderse felaket).
   
   Bu durumda "sebebini anlayalım" tuzağına düşme. Önce kanamayı durdur, teşhisi sonra yap. Postmortem'i sağlam prod'da yazmak, çökük prod'da yazmaktan iyidir.

**4. Reversibility'yi kontrol et.** Rollback'e karar verdin — ama güvenli mi? Adım 0'daki seviyeyi hatırla. Eğer bu deploy şema kırdıysa, düz rollback eski kodu yeni şemayla buluşturur ve **ikinci bir olay** yaratırsın. Burada seçenek:
   - Feature flag ile davranışı kapat (kod prod'da kalır, etki durur) — en güvenli.
   - İleri düzeltme (roll forward): küçük bir hotfix ile bug'ı gider, çünkü geri gitmek daha riskli.
   - Şema-uyumlu rollback: sadece eski kod hem eski hem yeni şemayla çalışıyorsa güvenli.

**5. Karar matrisi (zihinde tut):**

| | Kolay geri alınır | Zor / riskli geri alınır |
|---|---|---|
| **Yüksek zarar** | Hemen rollback | Kill switch / flag kapat, olmuyorsa roll forward |
| **Düşük zarar** | Gözlemle, gerekirse rollback | Roll forward planla, acele etme |

### Kritik takas: hız vs. kesinlik

Buradaki asıl ustalık, **"bekleyip daha çok veri toplamanın maliyeti" ile "hemen davranmanın maliyeti"ni** tartabilmektir. Her dakika bekleme, hem daha çok teşhis verisi hem de daha çok zarar demek. Kural: **etki tersinir ve yavaş yayılıyorsa gözlem lehine; tersinmez ve hızlıysa aksiyon lehine** eğil. Checkout'ta veri bozuluyorsa 20 dakika "grafiklere bakmak" affedilmez; bir raporlama sayfası %2 yavaşladıysa 10 dakika daha veri toplamak akıllıcadır.

### Kim karar verir

Olgun ekiplerde bu karar tek kişinin egosuna bırakılmaz ama komiteye de bırakılmaz. **Incident commander** (nöbetçi) karar verir, çünkü kararın hızı kalitesinden önemlidir çoğu zaman. "Rollback yapıp yapmayacağımızı toplantıda tartışalım" cümlesi, olay yönetiminin çöktüğünün işaretidir. Geri alınabilir bir sistemde, şüphedeysen geri al — çünkü rollback ucuzsa yanlış rollback'in maliyeti düşüktür.

### Bir ince nokta: "rollback" tek bir şey değildir

Acemi rollback'i tek bir düğme sanır. Sahada en az beş farklı "geri dönüş" aleti vardır ve doğru olanı seçmek kararın kendisidir:

- **Sürüm geri alma (deploy rollback):** Önceki artefaktı tekrar dağıt. Sadece kod tersinirken geçerli.
- **Feature flag kapatma:** Kod prod'da kalır, davranış anında durur. En hızlı ve en az yan etkili. Şema bozulmadıysa altın standart.
- **Trafik kaydırma (traffic shift):** Blue/green ya da canary'de yükü eski sürüme geri çevir. Saniyeler içinde, veri katmanına dokunmadan.
- **Roll forward (ileri düzeltme):** Geri gitmek riskliyse, minik bir hotfix ile ileri git. Kırıcı migration sonrası çoğu zaman tek güvenli yol.
- **Telafi işlemi (compensation):** Geri dönüşsüz bir eylem oldu (e-posta gitti, ödeme çekildi). "Geri alma" yok; ikinci bir düzeltici işlem var (iade, düzeltme e-postası, ters kayıt).

Kararın kalitesi, "geri alalım mı" sorusuna değil, **"bu beş aletten hangisi bu duruma uyar"** sorusuna verdiğin cevapta gizli. Çoğu kötü olay, doğru soru "flag kapat" iken birinin "deploy rollback" yazmasıyla derinleşir.

## 3. Gerçek senaryo üzerinden yürüyüş: kırıcı migration tuzağı

Somut bir olay anlatayım — bu kalıbı sahada defalarca gördüm.

**Bağlam:** `users` tablosunda `full_name` diye tek kolon var. Ekip bunu `first_name` + `last_name` olarak ayırmak istiyor. Bir junior mühendis şu migration'ı yazıyor ve tek deploy'da göndermeyi planlıyor:

```sql
-- migration_042.sql  (TEHLİKELİ: tek adımda kırıcı)
ALTER TABLE users ADD COLUMN first_name TEXT;
ALTER TABLE users ADD COLUMN last_name TEXT;
UPDATE users SET
  first_name = split_part(full_name, ' ', 1),
  last_name  = split_part(full_name, ' ', 2);
ALTER TABLE users DROP COLUMN full_name;   -- <-- kırıcı satır
```

Ve yeni kod artık her yerde `first_name`/`last_name` okuyup yazıyor. Deploy düğmesine basılıyor.

**Ne oluyor:** Deploy sırasında rolling update var, yani birkaç dakika **eski kod ile yeni kod aynı anda** çalışıyor. Eski kod `full_name` yazmaya çalışıyor — kolon yok — **eski pod'lar patlıyor**. Aynı anda `split_part` mantığı "Ayşe Nur Yılmaz" ismini `first_name='Ayşe', last_name='Nur'` diye kesiyor, "Yılmaz" kayboluyor. Binlerce kayıtta soyad yanlış.

**Teşhis:** Hata oranı deploy anında sıçradı (zamanlama korelasyonu net → deploy suçlu). 5xx'ler `full_name` içeren stack trace veriyor. Etki: tüm yazma yolu. Zarar yüksek, hızlı yayılıyor → **"durdur zararı" eşiği aşıldı.**

**Ama işte tuzak:** Nöbetçi refleksle `rollout undo` yazıyor. Eski kod geri geliyor — ama `full_name` kolonu artık **yok**. Eski kodun tamamı çöküyor. Rollback, olayı **kötüleştirdi**. Üstelik `UPDATE` ile kaybolan soyad verisi migration'ın içinde, geri gelmiyor. Tek deploy'da hem uygulamayı kırdın, hem veriyi bozdun, hem de rollback yolunu kapattın.

**Doğrusu — expand/contract (genişlet/daralt) deseni.** Aynı iş, üç ayrı deploy'a bölünür:

**Deploy 1 — Genişlet (expand), geriye dönük uyumlu:**
```sql
-- Sadece EKLE, hiçbir şey silme. Eski kod bozulmaz.
ALTER TABLE users ADD COLUMN first_name TEXT;
ALTER TABLE users ADD COLUMN last_name TEXT;
```
Kod bu adımda: yazarken **hem** `full_name`'i **hem** yeni kolonları doldurur (dual write), okurken hâlâ `full_name`'i kullanır. Rollback tam güvenli — hiçbir şey silinmedi.

**Backfill — ayrı, idempotent, batch'li:**
```sql
-- Küçük partiler halinde, tekrar çalıştırılabilir, prod'u kilitlemeden.
UPDATE users
SET first_name = split_part(full_name, ' ', 1),
    last_name  = substr(full_name, length(split_part(full_name,' ',1)) + 2)
WHERE first_name IS NULL
LIMIT 1000;  -- döngüyle, kalan 0 olana dek
```
Dikkat: soyad mantığı "ilk boşluktan sonrasının tamamı" olarak düzeltildi, "Ayşe Nur Yılmaz" → last_name `'Nur Yılmaz'`. İsim ayrıştırma zaten kusurludur; bu yüzden `full_name` **henüz silinmiyor** — hatalı ayrıştırmayı geri alabilmek için ham veri duruyor.

**Deploy 2 — Kod tamamen yeni kolonlara geçer:** Okuma da yazma da `first_name`/`last_name` üzerinden. `full_name`'e artık dokunulmuyor ama kolon hâlâ tabloda. Bir şey ters giderse Deploy 1'e güvenle dönülebilir.

**Deploy 3 — Daralt (contract), günler sonra:** Her şeyin sağlam çalıştığı doğrulandıktan sonra:
```sql
ALTER TABLE users DROP COLUMN full_name;
```
Bu adım artık düşük riskli, çünkü kod haftalardır bu kolona bakmıyor.

**Kilit içgörü:** Kırıcı değişikliği tek işleme sıkıştırmak, rollback'i imkânsız kılar. Genişlet/daralt deseni, her ara durumu geri alınabilir tutarak "olay anında rollback" seçeneğini **satın alır**. Pro, deploy'u kırıcı olmaktan çıkarmak için fazladan iki deploy'a katlanır — çünkü o iki fazladan deploy'un maliyeti, gece 03:00'te bozuk veriyi elle temizlemenin maliyetinin yanında hiçtir.

### İkinci senaryo: doğru rollback kararı ama yanlış zamanlama teşhisi

Başka bir kalıp. Bir ekip öğlen 14:00'te ödeme servisine yeni sürüm çıkarıyor. 14:35'te alarmlar ötüyor: ödeme başarı oranı %99'dan %88'e düştü. Nöbetçi grafiğe bakıyor, "deploy vardı, geri alalım" diyor ve `rollout undo` çalıştırıyor. 10 dakika sonra oran hâlâ %88. Panik büyüyor, ikinci bir mühendis DB'ye bakıyor, üçüncüsü ağ ekibini arıyor.

Gerçek sebep: 14:30'da **üçüncü parti ödeme sağlayıcısı** kendi tarafında bir bölgede kesinti yaşamaya başlamış. Deploy'un olayla hiçbir ilgisi yok — sadece zamansal yakınlık ekibi yanılttı. Rollback boşuna yapıldı, sağlam sürüm geri alındı, gerçek sorun (harici sağlayıcı) 40 dakika daha teşhis edilmeden sürdü.

**Ders — "post hoc ergo propter hoc" tuzağı:** "Deploy'dan sonra oldu, demek ki deploy yaptı" en yaygın olay yönetimi hatasıdır. Doğru refleks: rollback yapmadan önce **30 saniyelik zamanlama testi**. Belirti tam deploy anında mı başladı (dikey annotation ile grafikte kontrol et), yoksa 30+ dakika sonra mı? Sonra başladıysa, "acaba dışarıda ne değişti" sorusunu en az deploy kadar ciddiye al: harici bağımlılık dashboard'ları, trafik grafiği, altyapı olayları. Kıdemli, rollback'i "ilk hamle" değil, "korelasyon deploy'u işaret ediyorsa hamle" olarak konumlar.

Not: bu, "şüphedeysen geri al" ilkesiyle çelişmez. Fark incedir ve önemlidir — **rollback ucuz ve güvenliyse** şüphede geri al (kaybedecek bir şey yok). Ama rollback'in kendisi de bir değişiklik, bir risk ve bir dikkat dağıtıcıysa (ödeme servisini gereksiz yere sallamak), önce 30 saniyelik korelasyon kontrolü yap. İkisi arasındaki denge, rollback'inin ne kadar ucuz olduğuna bağlıdır — yine her şey Adım 0'daki tasarıma çıkıyor.

## 4. Acemi vs. pro: yaygın hatalar ve gerçek tuzaklar

**"Rollback = eski kodu koymak" sanmak.** En pahalı yanılgı. Kod tersinirdir; şema ve veri çoğu zaman değildir. Acemi rollback butonuna "her zaman güvenli kaçış" olarak güvenir. Pro bilir ki bir migration çalıştıktan sonra rollback, ileri gitmekten daha riskli olabilir. Deploy'dan önce sorulacak soru: "geri alırsam veri katmanı ne olur?"

**Refleksle rollback.** Belirti görünce sebebi düşünmeden geri almak. Sorun deploy'da değilse (üçüncü parti, altyapı, trafik) rollback hem çözmez hem de "değişkeni" boşuna oynatır, teşhisi zorlaştırır. Önce zamanlama korelasyonu, sonra karar.

**Rollback'i hiç prova etmemek.** Rollback prosedürü, ilk kez gerçek olayda çalıştırılıyorsa aslında bir prosedürün yoktur. Pro, rollback'i normal günlerde, baskısızken dener. "Cuma deploy'u riskli" klişesi aslında "rollback'imize güvenmiyoruz"un itirafıdır; güçlü rollback'i olan ekipler Cuma'dan korkmaz.

**Deploy = release sanmak.** İkisini ayırmamak. Olgun ekipte kod prod'a **çıkar** (deploy) ama kullanıcıya **açılmaz** (release) — feature flag arkasında bekler. Böylece "rollback" çoğu zaman bir DB/kod işlemi değil, bir bayrağı kapatmaktır: anında, temiz, veri katmanına dokunmadan. Acemi her davranışı deploy'a bağlar, tek geri dönüş yolu olarak riskli rollback'e mahkûm kalır.

**Migration'ı uygulama başlangıcına bağlamak.** Kod deploy'u ile şema migration'ını atomik sanmak. Gerçekte rolling update'te eski ve yeni sürüm dakikalarca birlikte yaşar. Migration'ın **hem eski hem yeni kodla uyumlu** olması zorunludur; değilse geçiş penceresinde eski pod'lar patlar (Bölüm 3'teki tam senaryo).

**Yeşil dashboard'a güvenip erken zafer ilanı.** Deploy'dan 5 dakika sonra "her şey yeşil" deyip dağılmak. Bazı hatalar cache dolunca, batch job tetiklenince, ya da belirli bir tenant giriş yapınca çıkar. Pro deploy sonrası bir **gözlem penceresi** tutar ve rollback kararını o pencere boyunca "hazırda" bekletir.

**"Backfill" migration'ı senkron ve kilitli çalıştırmak.** Milyonlarca satırda tek `UPDATE`, tabloyu kilitler, migration timeout'a düşer, uygulama donar — ve bu sırada deploy yarım kalır. Pro backfill'i batch'li, idempotent ve uygulama trafiğinden ayrı çalıştırır.

**Sadece teknik metriğe bakmak.** CPU, hata oranı yeşil ama **sipariş sayısı** dibi gördü. Kod hata fırlatmıyor ama yanlış davranıyor (ör. "Sepete ekle" sessizce çalışmıyor). En sinsi olaylar bunlardır. Pro, teknik metriklerin yanına **iş metriklerini** (checkout, signup, gelir) koyar; asıl rollback sinyali çoğu zaman oradan gelir.

## 5. Araçlar ve saha notları

**Kademeli çıkış (canary / progressive delivery).** Rollback'in en iyisi hiç yapılmayanıdır. Yeni sürümü önce trafiğin %1-5'ine ver, metrikleri karşılaştır, iyiyse otomatik ilerlet, kötüyse otomatik geri al. Argo Rollouts, Flagger gibi araçlar bunu otomatikleştirir. Buradaki tuyo: canary metrik eşiklerini **önceden** ve dürüstçe belirle; "gözle bakarım" dersen canary'nin faydasını yakarsın.

**Feature flag / kill switch (LaunchDarkly, Unleash, ya da basit bir config).** Deploy ve release'i ayırmanın motoru. Riskli her davranışı bir bayrağın arkasına koy. Saha notu: kill switch'in **çalıştığını düzenli test et** — kullanılmayan acil durum kolu paslanır. Ve bayrak okumasını cache'lersen, "kapattım ama hâlâ açık" tuzağına düşersin; kapatma yayılım süresini bil.

**Observability — sadece log değil.** Karar hızı, doğru grafiği bulma hızına eşittir. Deploy anını dikey çizgi olarak metrik grafiğine işleyen bir sistem (Grafana annotations, deploy marker) altın değerindedir: "bozulma çizginin sağında mı solunda mı" sorusunu saniyede yanıtlar. Dağıtık izleme (OpenTelemetry / trace) ile "hangi endpoint, hangi tenant" sorusunu dakikalar yerine saniyelerde çöz. RED metrikleri (Rate, Errors, Duration) her servis için standart olsun.

**Migration araçları ve güvenli varsayılanlar.** Flyway, Liquibase, ya da framework göçleri (Django/Rails migrations). Saha kuralı: migration'lar **ileri-uyumlu** yazılsın, DROP'lar ayrı ve geç deploy'a alınsın. `pt-online-schema-change` / `gh-ost` gibi araçlar büyük tabloda kilit almadan şema değiştirir — dev tablolarda ALTER'ın prod'u dondurmasını engeller.

**Sağlık kontrolü ve otomatik geri alış.** Deploy aracının (Kubernetes, ECS, Argo) sağlık probu (readiness/liveness) doğru ayarlıysa, kötü sürüm zaten trafiğe alınmadan takılır ve otomatik geri döner. Tuzak: probun "port açık mı" gibi yüzeysel bir kontrol yapması; gerçek bağımlılıkları (DB bağlantısı) test etmeyen prob, çökük sürümü sağlıklı sanıp trafik verir.

**Runbook ve olay disiplini.** Her kritik servis için "bu servis bozulursa: rollback komutu şu, kill switch şu bayrak, DB durumunu şöyle kontrol et" diye tek sayfalık runbook. Gece 03:00'te muhakeme değil, prosedür lazımdır. Ve deploy'ları **küçük ve sık** yap: küçük deploy = küçük blast radius = kolay teşhis. On günlük değişikliği tek deploy'da göndermek, olay anında "yüz commit'ten hangisi?" sorusunu çözülemez kılar.

**Son saha kuralı — kişisel deneyimden:** Deploy'a basmadan önce kendine tek cümle sor: *"Bu şimdi ters giderse, elimde çalışan ve prova edilmiş bir geri dönüş var mı?"* Cevap "hayır" ya da "sanırım" ise, deploy'un değil, **deploy'un tasarımının** hazır olmadığını anlarsın. Rollback kararı, o cevabı "evet, prova ettim" yaptığın anda çoktan kazanılmıştır.
