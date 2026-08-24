# Güvenli Refactoring Pratiği

## 1. Problem ve bağlam: refactoring aslında neyi çözer

Refactoring kelimesi ofislerde çok kirlendi. Çoğu ekipte "refactoring" dendiğinde kastedilen şey aslında yeniden yazma (rewrite), mimari değişiklik ya da özellik eklerken kodu "biraz daha temizlemek" oluyor. Martin Fowler'ın orijinal tanımı çok daha dar ve o darlık kasıtlı: refactoring, **kodun dışarıdan gözlemlenebilen davranışını değiştirmeden iç yapısını iyileştirmektir**. Anahtar cümle "davranışı değiştirmeden". Bir input verdiğinde aynı output'u, aynı yan etkileri, aynı hataları üretmeye devam etmelidir. Bir hata bile düzeltiyorsan, o artık refactoring değil; refactoring + bug fix'tir ve ikisini aynı commit'te karıştırmak sahada başının en çok belaya girdiği yerdir.

Peki bu disiplin neyi çözer? Yazılımın gerçek maliyeti yazıldığı gün değil, sonraki üç yıl boyunca değiştirilirken ortaya çıkar. Kod okunmak için değişir, değişmek için okunur. Zamanla anlaşılması zor, dokunulması riskli hâle gelen kod ekibi yavaşlatır: her yeni özellik daha uzun sürer, her tahmin daha çok kayar, kıdemli geliştiriciler "o modüle dokunmayalım" der. Refactoring bu birikmiş sürtünmeyi -teknik borcu- planlı, küçük, geri alınabilir adımlarla ödemenin yöntemidir. Amaç güzellik değil; **değişim maliyetini düşürmek**. Bu ayrım pratikte kritiktir çünkü "bu kod çirkin" bir refactoring gerekçesi değildir, "bu koda önümüzdeki sprint'te üç yerden dokunacağız ve şu anki hâli buna izin vermiyor" geçerli bir gerekçedir.

Ne zaman devreye girer? Klasik ve hâlâ en sağlam kural Kent Beck'in "önce değişimi kolay hâle getir, sonra kolay değişimi yap" ilkesidir. Yani bir özellik ekleyeceksin, mevcut yapı buna direniyor. Önce yapıyı özelliği kabul edecek şekilde -davranışı bozmadan- düzenlersin (hazırlayıcı refactoring / preparatory refactoring), sonra özelliği eklersin. İkinci devreye girme anı: bir bug'ı ararken kodu anlamakta zorlanıyorsun; anladıkça küçük temizlikler yaparsın (comprehension refactoring). Üçüncüsü: aynı deseni üçüncü kez kopyaladığında ("rule of three") soyutlamayı çıkarırsın. Boş zamanda, "bir cuma öğleden sonrası büyük temizlik" olarak yapılan refactoring ise saha tecrübesiyle söylüyorum, en riskli ve en az değer üreten türdür.

## 2. Metodoloji ve karar ağacı: pro adım adım nasıl ilerler

### Sıfırıncı adım: dokunmadan önce güvenlik ağı var mı?

Kıdemli birinin acemiden en net ayrıldığı yer burasıdır. Acemi editörü açar, "bu isim kötü" der ve değiştirmeye başlar. Pro önce şu soruyu sorar: **"Bu kodun davranışını yanlışlıkla değiştirirsem bunu ne yakalayacak?"** Cevap "hiçbir şey" ise refactoring'e başlamadan önce iş, test yazmaktır. Test yoksa güvenli refactoring diye bir şey yoktur; sadece kör bir yeniden düzenleme ve dua vardır.

Burada karar dallanır:

- **Test var, hızlı ve güvenilir mi?** O zaman doğrudan refactoring'e geç, testler senin ağın.
- **Test yok ama kod test edilebilir mi?** Önce **karakterizasyon testi** (characterization test) yaz. Bunlar kodun *doğru* davranışını değil, *mevcut* davranışını dondurur. Michael Feathers'ın "Legacy Code" yaklaşımıdır: mevcut çıktının doğru olup olmadığını umursamazsın; sadece "şu an ne yapıyorsa aynısını yapmaya devam etsin" garantisini kurarsın. Çirkin bir gerçek: bazen karakterizasyon testi yazarken kodun aslında yanlış olduğunu fark edersin. O bug'ı orada düzeltme; not al, ayrı ele al.
- **Kod test edilemez durumda mı** (her şey birbirine yapışık, global state, dış bağımlılıklar constructor'da new'leniyor)? O zaman en tehlikeli adım burada: test edilebilir hâle getirmek için bile önce biraz dokunman gerekir ama test yok. Feathers'ın "seam" kavramı devreye girer: davranışı değiştirmeden araya girebileceğin en küçük noktayı bulursun (bir metodu extract edip override edilebilir yapmak, bir bağımlılığı parametreye çıkarmak gibi). Bu ilk mikro-adımları IDE'nin otomatik refactoring aracıyla yaparsın çünkü otomatik araç senin elinden daha az hata yapar.

### Birinci adım: kapsamı ve niyeti daralt

Pro, "bu dosyayı temizleyeceğim" demez. "Bu fonksiyonu, üç ayrı sorumluluğu olduğu için üç fonksiyona böleceğim, davranış aynı kalacak" der. Niyet tek cümleyle ifade edilemiyorsa kapsam çok geniştir. Geniş kapsam refactoring'in bir numaralı ölüm sebebidir: iki gün süren, yüzlerce dosyaya yayılan, review edilemeyen, merge conflict cehennemine dönüşen ve sonunda "revert edelim gitsin" denen dev branch'ler hep "şöyle bir baştan temizleyeyim" ile başlar.

### İkinci adım: küçük, geri alınabilir adımlarla ilerle

Asıl yargı burada. Güvenli refactoring'in kalbi **adım büyüklüğüdür**. Doğru büyüklük, "her adımdan sonra testleri çalıştırabileceğim ve yeşil kalıp kalmadığını görebileceğim" büyüklüktür. İyi bir refactoring seansı git log'una bakıldığında onlarca küçük, her biri yeşil, her biri tek başına anlamlı ve revert edilebilir commit gibi görünür. Kötü bir seans tek dev commit'tir: "refactor auth module".

Ritim şudur: küçük değişiklik → testleri çalıştır → yeşil → commit → tekrar. Bu döngü dakikalar sürer. "Testleri en sonda bir kez çalıştırırım" diyen kişi, hata yaptığında son yeşil noktadan bu yana yaptığı her şeyi şüpheli hâle getirir ve hata avı saatler alır. Küçük adımların asıl faydası hızdan değil, **hata lokalizasyonundan** gelir: bir şey kırıldığında suçlu her zaman son adımdır.

### Karar ağacı: hangi belirtiyi görünce nereye giderim

