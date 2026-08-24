# Temiz Kod ve Refactoring: İsimlendirme, Coupling/Cohesion, DRY/KISS/YAGNI ve Teknik Borç

## Giriş: "Temiz Kod" Neyi Çözer?

Yazılım geliştirmenin en yaygın yanılgısı, kodun bir defa yazılıp bittiği düşüncesidir. Gerçekte kod bir defa yazılır ama onlarca, yüzlerce defa **okunur**. Bir fonksiyona altı ay sonra geri dönen kişi çoğu zaman kendinizsiniz ve o an, geçmişteki kendinizin bıraktığı ipuçlarına muhtaç kalırsınız. Temiz kodun (clean code) asıl derdi estetik değil, **okunabilirlik yoluyla değişim maliyetini düşürmektir**. Bir sistemin yaşam boyu maliyetinin büyük kısmı ilk yazımda değil, sonraki bakım (maintenance) ve genişletme aşamalarında ortaya çıkar. Dolayısıyla temiz kod bir lüks değil, ekonomik bir zorunluluktur.

Refactoring ise bu bakımı mümkün kılan disiplindir: **kodun dış davranışını (external behavior) değiştirmeden iç yapısını iyileştirmek.** Buradaki kilit kısıt "dış davranışı değiştirmeden" ifadesidir. Refactoring, yeni özellik eklemek değildir; hata düzeltmek değildir. Sadece yapıyı sağlamlaştırmaktır. Bu ayrımı kaybettiğinizde "refactoring yapıyorum" diyerek aslında gizlice davranış değiştiren, test edilmemiş, kontrolsüz bir yeniden yazıma (rewrite) sürüklenirsiniz. İyi refactoring, küçük ve davranışı koruyan adımların üst üste konmasıyla ilerler; her adımdan sonra testler yeşil kalır.

Bu makale dört eksende ilerliyor: isimlendirme, coupling/cohesion, DRY/KISS/YAGNI prensipleri ve teknik borç (technical debt). Bunlar birbirinden bağımsız konular gibi görünse de tek bir eksene bağlanır: **bilişsel yük (cognitive load) yönetimi.** İyi kod, okuyanın kafasında aynı anda tutması gereken bilgi miktarını azaltan koddur.

## İsimlendirme: En Ucuz ve En Güçlü Belgeleme

### Neden İsimlendirme Bu Kadar Önemli?

İsimlendirmenin bilgisayar bilimlerinin en zor iki probleminden biri sayılması bir espri değil, gözlemsel bir gerçektir. Bir değişkene, fonksiyona veya sınıfa isim vermek, aslında o şeyin **ne olduğuna, ne işe yaradığına ve sınırlarının nerede bittiğine** dair bir karar vermektir. İsim kötüyse, okuyan kişi ismin yalanını doğrulamak için gövdeye (implementation) inmek zorunda kalır. İşte bilişsel yükün asıl kaynağı budur: **isim bir soyutlama sözü verir, gövde bu sözü tutmak zorundadır.**

Kök nedene inersek: bir isim, o kimliğe erişen herkesin zihninde bir zihinsel model kurar. `d` gibi bir isim hiçbir model kurmaz; `elapsedTimeInDays` ismi ise hem büyüklüğü (süre), hem birimi (gün), hem de anlamı (geçen zaman) tek başına taşır. İkinci durumda okuyan kişi yorumlama yapmak zorunda kalmaz, tahmin etmez, doğrular.

### Somut Örnekler

Kötü isimlendirmeye tipik bir örnek:

```python
def calc(l, t):
    r = []
    for x in l:
        if x.s > t:
            r.append(x)
    return r
```

Bu kodu anlamak için her satırı okumak, `l`, `t`, `x`, `s`, `r`'nin ne olduğunu kafanızda tutmak gerekir. Aynı mantık, isimler düzeltildiğinde neredeyse yorum gerektirmeyecek hale gelir:

```python
def yuksek_puanli_ogrencileri_filtrele(ogrenciler, esik_puan):
    kalanlar = []
    for ogrenci in ogrenciler:
        if ogrenci.puan > esik_puan:
            kalanlar.append(ogrenci)
    return kalanlar
```

İkinci versiyonda fonksiyonun adı bir cümle gibi okunur, parametreler kendini açıklar ve gövde yalnızca ismin verdiği sözü doğrular. Kod aynı işi yapar, ama okuyanın zihninde çok daha az yer kaplar.

