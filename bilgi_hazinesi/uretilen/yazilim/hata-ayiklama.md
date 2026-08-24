# Hata Ayıklama Metodolojisi

## Tanım

Hata ayıklama (debugging), bir yazılım sisteminin gözlemlenen davranışı ile beklenen davranışı arasındaki farkın kök nedenini bulup ortadan kaldırma sürecidir. Burada kritik olan ayrım şudur: hata ayıklama bir *tamir* etkinliği değil, önce bir *anlama* etkinliğidir. Kodu değiştirmek işin son ve en kolay adımıdır; asıl zor olan, hangi kod satırının hangi mekanizma yüzünden yanlış sonucu ürettiğini kesin olarak kanıtlamaktır.

Bu makalenin temel tezi şudur: hata ayıklama sezgi ve şansa dayanan bir uğraş değil, uygulanabilir ve tekrar edilebilir bir *bilimsel yöntemdir*. Deneyimli mühendisler daha hızlı hata bulmalarını genellikle daha iyi "önseziye" bağlar; oysa gerçekte onları hızlandıran şey, farkında olmadan uyguladıkları disiplinli bir hipotez-test döngüsüdür. Bu döngüyü bilinçli hale getirdiğinizde, sadece daha hızlı değil, çok daha güvenilir hata ayıklarsınız.

