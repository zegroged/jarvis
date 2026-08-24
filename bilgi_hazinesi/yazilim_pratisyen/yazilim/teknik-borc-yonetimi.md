# Teknik Borç Yönetimi: Sahadan Yargı

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Teknik borç, bugün "hızlı" gitmek için verdiğimiz kararların yarın faiziyle geri dönmesidir. Metafor Ward Cunningham'a ait ve orijinal hâli çoğu insanın sandığından farklı: Cunningham teknik borcu "kötü kod" olarak değil, "kodun, problem alanı hakkındaki mevcut anlayışımızı yansıtmaması" olarak tanımladı. Yani borç mutlaka özensizlik değildir; çoğu zaman bir zamanlar doğru olan bir modelin, dünya değiştikçe yanlışa dönmesidir. Bu ayrım kritik, çünkü "borcu temizleyelim" dediğinizde neyi temizlediğinizi bilmezseniz yanlış yeri kazarsınız.

Sahada teknik borç yönetimi şu soruyu cevaplar: **Sınırlı mühendislik zamanını, yeni özellik ile mevcut sistemin bakımı arasında nasıl bölüştürürüm ki, altı ay sonra takım hızı çökmemiş olsun?** Bu bir muhasebe değil, bir yargı problemidir. Çünkü teknik borcun büyük kısmı görünmezdir: derleme geçer, testler yeşildir, ürün çalışır. Borç kendini ancak *değişiklik anında* gösterir. Basit bir özelliğin üç haftaya yayılması, herkesin "o dosyaya dokunmak istemiyorum" demesi, yeni gelenin altı ay sonra hâlâ korkarak commit atması: borcun faturası budur.

Bu iş ne zaman devreye girer? Sürekli. Ama yanlış zamanlar var: Startup'ın ilk product-market-fit arayışında teknik borç yönetimine kafa yormak çoğu zaman erken optimizasyondur; çünkü belki o kodun tamamı altı ay sonra çöpe gidecek. Öte yandan ölçeklenen, çok takımlı, uzun ömürlü bir üründe borcu görmezden gelmek intihardır. Yargının ilk katmanı zaten burası: **borcu ödemenin de bir maliyeti var, ve her borç ödenmeye değmez.**

## 2. Metodoloji ve karar ağacı: pro adım adım nasıl ilerler

### Önce sınıflandırma: her "kötü kod" borç değildir

Kıdemli mühendisin kafasındaki ilk ayrım, Fowler'ın borç çeyreğidir ama sahada ben bunu üç eksene indirgerim:

**Kasıtlı mı, kazara mı?** Kasıtlı borç bilinçli bir takas: "Bu lansmanı yetiştirmek için şimdilik cache katmanı koymuyorum, tek DB'ye vuruyoruz, Q3'te ayırırız." Bu meşrudur, hatta iyi mühendisliktir — *kaydedildiği* sürece. Kazara borç ise öğrenmeden doğar: o zaman bilmiyordunuz, şimdi biliyorsunuz. Bu ikisi farklı muamele ister. Kasıtlı borcun bir sahibi ve bir geri ödeme niyeti vardır; kazara borç ise refactoring sırasında keşfedilir.

**Yerel mi, yayılmış mı?** Tek bir sınıfın içine hapsedilmiş çirkin kod ile, tüm kod tabanına sızmış yanlış bir soyutlama çok farklıdır. Yerel borç ucuzdur: kimse görmez, değiştirmesi kolaydır, faizi düşüktür. En tehlikeli borç, *herkesin her gün dokunduğu* koddaki borçtur. Ben buna "sıcak nokta borcu" derim.

**Faiz oranı yüksek mi, düşük mü?** Bu en önemli eksen. Bir borcun faizi = o borç yüzünden her değişikliğin ne kadar yavaşladığı × o koda ne sıklıkla dokunulduğu. Mükemmel yazılmış ama iki yılda bir dokunulan bir modüldeki borç, faizi sıfıra yakın olduğu için pratikte önemsizdir. **"Çirkin ama stabil" kodu rahat bırakın.**

### Karar ağacı: "şu belirtiyi görünce şu yöne giderim"

Bir borç adayı önüme geldiğinde zihinsel akışım şu:

**Belirti: "Bu dosyaya herkes dokunmaktan korkuyor."** → Sıcak nokta + yüksek faiz. Öncelik listemin en tepesi. Git geçmişine bakarım (aşağıda anlatacağım `git log` heat analizi), bu dosya gerçekten sık mı değişiyor diye. Sık değişiyorsa ve her değişiklik acı veriyorsa, buraya yatırım en yüksek getiriyi verir.

**Belirti: "Bu kod çirkin ama üç aydır kimse dokunmadı."** → Yerel + düşük faiz. Dokunmam. Refactoring için harcanacak her saat, aslında ödemeyeceğim bir faize karşı yapılmış gereksiz bir masraf. Acemi buraya saldırır çünkü "temiz" görünmek ister; pro burayı geçer.

**Belirti: "Yeni özellik X'i eklemek için önce Y'yi düzeltmemiz lazım."** → Fırsatçı refactoring. Altın standart. Borcu, zaten o bölgeye gireceğim bir iş bahanesiyle, o işin bir parçası olarak öderim. Ayrı bir "refactoring sprinti" istemem — onlar neredeyse her zaman iş değeri kanıtlanamadığı için kesilir.

**Belirti: "Prodüksiyonda ayda üç kez bu yüzden alarm çalıyor."** → Bu borç değil, bu bir olay (incident). Faizi somut para ve uyku. Hemen sıraya girer, çünkü ölçülebilir bir zararı var ve bu zararı yönetime göstermek kolaydır.

**Belirti: "Mimarimiz yanlış, her şeyi baştan yazmalıyız."** → Dur. Bu "büyük yeniden yazım" (big rewrite) tuzağıdır ve neredeyse her zaman yanlış cevaptır. Joel Spolsky'nin ünlü tespiti hâlâ geçerli: baştan yazma kararı bir şirketin yapabileceği en tehlikeli stratejik hatadır, çünkü mevcut kodda gömülü olan yılların bug fix'lerini — yani öğrenilmiş bilgiyi — çöpe atarsınız. Cevap neredeyse her zaman *kademeli* dönüşümdür (strangler fig deseni, aşağıda).

### Takaslar ve önceliklendirme mantığı

Pro, borcu bir liste olarak değil, bir *bütçe* olarak yönetir. Sabit bir kural: takımın kapasitesinin belli bir yüzdesini (tipik olarak %15-20) sürekli borç ödemeye ayır. Bu, izin istemeyi bir müzakere olmaktan çıkarır ve bir rutine dönüştürür. Bu bütçeyi de faiz oranına göre harcarsın: en çok acıtan, en sık dokunulan yerlerden başlarsın.

Önceliklendirmede benim kullandığım pratik formül şudur: **etki × sıklık ÷ ödeme maliyeti**. Etki: her karşılaşmada ne kadar yavaşlatıyor. Sıklık: ne kadar sık karşılaşıyoruz. Ödeme maliyeti: düzeltmek ne kadar sürer ve ne kadar risklidir. Bu üçlü, çirkin ama stabil kodu (sıklık düşük) otomatik olarak dibe atar, sıcak noktaları tepeye çıkarır.

Bir başka pratik yargı: **borcun türü, ödeme stratejisini belirler.** Ben sahada dört tür ayırırım ve her birine farklı davranırım:

- **Kod-içi borç** (yapısal karmaşa, tekrar, kötü isimler): En ucuz ödenen tür. Fırsatçı, kademeli, işe gömülü olarak ödenir. Aciliyet nadiren vardır.
- **Mimari borç** (yanlış sınırlar, yanlış bağımlılık yönü, sızdıran soyutlamalar): En pahalı ve en tehlikeli tür. Ödemesi aylar sürer, "strangler" gerektirir, tek bir PR'a sığmaz. Bunu erken tespit etmek kritiktir çünkü faizi bileşiktir — yanlış mimarinin üstüne inşa ettiğiniz her özellik borcu büyütür.
- **Test borcu** (kapsam yok, kırılgan testler, yavaş test süiti): Sinsi çünkü görünmez. Faizi, her değişikliğin "acaba bir şey bozdum mu" korkusuyla yavaşlamasıdır. Yavaş test süiti ise bileşik faiz: her mühendis her gün onlarca kez bekler.
- **Bağımlılık/altyapı borcu** (eski framework sürümü, desteği biten kütüphane, eski runtime): Bu borcun faizi belli bir güne kadar sıfırdır, sonra aniden sonsuza fırlar — güvenlik açığı çıktığında veya sürüm desteği bittiğinde. Bunu "bir gün patlayacak bomba" olarak izlerim; düzenli, küçük yükseltmelerle ödenir. İki büyük sürüm geride kalmışsanız, geri dönüş neredeyse imkânsızlaşır.

