# Yaklaşık ve Sezgisel Optimizasyon Algoritmaları

## Giriş: Neden "Yaklaşık" Çözüme İhtiyaç Duyarız?

Bilgisayar biliminde birçok pratik problem, en iyi (optimal) çözümü makul bir sürede bulmanın **hesaplama açısından imkânsız** olduğu bir sınıfa girer. Bu problemler genellikle **NP-zor (NP-hard)** olarak sınıflandırılır: çözüm uzayı, girdi boyutuyla üstel (exponential) olarak büyür ve tüm olasılıkları tek tek denemek (brute force) evrenin yaşından daha uzun sürebilir.

Örneğin klasik **Gezgin Satıcı Problemi (Traveling Salesman Problem, TSP)** için 50 şehirlik bir turda olası rota sayısı `49!/2` gibi astronomik bir sayıdır. Optimal çözümü garantiyle bulmak yerine, "yeterince iyi" bir çözüme hızlıca ulaşmak çoğu zaman tek gerçekçi yoldur.

İşte bu noktada iki geniş yaklaşım ailesi devreye girer:

- **Yaklaşım algoritmaları (approximation algorithms):** Optimal çözüme belirli bir **matematiksel garanti** (approximation ratio) içinde kaldığını kanıtlayabildiğimiz algoritmalar.
- **Sezgisel/metasezgisel yöntemler (heuristics / metaheuristics):** Garanti sunmayan ama pratikte çok iyi sonuçlar veren, doğadan veya arama mantığından esinlenmiş yöntemler (Genetik Algoritmalar, Simulated Annealing, yerel arama, A* gibi).

Bu makale, bu tekniklerin **çalışma mantığını**, doğru kullanımını, tuzaklarını ve özellikle **güvenlik (fuzzing, sembolik yürütme, pentest)** bağlamındaki rolünü anlatır. Amaç mekanizmayı anlamak ve savunma/tespit perspektifi kazanmaktır.

---

## Temel Kavramlar: Arama Uzayı, Amaç Fonksiyonu ve Yerel Optimum

Optimizasyonu anlamak için üç kavram şarttır:

### Arama uzayı (search space / state space)
Tüm olası çözümlerin oluşturduğu kümedir. Bir fuzzing girdisi, bir program yürütme yolu, bir rota, bir parametre kombinasyonu... hepsi arama uzayındaki bir "nokta"dır.

### Amaç/uygunluk fonksiyonu (objective / fitness function)
Bir çözümün "ne kadar iyi" olduğunu sayısal olarak ölçen fonksiyondur. Optimizasyon, bu fonksiyonu ya en küçükleyen (minimize) ya da en büyükleyen (maximize) noktayı aramaktır. Fuzzing'de bu genellikle **kod kapsama (code coverage)** veya yeni keşfedilen dallardır.

### Yerel optimum vs. global optimum
Arama uzayını dağlık bir arazi gibi düşünürseniz, **global optimum** en yüksek tepe, **yerel optimum (local optimum)** ise çevresindeki her yönden yüksek ama en yüksek olmayan bir tepeciktir. Sezgisel yöntemlerin ana zorluğu, bir yerel optimuma "sıkışıp" global optimumu kaçırmamaktır. Bu tuzağa **premature convergence (erken yakınsama)** denir ve bu makaledeki her yöntemin ortak düşmanıdır.

---

## A* Algoritması: Bilgilendirilmiş Arama

### Tanım
**A*** (A-star), bir başlangıç durumundan hedef duruma **en düşük maliyetli yolu** bulan, graf/ağaç tabanlı bir arama algoritmasıdır. Dijkstra algoritmasının, bir **sezgisel tahmin (heuristic)** ile hızlandırılmış halidir.

### Çalışma mantığı
A*, her düğüm için şu değeri hesaplar:

```
f(n) = g(n) + h(n)
```

- `g(n)`: başlangıçtan `n` düğümüne kadar gelmenin **gerçek maliyeti** (kesin, bilinen).
- `h(n)`: `n` düğümünden hedefe kalan maliyetin **tahmini** (heuristic, geleceğe bakış).
- `f(n)`: bu düğüm üzerinden geçen yolun tahmini toplam maliyeti.

