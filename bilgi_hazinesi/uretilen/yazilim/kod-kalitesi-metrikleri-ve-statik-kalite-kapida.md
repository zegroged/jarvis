# Kod Kalitesi Metrikleri ve Statik Kalite Kapısı Yönetimi

Temiz kod, refactoring ve kod inceleme (code review) genellikle "sezgisel" ve "insan yargısına dayalı" disiplinler olarak konuşulur. Bu makale ise işin **ölçülebilir** tarafını ele alır: bir kod tabanının karmaşıklığını, kırılganlığını ve birikmiş teknik borcunu sayılarla nasıl ifade ederiz, bu sayıları nasıl doğru yorumlarız ve bir CI/CD hattında **statik kalite kapısı (quality gate)** olarak nasıl kullanırız. Amaç, metrikleri kutsallaştırmak değil; onları ne ölçüp ne ölçmediklerini anlayarak mühendislik kararlarına dönüştürmektir.

## 1. Neden Ölçüm? Metriklerin Rolü ve Sınırları

Bir metrik, gözlemlenemez bir niteliğin (örneğin "bakım yapılabilirlik" veya "anlaşılabilirlik") gözlemlenebilir bir vekilidir (proxy). Bu ayrımı baştan netleştirmek kritiktir: **cyclomatic complexity yüksek olan kod her zaman kötü değildir; düşük olan her zaman iyi değildir.** Metrik, dikkatinizi yönlendiren bir işaret fişeğidir, nihai hakem değil.

Buradaki en büyük tehlike **Goodhart Yasası**'dır: "Bir ölçüt hedef haline geldiğinde, iyi bir ölçüt olmaktan çıkar." Örneğin test kapsamını (coverage) %90 zorunlu kılarsanız, geliştiriciler assertion içermeyen, sadece satırı "dokunan" ama hiçbir şey doğrulamayan testler yazarak sayıyı tutturur. Metrik yeşile döner, kalite düşmüştür. Bu yüzden metrikler **trend** olarak ve **birlikte** okunmalı, tek başına bir eşik dayatması olarak değil.

## 2. Boyut ve Karmaşıklık Metrikleri

### 2.1. Cyclomatic Complexity (McCabe, V(G))

Thomas McCabe'in 1976'da tanımladığı cyclomatic complexity, bir fonksiyonun kontrol akış grafiğindeki (control flow graph) **bağımsız yol sayısını** ölçer. Sezgisel hesaplama basittir: **1'den başlarsınız, her karar noktası için 1 eklersiniz.** Karar noktaları: `if`, `else if`, `for`, `while`, `case`, `catch`, `&&`, `||`, ucuz operator (`?:`) ve benzeri dallanmalardır.

```python
def sinifla(puan):          # V(G) = 1 (baslangic)
    if puan >= 90:          # +1  -> 2
        return "A"
    elif puan >= 70:        # +1  -> 3
        return "B"
    elif puan >= 50 and puan >= 0:  # +1 (elif) +1 (and) -> 5
        return "C"
    return "F"
# Toplam V(G) = 5
```

**Çalışma mantığı ve neden önemli:** Grafik teorisi açısından V(G) = E - N + 2P formülünden gelir (E: kenar, N: düğüm, P: bağlantılı bileşen sayısı). Pratik değeri şudur: V(G), bir fonksiyonu **tam** test etmek için gereken minimum bağımsız test yolu sayısının üst sınırını verir. V(G) = 5 ise, tüm yolları gezmek için en az 5 test senaryosuna ihtiyacınız var demektir. Yani complexity, doğrudan **test edilebilirlik maliyetiyle** orantı.

Yaygın eşik değerleri (araçlarda tipik varsayılanlar):
- **1-10:** Basit, düşük riskli.
- **11-20:** Orta karmaşıklık, dikkat gerektirir.
- **21-50:** Yüksek risk, refactor adayıdır.
- **50+:** Test edilemez kabul edilir; acilen bölünmelidir.

Bu eşikler kesin bilimsel sabit değildir; ekip ve dil normuna göre ayarlanır.

### 2.2. Cognitive Complexity