Bir semptom (örneğin "kullanıcı çıkış yaptığında uygulama çöküyor") ile onun kök nedeni (örneğin oturum nesnesi serbest bırakıldıktan sonra bir arka plan thread'inin ona hâlâ erişmesi) arasındaki mesafe genellikle şaşırtıcı derecede uzundur. Metodolojinin görevi, bu mesafeyi rastgele denemelerle değil, ölçülü adımlarla katetmektir.

## Kök Neden: Neden Hata Ayıklama Zordur?

Hata ayıklamayı zorlaştıran şey, teknik karmaşıklıktan çok insan bilişinin doğasıdır. Bunu anlamak, metodolojinin neden bu şekilde tasarlandığını açıklar.

Birincisi, **belirti nedenin çok uzağında ortaya çıkar**. Modern yazılımda bir hata, onu doğuran satırdan yüzlerce çağrı, birçok modül ve bazen saniyeler ötede kendini gösterir. Bellek bozulması (memory corruption) bunun klasik örneğidir: bir yerde sınır dışına yazarsınız (buffer overflow), ama program tamamen alakasız bir yerde, çok sonra çöker; çünkü bozduğunuz bellek o ana kadar okunmaz. Belirtinin göründüğü yere bakmak, çoğu zaman yanlış yere bakmaktır.

İkincisi, **insan zihni onaylama yanlılığına (confirmation bias) yatkındır**. Bir hipotez oluşturduğumuzda, onu çürütecek kanıtları görmezden gelip destekleyecek kanıtları abartma eğilimindeyiz. "Kesinlikle şu fonksiyondadır" dediğimizde, saatlerce o fonksiyonu inceleyip hatanın başka yerde olduğunu fark etmeyebiliriz. Bilimsel yaklaşımın çekirdeği tam da bunu kırmak içindir: hipotezi *doğrulamaya* değil, *çürütmeye* çalışırız.

Üçüncüsü, **değiştirdiğimiz şeyler gözlemi bozar**. Bir log satırı eklemek zamanlamayı değiştirebilir ve bir race condition'ı gizleyebilir (bkz. Heisenbug). Debugger altında çalıştırmak, optimize edilmemiş bir derleme kullanmak, ölçüm eylemini gözlemlenen sisteme dahil eder. Bu yüzden metodoloji, gözlemin kendisini de bir değişken olarak ele almayı gerektirir.

Dördüncüsü, **çoğu ciddi hata belirleyici (deterministic) değildir**. Yeniden üretilebilir bir hata neredeyse çözülmüş bir hatadır; asıl işkence, on binde bir ortaya çıkan, üretimde görülüp geliştirici makinesinde asla görülmeyen hatalardır. Metodolojinin en değerli kısmı, tam da bu belirsizliği ehlileştirme tekniğidir.

## Bilimsel Yaklaşım: Hipotez-Test Döngüsü

Hata ayıklamanın omurgası, bilimsel yöntemin bire bir uyarlamasıdır. Döngü şu adımlardan oluşur ve her ciddi hata için bilinçli olarak dönülmelidir:

1. **Gözlem:** Tam olarak ne oluyor? Belirtiyi olabildiğince kesin tanımlayın. "Bazen çöküyor" bir gözlem değildir; "kullanıcı 500'den fazla satır içeren dosyayı içe aktardığında, ilerleme çubuğu %80'de donuyor" bir gözlemdir.
2. **Soru:** Bu gözlemi açıklayabilecek bir daralma sorusu sorun. "Donma, veri işleme aşamasında mı yoksa UI güncelleme aşamasında mı?"
3. **Hipotez:** Test edilebilir, *yanlışlanabilir* (falsifiable) bir tahmin kurun. İyi bir hipotezin ayırt edici özelliği, onu yanlış çıkaracak somut bir deneyin var olmasıdır. "Kod kötü yazılmış" hipotez değildir. "İşleme döngüsü, boş bir satırla karşılaştığında sonsuz döngüye giriyor" hipotezdir.
4. **Tahmin (prediction):** Hipotez doğruysa, hangi somut ölçümü *görmeliyim*? "Öyleyse, döngü sayacını loglarsam, boş satıra gelindiğinde sayacın artmayı durduğunu görmeliyim."
5. **Deney:** Bu tahmini test edecek *en küçük* değişikliği yapın ve gözlemleyin.
6. **Sonuç:** Tahmin gerçekleşti mi? Gerçekleştiyse hipotez güçlendi; gerçekleşmediyse hipotez çürüdü ve bu, çürümüş olması *iyi haberdir* — arama uzayınızı daralttınız.

Bu döngünün en çok ihmal edilen ama en değerli adımı 4. adımdır: **deneyi yapmadan önce sonucunu tahmin etmek.** Neden? Çünkü tahminini yazmadan deney yapan mühendis, çıkan her sonucu hipotezini destekliyormuş gibi yorumlar (yine onaylama yanlılığı). Tahmini önceden taahhüt ettiğinizde, sonuç sizinle çelişirse kaçamazsınız — hipotez yanlıştır, nokta. Bu küçük disiplin, saatlerce süren "bir şeyleri değiştirip ne olacağına bakma" turlarını ortadan kaldırır.

Bir başka kritik ilke **tek değişken kuralıdır**: her deneyde yalnızca *bir* şeyi değiştirin. Aynı anda üç şey değiştirip hata kaybolursa, hangisinin işe yaradığını asla bilemezsiniz — ve büyük olasılıkla ikisi zararlı, biri faydalıdır. Aceleyle atılan "her ihtimale karşı" değişiklikler, çözülmüş görünen ama aslında gizlenmiş hatalara yol açar.

## Yeniden Üretim (Repro): Her Şeyin Temeli

Güvenilir bir yeniden üretim adımı (reproduction, kısaca "repro"), hata ayıklamanın en değerli varlığıdır. Bir hatayı isteğe bağlı olarak, tekrar tekrar tetikleyebiliyorsanız, onu neredeyse çözmüşsünüz demektir; çünkü bilimsel döngünün "deney" adımını saniyeler içinde döndürebilirsiniz. Repro yoksa, her hipotez testi için saatlerce ya da günlerce beklemek zorunda kalırsınız.

**Neden bu kadar merkezi?** Çünkü repro, öznel "bende çalışıyor" tartışmasını nesnel bir olguya çevirir. Ölçülebilir, paylaşılabilir ve otomatikleştirilebilir. Bir repro'yu bir test senaryosuna dönüştürdüğünüzde, hem şimdi hatayı bulmak hem de gelecekte gerilemeyi (regression) önlemek için bir araç kazanırsınız.

İyi bir repro'nun iki hedefi vardır:

**Küçültme (minimization).** Hatayı tetikleyen senaryoyu, hâlâ hatayı gösteren *en küçük* girdiye indirin. 10.000 satırlık bir girdi dosyası hatayı tetikliyorsa, yarısını atın, hâlâ tetikliyor mu? Tetikliyorsa diğer yarıyı da atın. Bu, birazdan anlatacağımız bisect mantığının girdiye uygulanmış halidir. Genellikle 3 satırlık bir girdiye indiğinizde hatanın nedeni çıplak gözle görülür hale gelir. Karmaşıklık, hatayı saklayan bir gürültüdür; onu soyup çıplak çekirdeğe inersiniz.

**Belirlileştirme (determinism).** Hata rastgele ortaya çıkıyorsa, onu tetikleyen gizli değişkeni bulmaya çalışın. Rastgelelik nadiren gerçek rastgeleliktir; genellikle bizim gözlemlemediğimiz bir durumun (zamanlama, thread sıralaması, önbellek durumu, girdi sırası, saat, rastgele tohum) fonksiyonudur. Rastgele sayı üreteçlerini sabit bir tohumla (seed) çalıştırmak, thread sayısını bire indirmek, sistem saatini sabitlemek gibi teknikler, belirsiz bir hatayı belirli hale getirir. Bir race condition söz konusuysa, yapay gecikmeler (`sleep`) ekleyerek "kazanan" thread'i seçmeye zorlayabilir ve hatayı isteğe bağlı tetiklenebilir hale getirebilirsiniz.

Üretimde görülüp yerelde görülemeyen hatalarda, farkı yaratan çevresel değişkenleri sistematik olarak listeleyin: veri hacmi, eşzamanlı kullanıcı sayısı, gerçek ağ gecikmesi, farklı zaman dilimi, farklı yerel ayar (locale), 32-bit'e karşı 64-bit, farklı derleyici optimizasyon seviyesi. Hata çoğu zaman bu farklardan birinde saklıdır ve onu yerele taşıdığınız an repro'ya sahip olursunuz.

## Bisect: İkili Arama ile Kök Nedeni Sıkıştırma

Bisect, hata ayıklamada ikili aramanın (binary search) uygulanmasıdır ve muhtemelen en güçlü tek tekniktir. Temel fikir şudur: hatanın *bulunmadığı* bir durumla *bulunduğu* bir durum arasında bir aralık varsa, bu aralığın ortasını test ederek her adımda arama uzayını yarıya indirebilirsiniz. N adımlık bir aralıkta hatayı yaklaşık log₂(N) denemede bulursunuz — 1000 commit'lik bir aralık yaklaşık 10 denemede biter.

### Sürüm ekseninde bisect (version control bisect)

En bilinen biçimi, sürüm kontrol geçmişi üzerinde çalışır. "Geçen ay çalışıyordu, şimdi bozuk" dediğiniz klasik gerileme (regression) senaryosunda paha biçilmezdir. Yöntem şudur: hatanın olmadığı bilinen bir "iyi" commit ve hatanın olduğu bilinen bir "kötü" commit işaretlersiniz. Araç, ikisinin ortasındaki commit'e geçer; siz test edip "iyi" veya "kötü" dersiniz; araç aralığı yarıya indirir ve tekrar ortaya atlar. Birkaç adımda, hatayı *ilk kez getiren tek bir commit'e* iner.

Git'te bu iş için yerleşik bir alt komut vardır (kabaca "iyi" ve "kötü" uçları işaretleyip aracın sizi ortaya götürmesine izin verirsiniz). Gerçek güç ise otomasyondadır: hatayı sınayan bir betik yazabiliyorsanız — çıkış kodu 0 iyi, sıfır dışı kötü — bisect'i tamamen otomatik çalıştırıp yüzlerce commit'i insan müdahalesi olmadan tarayabilirsiniz. Bu, elle saatler sürecek bir aramayı dakikalara indirir.

Bisect'in incelikleri vardır. Test edilen commit derlenmiyorsa, o commit'i "atla" olarak işaretlemek gerekir; yoksa "kötü" sanılıp arama yanlış yönde daralır. Ayrıca bisect, hatayı *getiren* commit'i bulur — bu her zaman hatanın *nedenini içeren* commit değildir. Bazen suçlanan commit, altta yatan gizli bir kusuru sadece *ortaya çıkaran* masum bir değişikliktir. Yine de, bakılacak yeri bir dosyaya, hatta birkaç satıra indirmesi olağanüstü değerlidir.

### Bisect'in genelleştirilmiş biçimi

Asıl güçlü kavrayış şudur: bisect yalnızca commit'ler için değil, **monoton bir eksene sahip her arama uzayı** için geçerlidir. "Belirli bir noktadan sonra hata var, öncesinde yok" diyebildiğiniz her boyutta ikili arama uygulayabilirsiniz:

- **Girdi ekseni:** Repro'yu küçültürken girdinin yarısını atmak, girdi üzerinde bisect'tir.
- **Kod ekseni:** Uzun bir fonksiyonun ortasına bir kontrol (assertion veya log) koyup, hatanın bu noktaya gelmeden önce mi sonra mı oluştuğunu belirlemek, çalışma akışı üzerinde bisect'tir. Değişken hâlâ sağlamsa hata aşağıda, bozuksa yukarıda.
- **Konfigürasyon ekseni:** Sorunun hangi ayardan kaynaklandığını bulmak için ayarların yarısını devre dışı bırakmak.
- **Bağımlılık ekseni:** Bir kütüphane yükseltmesi sonrası hata çıktıysa, hangi ara sürümün getirdiğini sürümler arasında ikili aramayla bulmak.

Bisect'i bir *zihinsel alışkanlık* olarak içselleştirdiğinizde, her "nerede?" sorusuna "arama uzayını ikiye bölebileceğim bir sınır nerede?" diye yanıt verirsiniz. Bu, doğrusal arama (baştan sona her şeyi tek tek incelemek) yerine logaritmik aramayı varsayılan haline getirir.

## Loglama (Log): Zamanı Görünür Kılmak

Loglama, çalışan bir programın iç durumunu zaman ekseninde dışa aktarma tekniğidir. En büyük değeri, debugger'ın zayıf olduğu yerdedir: **zamanla değişen, eşzamanlı ve üretimde çalışan sistemler.** Debugger programı durdurur; log ise programı durdurmadan onun hikâyesini kaydeder. Bir race condition'ı ya da üretimde saatte bir görülen bir hatayı, programı durdurup inceleyemezsiniz — ama iyi loglarla olay sonrası yeniden kurabilirsiniz.

**Neden bazen log, debugger'dan üstündür?** Çünkü bazı hatalar gözlemlenince kaybolur. Debugger altında durup incelediğinizde zamanlama tamamen değişir ve race condition ortadan kalkar. Log, sisteme çok daha az müdahale ederek (özellikle asenkron, tamponlanmış loglama ile) gerçek davranışı yakalamaya daha yakındır. Ayrıca dağıtık sistemlerde tek bir debugger noktası yoktur; onlarca makinede olan biteni ancak toplanan loglardan bir araya getirebilirsiniz.

Etkili loglamanın ilkeleri:

**Seviyeler kullanın.** DEBUG, INFO, WARN, ERROR gibi seviyeler, üretimde gürültüyü kısıp bir olay olduğunda ayrıntıyı açmanıza olanak tanır. Her şeyi ERROR yazmak, gerçek hataları gürültüye boğar.

**Yapılandırılmış loglama (structured logging) tercih edin.** Serbest metin yerine, anahtar-değer alanları içeren (örneğin JSON) loglar, makinece sorgulanabilir. "user_id=4711 olan tüm istekleri, latency>2s koşuluyla göster" diye filtreleyebilmek, bir milyon satırlık düz metinde grep yapmaktan katbekat güçlüdür.

**Bağıntı kimliği (correlation ID) taşıyın.** Bir isteğin sistemin içinde geçtiği tüm bileşenlere aynı benzersiz kimliği iliştirin. Böylece dağıtık bir işlemin tüm parçalarını tek bir iplikte toplayabilirsiniz. Bu, mikroservis mimarilerinde neredeyse zorunludur.

**Karar noktalarını ve değişmezleri (invariant) loglayın.** En değerli log, "buraya geldim" değil, "şu koşul sağlandığı için şu dalı seçtim ve x değeri buydu" diyendir. Kararı doğuran veriyi loglarsanız, hipotezinizi doğrudan test edebilirsiniz.

Loglamanın tuzağı, gözlemcinin sistemi değiştirmesidir. Bir sıcak döngünün (hot loop) içine senkron log koymak, performansı o kadar değiştirebilir ki hata gizlenir ya da yeni bir hata doğar. Kritik yollarda tamponlu/asenkron log kullanın ve gürültü ile sinyal dengesini gözetin: her şeyi loglamak, hiçbir şeyi loglamamak kadar işe yaramaz olabilir, çünkü sinyal gürültüde kaybolur.

## Debugger: Durdur, İncele, İlerle

Debugger, programın yürütülmesini istenen noktada dondurup iç durumu — değişkenleri, çağrı yığınını (call stack), bellek içeriğini — doğrudan inceleme ve satır satır ilerleme imkânı veren araçtır. Loglamaya karşı üstünlüğü şudur: log yalnızca *önceden koymayı akıl ettiğiniz* bilgiyi verir; debugger ise durduğunuz anda *aklınıza gelen her şeyi* sorgulamanıza izin verir. Beklemediğiniz bir hatada, hangi bilginin lazım olacağını önceden bilemezsiniz — işte orada debugger'ın keşif gücü paha biçilmezdir.

Debugger'ın temel yetenekleri ve ne zaman hangisi:

**Kesme noktaları (breakpoints).** Yürütmeyi belirli bir satırda durdurur. Asıl güç, **koşullu kesme noktalarındadır**: "yalnızca `i == 4711` olduğunda dur." Milyon iterasyonlu bir döngüde hatanın oluştuğu tek iterasyonu yakalamak için elle "devam et"e milyon kez basmak yerine, koşulu makineye devredersiniz. Bu, döngü hatalarında zaman kazandıran en önemli tekniklerden biridir.

**İzleme noktaları (watchpoints / data breakpoints).** "Şu bellek adresi ya da değişken *değiştiği* anda dur." Bellek bozulması hatalarında altın değerindedir: bir değişken beklenmedik biçimde bozuluyorsa, watchpoint size onu *kimin* yazdığını, tam o yazma anında yakalayarak söyler. "Bu değeri kim değiştiriyor?" sorusunun en doğrudan yanıtıdır.

**Adım kontrolleri (step over / step into / step out).** Bir satırı, onun çağırdığı fonksiyonun içine girmeden çalıştırmak (over); fonksiyonun içine dalmak (into); bulunduğunuz fonksiyondan çıkana kadar çalıştırmak (out). Bu üçlü, kontrol akışını istediğiniz çözünürlükte izlemenizi sağlar.

**Çağrı yığını (call stack) incelemesi.** Bir çökme ya da durma anında, oraya *nasıl* gelindiğini gösterir — hangi fonksiyon hangisini çağırdı. Yığın çerçeveleri (stack frames) arasında yukarı aşağı gezerek her seviyedeki yerel değişkenleri görebilirsiniz. Bir hatanın bağlamını anlamanın en hızlı yolu genellikle yığını okumaktır.

İleri düzeyde iki teknik özellikle güçlüdür. Birincisi **ölüm sonrası (post-mortem) hata ayıklama**: bir çökme anında oluşturulan bellek dökümünü (core dump / crash dump) sonradan debugger'a yükleyip, çökme anındaki tüm durumu — yığın, değişkenler, thread'ler — incelemek. Üretimde bir kez çöküp tekrar üretilemeyen hatalarda bazen elinizdeki tek kanıt budur. İkincisi **geriye doğru/zaman yolculuklu hata ayıklama** (reverse / time-travel debugging): programın yürütülmesini kaydedip ileri *ve geri* adımlayabilmek. "Bu değer nereden bozuk geldi?" diye çökme noktasından geriye doğru yürüyebilmek, bazı araçların sunduğu güçlü ama görece pahalı bir yetenektir; her ortamda bulunmaz.

Debugger'ın sınırları da nettir: eşzamanlılık hatalarında programı durdurmak zamanlamayı bozar ve hatayı gizleyebilir; üretimde çalışan bir servisi debugger ile durduramazsınız; ağır optimize edilmiş derlemelerde satır-değişken eşlemesi bozulur ve incelediğiniz değer yanıltıcı olabilir. Bu yüzden log ve debugger rakip değil, tamamlayıcı araçlardır.

## Somut Örnek: Bir Hatanın Baştan Sona Çözümü

Senaryoyu ele alalım: Bir web servisi, "bazı" kullanıcılar için ara sıra 500 hatası döndürüyor. Üretimde görülüyor, yerelde asla.

**Gözlem ve repro çabası.** Önce belirtiyi keskinleştiririz. Loglara (yapılandırılmış, bağıntı kimlikli) bakarız ve hatanın yalnızca profil fotoğrafı olmayan kullanıcılarda ortaya çıktığını fark ederiz. Bu, "bazı" belirsizliğini somut bir koşula indirger. Artık yerelde profil fotoğrafsız bir kullanıcı oluşturup hatayı *isteğe bağlı* tetikleyebiliriz — repro elimizde. Bu tek bulgu, işin yarısıdır.

**Küçültme.** İsteği en yalın haline indiririz: fotoğrafsız bir kullanıcıya profil sayfası GET isteği. Hata hâlâ var. Gürültü temizlendi.

**Hipotez.** Loglardaki çağrı yığını, hatanın avatar URL'sini biçimlendiren bir yardımcı fonksiyonda oluştuğunu gösterir. Hipotez: "Profil fotoğrafı null olduğunda, URL biçimleyici null'a erişip patlıyor (null dereference)." Bu yanlışlanabilir bir hipotezdir.

**Tahmin.** Hipotez doğruysa, o fonksiyona girişte gelen değeri loglarsam ya da oraya koşullu bir kesme noktası koyarsam, fotoğrafsız kullanıcıda değerin null geldiğini görmeliyim.

**Deney.** Debugger'da, o fonksiyona "yalnızca argüman null ise dur" koşullu kesme noktası koyarız (koşullu breakpoint sayesinde binlerce normal çağrıyı atlarız). Fotoğrafsız kullanıcıyla istek yaparız — kesme noktası tetiklenir. Yığını yukarı çıkarız ve null değerin, veritabanından gelen boş bir alanın hiç kontrol edilmeden fonksiyona aktarıldığını görürüz.

**Sonuç ve düzeltme.** Tahmin gerçekleşti; hipotez doğrulandı. Ama burada durmayız: *önce hatayı yakalayan bir test yazarız* (fotoğrafsız kullanıcıyla profil isteği 500 dönmemeli), testin kırmızı (başarısız) olduğunu görürüz, sonra düzeltmeyi yaparız (null durumunda varsayılan avatar), testin yeşile döndüğünü doğrularız. Test önce yazılır çünkü test gerçekten hatayı yakalıyor mu, ancak kırmızıyken görebiliriz.

Bu örnekteki her adım metodolojiyi somutlar: belirsiz belirtiyi kesin repro'ya indirmek, gürültüyü küçültmek, yanlışlanabilir hipotez, önceden taahhüt edilmiş tahmin, tek değişkenli deney, ve gerileme testiyle sonlandırma.

## Doğru Kullanım ve Tuzaklar

**Aracı probleme göre seçin.** Belirleyici, yerelde üretilebilen bir mantık hatası için debugger genellikle en hızlısıdır. Eşzamanlı, zamanlamaya duyarlı ya da üretimde yaşayan bir hata için loglama ve gözlemlenebilirlik (observability) araçları üstündür. Bir gerileme için önce bisect ile *nerede* değil *ne zaman* getirildiğini bulun. Yanlış araç, doğru araçtan on kat yavaştır.

**"Değiştir-bak" tuzağına düşmeyin.** En yaygın kötü alışkanlık, hipotez kurmadan kodda bir şeyler değiştirip sonucuna bakmaktır. Bazen tesadüfen işe yarar, ama neyi neden düzelttiğinizi bilmediğiniz için hatayı gerçekten çözmez, sadece saklarsınız — ve genellikle başka bir yerden yeniden çıkar. Her değişikliğin arkasında bir hipotez olmalı.

**Gözlemcinin etkisini unutmayın.** Log satırı, debugger duraklaması, farklı derleme bayrağı — hepsi sistemi değiştirir. "Log ekleyince hata kayboldu" bir çözüm değil, bir ipucudur: büyük olasılıkla zamanlamaya duyarlı bir hatanız (Heisenbug) var. Hatanın gözleme duyarlı olması, kök nedene dair değerli bir bilgidir.

## Yaygın Hatalar

- **Semptomun göründüğü yere odaklanmak.** Çökmenin olduğu satır, hatanın *nedeninin* olduğu satır değildir; özellikle bellek bozulmasında neden çok öncede saklıdır. Belirtiyi başlangıç noktası olarak alın, varış noktası olarak değil.
- **Onaylama yanlılığına teslim olmak.** Bir hipoteze aşık olup onu çürütecek kanıtları görmezden gelmek. Bunun panzehiri, deney öncesi tahmini yazıya dökmek ve hipotezi çürütmeye çalışmaktır.
- **Aynı anda birden çok şey değiştirmek.** Hata kaybolduğunda hangi değişikliğin işe yaradığını bilememek; tek değişken kuralını çiğnemek.
- **Repro'yu atlayıp doğrudan koda dalmak.** Güvenilir repro olmadan yapılan her hipotez testi belirsizdir; "düzelttim sanırım, artık görünmüyor" tehlikeli bir cümledir.
- **Hata mesajını okumamak.** Şaşırtıcı derecede yaygın: yığın izini (stack trace) ya da hata metnini baştan sona okumadan tahmine başlamak. Mesaj çoğu zaman cevabı doğrudan içerir.
- **"Bende çalışıyor" ile yetinmek.** Ortam farkını (veri, yük, sürüm, yerel ayar) sistematik incelemeden hatayı reddetmek.
- **Düzeltmeyi test olmadan bırakmak.** Kök nedeni yakalayan bir gerileme testi eklemeden geçmek; aynı hata birkaç ay sonra geri döner ve ikinci kez sıfırdan avlanır.

## En İyi Pratikler

- **Her hatayı bir bilimsel döngü olarak ele alın:** gözlem, yanlışlanabilir hipotez, önceden taahhüt edilmiş tahmin, tek değişkenli deney, sonuç. Bu döngü hızlandıkça uzmanlaşırsınız.
- **İlk yatırımı repro'ya yapın.** Güvenilir, küçültülmüş, belirleyici bir yeniden üretim adımı, sonraki tüm işi katbekat hızlandırır. Zamanınızın büyük kısmı burada haklı olarak harcanır.
- **Bisect'i bir refleks yapın.** "Nerede?" sorusunu her zaman "arama uzayını nasıl ikiye bölerim?" sorusuna çevirin — commit'te, girdide, kodda ya da konfigürasyonda.
- **Loglamayı bir mimari karar olarak tasarlayın:** seviyeler, yapılandırılmış alanlar, bağıntı kimlikleri, karar noktalarının kaydı. İyi loglama hatadan *önce* konur, sonra değil.
- **Debugger'ın ileri özelliklerini öğrenin:** koşullu kesme noktaları, izleme noktaları (watchpoints), ölüm sonrası döküm analizi. Bunlar, saatleri dakikaya indiren tekniklerdir.
- **Kök nedeni yakalayan bir gerileme testi yazmadan hatayı kapatmayın.** Test önce kırmızı olmalı, sonra düzeltmeyle yeşile dönmeli.
- **Bulgularınızı ve akıl yürütmenizi yazın.** Zor bir hatanın çözüm günlüğü, hem geleceğe hem takım arkadaşlarınıza kalan değerdir; benzer belirti tekrar çıktığında yolu kısaltır.
- **Ne zaman ara vereceğinizi bilin.** Uzun süre saplanan bir hatada zihin onaylama yanlılığına kilitlenir; kısa bir mola ya da bir başkasına yüksek sesle anlatmak (rubber-duck debugging) çoğu zaman tıkanmayı açar. Sorunu birine anlatmak için sıraya dizmek, çoğu kez konuşma bitmeden çözümü kendiniz görmenizi sağlar.

Sonuç olarak hata ayıklama, doğuştan gelen bir yetenek değil, öğrenilebilir ve keskinleştirilebilir bir disiplindir. Onu şansa ve sezgiye bırakmak yerine bilimsel yöntemin adımlarına bağladığınızda, en sinsi hatalar bile — belirsiz, aralıklı, üretime özgü olanlar dahil — sistematik olarak sıkıştırılabilir, izole edilebilir ve kalıcı olarak ortadan kaldırılabilir hale gelir.
