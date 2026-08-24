# Hesaplama Karmaşıklığı Teorisi: P, NP, NP-Tam, NP-Zor ve İndirgemeler

## Giriş: Neden Big-O Yetmiyor

Big-O gösterimi bir algoritmanın *belirli bir çözümünün* büyüme hızını ölçer: elimizde çalışan bir algoritma varken onun kaynak tüketimini karakterize eder. Ama şu soruyu cevaplamaz: "Bu problem için verimli bir algoritma var mı, yoksa aramak boşuna mı?" Hesaplama karmaşıklığı teorisi (complexity theory) tam olarak bunu sorar — problemleri, onları çözen algoritmalardan bağımsız olarak, doğal zorluk sınıflarına ayırır.

Bu ayrım pratikte hayatidir. Bir mühendis "bu NP-tam" dediğinde aslında şunu söylüyordur: on yıllardır dünyanın en iyi araştırmacıları bu problem ailesi için polinom zamanlı (verimli, ölçeklenebilir) bir algoritma bulamadı; büyük olasılıkla da bulamayacaklar. Bu bilgi olmadan bir mühendis, çözümü olmayan bir optimizasyon problemine haftalarca "daha akıllı bir algoritma" arayarak zaman harcayabilir — oysa doğru yanıt "yaklaşık çözüm kullan" ya da "problemi kısıtla" olabilir. Güvenlik tarafında ise modern kriptografinin *tamamı* bu teori üzerine kuruludur: RSA'nın, eliptik eğri kriptografisinin güvenliği "bu matematiksel problemi tersine çözmek hesaplama açısından zor" varsayımına dayanır. Bu varsayımın ne anlama geldiğini, nereden geldiğini anlamayan biri kriptografik sistemlerin neden güvenli olduğunu da anlayamaz.

## Karar Problemleri ve Optimizasyon Problemleri Ayrımı

Karmaşıklık teorisi neredeyse her zaman **karar problemleri** (decision problems) üzerinden çalışır: cevabı sadece EVET/HAYIR olan sorular. "Bu graf 3 renkle boyanabilir mi?" bir karar problemidir. Oysa mühendislerin gerçek dünyada karşılaştığı çoğu şey **optimizasyon problemidir**: "Bu grafı en az kaç renkle boyayabilirim?", "Bu şehirleri gezen en kısa turu bul."

Bu ayrımın teknik bir nedeni var: karar problemleri matematiksel olarak temiz bir nesne sunar (bir dil, yani EVET yanıtı veren girdiler kümesi), bu da ispatları ve indirgemeleri kolaylaştırır. Ama pratik önemi de var — **optimizasyon problemi her zaman en az karşılık gelen karar problemi kadar zordur**. Eğer "gezgin satıcı turu K'den kısa mı?" sorusunu verimli çözemiyorsak, en kısa turu bulmak da en az o kadar zordur (çünkü en kısayı bulduktan sonra karar sorusuna trivially cevap verebilirsiniz). Bu yüzden mühendislik pratiğinde "TSP NP-zor" dediğimizde, hem karar hem optimizasyon versiyonunu kastediyoruz; ama ispat aparatı karar versiyonu üzerinden kurulur.

Pratik çıkarım: bir optimizasyon probleminin NP-zor olup olmadığını değerlendirirken önce onu bir karar problemine indirgeyin ("çözüm K eşiğini geçiyor mu?"). Eğer bu karar problemi bilinen NP-tam bir problemden indirgenebiliyorsa, optimizasyon versiyonu için de polinom zamanlı tam çözüm beklemeyin.

## P Sınıfı: "Verimli Çözülebilir"

**P**, deterministik bir Turing makinesiyle **polinom zamanda** (girdi boyutu n için O(n^k), sabit k) çözülebilen karar problemlerinin kümesidir. Sıralama (O(n log n)), en kısa yol (Dijkstra, O(E log V)), asal sayı testi (AKS algoritması ile polinom zamanda kanıtlanmıştır) hep P içindedir.

P'nin "verimli" ile eşleştirilmesi bir kurumsal sözleşmedir, matematiksel bir zorunluluk değil — n^100 de teknik olarak polinomdur ve pratikte kullanılamaz. Ama gözlemsel olarak, doğal problemlerin polinom zamanlı algoritmaları neredeyse hep küçük derecelidir (n, n log n, n^2, n^3). Bu yüzden "P içinde" pratikte "ölçeklenebilir" anlamına gelir; büyüme oranı girdi büyüdükçe patlamaz.