### İsimlendirmede İlkeler ve Tuzaklar

**Niyeti açıklayan isimler seçin.** Bir isim "ne yapıyor" değil, "neden var" sorusuna cevap vermeli. `flag` yerine `odemeAlindiMi`; `list2` yerine `bekleyenSiparisler` gibi.

**İsim uzunluğu kapsamla orantılı olmalı.** Bir `for` döngüsünde tek satır ömrü olan bir sayaç için `i` tamamen kabul edilebilir; çünkü tanımı ile kullanımı arasındaki mesafe göz alabildiği kadardır. Ama sınıf düzeyinde, yüzlerce satır boyunca yaşayan bir alanın (field) tek harfli olması affedilmez. **Kısa isimler kısa ömürler içindir.**

**Boolean isimleri bir soru veya iddia gibi okunmalı.** `active` belirsizdir; `isActive` veya `aktifMi` niyetini net verir. Bu, `if` bloklarının doğal dile yakın okunmasını sağlar.

**Gürültü kelimelerinden kaçının.** `UserData`, `UserInfo`, `UserObject` gibi isimler `User`'a hiçbir bilgi katmaz. `Manager`, `Processor`, `Helper` gibi son ekler çoğu zaman sınıfın aslında ne yaptığını gizler; bir sınıfa iyi isim bulamıyorsanız bu genellikle o sınıfın **çok fazla iş yaptığının** (düşük cohesion) işaretidir. İsimlendirme zorluğu, çoğu zaman tasarım probleminin belirtisidir.

**Yanıltıcı isimlerden kaçının.** `accountList` diye adlandırdığınız şey gerçekte bir liste değil de bir küme (set) veya sözlük (map) ise, isim yalan söyler. En kötü isim, yanlış olandır — çünkü okuyan ona güvenir.

**Tutarlı bir sözlük kullanın.** Aynı kavram için bazen `getir`, bazen `al`, bazen `oku` kullanmak okuyanı bunların farklı şeyler olduğunu sanmaya iter. Tek bir kavram, tek bir kelime.

## Coupling ve Cohesion: İyi Tasarımın İki Kutbu

### Tanımlar ve Kök Mantık

**Coupling (bağımlılık/kenetlenme)**, iki modülün birbirine ne kadar bağlı olduğunun ölçüsüdür. **Cohesion (yapışkanlık/uyum)** ise bir modülün içindeki parçaların birbiriyle ne kadar ilişkili, tek bir amaca ne kadar odaklı olduğunun ölçüsüdür. İyi tasarımın altın kuralı tek cümleyle özetlenir: **düşük coupling, yüksek cohesion.**

Bu kural neden bu kadar merkezi? Çünkü değişimin doğasıyla ilgilidir. Bir yazılımda değişiklik yapmanın maliyeti, o değişikliğin **kaç yere yayıldığıyla** doğru orantılıdır. Coupling yüksekse, bir modülü değiştirdiğinizde ona bağlı diğer modüller de kırılır; değişiklik dalga dalga yayılır. Buna "shotgun surgery" (saçma tüfek ameliyatı) denir: tek bir mantıksal değişiklik için onlarca dosyaya dokunmak zorunda kalırsınız. Cohesion düşükse, bir modül birbiriyle alakasız işleri barındırır; onu anlamak için hepsini birden zihninize almanız gerekir ve bir kısmını değiştirmek, alakasız bir kısmını yanlışlıkla bozma riskini artırır.

Kök neden şudur: **insan zihni yerelleştirilmiş (localized) düşünmeyi sever.** Bir problemi çözerken sadece ilgili parçaya bakabilmek isteriz. Yüksek cohesion ilgili şeyleri bir araya toplayarak bunu mümkün kılar; düşük coupling ise bir parçaya bakarken diğerlerini görmezden gelebilmemizi sağlar. Bu ikisi birlikte, sistemi zihinsel olarak **parçalara ayırıp ayrı ayrı ele alabilme** yeteneği verir. Modülerliğin tüm amacı budur.

### Coupling Türleri ve Somut Bir Örnek

Coupling'in derecesi vardır. En kötüsü, bir modülün başka bir modülün iç detaylarına (private alanlarına, iç yapısına) doğrudan erişmesidir. En iyisi ise modüllerin sadece iyi tanımlanmış, dar bir arayüz (interface) üzerinden konuşmasıdır.

Yüksek coupling örneği:

