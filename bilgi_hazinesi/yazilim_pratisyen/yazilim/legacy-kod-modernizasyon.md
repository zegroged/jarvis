# Legacy Kod Modernizasyonu

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Legacy kod, "kötü yazılmış kod" demek değildir. Legacy kod, **hâlâ para kazandıran ama artık kimsenin güvenle değiştiremediği** koddur. Aradaki fark kritik: kötü yazılmış kod terk edilir, legacy kod terk edilemez çünkü şirketin faturalama motoru, sipariş akışı ya da 12 yıllık müşteri geçmişi onun içindedir. Michael Feathers'ın tanımı hâlâ en dürüstüdür: legacy kod, **testi olmayan** koddur. Test yoksa değiştirdiğinde ne kırdığını bilemezsin; bilemediğin için dokunmazsın; dokunmadığın için çürür.

Modernizasyon işi şu belirtiler ortaya çıktığında devreye girer:

- Küçük bir değişiklik (bir alan ekle, bir vergi oranı değiştir) haftalar sürüyor ve her seferinde alakasız bir yer patlıyor.
- Sistemi bilen tek kişi emekli oldu / istifa etti, kod "kutsal bilgi" hâline geldi.
- Kullanılan dil/framework/veritabanı sürümü artık güvenlik yaması almıyor (örn. desteği bitmiş bir runtime, EOL olmuş bir veritabanı).
- Yeni özellik eklemenin maliyeti, özelliğin getirdiği gelirden yüksek. Yani sistem ekonomik olarak sürünüyor.
- İşe alım kanıyor: kimse o teknolojiyle çalışmak istemiyor.

Bu işin **çözmediği** şeyi de baştan söyleyelim: modernizasyon bir "estetik" projesi değildir. Kodu güzelleştirmek iş değeri üretmez. Modernizasyon, **değişim maliyetini düşürme** ve **risk azaltma** projesidir. Bu çerçeveyi kaybedersen, altı ay sonra yönetime "para ve zaman harcadık, kullanıcı hiçbir fark görmedi" demek zorunda kalırsın ve proje ortada kesilir. Sahada en çok gördüğüm başarısızlık türü budur: teknik olarak doğru, ekonomik olarak savunulamaz modernizasyon.

## 2. Metodoloji ve karar ağacı (asıl değer)

### 2.1 Önce karar: yeniden yazmak mı, dönüştürmek mi?

Acemi ve pro arasındaki ilk çatal burada ayrışır. Acemi kodu açar, iğrenir, "bunu baştan yazmak daha hızlı" der. Bu neredeyse her zaman yanlıştır. Joel Spolsky'nin yıllar önce yazdığı şey hâlâ geçerli: baştan yazmak, **yıllara yayılmış binlerce hata düzeltmesini çöpe atmaktır.** O çirkin `if` bloğu genelde birinin gece 3'te canlıda bulduğu bir uç durumun izidir. Silersen o hatayı geri getirirsin.

Pro'nun karar ağacı şöyle işler:

**Big-bang rewrite'ı ne zaman seçerim?** Neredeyse hiç. Sadece şu koşulların hepsi varsa: sistem küçük (birkaç haftada kavranabilir), iş mantığı basit ve iyi anlaşılmış, ve mevcut sistemin dondurulması (yeni özellik gelmemesi) iş açısından kabul edilebilir. Bu üç koşul aynı anda nadiren sağlanır. Netflix, Amazon, hemen her büyük ölçekli şirket big-bang yerine **kademeli dönüşüm** (incremental strangler) seçer, çünkü büyük yeniden yazımların meşhur özelliği canlıya hiç çıkamadan iptal edilmeleridir.

**Strangler Fig (Boğan İncir) pattern'i** varsayılan stratejidir: yeni sistemi eski sistemin **etrafına** örersin, trafiği parça parça yeni tarafa kaydırırsın, eski parça kullanılmaz hâle gelince keser atarsın. İsim gerçek bir bitkiden gelir: incir ağacı ev sahibi ağacın etrafını sarar, sonunda içerideki ağaç çürür ama yapı ayakta kalır.

### 2.2 İlk 30 gün: dokunmadan önce anlamak ve emniyet ağı kurmak

Pro modernizasyona **kod yazarak başlamaz.** Sırayla şu adımları atarım:

**Adım 1 — Karakterizasyon (davranışı dondur).** Sistemin *ne yaptığını* değil, *gerçekte ne yaptığını* öğrenirim. Bunlar farklı şeylerdir. Dokümantasyon yalan söyler, kod söylemez. Feathers'ın "characterization test" tekniği: sistemi mevcut çıktısına karşı test yazarım — doğru olduğunu düşündüğüm çıktıya değil, **şu an ürettiği** çıktıya. Örneğin fonksiyona bir girdi veririm, çıktının ne olduğunu bilmiyorum, teste `assertEquals(???, sonuc)` yazıp çalıştırırım, testin bana verdiği gerçek değeri assertion'a koyarım. Böylece "bu sistem bugün şöyle davranıyor" diye kilitlerim. Amaç doğruluk değil, **mevcut davranışı çivilemek.** Modernizasyon sırasında bu testler kırmızıya dönerse, bir davranışı yanlışlıkla değiştirdim demektir.

**Adım 2 — Kaynak koddan bağımlılık haritası.** Hangi modül neye bağlı, veritabanına kim yazıyor, dış dünyaya hangi entegrasyonlar var. En tehlikeli şey görünmeyen bağımlılıklardır: paylaşılan bir veritabanı tablosu, bir cron job, başka bir ekibin doğrudan senin tablonu okuduğu bir rapor. Bunları haritalamadan bir şeyi "keserim" dersen, üç hafta sonra muhasebe departmanı raporunun boş geldiğini söyler.

**Adım 3 — Değişim sıcak noktalarını bul.** Git geçmişinden hangi dosyaların en sık değiştiğini çıkarırım (`git log` üzerinden değişiklik frekansı) ve bunu karmaşıklıkla çaprazlarım. **En sık değişen + en karmaşık** dosyalar modernizasyonun başlangıç noktasıdır. Hiç değişmeyen çirkin koda dokunmam — çirkin ama stabil, iş değeri üretmez. Adam Tornhill'in "hotspot analizi" dediği şey budur ve sahada altın değerindedir: 500 bin satırlık bir sistemde genelde acının %80'i dosyaların %5'inden gelir.

### 2.3 Kesme sırası: takaslar

Sırayı belirlerken üç eksende düşünürüm:

- **Risk vs. değer:** Yüksek değer + düşük risk olanı önce alırım (hızlı kazanç, momentum, yönetime gösterilecek sonuç).
- **Bağımlılık yönü:** Yaprak modüllerden (başka şeye bağımlı olmayan) başlarım, kök modüllere doğru ilerlerim. Kalbe önce dokunursan tüm sistemi aynı anda oynatmak zorunda kalırsın.
- **Öğrenme:** İlk dilimi bilerek küçük ve "sıkıcı" seçerim. Amaç kod değil, **süreci** test etmek: deploy hattı, geri alma (rollback), gözlemlenebilirlik, çift-yazma (dual-write) mekanizması gerçekten çalışıyor mu?

Kritik prensip: **her adım kendi başına canlıya çıkabilmeli ve geri alınabilmeli.** Altı ay dallanıp (branch) sonra "büyük birleştirme" yapmak, big-bang rewrite'ın kılık değiştirmiş hâlidir ve aynı şekilde ölür.

## 3. Gerçek senaryo üzerinden yürüyüş

Somut bir örnek alalım. 14 yıllık bir e-ticaret sisteminde **sipariş fiyat hesaplama** modülü. Tek bir dev fonksiyon, 800 satır, indirimler + kupon + vergi + kargo + sadakat puanı hepsi iç içe. Her Black Friday öncesi buraya dokunmak zorundalar ve her yıl bir şey patlıyor. Klasik legacy sıcak noktası.

### Başlangıç: zafiyetli / kırılgan hâl

Sözde-kod (dilden bağımsız, ama gerçek bir yapı):

```
function siparisFiyatiHesapla(siparis) {
    toplam = 0
    for (kalem in siparis.kalemler) {
        toplam += kalem.fiyat * kalem.adet
    }
    // indirim
    if (siparis.musteri.tip == "VIP") {
        toplam = toplam * 0.9
    } else if (siparis.musteri.tip == "yeni" 
               && bugun < siparis.musteri.kayitTarihi + 30gun) {
        toplam = toplam * 0.95
    }
    // kupon
    if (siparis.kupon != null) {
        kupon = veritabani.kuponGetir(siparis.kupon)   // <-- DİKKAT
        if (kupon != null && kupon.gecerli) {
            toplam = toplam - kupon.tutar
        }
    }
    // vergi
    toplam = toplam * 1.18                              // <-- DİKKAT
    // kargo
    if (toplam < 150) { toplam += 25 }
    return toplam
}
```

Buradaki hastalıkları teşhis edelim. Bir pro bu koda bakınca hemen şunları görür:

1. **Gizli bağımlılık:** Fonksiyonun içinde `veritabani.kuponGetir()` çağrısı var. Bu fonksiyon "saf" değil; test etmek için veritabanı ayağa kaldırmak gerekir. Bu yüzden kimse test yazmamış. Bu yüzden kimse dokunamıyor. Kısır döngünün kaynağı tam olarak burasıdır.

2. **Sihirli sabit:** `1.18` vergi oranı koda gömülü. KDV %18'den %20'ye çıktığında (Türkiye'de gerçekten oldu) bu satırı bulmak, kaç yerde tekrarlandığını bulmaktan zor. Ve genelde 3 yerde farklı yazılmış olur.

3. **Sıra bağımlılığı gizli:** İndirim mi önce, kupon mu önce, vergi kupondan önce mi sonra mı? İş açısından bunun cevabı çok önemli (vergiyi kupon indiriminden önce mi sonra mı hesaplıyorsun — muhasebe ve yasal olarak fark eder) ama kod bunu sadece "satır sırası" ile ifade ediyor. Kimse kararı bilinçli vermemiş; öylece olmuş.

### Teşhis: önce çivile, sonra oyna

Pro'nun yapmayacağı şey: hemen "temiz mimari" yazmaya girişmek. Yapacağı şey **önce karakterizasyon testi** ile mevcut davranışı dondurmak:

```
test("VIP müşteri, kuponsuz, 200 TL sepet") {
    siparis = kur(kalemler=200TL, tip="VIP", kupon=yok)
    sonuc = siparisFiyatiHesapla(siparis)
    assertEquals(212.40, sonuc)   // bugün gerçekte bunu üretiyor
}
```

Bu 212.40'ın "doğru" olup olmadığı umurumda değil — sistem bugün bunu üretiyor, müşteriler buna göre ödüyor. Ben bunu kilitliyorum. Kupon çağrısını test edilebilir kılmak için ilk cerrahi müdahale **bağımlılığı dışarı çıkarmaktır** (dependency injection):

```
function siparisFiyatiHesapla(siparis, kuponServisi) {   // bağımlılık parametre oldu
    ...
    kupon = kuponServisi.getir(siparis.kupon)
    ...
}
```

Bu değişiklik davranışı değiştirmez ama artık teste sahte (mock/fake) bir kupon servisi verebilirim. Bu Feathers'ın "seam" (dikiş) dediği yerdir: davranışı değiştirmeden araya girebildiğin nokta. Emniyet ağı kurulduktan sonra, ancak o zaman parçalamaya başlarım.

### Düzeltilmiş hâl

```
// Vergi oranı artık dışarıdan, tek kaynaktan
function siparisFiyatiHesapla(siparis, kuponServisi, vergiOrani) {
    araToplam = kalemToplami(siparis.kalemler)
    indirimliTutar = indirimUygula(araToplam, siparis.musteri)
    kuponSonrasi  = kuponUygula(indirimliTutar, siparis.kupon, kuponServisi)
    vergiliTutar  = kuponSonrasi * (1 + vergiOrani)
    return kargoEkle(vergiliTutar)
}
```

Her parça artık ayrı, saf, test edilebilir bir fonksiyon. `indirimUygula` veritabanına gitmiyor, sadece hesaplıyor — yüzlerce durumu milisaniyede test edebilirsin. Vergi oranı tek yerden geliyor. Ve en önemlisi: hesaplama **sırası artık kodda açıkça okunuyor**, gizli değil. Sıra hakkında bir iş kararı vermek gerektiğinde (vergiyi kupondan önce mi?) tartışacak somut bir yer var.

Dikkat: bu yürüyüşte sistemin *davranışını değiştirmedim.* Karakterizasyon testleri hâlâ yeşil — 212.40 hâlâ 212.40. Bir modernizasyon adımının başarı ölçütü budur: **yapı değişti, davranış değişmedi.** Davranışı değiştirmek istediğim an (vergi sırasını düzeltmek gibi) bunu **ayrı bir commit** olarak, bilinçli, iş birimiyle konuşarak yaparım. İki işi karıştırmak — refactor + davranış değişikliği aynı commit'te — sahadaki en pahalı hatadır, çünkü bir şey patladığında hangisinin suçlu olduğunu bilemezsin.

## 4. Acemi vs. pro: tuzaklar

**Tuzak 1 — "Baştan yazalım" refleksi.** Acemi kodu okuyamadığı için kötü sanır. Genelde kod kötü değil, *domain karmaşık.* Baştan yazınca karmaşıklık kaybolmaz, sadece yeni kodda yeniden keşfedilir — bu sefer yıllarca birikmiş uç durum bilgisi olmadan. Pro şunu bilir: **çirkin kod, çözülmüş problemlerin mezar taşıdır.**

**Tuzak 2 — Refactor ile davranış değişikliğini karıştırmak.** Acemi "madem elim değdi, şunu da düzeltirim" der. Sonra bir hata çıkar, 40 dosya değişmiştir, hata refactor'dan mı yoksa "iyileştirmeden" mi belli değildir. Pro'nun demir kuralı: **bir commit ya yapıyı değiştirir ya davranışı, ikisini birden asla.**

**Tuzak 3 — Emniyet ağı olmadan dalmak.** Acemi test yazmayı "zaman kaybı" görür, doğrudan düzeltmeye girer. İlk hafta hızlı görünür, üçüncü hafta canlıda geri dönüşü olmayan bir hata çıkar. Karakterizasyon testleri sıkıcıdır ama modernizasyonun tek gerçek güvenlik kemeridir.

**Tuzak 4 — "Tüm bağımlılıkları aynı anda güncelleyelim."** Runtime + framework + veritabanı + kütüphaneler hepsi birden. Bir şey patlar, hangisinin patlattığını bulmak imkânsızdır. Pro **tek eksende** hareket eder: önce sadece runtime sürümünü yükselt, yeşil, canlı, sonra bir kütüphane, yeşil, canlı. Küçük, tersinir adımlar.

**Tuzak 5 — Kılavuz yıldızı olarak "temiz kod".** Acemi soyutlama katmanları, tasarım desenleri ekler çünkü "doğru" olan budur. Sonuç: eskisinden anlaşılması daha zor, ama farklı biçimde karmaşık bir sistem. Pro sorar: "Bu değişiklik bir sonraki değişikliği ucuzlatıyor mu, yoksa sadece bana estetik tatmin mi veriyor?" Değer üretmeyen soyutlama, borçtur.

**Tuzak 6 — Görünen ama ölü koda dokunmak.** Karmaşık ama hiç değişmeyen bir modül seni cezbeder. Dokunma. Git geçmişi son 2 yılda o dosyaya kimsenin dokunmadığını söylüyorsa, o kod modernizasyon değil, *arkeoloji.* Enerjini sıcak noktalara harca.

**Tuzak 7 — "İşe yarar gibi görünüp üretimde patlayan" klasik: karakter kodlaması, saat dilimi, para birimi hassasiyeti.** Legacy sistemler para hesabını çoğu zaman kayan noktalı sayıyla (float) yapar ve bu yıllarca "çalışır" görünür çünkü kuruş farkları yuvarlanır. Modernizasyonda naifçe aynı yapıyı taşırsan, ölçek büyüdüğünde ya da yeni bir para birimi eklendiğinde birikmiş yuvarlama hataları muhasebeyi tutmaz hâle getirir. Pro para hesabını tam sayı kuruş ya da ondalık (decimal) tiple yapar. Aynı sinsilik tarih/saat diliminde de vardır: "yerel saat" varsayımıyla yazılmış legacy kod, sunucu başka bölgeye taşınınca ya da yaz saati uygulaması değişince sessizce yanlış sonuç üretir.

**Tuzak 8 — İnsan boyutunu unutmak.** Modernizasyon yarı teknik yarı sosyal bir iştir. O sistemi 10 yıldır besleyen kişi tehdit altında hisseder ve bilerek/bilmeyerek bilgiyi paylaşmaz. Bağlamı en çok bilen kişiyi düşman değil ortak yaparsan modernizasyon iki kat hızlanır. Acemi bunu "insan işi" diye küçümser; pro projenin kaderinin çoğunlukla burada belirlendiğini bilir.

## 5. Araçlar ve saha notları

**Sürüm kontrolü / tarih analizi.** Git tek başına en güçlü modernizasyon aracıdır. `git log`'tan dosya değişim frekansı çıkarıp sıcak noktaları bulmak, hangi kodun canlı hangisinin ölü olduğunu görmek, `git blame` ile "bu tuhaf satır ne zaman ve neden geldi" sorusunu commit mesajından yanıtlamak. Değişim frekansı + karmaşıklık çaprazı için `code-maat` gibi analiz araçları ve Adam Tornhill'in "Your Code as a Crime Scene" yaklaşımı sahada gerçekten işe yarar.

**Test ve emniyet ağı.** Karakterizasyon testleri için dilin standart test çatısı yeter (JUnit, pytest, Go test, ne kullanıyorsan). Kaplama (coverage) aracını "kaç satır test edildi" için değil, **"dokunacağım bölge test altında mı"** sorusu için kullan. Yüzde peşinde koşma; değiştireceğin sıcak noktanın %90 kaplı olması, hiç dokunmayacağın modülün %0 olmasından iyidir.

**Yaklaşım testi (approval testing).** Karakterizasyon için özellikle kullanışlı: çıktıyı (JSON, metin, rapor) bir "onaylanmış" dosyaya karşı kıyaslar. Büyük legacy çıktılarını (fatura, rapor) dondurmak için elle assertion yazmaktan çok hızlıdır. `ApprovalTests` ailesi çoğu dilde mevcuttur.

**Profiler ve gözlemlenebilirlik.** Modernizasyondan *önce* ve *sonra* ölç. Acemi "daha temiz, dolayısıyla daha hızlı olmalı" varsayar — çoğu zaman yanlış. Bir profiler (dilin kendi profiler'ı, ya da sürekli profil için Datadog/benzeri) darboğazın gerçekte nerede olduğunu söyler; sezgin neredeyse her zaman yanlış yeri gösterir. Canlıda **dağıtık izleme (distributed tracing)** ve yapılandırılmış loglama olmadan strangler pattern uygulamak körlemesine ameliyattır: trafiği yeni tarafa kaydırdığında yeni yolun eskiyle **aynı sonucu** üretip üretmediğini görmen şart.

**Karşılaştırmalı çalıştırma (parallel run / dual-run).** Sahanın en değerli tekniklerinden. Yeni kodu canlıya alırken eski ve yeni yolu **aynı anda** çalıştırırsın; kullanıcıya eskisinin cevabını dönersin ama yeninin cevabını da hesaplayıp ikisini karşılaştırıp loglarsın. GitHub bunu açık kaynak `Scientist` kütüphanesiyle popülerleştirdi (ve birçok dile taşındı). Günlerce gerçek trafikte "yeni kod eskisiyle aynı sonucu veriyor mu" verisi toplarsın; fark oranı yeterince düşünce güvenle geçiş yaparsın. Bu, "test yeşildi ama canlıda uç durum patladı" korkusunun panzehridir çünkü test veremini gerçek trafik verir.

**Otomatik dönüşüm / codemod.** Mekanik ve tekrarlayan değişiklikler (bir API'nin her çağrısını yenisiyle değiştir, sözdizimi göçü) için elle uğraşma. AST tabanlı codemod araçları (dile göre: `jscodeshift`, `OpenRewrite`, `Rector`, gibi gerçek ve yaygın araçlar) yüzlerce dosyayı tutarlı biçimde dönüştürür. Elle yaparsan hem yorulur hem de %2'sini kaçırırsın; işte o kaçırdığın %2 canlıda seni bulur.

**Feature flag / sürüm bayrağı.** Strangler geçişinde trafiği eskiden yeniye kaydırmayı kodla değil bayrakla yönet. Böylece bir sorun çıkınca **deploy geri almadan**, saniyeler içinde eski yola dönebilirsin. Yüzdeli açılım (önce %1 trafik, sonra %10, sonra %100) canary yaklaşımıyla birleşince modernizasyon riskini dramatik biçimde düşürür.

**Bağımlılık ve güvenlik taraması.** EOL sürümleri ve bilinen açıkları bulmak için bağımlılık tarayıcıları (Dependabot, `npm audit`, OWASP Dependency-Check gibi gerçek araçlar). Legacy sistemlerde en acil modernizasyon nedeni genelde estetik değil, yaması gelmeyen bir güvenlik açığıdır; onu önce görmen gerekir.

### Kapanış saha notu

Modernizasyonda en zor beceri kod yazmak değil, **durmayı bilmektir.** İyi bir kural: her modernizasyon dilimini, iş değeri üreten bir teslimatın (bir özellik, bir hata düzeltmesi) yanına iliştir. "Sadece refactor" projeleri yönetim desteğini kaybeder ve yarıda kalır; yarıda kalmış modernizasyon, iki farklı stil ve iki mimarinin bir arada yaşadığı, başladığından **daha kötü** bir sistem bırakır. Boy Scout kuralı — "kampı bulduğundan daha temiz bırak" — burada altındır: dokunduğun her yeri bir tık iyileştir, ama işini bitirmediğin bir yeri yarım bırakma. Modernizasyon bir maraton değil, sırt sırta koşulan yüzlerce kısa mesafedir; her biri tek başına canlıya çıkabilen, tek başına geri alınabilen, ve iş için gerçekten bir şey ifade eden.