**Kök neden / çalışma mantığı**: P'nin önemi, polinomların kompozisyon altında kapalı olmasından gelir. Bir polinom zamanlı algoritmanın alt rutini olarak başka bir polinom zamanlı algoritma çağırırsanız, toplam yine polinomdur. Bu, P'yi *bileşim altında kararlı* (robust) bir sınıf yapar — donanım hızından, programlama dilinden, makine modelinden bağımsız bir soyutlama seviyesinde "verimlilik" tanımlar (Cobham-Edmonds tezi).

## NP Sınıfı: "Doğrulaması Verimli"

**NP** (Nondeterministic Polynomial Time), bir EVET cevabının **verilen bir tanık/sertifika (certificate) ile polinom zamanda doğrulanabildiği** karar problemleri kümesidir. Kritik nokta: NP, "verimli çözülebilir" değil, "**çözüm önerildiğinde verimli doğrulanabilir**" demektir.

Örnek: "Bu graf Hamilton devri içeriyor mu?" sorusunda, biri size bir vertex sırası (tanık) verirse, bu sıranın gerçekten geçerli bir Hamilton devri olup olmadığını polinom zamanda (kenarları tek tek kontrol ederek) doğrularsınız. Ama devri *bulmak* (aday sırayı üretmek) zor olabilir — tüm permütasyonları denemek üstel zaman alır.

**Kök neden**: NP tanımının "nondeterministic" kısmı tarihseldir — bir nondeterministik Turing makinesi, her adımda tüm olası dalları "aynı anda" (paralel evrenlerde) deneyip herhangi biri kabul ederse kabul eder şeklinde tanımlanır. Bu, "doğru tanığı tahmin et, sonra doğrula" ile matematiksel olarak eşdeğerdir. Bu yüzden NP = "polinom zamanda doğrulanabilir tanığı olan problemler."