```python
class SiparisRaporu:
    def toplam_hesapla(self, siparis):
        toplam = 0
        # Siparis'in ic yapisina dogrudan dalıyor
        for i in range(len(siparis.kalemler)):
            toplam += siparis.kalemler[i].fiyat * siparis.kalemler[i].adet
        return toplam
```

Burada `SiparisRaporu`, `Siparis` sınıfının iç yapısını (kalemlerin bir liste olduğunu, her kalemin `fiyat` ve `adet` alanı taşıdığını) biliyor. `Siparis` sınıfı iç yapısını değiştirdiği anda `SiparisRaporu` kırılır. Sorumluluk yanlış yerdedir: toplam hesaplamak `Siparis`'in kendi işidir.

Düşük coupling versiyonu:

```python
class Siparis:
    def toplam_tutar(self):
        return sum(kalem.ara_toplam() for kalem in self._kalemler)

class SiparisRaporu:
    def yazdir(self, siparis):
        print(f"Toplam: {siparis.toplam_tutar()}")
```

Şimdi `SiparisRaporu` yalnızca `toplam_tutar()` arayüzünü bilir. `Siparis` iç yapısını istediği gibi değiştirebilir; arayüz aynı kaldığı sürece rapor etkilenmez. Bu, "Tell, Don't Ask" (Söyle, Sorma) prensibinin uygulanışıdır: nesneden verisini alıp dışarıda işlem yapmak yerine, nesneye işi yaptırın.

### Tuzaklar ve İyi Pratikler

**Gizli coupling en tehlikelisidir.** İki modül aynı global değişkeni, aynı veritabanı tablosunu veya aynı dosya formatını paylaşıyorsa, aralarında kodda görünmeyen ama gerçek bir bağ vardır. Birini değiştirdiğinizde diğerinin sessizce bozulması bu yüzdendir. Paylaşılan durumu (shared mutable state) mümkün olduğunca azaltmak, coupling'i azaltmanın en etkili yollarından biridir.

**Yüksek cohesion, tek sorumluluk demektir.** Bir sınıf hem veritabanına yazıyor, hem HTML üretiyor, hem de iş kuralı doğruluyorsa, bu üç farklı değişim ekseni tek bir yerde toplanmış demektir. Veritabanı şeması değişince, arayüz değişince ve iş kuralı değişince hep aynı sınıfa dokunursunuz. Bunları ayırmak, her birinin bağımsız değişebilmesini sağlar. Bu, Single Responsibility Principle'ın (Tek Sorumluluk İlkesi) özüdür: **bir sınıfın değişmek için tek bir nedeni olmalı.**

**Ama aşırıya kaçmayın.** Her şeyi ayırmak, aşırı parçalanmaya yol açar; artık basit bir işi anlamak için on dosya arasında zıplamak gerekir. Bu da bir tür maliyettir. Coupling ve cohesion, mutlak değil dengelenecek büyüklüklerdir. Birbiriyle gerçekten sıkı ilişkili şeyler zaten bir arada durmalıdır — onları zorla ayırmak sahte bir modülerlik yaratır.

## DRY, KISS ve YAGNI: Prensiplerin İnce Ayarı

Bu üç kısaltma, temiz kodun en çok tekrarlanan ama en çok yanlış anlaşılan sloganlarıdır. Her biri güçlü bir sezgi taşır; ama her biri, körü körüne uygulandığında zarar verir. Bu yüzden asıl mesele bunları ezberlemek değil, **ne zaman geçerli olduklarını** anlamaktır.

### DRY (Don't Repeat Yourself) — Kendini Tekrarlama

DRY sıklıkla "aynı kodu iki kere yazma" olarak özetlenir, ama bu tanım yüzeyseldir ve tehlikelidir. Prensibin özgün ifadesi şudur: **her bilgi parçasının sistemde tek, kesin ve yetkili bir temsili olmalıdır.** DRY kod tekrarıyla değil, **bilgi tekrarıyla** ilgilidir.

Fark şurada kritik: iki kod bloğu tesadüfen birbirine benziyor diye onları birleştirmek DRY değildir. Eğer bu iki blok aynı iş kuralını temsil ediyorsa ve kural değiştiğinde ikisinin de birlikte değişmesi gerekiyorsa, birleştirmek doğrudur. Ama iki blok **farklı nedenlerle** var olmuş, tesadüfen benzer görünüyorsa, onları birleştirmek yanlış bir coupling yaratır. Gelecekte biri değişmesi gerektiğinde diğeri de değişmek zorunda kalır ve o noktada acı verici bir şekilde ayırmanız gerekir.