Bir de zamanlama yargısı var: **borcu ne zaman ödemem gerektiği kadar, ne zaman ödememem gerektiği de önemli.** Ürünün geleceği belirsizse (deneysel özellik, pazar testi), o bölgedeki borcu ödemem — çünkü belki tüm kod silinecek. Deadline'a iki gün kala kritik yola dokunmam — refactoring risktir, yanlış zamanda alınan risk aptallıktır. Ekipte o bölgeyi bilen tek kişi izindeyse, dönene kadar beklerim. Yargı, çoğu zaman "ne yapacağım" değil, "ne zaman yapacağım"dır.

## 3. Gerçek kod üzerinden yürüyüş: zafiyet → teşhis → düzeltme

Somut bir senaryo. Bir e-ticaret sisteminde sipariş işleme kodu. Zamanla büyümüş, klasik bir borç örneği. Dil-bağımsız anlatacağım ama gerçek bir kod:

### Zafiyetli hâl

```
function processOrder(order) {
  // 3 yıl boyunca eklenen if'ler
  if (order.type == "standard") {
    applyTax(order);
    if (order.country == "DE") { order.tax = order.tax * 1.19; }
    else if (order.country == "TR") { order.tax = order.tax * 1.20; }
    else if (order.country == "US") { /* eyalet bazlı, aşağıda */ 
      if (order.state == "CA") order.tax = order.subtotal * 0.0725;
      // ... 20 eyalet daha
    }
    charge(order.card, order.total);
    sendEmail(order.email);
    updateInventory(order.items);
  } else if (order.type == "subscription") {
    // standard'ın %80'i kopyalanmış, ufak farklarla
    applyTax(order);
    if (order.country == "DE") { order.tax = order.tax * 1.19; }
    // ... aynı vergi bloğu TEKRAR
    scheduleNextCharge(order);
    charge(order.card, order.total);
    sendEmail(order.email);
  } else if (order.type == "gift") {
    // yine kopyala-yapıştır, ama email farklı
    ...
  }
}
```

Bu koda bakan acemi "çirkin, hepsini strategy pattern'e çevireyim" der. Pro önce **teşhis** yapar.

### Teşhis: gerçekte ne acıtıyor?

Ben bu koda dokunmadan önce üç soru sorarım:

1. **Bu fonksiyon ne sıklıkla değişiyor?** `git log --oneline -- orders.js | wc -l` → son bir yılda 47 commit. Bu sıcak bir dosya. Faiz yüksek.

2. **Değişiklikler nerede yoğunlaşıyor?** Commit mesajlarına bakarım: 47 commit'in 31'i vergi mantığıyla ilgili. "add tax for state X", "fix VAT calculation", "hotfix wrong tax". İşte gerçek borç burada — sipariş tiplerinde değil, **vergi hesabının üç ayrı yere kopyalanmış olmasında.** Her yeni vergi kuralı üç yere birden eklenmek zorunda, biri unutuluyor, prodüksiyonda yanlış vergi kesiliyor.

3. **En son bug nerede çıktı?** Incident kaydına bakarım: geçen ay abonelik siparişlerinde CA eyalet vergisi eksik hesaplandı, çünkü standard'a eklenen eyalet mantığı subscription bloğuna kopyalanmamıştı. İşte kanıtlanmış, paralı bir zarar.

Teşhis net: sorun "büyük if-else" estetiği değil, **vergi mantığının tekrarı** (DRY ihlali) ve bunun ürettiği *tutarsızlık* riski. Ödemeyi buraya odaklarım. Sipariş tipi if-else'i çirkin ama tek bir kişinin tek bir yerde okuyabildiği, aslında düşük faizli bir borç — ona şimdilik dokunmam.

### Düzeltilmiş hâl (odaklı, minimal)

