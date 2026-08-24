# Hesaplanabilirlik Teorisi: Turing Makineleri, Durma Problemi ve Karar Verilemezlik

## Neden Bu Konu Önemli?

Statik analiz, dinamik analiz, sandbox, imza tabanlı tarama, davranışsal tespit... Modern malware tespit araçlarının tamamı, özünde şu soruyu cevaplamaya çalışır: "Bu program zararlı mı?" Bu araçların neden hiçbir zaman kusursuz olamadığını, neden hep heuristic (sezgisel) ve olasılıksal kalmak zorunda olduğunu anlamak istiyorsak, meselenin mühendislik yetersizliği değil, matematiksel bir imkânsızlık olduğunu görmemiz gerekir. İşte o imkânsızlığın kaynağı **hesaplanabilirlik teorisi** (computability theory), özellikle de **durma problemi** (halting problem) ve **karar verilemezlik** (undecidability) kavramlarıdır.

Bu makale, bir güvenlik mühendisinin "genel bir virüs tespit algoritması neden yazılamaz?" sorusuna teorik olarak sağlam bir cevap vermesini amaçlar. Bu, karamsarlık değil; savunmanın gerçekçi tasarım prensiplerini belirlemektir.

## Temel Kavramlar

### Algoritma ve Hesaplama Modeli

Bir **algoritma**, sonlu adımda tanımlanmış, belirsizlik içermeyen bir prosedürdür. 1930'larda matematikçiler "hesaplanabilir olan nedir?" sorusunu resmileştirmek istediklerinde birden çok eşdeğer model ortaya çıktı: Alonzo Church'ün **lambda calculus**'ı, Kurt Gödel'in **recursive functions**'ı ve Alan Turing'in **Turing machine**'i. Bunların hepsinin aynı fonksiyon sınıfını hesaplayabildiği kanıtlandı. Bu gözlem **Church-Turing tezi** olarak bilinir: "Sezgisel olarak 'etkin biçimde hesaplanabilir' dediğimiz her şey, bir Turing makinesi tarafından hesaplanabilir."

Church-Turing tezi bir teorem değil, bir tezdir (kanıtlanamaz çünkü "sezgisel hesaplanabilirlik" resmi bir tanım değildir), ancak bugüne kadar bilinen her hesaplama modeli (klasik bilgisayarlar, hatta prensipte kuantum bilgisayarlar da hesaplanabilirlik sınırı açısından) bu teze uyar. Pratik sonucu şudur: Bir Turing makinesinin çözemediği bir problemi, hiçbir gerçek bilgisayar (ne kadar hızlı, ne kadar bellekli olursa olsun) çözemez.

### Turing Makinesi

Bir **Turing machine** (TM), soyut ama tam bir hesaplama modelidir. Bileşenleri:

- **Sonsuz bir teyp** (tape): Hücrelere bölünmüş, her hücrede bir sembol.
- **Bir okuma/yazma kafası** (head): Teyp üzerinde sağa-sola hareket eder.
- **Sonlu durum kümesi** (states): Makinenin "iç hafızası".
- **Geçiş fonksiyonu** (transition function): "Mevcut durum + okunan sembol" ikilisine karşılık "yaz, hareket et, durum değiştir" üçlüsü.

Makine bir başlangıç durumunda başlar, geçiş fonksiyonunu uygulaya uygulaya çalışır ve ya bir **halt** (durma/kabul-red) durumuna ulaşır, ya da sonsuza kadar çalışır (halt etmez).

Basit görünmesine rağmen bu model **Turing-complete**'tir: Modern bir programlama dilinin (Python, C, Java) yapabildiği her hesaplamayı yapabilir. Sınırsız döngü, koşul, bellek erişimi... hepsi bu modelde temsil edilebilir. Bu yüzden "TM için doğru olan, gerçek yazılım için de doğrudur" diyebiliriz.

### Karar Problemi (Decision Problem)

Bir **decision problem**, cevabı "evet/hayır" olan bir sorudur; girdi bir string, çıktı bir bit. Örnek: "Verilen sayı asal mı?" Bir problem **decidable** (karar verilebilir) ise, o problemi her girdi için **daima durup** doğru evet/hayır veren bir algoritma vardır. **Undecidable** (karar verilemez) ise, böyle bir algoritma **hiç yoktur** ve hiçbir zaman olmayacaktır — bu bir mühendislik eksikliği değil, matematiksel bir kanıttır.