Buna "yanlış DRY" veya erken soyutlama denir. Deneyimli bir gözlem şudur: **yanlış soyutlama, biraz tekrardan daha pahalıdır.** İki kez benzer kod görünce hemen ortak bir fonksiyona çıkarmak yerine, üçüncü tekrarı beklemek çoğu zaman daha sağlıklıdır ("Rule of Three"). Üçüncü tekrarda, gerçekten ortak olan neyse o netleşir; ikinci tekrarda ise henüz genellemeyi yanlış yapma riski yüksektir.

Somut örnek: Diyelim ki bir yerde çalışanların, başka bir yerde tedarikçilerin adres doğrulaması var ve kod benzer. Bugün aynı görünüyorlar. Ama yarın çalışan adresi için farklı bir kural (örneğin ülke içi zorunluluğu), tedarikçi için başka bir kural gerekebilir. Bunlar aynı bilgi değil, sadece bugün aynı şekle sahip iki farklı bilgi. Erken birleştirirseniz, ayrışma günü geldiğinde `if tur == "calisan"` gibi parametrelerle şişen, okunması güç bir fonksiyon elde edersiniz.

### KISS (Keep It Simple, Stupid) — Basit Tut

KISS, en basit çalışan çözümü tercih etmeyi söyler. Kök mantığı şudur: karmaşıklık, hata için yüzey alanıdır. Her ekstra dallanma (branch), her ekstra soyutlama katmanı, her "akıllıca" numara, hem yeni hata olasılığı hem de yeni bilişsel yük getirir.

Buradaki tuzak, karmaşıklığı zekâyla karıştırmaktır. Genç geliştiriciler sıklıkla karmaşık, "gösterişli" çözümlerin daha yetkin olduğunu sanır. Gerçekte usta işi, karmaşık bir problemi **basit görünecek** kadar iyi anlamış olmaktır. Bir zincirleme ternary ifadesi veya iç içe üç seviye lambda, "zeki" değil, çoğu zaman sadece okunması zor demektir. Aynı işi yapan düz bir `if-else` bloğu, altı ay sonra kodu okuyan için hediye gibidir.

KISS ile DRY bazen çatışır. Tekrarı yok etmek için kurduğunuz soyutlama, sistemi anlamayı zorlaştırıyorsa, biraz tekrar pahasına basitliği korumak daha akıllıcadır. Basitlik, çoğu durumda tekrarsızlıktan daha değerlidir; çünkü kodun asıl maliyeti anlaşılmasındadır.

### YAGNI (You Aren't Gonna Need It) — Buna İhtiyacın Olmayacak

YAGNI, "belki ileride lazım olur" diye şu an gerekmeyen özellik, soyutlama veya esneklik eklememeyi söyler. Kök mantık ekonomiktir: gelecekte lazım olacağını **tahmin ettiğiniz** şeylerin çoğu ya hiç lazım olmaz, ya da lazım olduğunda tahmin ettiğinizden farklı bir şekle bürünür. Bu arada eklediğiniz "esnek" altyapı bugünden itibaren bakım maliyeti, karmaşıklık ve hata yüzeyi yaratır.

En yaygın YAGNI ihlali, gelecekteki hayali gereksinimler için genelleştirilmiş, konfigüre edilebilir, "her şeyi yapabilen" soyutlamalar kurmaktır. "Belki ileride birden fazla veritabanı destekleriz" diye kurduğunuz soyutlama katmanı, tek veritabanıyla çalıştığınız iki yıl boyunca sadece yol gösteren değil, yolu tıkayan bir engel olur. İhtiyaç gerçekten doğduğunda, o zamanki gerçek gereksinime göre tasarım yapmak, bugünden tahmine göre yapmaktan neredeyse her zaman daha iyidir.

YAGNI'nin ince yanı şudur: **geri dönülmez kararlarda geçerli değildir.** Veri şeması, genel API kontratları, güvenlik temelleri gibi sonradan değiştirmenin çok pahalı olduğu alanlarda öngörülü olmak gerekir. YAGNI, ucuza ertelenebilir kararlar için bir rehberdir; pahalı ve kalıcı kararlar için değil. "Sonradan eklemesi kolay mı?" sorusu, YAGNI'yi uygulayıp uygulamayacağınızın turnusol testidir.