```
// Vergi mantığını TEK yere çıkardım. Tek doğruluk kaynağı.
function calculateTax(order) {
  const rate = TAX_RULES[order.country]?.(order) ?? 0;
  return order.subtotal * rate;
}

// TAX_RULES ayrı, test edilebilir, veri gibi:
const TAX_RULES = {
  DE: () => 0.19,
  TR: () => 0.20,
  US: (order) => US_STATE_RATES[order.state] ?? 0,
};

// processOrder artık vergiyi tek yerden çağırıyor:
function processOrder(order) {
  order.tax = calculateTax(order);   // artık üç yerde değil, bir yerde
  // sipariş tipi if-else'i ŞİMDİLİK OLDUĞU GİBİ KALDI
  if (order.type == "standard") { charge(...); sendEmail(...); updateInventory(...); }
  else if (order.type == "subscription") { scheduleNextCharge(order); charge(...); sendEmail(...); }
  ...
}
```

Dikkat edin: **her şeyi düzeltmedim.** Sipariş tipi dallanmasını olduğu gibi bıraktım. Çünkü teşhis, acının vergide olduğunu söylüyordu. Vergiyi tek doğruluk kaynağına çektim; artık yeni bir eyalet vergisi tek satırda ekleniyor, üç yerde değil. Tutarsızlık riski yok oldu. Bu, "cerrahi" refactoring'dir: en çok kanayan damarı dikersin, tüm hastayı yeniden inşa etmezsin.

Kritik nokta: bu değişikliği yapmadan önce **karakterizasyon testleri** yazdım. Mevcut vergi çıktısını 50 gerçek sipariş için kaydettim (golden master), refactoring sonrası aynı çıktının geldiğini doğruladım. Test olmadan bu kodu refactor etmek, gözü kapalı ameliyattır — Michael Feathers'ın "Legacy Code" kitabındaki temel kural: davranışı kilitleyen test olmadan refactor edilmez.

## 4. Acemi vs pro: tuzaklar ve gözden kaçanlar

**Acemi her çirkinliği borç sanır.** Uzun fonksiyon, tuhaf isim, eski desen — hepsini "temizlemek" ister. Pro bilir ki estetik ≠ borç. Faizi olmayan çirkinlik borç değildir. Bir kod tabanının %40'ı çirkin olabilir ve tamamen sağlıklı olabilir, çünkü o %40'a kimse dokunmuyor.

**Acemi "büyük yeniden yazım"a âşıktır.** "Bu kadar kötü kodla uğraşacağıma sıfırdan yazarım" — bu cümle bir startup mezarlığının kapı yazısıdır. Pro bilir: mevcut kod çirkin olabilir ama içinde binlerce edge-case'in çözümü gömülüdür. Yeniden yazdığınızda o edge-case'leri tek tek yeniden keşfedersiniz, prodüksiyonda, müşteri üzerinde. Netscape 6, tam da bunu yaparak pazar liderliğini kaybetti. Pro yeniden yazmaz, *boğar* (strangler fig): yeni sistemi eskinin etrafında büyütür, trafiği parça parça yeni tarafa kaydırır, eski kod doğal ölümle gider.

**Acemi refactoring ile davranış değişikliğini karıştırır.** "Madem buraya girdim, şu bug'ı da düzelteyim, şu davranışı da iyileştireyim." Hayır. Refactoring, davranışı DEĞİŞTİRMEDEN yapıyı iyileştirmektir. İkisini aynı commit'te karıştırırsanız, bir şey bozulduğunda refactoring mi yoksa davranış değişikliği mi kırdı ayırt edemezsiniz. Pro'nun kuralı: **"İki şapka."** Ya refactoring şapkası (yapı değişir, davranış sabit), ya feature şapkası (davranış değişir). Aynı anda ikisi takılmaz.

**Acemi "büyük patlama" refactoring PR'ı açar.** 4000 satır değişen, 60 dosyaya dokunan bir PR. Kimse review edemez, merge edilemez, main'den günlerce ayrı kalır, çakışmalarda boğulur ve sonunda terk edilir. Pro küçük, güvenli, birbirinin üstüne binen adımlarla ilerler; her adım kendi başına merge edilebilir ve sistemi asla bozuk bırakmaz.