Cyclomatic complexity'nin kritik bir zayıflığı vardır: bir `switch` ifadesindeki 10 `case`, insan için okunması kolay olsa da V(G)'yi 10 artırır; oysa 3 seviye iç içe geçmiş (nested) `if` insan zihnini çok daha fazla yorar ama V(G)'ye katkısı daha azdır. **Cognitive complexity** (SonarSource'un önerdiği metrik) bu boşluğu doldurur: amacı matematiksel yol sayısı değil, **kodu okuyan insanın zihinsel yükünü** modellemektir.

Temel farklar:
- İç içe geçme (nesting) **cezalandırılır**: her seviye derinlik ekstra puan ekler. `if` içinde `for` içinde `if`, yassı (flat) yapıya göre çok daha pahalıdır.
- Düz dizilimler (linear `switch`) daha az cezalandırılır.
- Akışı kesen yapılar (`break`, `continue`, `goto`, iç içe ternary) ceza alır.

Pratikte cognitive complexity, refactor önceliğini belirlemede cyclomatic'ten daha iyi bir rehberdir çünkü "insan bu koda bakınca neden acı çekiyor?" sorusuna daha yakın cevap verir.

### 2.3. Boyut Metrikleri: LOC, Fonksiyon/Sınıf Uzunluğu

En kaba metrik **LOC** (lines of code) veya daha doğrusu **SLOC** (source lines, yorum ve boş satır hariç). Tek başına kalite göstermez ama:
- Çok uzun fonksiyonlar (örneğin 60+ satır) genellikle tek sorumluluk ilkesini (SRP) ihlal eder.
- Çok büyük sınıflar (God Class) coupling ve bakım sorunlarının habercisidir.

Boyut, complexity ile birlikte okunmalıdır: kısa ama V(G)'si 20 olan bir fonksiyon, uzun ama düz bir fonksiyondan daha tehlikelidir.

## 3. Bağımlılık (Coupling) ve Uyum (Cohesion) Metrikleri

Robert C. Martin'in tanımladığı paket-seviyesi metrikler, mimari sağlık için kritiktir:

- **Afferent Coupling (Ca):** Bir modülü **dışarıdan kaç modül kullanıyor** (gelen bağımlılık). Yüksek Ca = bu modül "önemli", değiştirmek risklidir.
- **Efferent Coupling (Ce):** Bu modül **kaç dış modüle bağımlı** (giden bağımlılık). Yüksek Ce = bu modül kırılgan, dışarıdaki değişimlerden etkilenir.
- **Instability (I) = Ce / (Ca + Ce):** 0 ile 1 arası. 0 = tamamen kararlı (çok kullanılan, hiçbir şeye bağımlı olmayan çekirdek). 1 = tamamen kararsız (hiçbir şey kullanmayan, her şeye bağımlı uç modül).
- **Abstractness (A):** Modüldeki soyut tip (interface/abstract class) oranının somut tiplere oranı.

**Ana Sekans (Main Sequence) ve Distance (D):** İdeal olarak bir modül ya "kararlı ve soyut" (A yüksek, I düşük — değiştirmesi zor ama soyut olduğu için genişletilebilir) ya da "kararsız ve somut" (A düşük, I yüksek — kolayca değiştirilebilir detay) olmalıdır. `A + I = 1` çizgisine "ana sekans" denir. Bu çizgiden uzaklık (D = |A + I - 1|) iki tehlikeli bölgeyi işaret eder:
- **Acı Bölgesi (Zone of Pain):** Kararlı ama somut (I~0, A~0). Çok kullanılan ama soyutlanmamış kod — değiştirmek kabus. Klasik örnek: yaygın kullanılan bir utility/DB sınıfı.
- **İşe Yaramazlık Bölgesi (Zone of Uselessness):** Kararsız ve soyut (I~1, A~1). Kimsenin kullanmadığı soyut kod — ölü soyutlama.

**LCOM (Lack of Cohesion of Methods):** Bir sınıfın metotlarının aynı alanlar (field) üzerinde ne kadar ortak çalıştığını ölçer. Yüksek LCOM = sınıf aslında birbirinden bağımsız birkaç işi yapıyor, bölünmeli demektir (düşük cohesion).

## 4. Teknik Borcun Kantifikasyonu (Technical Debt)