Ayrı bir kavram: **semi-decidable** (recursively enumerable). Burada cevabı "evet" olan girdilerde algoritma durup "evet" der, ama "hayır" durumlarında sonsuza kadar çalışabilir. Yani "evet"i doğrulayabilirsiniz ama "hayır"ı garanti edemezsiniz. Bu ayrım tespit sistemleri için kritiktir, aşağıda döneceğiz.

## Durma Problemi (The Halting Problem)

### Tanım

Durma problemi şudur: **Girdi olarak bir program P ve bir girdi x alan; P(x) çalıştırıldığında durur mu (halt eder mi), yoksa sonsuza kadar mı çalışır sorusunu her zaman doğru cevaplayan genel bir algoritma var mıdır?**

Alan Turing 1936'da bu problemin **undecidable** olduğunu kanıtladı. Yani böyle bir "evrensel durma dedektörü" yazmak matematiksel olarak imkânsızdır.

### Kanıtın Mantığı (Diagonalization / Çelişki)

Kanıt, **reductio ad absurdum** (çelişkiye indirgeme) ile ilerler. Sezgisel akış şöyledir:

1. Varsayalım ki `HALT(P, x)` diye bir fonksiyon var; P programı x girdisiyle durursa `true`, durmazsa `false` döndürüyor ve **daima kendisi durup** doğru cevabı veriyor.

2. Şimdi bu `HALT`'ı kullanarak kötü niyetli bir program yazalım, adı `TROUBLE(P)` olsun:

```
TROUBLE(P):
    if HALT(P, P) == true:
        sonsuz döngü  # asla durma
    else:
        dur  # hemen dur
```

`TROUBLE`, bir program P'yi alır, "P kendi kendisine uygulandığında durur mu?" diye `HALT`'a sorar. Eğer "durur" derse `TROUBLE` sonsuza girer; "durmaz" derse `TROUBLE` durur. Yani `TROUBLE`, `HALT`'ın söylediğinin **tam tersini** yapar.

3. Şimdi kritik soru: `TROUBLE(TROUBLE)` çalıştırılırsa ne olur?

   - Diyelim `TROUBLE(TROUBLE)` **durur**. O halde tanımı gereği `HALT(TROUBLE, TROUBLE)` `true` dönmüştür, ama o zaman `TROUBLE` sonsuz döngüye girer — yani **durmaz**. Çelişki.
   - Diyelim `TROUBLE(TROUBLE)` **durmaz**. O halde `HALT(TROUBLE, TROUBLE)` `false` dönmüştür, ama o zaman `TROUBLE` hemen durur — yani **durur**. Çelişki.

Her iki durum da çelişkiye götürür. Çelişkinin kaynağı tek bir varsayımdı: kusursuz `HALT`'ın var olması. Demek ki o varsayım yanlıştır. **Genel bir durma dedektörü yazılamaz.** Bu, Cantor'un köşegen argümanının (diagonalization) hesaplamaya uyarlanmış halidir.

### Neden "Ama Ben Çoğu Programın Durup Durmadığını Anlayabiliyorum"?

Yaygın bir yanlış anlama: "Ben basit döngülere bakıp durur mu görebiliyorum, o halde bir program da bunu yapabilir." Doğru — **belirli** programlar için, **belirli** analizlerle karar verebilirsiniz. Undecidability iddiası bu değildir. İddia şudur: **Her olası program için çalışan tek bir genel algoritma** yoktur. Her tespit yöntemi için, o yöntemi yanıltan bir karşı-program **inşa edilebilir**. İşte adversary (saldırgan) tam olarak bu boşlukta yaşar.

## Rice Teoremi: Kötü Haberin Genellenmesi

Durma problemi tek başına çarpıcıdır ama malware tespiti için asıl yıkıcı sonuç **Rice teoremi**'dir (Henry Gordon Rice, 1951).

**Rice teoremi, kabaca:** Bir programın hesapladığı fonksiyonun (yani davranışının/anlamının, "input-output davranışının") **önemsiz (non-trivial) her semantik özelliği undecidable'dır.**

Burada:
- **Semantik özellik**: Programın ne yaptığıyla ilgili özellik (kodun nasıl yazıldığıyla değil). Örnek: "Bu program hiç ağ bağlantısı açıyor mu?", "Bu program bir dosyayı şifreliyor mu?", "Bu program zararlı davranış sergiliyor mu?"
- **Non-trivial (önemsiz olmayan)**: Bazı programlar bu özelliğe sahip, bazıları değil (yani ne her zaman doğru, ne her zaman yanlış).