**En sinsi tuzak: "ise yarar gibi görünüp üretimde patlayan" erken soyutlama.** Acemi tekrarı görünce hemen soyutlar (DRY dogması). Ama iki kod bloğu *bugün* aynı görünüyor diye *yarın* aynı sebeple değişecek demek değildir. Sandi Metz'in ünlü sözü sahada altındır: **"yanlış soyutlama, tekrardan daha pahalıdır."** Yanlış soyutlamayı geri almak, tekrarı ortadan kaldırmaktan çok daha zordur, çünkü artık her yerden çağrılıyordur. Pro tekrarı hemen öldürmez; üçüncü tekrarı bekler (rule of three), ve tekrarın *tesadüfi* mi yoksa *özsel* mi olduğunu sorar. İki fatura hesabı bugün aynı formülü kullanıyor olabilir ama biri KDV biri stopaj mantığıysa, birleştirmek felakettir.

**Gözden kaçan: borcun sosyal boyutu.** Teknik borç sadece kodda değil, kafalardadır. "Bu sistemi sadece Ahmet biliyor" bir borçtur — bus factor borcu. Ahmet ayrılınca faizi ödersiniz. Pro bunu dokümantasyon, çift programlama ve bilgi yayımıyla yönetir; sadece kodu değil, *kim neyi biliyor*u da izler.

**Acemi borcu "bir gün" öderim diye erteler; pro bilir ki "bir gün" gelmez.** "Şimdi hızlı yapalım, sonra düzeltiriz" cümlesindeki "sonra" istatistiksel olarak asla gelmez, çünkü o zaman geldiğinde yeni bir deadline vardır. Bu yüzden pro, ödeme niyetini bir *mekanizmaya* bağlar: ya kasıtlı borcu bir bilete + tarihe + sahibe bağlar, ya da hiç almaz. Sahipsiz ve tarihsiz "sonra düzeltiriz" borcu, kalıcı borçtur.

**Acemi tüm testleri yeşil tutmak için testi değiştirir; pro kodun mu testin mi haklı olduğunu sorar.** Legacy sistemde bir test kırıldığında acemi refleksi testi "düzeltmektir" (beklenen değeri yeni çıktıya eşitlemek). Bu, karakterizasyon testinin tüm değerini yok eder — çünkü belki de o test, sizin farkında olmadan bozduğunuz gerçek bir davranışı yakaladı. Pro önce "bu değişiklik kasıtlı mıydı?" diye sorar, sonra testi değiştirir.

**Gözden kaçan: refactoring'in de bir bitiş çizgisi olması gerekir.** Acemi ya hiç refactor etmez, ya da başlayınca duramaz — "şunu da düzelteyim, buraya da bakayım" derken üç günlük iş üç haftaya yayılır ve yarısı bitmemiş bırakılır. Pro her refactoring'e girmeden önce "başarı neye benziyor, ne zaman duracağım" tanımını yapar. Kapsamı önceden çizmeyen refactoring, biten değil terk edilen bir iştir.

## 5. Araçlar ve saha notları

**Git tarihi, en ucuz ve en değerli borç radarıdır.** Hiçbir statik analiz aracı, "bu dosya hem sık değişiyor hem karmaşık" bilgisini `git log` kadar dürüst veremez. Adam Tornhill'in "behavioral code analysis" yaklaşımı burada altın: değişiklik sıklığı (churn) ile karmaşıklığı çaprazlarsın. Yüksek churn + yüksek karmaşıklık = borcun kalbi. `CodeScene` bu analizi otomatik yapan bir araçtır ama elle de yapabilirsiniz: `git log --format=format: --name-only | sort | uniq -c | sort -rg` size en sık değişen dosyaları verir. Bu listenin tepesindeki karmaşık dosyalar, refactoring bütçenizin gideceği yerdir.

**Statik analiz araçları (SonarQube, linterlar) borç *sayar* ama *önceliklendirmez*.** SonarQube size "1.240 kod kokusu, 18 gün teknik borç" der. Bu sayı çöptür — çünkü o 1.240 kokunun çoğu, kimsenin dokunmadığı ölü kodda. Aracı kullanın ama çıktısını git-churn ile filtreleyin: sadece sıcak dosyalardaki uyarılara bakın. Aracın "teknik borç: 18 gün" tahminine yönetime rapor diye asla güvenmeyin; o sayı mühendislik dışı bir kitleye yanlış bir kesinlik hissi verir.