**Teknik borç**, Ward Cunningham'in ortaya attığı metafordur: bugün hızlı gitmek için verilen kalite tavizinin, gelecekte "faiziyle" geri ödenmesi. Sorun şudur: borç soyut bir kavramken, yönetim ve planlama için onu **paraya veya zamana** çevirmek gerekir.

### 4.1. SQALE Metodolojisi ve Remediation Cost

SonarQube gibi araçların kullandığı **SQALE** (Software Quality Assessment based on Lifecycle Expectations) modeli, teknik borcu **düzeltme süresi** cinsinden ifade eder. Mantık şu:

1. Her kural ihlali (issue) için bir **remediation effort** (düzeltme eforu) atanır — örneğin "bu kokuyu düzeltmek ~20 dakika sürer".
2. Tüm ihlallerin eforu toplanır: bu **toplam teknik borç** (örneğin "12 gün").
3. Bu borç, kodu sıfırdan yazmanın tahmini eforuna oranlanır.

### 4.2. Technical Debt Ratio (TDR)

```
TDR = (Duzeltme Maliyeti) / (Gelistirme Maliyeti) x 100

Gelistirme Maliyeti = Toplam Satir Sayisi x (Satir basina dakika, orn. ~30 dk)
```

Örnek: Kodun tamamını yazmanın 1000 saat tuttuğu tahmin ediliyor, borcu düzeltmek 50 saat tutuyorsa TDR = %5. SonarQube bu orana göre harf notu (Maintainability Rating) verir; kabaca A = çok düşük borç, E = çok yüksek borç. Eşikler araca göre ayarlanabilir.

**Önemli uyarı — dürüstlük notu:** Bu dakika değerleri (satır başına 30 dk, kök başına 20 dk) araçların **varsayılan tahminleridir**, kesin gerçek değildir. Amaç mutlak doğruluk değil, **tutarlı ve karşılaştırılabilir** bir sayıdır. "12 gün teknik borç" ifadesini "kesinlikle 12 gün sürer" diye değil, "göreceli olarak büyük ve trendi şu yönde" diye okuyun.

### 4.3. Teknik Borç Türleri

Martin Fowler'in matrisi borcu iki eksende sınıflar: **kasıtlı/kasıtsız** ve **ihtiyatlı/pervasız**:
- **Kasıtlı-ihtiyatlı:** "Şimdi hızlı teslim edelim, sonucu biliyoruz, sonra öderiz." (Sağlıklı borç.)
- **Kasıtlı-pervasız:** "Tasarıma vaktimiz yok, öylesine yazalım." (Tehlikeli.)
- **Kasıtsız-ihtiyatlı:** "Şimdi anladık ki doğrusu şöyleymiş." (Öğrenmeden doğan, kaçınılmaz.)
- **Kasıtsız-pervasız:** "Katmanlı mimari neymiş?" (Bilgisizlik borcu.)

Bu sınıflandırma, hangi borcun önceden planlanıp ödeneceğini, hangisinin eğitimle önleneceğini ayırt etmeye yarar.

## 5. Kod Kokusu (Code Smell) Kataloğu

**Kod kokusu**, Kent Beck ve Martin Fowler'in popülerleştirdiği kavramdır: kod bir hata (bug) içermese bile, derin bir tasarım probleminin **yüzeydeki işareti**. Koku bir teşhis değil, bir semptomdur. Başlıca taksonomi:

### 5.1. Şişmişler (Bloaters)
Zamanla büyüyüp yönetilemez hale gelen yapılar:
- **Long Method:** Çok iş yapan uzun fonksiyon. Çözüm: *Extract Method*.
- **Large Class / God Class:** Her şeyi bilen ve yapan dev sınıf. Çözüm: *Extract Class*, sorumluluk dağıtımı.
- **Long Parameter List:** Çok fazla parametre. Çözüm: *Introduce Parameter Object*.
- **Primitive Obsession:** Alan-kavramlarını (para, tarih, telefon) hep `string`/`int` ile temsil etme. Çözüm: değer nesneleri (value object).
- **Data Clumps:** Hep birlikte dolaşan veri grupları; bir sınıf olmak istiyorlardır.