Sonuç: "Bu program X yapıyor mu?" biçimindeki hemen her ilginç davranışsal soruya, **her girdi/her program için daima doğru** cevap veren bir algoritma yazmak imkânsızdır. Malware tespiti tam olarak bu türden bir sorudur: "Bu programın davranışı zararlı sınıfına giriyor mu?" Rice teoremi der ki: **Genel, kusursuz, her zaman duran bir malware dedektörü matematiksel olarak var olamaz.**

Dikkat: Rice teoremi **semantik** (davranışsal) özellikler hakkındadır. **Sözdizimsel/statik** özellikler (örneğin "kodda şu byte dizisi var mı?", "dosya boyutu 4KB'den büyük mü?") decidable'dır — çünkü bunlar programın anlamına değil, metnine bakar. İmza tabanlı taramanın (signature-based detection) neden hızlı ve kesin ama kolay atlatılabilir olduğunun teorik açıklaması budur: Sözdizimsel özellik decidable ama saldırganın kod metnini (packing, polymorphism, obfuscation ile) değiştirmesi trivialdir; davranış aynı kalır ama imza değişir.

## Malware Tespitine Uygulanışı

### Fred Cohen'in Sonucu

Bilgisayar virüsü kavramını 1980'lerde resmileştiren Fred Cohen, "bir programın virüs olup olmadığını genel olarak belirlemenin" durma problemine indirgenebilir olduğunu gösterdi. Basit bir kanıt taslağı:

Diyelim kusursuz bir `IS_MALWARE(P)` dedektörümüz var. Şöyle bir program yazalım:

```
EVIL:
    # bir yerde durma problemine bağlı bir dallanma
    if (bilinmeyen_program_Q durur):
        zararlı_yük_çalıştır()
    else:
        zararsız_kal()
```

`EVIL`'in zararlı olup olmadığına karar vermek, `Q`'nun durup durmadığına karar vermeyi gerektirir. Ama durma problemi undecidable olduğundan, `IS_MALWARE` de undecidable olur. Yani mükemmel dedektör varsayımı yine çelişkiye götürür.

### Bunun Pratik Anlamı: İki Tür Hata Kaçınılmazdır

Kusursuz dedektör olamayacağına göre, her gerçek tespit sistemi iki hatadan en az birini yapmaya mahkûmdur:

- **False positive** (yanlış alarm): Zararsız bir programı zararlı sanmak.
- **False negative** (kaçırma): Zararlı bir programı zararsız sanmak.