Açıkça P ⊆ NP: eğer bir problemi polinom zamanda çözebiliyorsanız, tanığa hiç ihtiyacınız yok, doğrulama otomatik geçer (ya da problemi baştan çözüp cevabı kontrol edersiniz). Sorunun özü, bu içermenin **kesin** (P = NP) mi yoksa **kesin** (P ≠ NP) mi olduğudur — ve bu, bilgisayar biliminin çözülmemiş en büyük problemidir (Clay Matematik Enstitüsü'nün Milenyum Ödülü problemlerinden biri).

**Yaygın yanlış anlama**: "NP" = "Not Polynomial" (polinom olmayan) değildir. Bu çok yaygın bir hatadır. NP, P'yi *içeren* bir sınıftır, P'nin *zıddı* değildir. NP dışındaki problemler (örneğin karar verilemez problemler, ya da EXPTIME-tam problemler) çok daha zordur.

## NP-Tam: NP'nin En Zor Problemleri

Bir problem **NP-tam** (NP-complete) ise:
1. NP içindedir (çözüm önerildiğinde polinom zamanda doğrulanabilir), **VE**
2. NP içindeki **her** problem ona polinom zamanda indirgenebilir (NP-hard).

İkinci koşul şu demektir: eğer NP-tam bir problemi polinom zamanda çözebilseydiniz, NP içindeki *her* problemi de polinom zamanda çözebilirdiniz (indirgeme + o çözücüyü kullanarak). Bu yüzden NP-tam problemler NP'nin "en zor" temsilcileridir — biri düşerse (polinom zamanda çözülürse) hepsi düşer, yani P = NP olur.

**Cook-Levin Teoremi (1971)**, ilk NP-tam problemi kanıtladı: **Boolean Satisfiability (SAT)** — bir Boolean formülünün onu doğru yapan bir değişken ataması olup olmadığı. İspatın özü: herhangi bir NP problemi için, "polinom zamanlı doğrulayıcı çalıştırıldığında kabul eder" ifadesini, o doğrulayıcının çalışmasını simüle eden dev bir Boolean formülüne kodlayabilirsiniz (Turing makinesinin her adımını, her hücresini, her geçişini formül değişkenleri ve kısıtlarıyla temsil ederek). Bu, hesaplamanın kendisinin bir SAT örneğine "derlenebileceğini" gösterir — yani SAT, hesaplamanın evrensel bir dilidir.

Cook-Levin'den sonra, SAT'tan **polinom zamanlı indirgemeler** zinciriyle yüzlerce başka problem NP-tam olarak kanıtlandı: 3-SAT, Vertex Cover, Clique, Hamilton Devri, Gezgin Satıcı Problemi (karar versiyonu), Graf Boyama, Knapsack (karar versiyonu, 0/1), Subset Sum.

### İndirgeme Tekniği: Nasıl Çalışır

Bir problem A'nın NP-tam olduğunu kanıtlamak için standart tarif:

1. **A ∈ NP olduğunu göster**: bir tanık verilince polinom zamanda doğrulanabildiğini göster (genelde kolay kısım).
2. **Bilinen bir NP-tam problem B seç** (SAT, 3-SAT, Vertex Cover gibi).
3. **B'den A'ya polinom zamanlı bir indirgeme (B ≤_p A) kur**: B'nin herhangi bir örneğini, A'nın bir örneğine, öyle bir şekilde dönüştüren bir fonksiyon f tanımla ki, B örneği EVET ise f(örnek) A içinde EVET, B örneği HAYIR ise f(örnek) A içinde HAYIR olsun. Bu dönüşümün kendisi polinom zamanda hesaplanabilmeli.

Bu üçüncü adım işin kalbidir ve genelde bir "gadget" (yapı taşı) inşası gerektirir: B'nin her bileşenini (örneğin bir SAT formülünün her klozunu), A'nın diline (örneğin bir grafın kenarlarına) çeviren yerel bir yapı tasarlarsınız, sonra bu yapıların doğru şekilde birleştiğinde global çözümün korunduğunu kanıtlarsınız.

**Neden bu mantıklı**: Eğer B ≤_p A ve A polinom zamanda çözülebiliyorsa, B'yi şöyle çözersiniz: girdiyi f ile dönüştür (polinom zaman), A çözücüsüne ver (polinom zaman), cevabı doğrudan kullan. Toplam yine polinom zaman — yani B de P içinde olurdu. Kontrpozitif olarak: B'nin P içinde olmadığını biliyorsak (ya da NP-tam olduğu için P içinde olmadığına inanıyorsak), A da P içinde olamaz (aksi halde B de olurdu). **İndirgeme yönü kritiktir**: zorluğu bilinenden bilinmeyene taşırsınız, tersi değil. Yeni problemi eski (zor olduğu bilinen) probleme indirgersiniz — eski problemi yeniye değil.

Bu, birçok yeni mezunun karıştırdığı noktadır: "A'yı B'ye indirgedim, B NP-tam, o yüzden A NP-tam" mantığı **yanlıştır**. Doğrusu: bilinen NP-tam problemi *yeni probleminize* indirgemeniz gerekir (B ≤_p A), tersi değil.

## NP-Zor: Doğrulama Şartı Olmadan Zorluk

**NP-zor (NP-hard)**, NP-tam tanımının sadece ikinci koşulunu taşıyan, ama NP içinde olması *gerekmeyen* problemler kümesidir. Yani bir problem NP-zor ise, NP'deki her problem ona indirgenebilir — ama problemin kendisi NP'de bile olmayabilir (örneğin karar verilemez olabilir, ya da NP'den çok daha zor bir sınıfta olabilir).

Klasik örnek: **Gezgin Satıcı Problemi'nin optimizasyon versiyonu** ("en kısa turu bul", karar versiyonu değil) NP-zordur ama NP'de değildir — çünkü "bu tur en kısasıdır" iddiasını polinom zamanda doğrulamanın bilinen bir yolu yoktur (her turu tek tek karşılaştırmadan). Başka bir örnek: **Durma Problemi** (Halting Problem) NP-zordur (aslında NP-tam problemlerden çok daha zordur — karar verilemezdir), ama NP'de değildir çünkü hiçbir tanıkla polinom zamanda doğrulanamaz, algoritma sonsuza dek çalışabilir.

**Pratik ayrım tablosu**:
- **NP-tam** = NP-zor ∩ NP (hem zor hem doğrulanabilir)
- **NP-zor** = en az NP kadar zor olan her şey (doğrulanabilirlik şartı yok)

Bir mühendisin "bu problem NP-zor" dediğini duyduğunuzda, "kesin çözüm bulmak pratik değil" demektir; "NP-tam" dediğinde ek olarak "ama bir çözüm önerilirse hızlıca kontrol edebilirim" demektir.

## P = NP Sorusu ve Neden Önemli

P = NP mi sorusu şunu sorar: **her verimli doğrulanabilen problem, aynı zamanda verimli çözülebilir mi?** Sezgisel olarak hayır gibi görünür — bir Sudoku çözümünü kontrol etmek, çözümü bulmaktan çok daha kolaydır. Ama bu sezgi 50 yılı aşkın süredir kanıtlanamadı.

Eğer **P = NP** kanıtlanırsa (yani birileri herhangi bir NP-tam problem için polinom zamanlı algoritma bulursa), sonuçlar devrim niteliğinde olurdu: tüm NP-tam problemler (dolayısıyla NP'deki her şey) polinom zamanda çözülebilir hale gelirdi — çünkü hepsi birbirine indirgenebilir. Bu, optimizasyon, lojistik, ilaç tasarımı gibi alanlarda muazzam kazanımlar getirirdi, ama **modern kriptografinin çoğunu da çökertirdi** (aşağıda detaylandırılıyor).

Çoğu araştırmacı **P ≠ NP** olduğuna inanır (kanıtlanmamış olsa da), çünkü on binlerce farklı NP-tam problem üzerinde onlarca yıllık yoğun araştırmaya rağmen hiçbiri için polinom zamanlı algoritma bulunamadı. Bu, kesin bir kanıt değil ama güçlü bir ampirik kanıttır.

## Kriptografi Bağlantısı: One-Way Fonksiyonlar ve NP-Zorluk Varsayımları

Bu, güvenlik mühendisliği için en kritik bağlantıdır. Modern kriptografinin (RSA, Diffie-Hellman, eliptik eğri kriptografisi) güvenliği, **tek yönlü fonksiyonların** (one-way functions) var olduğu varsayımına dayanır: hesaplaması kolay ama tersine çevirmesi (hesaplama açısından) zor fonksiyonlar.

**Kök neden — neden bu işe yarıyor**: RSA'da açık anahtar, iki büyük asal sayının çarpımı olan N = p × q sayısıdır. N'yi hesaplamak (p ve q biliniyorsa) polinom zamanda trivialdir — direkt çarpma. Ama N verildiğinde p ve q'yu geri bulmak (**asal çarpanlara ayırma / integer factorization**) bilinen hiçbir klasik algoritma ile polinom zamanda yapılamıyor; en iyi bilinen algoritmalar (Genel Sayı Alanı Eleği gibi) alt-üstel zamanda çalışır. Diffie-Hellman ve eliptik eğri kriptografisi benzer şekilde **ayrık logaritma probleminin** zorluğuna dayanır: g^x mod p hesaplamak kolay, ama sonuçtan x'i (üssü) geri çıkarmak zor.

Burada önemli bir teknik ayrıntı var: **asal çarpanlara ayırma ve ayrık logaritma, NP-tam olduğu bilinen problemler DEĞİLDİR**. Aslında ikisi de NP ∩ co-NP içindedir (hem EVET hem HAYIR cevapları verimli doğrulanabilir), ki bu NP-tam problemler için beklenmeyen bir özelliktir (eğer NP-tam bir problem NP ∩ co-NP'de olsaydı, bu NP = co-NP anlamına gelirdi, ki bu da beklenmedik bir sonuç olurdu). Bu yüzden kriptografik güvenlik, "P ≠ NP" varsayımından değil, daha **spesifik ve daha güçlü** varsayımlardan gelir: "bu belirli problem (çarpanlara ayırma, ayrık log) klasik bilgisayarlarda polinom zamanda çözülemez." P ≠ NP kanıtlansa bile, bu otomatik olarak RSA'yı güvenli yapmaz; P = NP kanıtlansa bile (ki bu felaket olurdu), RSA'nın kırılabileceğinin garantisi olurdu ama pratik bir algoritma anlamına gelmezdi (kanıt yapıcı/non-constructive olabilir). Bu ayrımı karıştırmak yaygın bir kavramsal hatadır: **"P ≠ NP kriptografiyi güvenli kılar" demek yanlıştır** — kriptografi çok daha dar ve spesifik hesaplamsal zorluk varsayımlarına dayanır.

**Kuantum bilgisayarların etkisi**: Shor algoritması, asal çarpanlara ayırma ve ayrık logaritmayı **kuantum bilgisayarda polinom zamanda** çözer. Bu NP-tamlık ile ilgisiz bir sonuçtur — bu problemler zaten NP-tam değildi, sadece klasik bilgisayarda zor olduğu varsayılıyordu. Bu yüzden post-kuantum kriptografi, **kafes problemleri (lattice problems)** gibi hem klasik hem kuantum bilgisayarlarda zor olduğu düşünülen farklı matematiksel yapılara kaymaktadır. Bir güvenlik mühendisinin çıkarması gereken ders: kriptografik güvenlik her zaman **belirli bir hesaplama modeli altında belirli bir problemin zorluğu varsayımına** dayanan, kanıtlanmamış ama ampirik olarak desteklenmiş bir bahistir; matematiksel kesinlik değildir.

## Doğru Kullanım, Tuzaklar, En İyi Pratikler

**Doğru kullanım — bir problemle karşılaştığınızda sorulacak sorular**:
1. Bu bir karar problemi mi, optimizasyon problemi mi? Optimizasyonsa, karar versiyonuna indirgeyerek analiz kolaylaştırılabilir.
2. Bilinen bir NP-tam probleme benziyor mu (yapısal olarak)? Vertex cover, set cover, graf boyama, knapsack gibi "kalıp" problemlere benzeyen yeni problemler genelde de NP-zordur.
3. Eğer NP-zorsa, gerçekten kesin çözüm mü gerekiyor, yoksa yaklaşık/sezgisel bir çözüm kabul edilebilir mi? (Yaklaşım algoritmaları, sezgisel yöntemler — genetik algoritmalar, simulated annealing —, ya da girdi boyutunu pratikte küçük tutan kısıtlamalar genelde asıl mühendislik çözümüdür.)
4. Girdi boyutu pratikte gerçekten büyük mü? Küçük sabit girdilerde üstel algoritmalar bile kabul edilebilir olabilir (parametrized complexity / sabit-parametre izlenebilirlik burada devreye girer).

**Yaygın hatalar**:
- **"NP-tam = imkansız" demek**: Yanlış. NP-tam, *en kötü durumda garantili verimli genel algoritma yok* demektir. Özel yapıdaki girdiler (örneğin ağaç yapılı graflar, sınırlı boyutlu girdiler) için polinom zamanlı özel algoritmalar sıkça vardır.
- **NP-zor ile NP-tam'ı karıştırmak**: NP-zor daha geniş bir kümedir, NP üyeliği gerektirmez.
- **İndirgeme yönünü ters çevirmek**: Yeni problemi NP-tam bir probleme indirgemek (kolay yön) ile NP-tam problemi yeni probleme indirgemek (zorluk kanıtlayan yön) birbirine karıştırılır.
- **"P ≠ NP kriptografiyi kanıtlar" demek**: Yukarıda açıklandığı gibi, kriptografi çok daha spesifik varsayımlara dayanır.
- **Yaklaşım algoritmalarını "yanlış" sanmak**: NP-zor bir problem için %100 optimal olmayan ama garanti edilmiş bir yaklaşım oranı sunan algoritma (örneğin Vertex Cover için 2-yaklaşım) genelde doğru mühendislik yanıtıdır, "yenilgi" değildir.

**En iyi pratikler**:
- Yeni bir zorlu problemle karşılaştığınızda, önce literatürde benzer bir NP-tam probleme indirgeme olup olmadığını araştırın (çoğu pratik kombinatorik problem zaten kataloglanmıştır — Garey & Johnson'ın klasik NP-tamlık kataloğu hâlâ referans niteliğindedir).
- Güvenlik değerlendirmesi yaparken "bu algoritma NP-zor bir probleme dayanıyor, o yüzden güvenli" demek yerine, hangi *spesifik* problemin (RSA için çarpanlara ayırma, ECC için eliptik eğri ayrık logaritması) hangi *spesifik* saldırı modeline (klasik, kuantum) karşı ne kadar süredir kırılmadan durduğuna bakın.
- Karmaşıklık sınıflandırmasını erken yapın: bir sistemi tasarlarken "bu alt problemi tam çözecek miyiz yoksa yaklaşık mı çözeceğiz" kararını mimari aşamada verin, kodlama sırasında değil.

## Özet

P, bir problemin *verimli çözülebilirliğini*; NP, bir çözümün *verimli doğrulanabilirliğini* tanımlar. NP-tam problemler, NP'nin en zor üyeleridir ve birbirlerine polinom zamanlı indirgemelerle bağlıdır — biri düşerse hepsi düşer. NP-zor, doğrulanabilirlik şartı olmadan en az o kadar zor olan her şeyi kapsar. P = NP sorusu hâlâ açık, ama pratik mühendislik kararları (yaklaşım algoritması mı kullanılır, problem nasıl kısıtlanır) bu sınıflandırmaya dayanır. Kriptografik güvenlik ise NP-tamlıktan değil, çarpanlara ayırma ve ayrık logaritma gibi *spesifik* problemlerin klasik (ve mümkünse kuantum) bilgisayarlarda zor olduğuna dair ampirik, kanıtlanmamış ama uzun süredir sınanmış varsayımlardan gelir — bu ayrımı net tutmak, hem doğru mühendislik kararları hem doğru güvenlik değerlendirmesi için şarttır.