### 5.2. Nesne Yönelimi Kötü Kullananlar (OO Abusers)
- **Switch Statements:** Tip koduna göre dallanan uzun `switch`; genellikle polimorfizm ile çözülmelidir.
- **Refused Bequest:** Alt sınıfın, üst sınıftan miras aldığı şeylerin çoğunu kullanmaması/reddetmesi — yanlış kalıtım.
- **Temporary Field:** Sadece belirli durumlarda dolan, çoğu zaman boş alanlar.

### 5.3. Değişimi Zorlaştıranlar (Change Preventers)
- **Divergent Change:** Tek bir sınıfın farklı sebeplerle sürekli değişmesi (düşük cohesion).
- **Shotgun Surgery:** Tek bir mantıksal değişikliğin, bir sürü farklı sınıfta ufak düzenlemeler gerektirmesi (aşırı coupling). Divergent Change'in tersidir.
- **Parallel Inheritance Hierarchies:** Bir hiyerarşiye sınıf ekleyince diğerine de eklemek zorunda kalmak.

### 5.4. Gereksizler (Dispensables)
- **Duplicated Code:** Kopyala-yapıştır kod. En yaygın ve zararlı koku; bir yeri düzeltince ötekiler unutulur.
- **Dead Code:** Hiç çağrılmayan, ulaşılamayan kod.
- **Speculative Generality:** "İleride lazım olur" diye eklenmiş, kimsenin kullanmadığı soyutlama/parametre (YAGNI ihlali).
- **Comments (kötü kullanım):** Kötü kodu açıklamak için yazılan yorumlar — yorum bazen "deodorant" görevi görür; asıl çözüm kodu netleştirmektir.

### 5.5. Bağlayıcılar (Couplers)
- **Feature Envy:** Bir metodun, kendi sınıfından çok başka bir sınıfın verisiyle ilgilenmesi.
- **Inappropriate Intimacy:** İki sınıfın birbirinin iç detaylarına aşırı girmesi.
- **Message Chains:** `a.getB().getC().getD().yap()` — Demeter Yasası ihlali.
- **Middle Man:** Sadece çağrıyı başka sınıfa devreden, kendi değeri olmayan sınıf.

## 6. Statik Kalite Kapısı (Quality Gate) Yönetimi

Metrikleri toplamak yetmez; onları **otomatik bir karar mekanizmasına** bağlamak gerekir. **Quality gate**, bir kod değişikliğinin (PR/merge) belirlenmiş eşikleri geçemezse **build'i kırmasıdır** (fail).

### 6.1. "Clean as You Code" Prensibi — Yeni Kod Odaklı Kapı

Kalite kapısı tasarımının en önemli fikri şudur: **Eski kodun tamamını bir anda temizlemeye çalışmayın.** Milyonlarca satırlık legacy koda "TDR %5 olacak" dayatırsanız kapı sürekli kırmızıdır ve ekip onu tümden kapatır (bypass eder). Bunun yerine SonarQube'un popülerleştirdiği **"Clean as You Code"** yaklaşımı: kapı yalnızca **yeni veya değiştirilmiş kodu (new code)** denetler.

Tipik "yeni kod" kapısı koşulları:
- Yeni kodda **0 yeni bug / 0 yeni güvenlik açığı**.
- Yeni kod **coverage** >= %80 (örnek eşik).
- Yeni kodda **duplication** <= %3.
- Yeni kodda Maintainability/Security rating = A.

Böylece kod tabanı her commit'te biraz daha temizlenir; eski borç dokunuldukça ödenir, dayatılmaz.

### 6.2. Güvenlik Açısı: SAST ve Kalite Kapısı

Kalite kapısı sadece bakım değil, **güvenlik savunmasının** da ilk hattıdır. **SAST** (Static Application Security Testing) araçları, kodu çalıştırmadan bilinen zafiyet desenlerini tarar:
- **Taint analysis:** Güvenilmez girdinin (user input) sanitize edilmeden hassas bir noktaya (SQL sorgusu, komut, dosya yolu) ulaşıp ulaşmadığını akış analiziyle izler. SQL injection, command injection, path traversal gibi sınıflar böyle yakalanır.
- **Hardcoded secrets:** Koda gömülü parola/anahtar tespiti.
- **Güvensiz API kullanımı:** Zayıf kripto, güvensiz deserializasyon desenleri.