Algoritma, bir **öncelik kuyruğu (priority queue)** kullanarak her adımda `f(n)` değeri en düşük düğümü açar. Böylece Dijkstra gibi her yöne eşit yayılmak yerine, hedefe doğru "eğilimli" ilerler.

### Kabul edilebilirlik (admissibility) ve tutarlılık (consistency)
A*'ın **optimal** sonucu garanti etmesi için `h(n)` fonksiyonunun **admissible** olması gerekir: gerçek kalan maliyeti asla olduğundan fazla tahmin etmemelidir (never overestimates). Ek olarak `h(n)` **consistent (monotone)** ise, aynı düğümü tekrar tekrar işlemek gerekmez ve verimlilik artar.

- `h(n) = 0` alırsanız A*, aynen **Dijkstra**'ya dönüşür (hâlâ optimal, ama yavaş).
- `h(n)` gereğinden büyükse (inadmissible), A* daha hızlı olabilir ama **optimal olmayan** bir yol bulabilir (bu, weighted A*'ın bilinçli bir tercihi olabilir).

### Örnek: Grid üzerinde yol bulma
Bir haritada A noktasından B'ye giderken, `h(n)` olarak genellikle **Manhattan mesafesi** (yalnızca dik hareket varsa) veya **Öklid mesafesi (Euclidean distance)** kullanılır. Bunlar gerçek yolu asla abartmadığı için admissible'dır.

### Güvenlik bağlamı: Sembolik yürütmede A*
**Sembolik yürütme (symbolic execution)** motorlarında (örneğin KLEE benzeri araçlarda), program bir **yürütme ağacı** olarak açılır; her dallanma (branch) yeni bir durum üretir. Bu durum uzayı üstel patlar (**path explosion / yol patlaması**). Burada A* benzeri bilgilendirilmiş arama, hedef bir koda (örneğin şüpheli bir `memcpy`) en muhtemel yakın yolları önceliklendirerek analizin işe yarayan bölgelere odaklanmasını sağlar. `h(n)` olarak genellikle kontrol akış grafiğindeki (control flow graph, CFG) hedefe olan mesafe kullanılır.

### Yaygın hatalar ve tuzaklar
- **Inadmissible heuristic kullanıp optimal sonuç beklemek.** Garanti kaybolur.
- **Bellek patlaması:** A* açık düğümleri (open set) bellekte tutar; büyük graflarda RAM tükenir. Çözüm için IDA* (Iterative Deepening A*) gibi varyantlar vardır.
- **Yanlış heuristic:** Çok zayıf (`h≈0`) heuristic yavaşlatır; çok agresif heuristic yanlış yol verir. Denge kritiktir.

---

## Yerel Arama (Local Search) ve Hill Climbing

### Tanım
**Yerel arama**, mevcut bir çözümden başlayıp **komşu çözümlere** (küçük değişikliklerle elde edilen) bakarak adım adım iyileşen yönde ilerleyen yöntemlerin genel adıdır. En basit hali **hill climbing (tepe tırmanma)** algoritmasıdır: her adımda amaç fonksiyonunu iyileştiren komşuya geç, iyileşme kalmayınca dur.

### Kök sorun: Yerel optimuma sıkışma
Hill climbing hızlıdır ama **yerel optimuma** takılır. Bir tepeciğe çıktığında, global tepeye ulaşmak için önce **aşağı inmesi** gerekse bile bunu yapamaz, çünkü sadece "yukarı" adım kabul eder. Bu sınırlamayı aşmak için geliştirilen iki büyük fikir Simulated Annealing ve Genetik Algoritmalar'dır.

### Kaçış stratejileri
- **Random restart (rastgele yeniden başlatma):** Farklı başlangıç noktalarından defalarca dene, en iyisini sakla.
- **Tabu search:** Yakın geçmişte ziyaret edilen çözümleri bir "yasaklı liste"de (tabu list) tutarak döngüye girmeyi ve aynı yere geri dönmeyi engelle.

---

## Simulated Annealing (Benzetimli Tavlama)

### Tanım
**Simulated Annealing (SA)**, metalürjideki **tavlama** işleminden esinlenen bir metasezgiseldir. Metali yavaşça soğutarak kristal yapısını düşük enerjili (kararlı) hale getirme fikri, optimizasyona uyarlanır: yüksek "sıcaklıkta" sistem serbestçe dolaşır, sıcaklık düştükçe iyi çözümlere yerleşir.

### Çalışma mantığı
Hill climbing'in aksine SA, **bazen daha kötü çözümü de kabul eder**. Bu, yerel optimumdan kaçmanın anahtarıdır. Kabul kararı **Metropolis kriteri** ile verilir:

```
ΔE = yeni_maliyet - mevcut_maliyet
Eğer ΔE < 0 (daha iyi):  her zaman kabul et
Eğer ΔE ≥ 0 (daha kötü):  P = exp(-ΔE / T) olasılığıyla kabul et
```

Burada `T` **sıcaklık (temperature)** parametresidir:

- **Yüksek T:** Kötü çözümler bile yüksek olasılıkla kabul edilir → geniş keşif (exploration).
- **Düşük T:** Neredeyse sadece iyileşmeler kabul edilir → yerel iyileştirme (exploitation).

Sıcaklık, bir **soğutma çizelgesi (cooling schedule)** ile zamanla azaltılır (örneğin her adımda `T = T × 0.95`). Bu keşif-den-sömürüye geçiş, SA'nın gücüdür.

### Örnek
TSP'de bir rotayı alıp iki şehri rastgele yer değiştirmek bir "komşu" üretir. Rota kısaldıysa kabul; uzadıysa `exp(-ΔE/T)` olasılığıyla yine de kabul edilir. Böylece algoritma, önce kötü görünen bir hamlenin ileride daha iyi bir bölgeye açılmasına izin verir.

### Doğru kullanım ve tuzaklar
- **Çok hızlı soğutma (quenching):** T çok çabuk düşerse SA, hill climbing'e döner ve yerel optimuma sıkışır. **En sık yapılan hata budur.**
- **Çok yavaş soğutma:** İsraf; gereksiz uzun çalışır.
- **Kötü komşuluk tanımı:** "Komşu" üretme operatörü çözüm uzayında akıcı gezinmeye izin vermelidir; kötü tasarlanırsa algoritma tıkanır.
- SA **rastgeleliğe** dayanır; aynı problemde farklı çalıştırmalar farklı sonuç verir. Tekrarlanabilirlik için seed sabitlenmelidir.

---

## Genetik Algoritmalar (Genetic Algorithms)

### Tanım
**Genetik Algoritmalar (GA)**, Darwin'in doğal seçilim teorisinden esinlenen, bir **çözüm popülasyonunu** nesiller boyunca evrimleştiren yöntemlerdir. Tek bir çözüm yerine aynı anda birçok aday çözümle çalışır (populasyon tabanlı arama).

### Temel bileşenler
- **Kromozom (chromosome):** Bir çözümün kodlanmış hali (genellikle bir bit dizisi, sayı vektörü veya bir yapı).
- **Fitness fonksiyonu:** Her bireyin ne kadar iyi olduğunu ölçer.
- **Seçilim (selection):** İyi fitness'lı bireyler üremeye seçilir (örneğin tournament selection, roulette wheel).
- **Çaprazlama (crossover):** İki ebeveyn kromozom birleşerek yeni yavrular üretir; iyi özellikleri harmanlar.
- **Mutasyon (mutation):** Kromozomda küçük rastgele değişiklikler; çeşitliliği korur ve yerel optimumdan kaçmayı sağlar.
- **Elitizm (elitism):** En iyi bireylerin bir sonraki nesle doğrudan aktarılması; kaliteyi kaybetmeme sigortası.

### Çalışma döngüsü
1. Rastgele bir başlangıç popülasyonu üret.
2. Her bireyin fitness'ını hesapla.
3. İyi bireyleri seç.
4. Çaprazlama ve mutasyonla yeni nesil oluştur.
5. Durma koşuluna kadar (nesil sayısı / yeterli fitness) 2. adıma dön.

### Keşif-sömürü dengesi
GA'nın gücü **crossover (sömürü: iyi parçaları birleştirme)** ile **mutation (keşif: yeni bölgeler yoklama)** arasındaki dengedir. Mutasyon oranı çok düşükse popülasyon çeşitliliğini kaybeder ve erken yakınsar; çok yüksekse arama rastgele yürüyüşe döner ve öğrendiğini kaybeder.

### Güvenlik bağlamı: Coverage-guided fuzzing
Modern fuzzing araçlarının (AFL ailesi gibi) çekirdek mantığı, aslında **evrimsel bir arama**dır ve GA fikirlerine çok benzer:

- **Popülasyon:** İlginç girdilerin (test case) havuzu.
- **Fitness:** Bir girdinin **yeni kod yolu / yeni dal** tetikleyip tetiklemediği (code coverage). Yeni kapsama açan girdi "değerli" sayılıp havuza eklenir.
- **Mutasyon:** Girdiye bit çevirme (bit flip), byte değiştirme, blok ekleme/silme gibi operatörler uygulanır.
- **Seçilim:** Kapsama artıran girdiler önceliklendirilir; verimsizler elenir.

Böylece fuzzer, kör rastgele denemeler yerine, programın derinliklerine ulaşan girdileri "evrimle" keşfeder. GA tabanlı fuzzing özellikle **yapılandırılmış girdiler** (dosya formatları, protokoller) için crossover kullanarak geçerli ama yeni girdi kombinasyonları üretmede etkilidir.

### Tuzaklar ve yaygın hatalar
- **Erken yakınsama (premature convergence):** Bir "süper birey" popülasyonu erken domine eder, çeşitlilik ölür. Elitizm dozunu abartmak bunu tetikler.
- **Kötü kodlama (representation):** Kromozom temsili çözüm uzayını doğru yansıtmazsa crossover anlamsız yavrular üretir.
- **Fitness'ın yanlış tanımı:** Fuzzing'de sadece "çökme (crash)" sayısını fitness almak zayıftır; kapsama (coverage) çok daha zengin bir sinyaldir.
- **Fitness hesabının pahalılığı:** Her bireyi değerlendirmek maliyetliyse GA yavaşlar; paralelleştirme ve önbellekleme gerekir.

---

## Yaklaşım Algoritmaları (Approximation Algorithms)

### Tanım
Yukarıdaki sezgisellerin aksine, **yaklaşım algoritmaları** matematiksel bir **garanti** sunar. Bir algoritmanın **approximation ratio**'su (yaklaşım oranı) `ρ`, ürettiği çözümün optimal çözümden en fazla `ρ` kat kötü olacağını **kanıtlar**.

### Örnek: Vertex Cover için 2-yaklaşım
Minimum **vertex cover** (bir graftaki tüm kenarları örten en küçük düğüm kümesi) NP-zordur. Ama basit bir açgözlü (greedy) yöntem: rastgele bir kenar seç, **her iki ucunu** da çözüme ekle, o kenarlara bağlı tüm kenarları kaldır, bit. Bu algoritmanın sonucu, optimal çözümün **en fazla 2 katı** kadar büyüktür (2-approximation). Bu bir **kanıtlanmış üst sınırdır**, umut değil.

### Metaheuristic'ten farkı
- **Approximation algorithm:** "Sonuç optimalin en fazla ρ katı" diye **kanıt** verir; ama pratikte her zaman en hızlı/en iyi olmayabilir.
- **Metaheuristic (SA, GA):** Garanti **yok**, ama pratikte çoğu zaman garantili algoritmalardan bile iyi sonuç verir. Belirsizliği kabul edip performans kazanırsınız.

### Yaklaşılamazlık (inapproximability)
İlginç bir teorik gerçek: bazı problemler için, belirli bir orandan daha iyi bir yaklaşım bulmak da NP-zordur (`P ≠ NP` varsayımı altında). Örneğin genel TSP'nin sabit oranlı yaklaşımı yoktur; ancak üçgen eşitsizliğini sağlayan **metric TSP** için ünlü **Christofides algoritması** 1.5-yaklaşım verir. Bu, "her problem güzelce yaklaşılabilir" sanısına karşı önemli bir uyarıdır.

### Tuzaklar
- **Yaklaşım oranını ortalama performans sanmak:** `ρ` en kötü durum (worst-case) garantisidir; tipik girdide sonuç çok daha iyi olabilir.
- **Yanlış problem sınıfı:** Metric olmayan bir TSP'ye Christofides uygulamak geçersizdir. Garantinin dayandığı varsayımlar (üçgen eşitsizliği vb.) mutlaka sağlanmalıdır.

---

## Yöntem Seçimi: Hangi Durumda Ne Kullanmalı?

| Durum | Uygun yaklaşım |
|---|---|
| Kesin en kısa yol, iyi bir heuristic mevcut | **A*** |
| Tek çözümü hızla iyileştirmek, sürekli uzay | **Simulated Annealing** |
| Karmaşık, yapılandırılmış çözümler, paralel arama | **Genetik Algoritma** |
| Kanıtlanmış kalite garantisi şart | **Approximation algorithm** |
| Basit, hızlı, "yeterince iyi" yeter | **Hill climbing + random restart** |

Pratikte bu yöntemler **birleştirilir**: örneğin GA ile kaba bir çözüm bulup, ardından yerel arama (SA veya hill climbing) ile ince ayar yapmak yaygındır (buna **memetic algorithm** denir).

---

## Güvenlik ve Savunma Perspektifi

Bu algoritmaların güvenlik alanındaki rolü çift yönlüdür ve **savunma tarafı için de kritik** anlamlar taşır:

- **Kapsama-güdümlü fuzzing (coverage-guided fuzzing)** evrimsel bir arama olduğu için, kendi yazılımınızı **CI/CD hattında** düzenli fuzzing'e sokmak, saldırganların bulacağı girdileri onlardan önce bulmanızı sağlar. Bu, en etkili proaktif savunmalardan biridir.
- **Sembolik yürütme + bilgilendirilmiş arama**, kod tabanınızdaki ulaşılması zor hataları (deep bugs) sistematik keşfeder. Bunu güvenlik incelemesinde bir **tespit aracı** olarak kullanmak, aynı tekniğin saldırgan elindeki gücünü dengeler.
- **Tespit tarafında:** Bir hedefe karşı çalışan otomatik/evrimsel fuzzing genellikle **anormal derecede yüksek istek hacmi, hızlı ve sistematik girdi mutasyonları** ve hata/çökme yanıtlarını tetikleyen desenler üretir. Rate limiting, anormal girdi tespiti ve çökme (crash) telemetrisinin izlenmesi bu tür otomatik arama davranışlarını erken yakalamaya yardımcı olur.
- **Tasarım ilkesi:** Sisteminizin arama uzayını saldırgan için "engebeli ve pahalı" hale getirmek (girdi doğrulama, erken reddetme, deterministik olmayan yanıt maliyetleri) sezgisel aramaların fitness sinyalini zayıflatır.

Özetle: Bu algoritmalar hem saldırganın hem savunmacının araç kutusundadır. Mekanizmayı anlamak, savunmayı kurmanın ön koşuludur.

---

## Sonuç

Yaklaşık ve sezgisel optimizasyon, "mükemmelin iyi olanın düşmanı olduğu" NP-zor dünyada mühendisliğin temel taşıdır. **A*** bilgilendirilmiş ve garantili yol bulmayı, **Simulated Annealing** kontrollü rastgelelikle yerel optimumdan kaçmayı, **Genetik Algoritmalar** popülasyon evrimiyle geniş keşfi, **approximation algorithms** ise kanıtlanmış kalite sınırlarını temsil eder.

Hepsinin ortak dersi aynıdır: **keşif (exploration) ile sömürü (exploitation) arasındaki dengeyi doğru kurmak.** Bu dengeyi kaybeden her algoritma ya bir yerel optimuma sıkışır ya da rastgele yürüyüşe düşer. Bu ilkeyi kavramak, hem daha iyi optimizasyon hem de daha sağlam güvenlik tasarımı için gereken sezgiyi verir.