**Karakterizasyon/golden-master testleri, güvenli refactoring'in ön koşuludur.** Test kapsamı olmayan legacy koda dokunmadan önce, mevcut davranışı kilitleyen testler yazın — kod "doğru" olduğu için değil, *mevcut* olduğu için. `approvaltests` gibi kütüphaneler golden-master yaklaşımını kolaylaştırır: çıktıyı bir kez kaydeder, sonraki her çalıştırmada karşılaştırır.

**Feature flag / branch by abstraction, büyük dönüşümlerin can simididir.** Bir modülü değiştirirken eski ve yeni implementasyonu yan yana koyup trafiği flag ile yönetirsiniz. Yeni yol %1 trafikle başlar, metrikler iyiyse %100'e çıkar, kötüyse anında geri alınır — deploy beklemeden. Bu, "strangler fig" desenini prodüksiyonda güvenli kılan tekniktir.

**Observability, borcun faizini *ölçülebilir* kılar.** "Bu kod yavaş" bir histir; "bu endpoint p99'da 2.3 saniye ve ayda 40.000 kez çağrılıyor" bir argümandır. Profiler (CPU/allocation profilleri), dağıtık izleme (tracing), ve metrikler borcu somut paraya çevirir. Yönetime "kod çirkin" diyemezsiniz ama "bu borç yüzünden her deploy 40 dakika sürüyor ve ayda 12 saat mühendis zamanı yakıyoruz" diyebilirsiniz. Borcu iş diline çevirmek, pro'nun en önemli becerisidir.

**Pratik saha notları:**

- **Boy Scout Kuralı'nı** ölçülü uygulayın: "kampı bulduğundan temiz bırak" iyidir, ama her dokunduğunuz dosyayı yeniden yazmak PR'ları şişirir ve review'ı öldürür. Kural şu olmalı: dokunduğun *satırların etrafını* iyileştir, tüm dosyayı değil.
- **Borcu görünür kılın ama ürün backlog'una gömmeyin.** Teknik borç ürün özellikleriyle aynı listede yarışırsa her zaman kaybeder, çünkü iş değeri anlatması zordur. Ayrı bir "mühendislik sağlığı" bütçesi ve düzenli bir gözden geçirme rutini kurun.
- **Kasıtlı borcu YAZILI kaydedin.** Kodun içine `// KASITLI BORÇ: cache yok, tek DB. Sahip: X. Koşul: >1000 rps olunca ayır. Tarih: 2026-03.` gibi bir not, o borcun neden var olduğunu ve ne zaman ödeneceğini gelecekteki size anlatır. Kaydedilmemiş kasıtlı borç, altı ay sonra "kim yaptı bunu?" diye lanetlenen kazara borca dönüşür.
- **"Refactoring haftası" antipattern'inden kaçının.** Biriktirilmiş borcu tek seferde ödemeye çalışan özel sprintler genellikle hüsranla biter: iş değeri kanıtlanamaz, yarıda kesilir, moral bozulur. Sürekli, küçük, işe gömülü ödeme her zaman kazanır.
- **Metriklere körü körüne bağlanmayın.** "Test coverage %80 olsun" gibi bir hedef, ekibi anlamsız testler yazmaya iter (Goodhart yasası: bir ölçüt hedef olunca ölçüt olmaktan çıkar). Kapsamın *nerede* olduğu, yüzdesinden önemlidir.

### Kapanış yargısı

Teknik borç yönetiminin özü, kodu mükemmelleştirmek değil, **değişim maliyetini yönetilebilir tutmaktır.** Kıdemli mühendis borcu bir düşman değil, bir araç olarak görür: doğru zamanda alınan, kaydedilen, faizine göre önceliklendirilen ve sık dokunulan yerlerde cerrahi olarak ödenen bir kaldıraç. En büyük hata borç almak değil, aldığını unutmak ve faizini görmezden gelmektir. İkinci en büyük hata ise, faizi olmayan borcu ödemek için gerçek işten çalınan zamandır. İkisinin arasındaki dengeyi kurmak — işte pro'yu acemiden ayıran yargı budur.