- **"Bir fonksiyon ekranıma sığmıyor"** → Extract Method. Ama körlemesine değil; önce mantıksal blokları bul (genelde yorum satırlarıyla ayrılmışlardır ya da boş satırlarla), her bloğu niyetini anlatan bir isimle metoda çıkar. Yorum yazmak istediğin her yer aslında bir metot çıkarma fırsatıdır.
- **"Aynı kodu üçüncü kez görüyorum"** → soyutlamayı çıkar, ama üçünün *gerçekten* aynı olduğundan emin ol. Yanlışlıkla birbirine benzeyen ama farklı sebeplerle değişecek iki kodu birleştirmek (yanlış DRY) daha sonra çok acı verir.
- **"Bir sınıf her şeyi biliyor, 2000 satır"** → hemen bölmeye çalışma. Önce sorumlulukları isimlendir, birbirine ait alanları ve metotları grupla (bu bile bir refactoring'dir), sonra bir grubu ayrı sınıfa çıkar.
- **"Bir değişiklik yapınca alakasız üç yer bozuluyor"** → bu kötü bir bağımlılık kokusudur, ama refactoring'e mimari değişiklikle başlama. Önce bağımlılıkları görünür kıl.
- **"Kodu anlamıyorum"** → burada refactoring bir *öğrenme aracıdır*. Değişkenleri yeniden adlandır, blokları çıkar, anladıkça kodun sana kendini anlatmasını sağla. Bu "comprehension refactoring" seansının çıktısı bazen sadece anlamandır; hatta bazen değişiklikleri commit bile etmezsin.

### Takaslar

Her refactoring bir bahistir: harcadığın zaman, gelecekteki değişim kolaylığıyla geri dönecek. Eğer o modüle bir daha dokunmayacaksan, ne kadar çirkin olursa olsun, refactoring'in getirisi sıfırdır. Sahada en olgun karar çoğu zaman **"bu kodu şimdilik olduğu gibi bırak"** kararıdır. Çirkin ama stabil, iyi test edilmiş, nadiren değişen kod, güzel ama taze ve riskli koddan iyidir. Bir başka takas: performans. Bazen okunabilirlik için yapılan soyutlama sıcak bir döngüde ölçülebilir yavaşlama getirir; bu durumda önce ölçer, sonra karar verirsin, tahminle değil.

## 3. Gerçek kod üzerinden yürüyüş

Somut bir senaryo alalım: bir e-ticaret sisteminde sipariş toplam tutarını hesaplayan, zamanla büyümüş bir fonksiyon. Dil önemli değil ama gerçek yazacağım; burada JavaScript benzeri bir sözdizimi kullanacağım.

Başlangıç hâli, sahada gerçekten karşılaşacağın türden:

```
function hesapla(o) {
  let t = 0;
  for (let i = 0; i < o.items.length; i++) {
    t += o.items[i].price * o.items[i].qty;
  }
  if (o.customer.type == "vip") {
    t = t - t * 0.1;
  }
  if (t > 500) {
    t = t - 20;
  }
  if (o.country == "TR") {
    t = t + t * 0.18;
  } else {
    t = t + t * 0.20;
  }
  return t;
}
```

Bu fonksiyon "çalışıyor". Ama dört ayrı iş yapıyor: ara toplam, müşteri indirimi, tutar eşiği indirimi, vergi. İsimler kötü (`t`, `o`), sayılar sihirli (`0.1`, `20`, `500`, `0.18`), ve yeni bir indirim kuralı eklemek isteyen kişi bu if yığınına bir dal daha ekleyecek. Klasik "değişime direnç".

**Teşhis:** Long Method + Magic Numbers + belirsiz isimler + tek fonksiyonda birden çok değişim sebebi. Ama teşhisten sonra ilk yapacağım şey düzeltmek değil, **güvenlik ağı kurmak**.

Karakterizasyon testleri -mevcut davranışı donduruyorum, doğruluğunu sorgulamıyorum:

```
test("vip, TR, 600 TL sepet", () => {
  const o = {
    items: [{ price: 300, qty: 2 }],
    customer: { type: "vip" },
    country: "TR",
  };
  // Şu an ne dönüyorsa onu yazıyorum: 600 -> vip -10% = 540 -> >500 -20 = 520 -> +18% = 613.6
  expect(hesapla(o)).toBeCloseTo(613.6);
});

test("normal müşteri, yurtdışı, küçük sepet", () => {
  const o = {
    items: [{ price: 100, qty: 1 }],
    customer: { type: "normal" },
    country: "DE",
  };
  // 100 -> indirim yok -> 500 altı, eşik indirimi yok -> +20% = 120
  expect(hesapla(o)).toBeCloseTo(120);
});
```

Dikkat: bu testleri yazarken indirim vergiden *önce* uygulanıyor fark ettim. Bu doğru mu? Muhasebe açısından tartışmalı. Ama bunu şimdi düzeltmiyorum. Refactoring davranışı korur; test bu davranışı dondurur. Vergi sırasını değiştirmek ayrı bir iş, ayrı bir commit, ürün sahibiyle ayrı bir konuşma.

Şimdi küçük adımlarla ilerliyorum. **Adım 1**, ara toplamı çıkar:

```
function araToplam(items) {
  return items.reduce((toplam, kalem) => toplam + kalem.price * kalem.qty, 0);
}
```

Testleri çalıştır → yeşil → commit. **Adım 2**, sihirli sayıları isimlendir ve indirimleri ayır:

```
const VIP_INDIRIM_ORANI = 0.10;
const YUKSEK_TUTAR_ESIGI = 500;
const YUKSEK_TUTAR_INDIRIMI = 20;
const KDV_ORANI = { TR: 0.18, DIGER: 0.20 };

function musteriIndirimi(tutar, musteri) {
  return musteri.type === "vip" ? tutar * VIP_INDIRIM_ORANI : 0;
}

function tutarEsigiIndirimi(tutar) {
  return tutar > YUKSEK_TUTAR_ESIGI ? YUKSEK_TUTAR_INDIRIMI : 0;
}

function vergi(tutar, ulke) {
  const oran = ulke === "TR" ? KDV_ORANI.TR : KDV_ORANI.DIGER;
  return tutar * oran;
}
```

Testleri çalıştır → yeşil → commit. **Adım 3**, ana fonksiyonu bu parçalardan yeniden kur:

```
function siparisToplami(siparis) {
  let tutar = araToplam(siparis.items);
  tutar -= musteriIndirimi(tutar, siparis.customer);
  tutar -= tutarEsigiIndirimi(tutar);
  tutar += vergi(tutar, siparis.country);
  return tutar;
}
```

Testleri çalıştır → yeşil. Şimdi `siparisToplami` bir "neyi ne sırayla yaptığımızın" hikâyesini okutuyor; her kural kendi test edilebilir fonksiyonunda. Yeni bir indirim eklemek isteyen kişi artık if yığınına dal eklemiyor, yeni bir fonksiyon yazıp zincire bir satır ekliyor.

Kritik detay: eski `hesapla` fonksiyonunu hemen silmiyorum. Önce çağıranları yeni isme taşırım (IDE'nin "inline/rename" aracıyla), her taşımadan sonra test, en son ölü fonksiyonu kaldırırım. Bu "paralel değişim" (parallel change / expand-contract) tekniğidir ve büyük çaplı refactoring'de tek güvenli yoldur: yeniyi eskinin yanına kur, tüketicileri tek tek taşı, sonra eskiyi kaldır.

## 4. Acemi vs pro: tuzaklar ve gözden kaçanlar

**Refactoring ile davranış değişikliğini karıştırmak.** Acemi "madem buradayım, şu bug'ı da düzeltiveririm" der. Sonra test kırılır, kırılan test refactoring hatası mı yoksa bilinçli davranış değişikliği mi anlaşılmaz, saatler kaybolur. Pro'nun kuralı katıdır: **bir commit ya davranışı korur ya davranışı değiştirir, ikisini birden asla yapmaz.** İki farklı şapka -refactoring şapkası ve özellik/bugfix şapkası- ve aynı anda ikisi başında olmaz.

**Test olmadan başlamak.** En yaygın ve en pahalı hata. "Basit bir yeniden adlandırma, ne olacak ki" diye başlanır, o isim bir string olarak reflection'da ya da bir config'de kullanılıyordur, IDE bunu göremez, üretimde patlar. Test yoksa refactoring bir tahmindir.

**IDE'nin otomatik aracı yerine elle değiştirmek.** Rename, Extract Method, Move gibi işlemleri elle yapmak insan hatasına açıktır. Otomatik araç dilin semantiğini bilir, bütün referansları bulur, kapanış/kapsam kurallarına uyar. Pro, otomatik yapılabilecek bir refactoring'i asla elle yapmaz. Elle yapılan "extract" sırasında bir değişkeni parametre olarak taşımayı unutmak klasik bir hatadır.

**"Yanlış DRY" -tesadüfen benzeyen kodu birleştirmek.** Acemi iki benzer kod bloğu görünce hemen birleştirir. Ama bu iki blok farklı iş kurallarını temsil ediyorsa, yarın biri değişince ötekini de yanlışlıkla değiştirmiş olursun ya da birleşik fonksiyona sürekli `if flag` parametreleri eklersin ve o fonksiyon canavara döner. Sandi Metz'in ünlü sözü: "yanlış soyutlama, kod tekrarından pahalıdır." Üç kez kuralı tam da bu yüzden var: iki örnek yanıltıcı olabilir, üçüncüde desen gerçekten görünür.

**Kapsamı büyütmek -"boy scout" bahanesi.** "Kampı bulduğundan temiz bırak" iyi bir ilkedir ama sınırsız uygulanınca beş satırlık bir bugfix, iki yüz satırlık bir refactoring PR'ına dönüşür, review edilemez, gözden geçiren onaylamak zorunda kalır ve gerçek değişiklik gürültünün içinde kaybolur. Pro, davranış değiştiren PR ile temizlik PR'ını ayırır. "Bu satırı düzeltmem için şu üç şeyi de temizlemem lazım" diyorsan, önce temizlik PR'ını ayrı gönder, merge et, sonra asıl işi yap.

**Yeşil testlere güvenip kapsamı görmezden gelmek.** Testler yeşil ama kapsamı %20 ise, yeşil olması yanıltıcı güven verir. Refactoring öncesi kapsamı bilmek gerekir. Özellikle karakterizasyon testi yazarken, dokunacağın kod yollarının test edildiğinden emin ol; kapsanmayan bir dalı refactor edip sessizce bozabilirsin.

**"Üretimde patlayan" en sinsi tür: davranışı koruduğunu sandığın ama korumadığın durumlar.** Kayan nokta (floating point) aritmetiğinde işlem sırasını değiştirmek sonucu son bitte değiştirir. Bir döngüyü map/reduce'a çevirirken kısa devre (short-circuit) davranışını kaybedebilirsin. Lazy bir değerlendirmeyi eager yaparsan yan etkilerin sırası değişir. Null/undefined kenar durumlarında `if (x)` ile `if (x != null)` aynı değildir. Bunlar testlerin zayıfsa yakalayamayacağı, refactoring'i "davranış korundu" sanıp aslında değiştirdiğin tuzaklardır. Bu yüzden kenar durum testleri (boş liste, null, sıfır, negatif, çok büyük değer) refactoring'in gerçek sigortasıdır.

**Concurrency'de refactoring.** Çok kanallı/thread'li kodda "davranış" tek bir thread'in çıktısı değildir; yarış koşullarını (race condition), kilit sıralamasını da içerir. İki satırı yer değiştirmek deterministik testlerde masum görünür, üretimde kilitlenmeye (deadlock) yol açar. Buradaki kural: eşzamanlılık kodunda "masum" refactoring diye bir şey yoktur, her adım ekstra şüpheyle ele alınır.

## 5. Araçlar ve saha notları

**IDE / otomatik refactoring.** Modern IDE'ler (IntelliJ ailesi, VS Code + dil sunucuları, Visual Studio) Rename, Extract Method/Variable/Function, Inline, Move, Change Signature gibi işlemleri semantik olarak güvenli yapar. Statik tipli dillerde (Java, C#, TypeScript, Go, Rust) bu araçlar neredeyse kusursuzdur; derleyici ve tip sistemi arkanı kollar. Dinamik dillerde (Python, JavaScript, Ruby) araç daha az emindir çünkü reflection, monkey-patching, string ile erişim gibi teknikler statik analizi kör eder. Pratik tüyo: dinamik dilde otomatik rename sonrası mutlaka tüm test suite'i ve mümkünse bir grep/arama ile string olarak geçen kullanımları da tara.

**Sürüm kontrolü refactoring'in en önemli aracıdır.** Git burada güvenlik ağının ikinci katmanıdır. Küçük, sık commit'ler; her adım revert edilebilir. `git stash` ile "bir dakika, bu deneme işe yaramadı" durumundan temiz dön. Bir refactoring büyük ve riskliyse ayrı branch. `git bisect`, refactoring sonrası ortaya çıkan bir regresyonu yüzlerce commit içinde ikili aramayla bulmanın en hızlı yoludur -bu yüzden her commit'in kendi başında yeşil olması altın değerindedir; bisect ancak commit'ler atomikse çalışır.

**Test araçları.** Hızlı bir birim test suite'i refactoring'in oksijenidir. Test dakikalarca sürüyorsa "küçük adım → test → tekrar" ritmi ölür, insanlar testleri seyrek çalıştırır, hatalar birikir. Bu yüzden test hızına yatırım, refactoring kabiliyetine yatırımdır. Kapsam ölçüm araçları (coverage) sana dokunacağın kodun test edilip edilmediğini gösterir; ama kapsamı hedef değil, körlük haritası olarak kullan -%100 kapsam kötü testi iyi yapmaz. **Mutation testing** araçları (kodu kasıtlı bozup testlerin yakalayıp yakalamadığına bakar) testlerinin gerçekten güçlü olup olmadığını söyler; refactoring öncesi kritik modülde testlerin sahte güven verip vermediğini anlamanın en dürüst yoludur.

**Statik analiz ve linter'lar.** Karmaşıklık metrikleri (cyclomatic complexity), çok uzun fonksiyonlar, çok parametreli metotlar, tekrar eden bloklar gibi "kod kokularını" otomatik işaretler. Bunları refactoring hedefi *bulmak* için kullan, ama körü körüne uyma; yüksek karmaşıklık bazen sahiden gereklidir. SonarQube gibi araçlar teknik borcu görünür kılar, ama metrik takıntısı -"karmaşıklığı 10'un altına indir"- gerçek değeri değil sayıyı kovalamaya iter.

**Observability ve üretim doğrulaması.** Refactoring "davranışı korumalı" ama en güçlü test suite bile üretimin bütün girdilerini kapsamaz. Riskli, geniş etkili bir refactoring'i üretime çıkarırken **feature flag** arkasına al, yeni ve eski yolu bir süre paralel çalıştır ve çıktılarını karşılaştır (bu tekniğin adı sahada "shadowing" veya GitHub'ın açtığı isimle "scientist" desenidir: eski yolu canlı tut, yeniyi de çalıştır, sonuçları logla, ama kullanıcıya hâlâ eskinin cevabını dön). Farklar loglanır, güven oluşunca yeni yola geçilir. Metrikler (hata oranı, gecikme, iş metrikleri) refactoring öncesi ve sonrası karşılaştırılır. "Test yeşildi ama üretimde bir şey değişti" en çok bu paralel çalıştırma + metrik izlemeyle yakalanır.

**Profiler.** Performans amaçlı refactoring'de tek meşru rehber profiler'dır. "Bu döngü yavaştır herhalde" tahmini neredeyse her zaman yanlış yeri işaret eder. Önce profille, darboğazı bul, orayı refactor et, tekrar profille -değişimin gerçekten ölçülebilir fayda getirdiğini doğrula. Ölçmeden yapılan performans "iyileştirmesi" çoğu zaman kodu okunmaz yapıp hiçbir kazanç sağlamaz.

### Kapanış saha notu

Güvenli refactoring bir yetenek değil, bir **disiplindir**. Yetenekli programcı büyük bir zıplamayla kötü kodu güzel koda çevirebileceğini sanır ve çoğu zaman yolda bir yeri kırar. Olgun programcı ise sıkıcı görünen küçük, güvenli, geri alınabilir adımların üst üste binmesiyle aynı sonuca -ama kimse fark etmeden, üretim hiç sarsılmadan- ulaşır. İyi yapılmış bir refactoring dışarıdan hiçbir şey olmamış gibi görünür: aynı davranış, aynı çıktılar, ama içeride bir sonraki değişiklik artık çok daha kolaydır. Fark edilmeyen refactoring, iyi yapılmış refactoring'dir. Ve her zaman aklında tut: en güvenli refactoring, gerçekten gerekmediğinde yapmadığın refactoring'dir.