Savunma tasarımı açısından doğru yaklaşım: **güvenlik bulgularını kalite kapısına "bloklayıcı" olarak koymak** — yani yeni bir Critical/Blocker güvenlik bulgusu varsa merge engellenir. Bu, zafiyetin production'a ulaşmadan **sol tarafa (shift-left)** kaydırılmasıdır. SAST'in sınırı ise şudur ve dürüstçe söylenmelidir: statik analiz **çalışma zamanı** bağlamını görmez, bu yüzden **false positive** (yanlış alarm) ve **false negative** (kaçan gerçek açık) üretir; DAST ve manuel inceleme ile tamamlanmalıdır.

### 6.3. CI/CD Entegrasyonu

Pratik akış:
1. Geliştirici PR açar.
2. CI hattı derler, testleri koşar, **coverage raporu** üretir.
3. Statik analiz aracına (örn. SonarQube scanner) coverage raporu ve kaynak beslenir.
4. Araç quality gate'i değerlendirir; sonuç PR'a status olarak döner.
5. Kapı **kırmızı** ise merge butonu bloke olur (branch protection).

## 7. Yaygın Hatalar ve Tuzaklar

**Tuzak 1 — Tek metriğe tapmak.** Sadece coverage'a bakmak klasik hatadır. %100 coverage, kodun **doğru** olduğunu değil, satırların **çalıştırıldığını** gösterir. Assertion'sız test coverage'i şişirir ama hiçbir şey doğrulamaz. Coverage'i mutation testing (kod bilerek bozulunca testler yakalıyor mu?) ile denetleyin.

**Tuzak 2 — Legacy koda pervasız eşik dayatmak.** Bütün kod tabanına retroaktif kapı koymak ekibi kapıyı devre dışı bırakmaya iter. Çözüm: yeni-kod odaklı kapı.

**Tuzak 3 — Metriği hedef yapmak (Goodhart).** "Complexity 10'u geçmesin" derseniz, geliştirici tek büyük fonksiyonu, hiçbir şey kazandırmayan beş anlamsız küçük fonksiyona böler; sayı düşer, anlaşılabilirlik düşebilir. Metriği **tetikleyici** (konuşma başlatıcısı) olarak kullanın, otomatik hüküm olarak değil.

**Tuzak 4 — False positive yorgunluğu.** Çok fazla düşük değerli uyarı, ekibin bütün uyarılara kör olmasına yol açar. Kural setini **titizlikle** ayarlayın; gürültüyü susturmak, sinyali öldürmekten iyidir.

**Tuzak 5 — Borcu ölçüp hiçbir şey yapmamak.** TDR panosu süslü ama kimse "yeniden ödeme" (refactoring) için zaman ayırmıyorsa, ölçüm bir tiyatrodur. Metrik, sprint planlamasında somut iş kalemlerine bağlanmadıkça değersizdir.

**Tuzak 6 — Üretilmiş/generated kodu ölçmek.** Otomatik üretilen kod (ORM mapping, protobuf, migration) metrikleri kirletir ve gereksiz alarm üretir; kapsam dışı bırakılmalıdır.

## 8. Özet ve Doğru Zihniyet

Kod kalitesi metrikleri, subjektif "bu kod kötü" hissini **mühendislikçe tartışılabilir**, **trendi izlenebilir** ve **CI'da uygulanabilir** bir dile çevirir. Ancak her metrik bir vekildir: cyclomatic/cognitive complexity test ve anlama yükünü; coupling/cohesion mimari sağlığı; SQALE/TDR birikmiş borcu; kod kokusu kataloğu ise tekrarlayan tasarım problemlerini işaret eder.

Doğru zihniyet üç ilkeye dayanır: **(1)** Metrikleri tek başına değil, birlikte ve trend olarak oku. **(2)** Kalite kapısını "yeni kod" üzerine kur (Clean as You Code), legacy'yi boğma. **(3)** Metriği hedefe çevirme (Goodhart); onu bir keşif ve konuşma aracı olarak tut. Sayı, mühendisin yerine karar vermez — dikkatini nereye vermesi gerektiğini söyler.