## Teknik Borç: Metaforu Doğru Anlamak

### Tanım ve Metaforun Gücü

Teknik borç (technical debt) metaforu, finansal borçtan ödünç alınmıştır ve bu benzetme derinlemesine doğrudur. Bir işi hızlıca ama kusurlu şekilde yaparsanız, bugün zaman kazanırsınız (borç alırsınız), ama bu kusur her dokunuşta size **faiz** olarak geri döner: her yeni özellik daha yavaş eklenir, her hata düzeltmesi daha risklidir. Faiz ödemeye devam eder ama borcu (kusuru düzeltmeyi) hiç yapmazsanız, bir noktada gelirinizin tamamı faize gider — yani tüm zamanınız borcu çevirmeye harcanır, yeni değer üretemezsiniz.

Metaforun asıl gücü, **teknik borcun her zaman kötü olmadığını** kabul etmesidir. Tıpkı finansal borç gibi, bilinçli alınan bir teknik borç akıllıca olabilir. Bir ürünü pazara yetiştirmek için geçici bir kısayol almak, o pazar penceresini kaçırmaktan iyidir — **eğer** borcun farkındaysanız ve geri ödeme planınız varsa. Sorun borç almakta değil, **görünmez ve plansız** borçtadır.

### Teknik Borcun Dört Çeyreği

Teknik borcu ayırt etmenin yaygın bir yolu, iki eksende düşünmektir: kasıtlı mı kazara mı, ve sağduyulu mu pervasız mı?

- **Kasıtlı ve sağduyulu:** "Bu tasarımın ideal olmadığını biliyoruz, ama son teslim tarihine yetişmek için şimdilik böyle bırakıyoruz; sürüm sonrası düzelteceğiz." Bu, en sağlıklı borç türüdür — bilinçli bir mühendislik kararıdır.
- **Kasıtlı ve pervasız:** "Test yazmaya vaktimiz yok, atlayalım." Sonucun bilincinde ama sorumsuz.
- **Kazara ve sağduyulu:** "Şimdi anlıyoruz ki daha iyi bir tasarım varmış." Ekip öğrendikçe kaçınılmaz olarak oluşur; kötü değildir, öğrenmenin doğal ürünüdür.
- **Kazara ve pervasız:** "Katman nedir, biz sadece kod yazıyoruz." Bilgisizlikten doğan, en tehlikeli borç.

Bu çerçevenin değeri, "kod kötü" demekten çıkıp borcun **nereden geldiğini** ve dolayısıyla nasıl önleneceğini konuşmayı mümkün kılmasıdır. Bilgisizlikten doğan borcun çaresi eğitim ve code review'dur; kasıtlı borcunki ise disiplinli bir geri ödeme takibidir.

### Teknik Borcu Yönetmek: Pratikler ve Hatalar