Teorik olarak, bir dedektörü "asla false negative vermesin" diye ayarlarsanız (yani hiçbir malware'i kaçırmasın), matematik sizi ya bazı zararsızları da yakalamaya (false positive) ya da bazı girdilerde **hiç durmamaya/karar verememeye** zorlar. Bu bir denge (trade-off) değil, bir **imkânsızlık teoremi**dir. Antivirüs sektörünün "detection rate %99.x" demesi ama asla %100 dememesi tesadüf değildir.

### Neden Tespit "Semi-decidable" Gibi Davranır

Malware tespiti pratikte semi-decidable bir yapıya benzer: Bir davranış **gözlemlenirse** (örneğin sandbox içinde program gerçekten dosyaları şifrelemeye başlarsa) "evet, zararlı" diyebiliriz — pozitifi doğrulayabiliriz. Ama davranış gözlemlenmezse, bu "program zararsız" demek değildir; sadece "verilen gözlem süresinde/verilen tetikleyicilerle zararlı davranış görmedik" demektir. Malware'in **logic bomb**, **time bomb** veya **sandbox evasion** (analiz ortamını tanıyıp uyumasını) teknikleri tam bu boşluğu sömürür: "Hayır"ı asla kesinleştiremezsin.

## Doğru Kullanım: Teoriyi Savunmaya Çevirmek

Undecidability karamsarlığa değil, gerçekçi mühendisliğe götürmeli. Doğru çıkarımlar:

### 1. Kesinlik Yerine Olasılık ve Katmanlı Savunma

Genel kusursuz tespit imkânsız olduğundan, savunma **defense-in-depth** (katmanlı) olmalı. Statik imza + heuristic + davranışsal analiz + reputation + ML tabanlı sınıflandırma bir arada kullanılır. Her katman farklı bir yaklaşımın körlüğünü kapatır; tek bir katmandan "kusursuzluk" beklemek teoriye aykırıdır.

### 2. Sınırlı Zaman/Sınırlı Kaynak Analizi (Bounded Analysis)

Durma problemi **sınırsız** çalışma hakkındadır. Pratikte tespit sistemleri problemi **decidable bir alt-probleme** indirger: "Bu program **ilk N adımda / T saniye içinde** zararlı davranış sergiliyor mu?" Bu soru decidable'dır (sonlu zaman, sonlu durum). Sandbox'lar tam da bunu yapar. Bedeli: N adımdan sonra tetiklenen davranışı kaçırırsınız (bkz. sandbox evasion). Bu, teorinin dayattığı bilinçli bir tavizdir.

### 3. Sound vs. Complete Ayrımını Kabul Etmek

Statik analiz araçlarında (ve genelde program analizinde) iki ideal vardır:
- **Sound** (sağlam): "Zararlı yoktur" dediğinde gerçekten yoktur (false negative yok), ama false positive verebilir.
- **Complete** (tam): "Zararlı vardır" dediğinde gerçekten vardır (false positive yok), ama kaçırabilir.

Undecidability nedeniyle **aynı anda hem sound hem complete hem de her zaman duran** bir analizör olamaz. Güvenlikte genellikle **sound tarafı** tercih edilir (kaçırmaktansa fazla alarm ver), çünkü kaçırmanın maliyeti daha yüksektir. Bu bilinçli bir mühendislik tercihidir, aracın "kötü" olması değil.

### 4. Over-approximation (Aşırı Yaklaşım)

Modern statik analiz (abstract interpretation, taint analysis) programın davranışını **decidable bir soyutlama** ile üstten sınırlar: Gerçek davranış kümesini kapsayan daha büyük ama analiz edilebilir bir küme hesaplar. Sonuç sound olur ama false positive üretir. "Şu değişken kesinlikle kullanıcı girdisinden gelmiyor" diyemeyeceğiniz her yerde "gelebilir" varsayılır. Bu, undecidability ile başa çıkmanın standart yoludur.

## Yaygın Hatalar ve Tuzaklar

- **"Yeterince zeki bir AI durma problemini çözer."** Hayır. Church-Turing tezi gereği, herhangi bir hesaplama modeli (sinir ağları dahil) Turing makinesinden daha güçlü değildir. Undecidable bir problem yapay zekâ için de undecidable'dır. AI, ortalama vakada daha iyi **tahmin** yapabilir ama kusursuz **karar** veremez.

- **"Undecidable, yani hiçbir program hakkında hiçbir şey söyleyemeyiz."** Yanlış. Undecidability **genel** algoritma hakkındadır. Birçok **belirli** program hakkında kesin şeyler söylenebilir. "Her zaman/her girdi için" ile "çoğu pratik durumda" karıştırılmamalı.

- **"İmza tabanlı tarama undecidable'a takılıyor, o yüzden işe yaramaz."** Yanlış. İmza taraması **sözdizimsel** ve decidable'dır, çok hızlı ve kesindir; sadece **kolay atlatılır** (polymorphism). Zayıflığı teorik imkânsızlık değil, saldırganın kod metnini değiştirebilmesidir.

- **Undecidability ile intractability (NP-hardness) karıştırmak.** Undecidable = **hiç** algoritma yok. NP-hard = algoritma var ama **çok yavaş** (üstel zaman). İkisi farklı engellerdir. Malware tespitinde her ikisi de karşımıza çıkar ama kaynakları farklıdır.

- **"Sandbox'ta zararlı davranış görmedik, demek ki temiz."** En tehlikeli hata. Bu, semi-decidability'nin "hayır" tarafını kesinleştirmektir; teorik olarak garanti edilemez. Logic bomb ve evasion tam buraya oynar.

- **Halting problem'i "programım neden takıldı?" ile karıştırmak.** Halting problem belirli bir programın neden takıldığını değil, **genel bir dedektörün var olamayacağını** söyler. Debugging ayrı bir iştir.

## Özet

Turing makineleri, hesaplamanın evrensel modelini verir; Church-Turing tezi bu modelin gerçek bilgisayarları da kapsadığını söyler. Durma problemi, köşegen argümanıyla, "her program için durup durmadığını söyleyen genel bir algoritma"nın imkânsızlığını kanıtlar. Rice teoremi bunu genelleştirir: Bir programın **her önemli semantik özelliği** undecidable'dır. Malware tespiti de böyle bir semantik özelliktir; dolayısıyla **kusursuz, her zaman duran, genel bir malware dedektörü matematiksel olarak var olamaz.**

Bu, savunmanın neden hep heuristic, olasılıksal, katmanlı ve zaman-sınırlı olmak zorunda olduğunun kökenidir. İyi güvenlik mühendisi bu sınırı bilir: Kusursuzluk peşinde koşmaz; false positive/negative dengesini bilinçle yönetir, sound over-approximation'lar kurar, bounded analizle decidable alt-problemlere iner ve tek katmana güvenmez. Teori bize "kazanamazsın" demez; "hangi oyunu oynadığını bil" der.