**En büyük hata: borcu görünmez bırakmak.** Kafanızda "burayı sonra düzeltmeliyiz" diye tuttuğunuz her şey, siz o ekipten ayrıldığınızda kaybolur. Teknik borç görünür kılınmalıdır — kod içinde belirgin işaretlerle (`TODO`, `FIXME` gibi, ama bunlar kolayca çürür), daha iyisi bir borç kaydında (backlog'da açık kalem olarak). Ölçülmeyen borç yönetilemez.

**İkinci hata: "büyük yeniden yazım" tuzağı.** Borç birikince ekip sıklıkla "her şeyi baştan yazalım" arzusuna kapılır. Bu neredeyse her zaman felakettir: mevcut sistem yıllarca öğrenilmiş binlerce ince iş kuralını içerir; sıfırdan yazım bunların hepsini yeniden keşfetmeyi gerektirir ve bu sırada eski sistemi de bakım altında tutmak zorundasınızdır. Doğru yol neredeyse her zaman **kademeli refactoring'dir**: sistemi çalışır tutarken, dokunduğunuz her yeri biraz daha temiz bırakmak.

Buradaki en pratik disiplin **"İzci Kuralı" (Boy Scout Rule)** dir: "Kamp alanını bulduğundan daha temiz bırak." Yani her dosyaya dokunduğunuzda, o an yaptığınız işin dışında küçük bir iyileştirme yapın — bir isim düzeltin, bir fonksiyonu ikiye bölün, bir yorumu güncelleyin. Böylece borç, ayrı bir "temizlik projesi" beklemeden, günlük işin doğal bir parçası olarak sürekli azalır. Büyük tek seferlik temizlik projelerine göre bunun avantajı, riskin küçük parçalara dağılması ve iş akışını durdurmamasıdır.

**Refactoring'i test olmadan yapmak, teknik borç eklemektir.** Refactoring'in tanımı davranışı korumaktır; ama davranışı koruduğunuzu nasıl bilirsiniz? Ancak testlerle. Yeterli test kapsamı (test coverage) olmayan bir kodu refactor etmek, gözü kapalı ameliyat yapmaya benzer. Bu yüzden çok sık, doğru sıra şudur: önce mevcut davranışı kilitleyen testleri yaz ("characterization tests"), sonra refactor et, her adımda testleri çalıştır. Testler sizin güvenlik ağınızdır (safety net); onlar olmadan cesur refactoring imkânsızdır.

### Refactoring'i Ne Zaman ve Nasıl Yapmalı?

Refactoring için ayrı bir "refactoring haftası" ayırmak genellikle yanlış modeldir; çünkü davranış değiştirmeyen bu iş, iş değeri üretmiyor gibi göründüğü için ilk kesilen kalem olur. Bunun yerine refactoring, özellik geliştirmenin **içine dokunmalıdır**. Deneyimli bir yaklaşım şudur: yeni bir özellik ekleyeceğiniz kod parçası mevcut haliyle bu özelliği eklemeye elverişli değilse, **önce kodu bu özelliği eklemeyi kolaylaştıracak şekilde refactor edin, sonra özelliği ekleyin.** Böylece refactoring, hemen ardından gelen somut işle kendini haklı çıkarır ve doğru yönde ilerlediğinizi anında test etmiş olursunuz.

Bir refactoring'in "kokan" (code smell) yerleri tespit etmesi de önemlidir. Tekrarlayan kod, aşırı uzun fonksiyonlar, çok fazla parametre alan metotlar, iç içe geçmiş derin `if` blokları, bir sınıfın başka bir sınıfın verisine sürekli erişmesi (feature envy), yorum satırlarıyla açıklanmaya çalışılan karmaşık ifadeler — bunların hepsi refactoring'e ihtiyaç duyulan bölgeleri işaret eden kokulardır. Kokular kesin kanıt değildir, ama nereye bakılacağını söyleyen değerli sezgilerdir.

## Bütünsel Bakış: Prensipler Birbirine Nasıl Bağlanır?

Bu makalede ele alınan konular tek bir omurgada birleşir. İyi isimlendirme, cohesion'ı görünür kılar — bir şeye iyi isim veremiyorsanız, muhtemelen o şey çok fazla iş yapıyordur. Düşük coupling, DRY'ın doğru uygulanmasıyla ilişkilidir — yanlış birleştirilen kod, aslında sahte bir coupling yaratır. KISS ve YAGNI, teknik borcu daha en baştan önlemenin yollarıdır — gereksiz karmaşıklık eklememek, sonradan ödenecek borcu hiç almamaktır. Ve refactoring, tüm bu prensipleri mevcut koda uygulamanın disipline edilmiş yöntemidir.

Hepsinin altında yatan tek soru şudur: **"Bu kodu altı ay sonra okuyan kişi, ne kadar az düşünmek zorunda kalacak?"** Temiz kodun tüm amacı, bu düşünme yükünü azaltmaktır. İyi isimler tahmini azaltır, iyi modülerlik ilgisiz şeyleri görmezden gelmeyi mümkün kılar, doğru prensipler gereksiz karmaşıklığı engeller, ve refactoring biriken yükü sürekli düşürür.

Son bir uyarı gereklidir: bu prensipler kural değil, **rehberdir.** Her birinin geçerli olmadığı, hatta zararlı olduğu durumlar vardır. DRY erken uygulandığında zarar verir; KISS güvenlik gibi gerçekten karmaşık gereksinimleri gereğinden basite indirgemeyi haklı çıkarmaz; YAGNI geri dönülmez kararlarda tehlikelidir. Ustalık, bu prensipleri ezberlemekte değil, **ne zaman esneteceğinizi** bilmektedir. Kör bir şekilde uygulanan her prensip, düşünmenin yerini alan bir dogmaya dönüşür ki bu, temiz kodun asıl amacının — düşünmeyi kolaylaştırmanın — tam tersidir.
