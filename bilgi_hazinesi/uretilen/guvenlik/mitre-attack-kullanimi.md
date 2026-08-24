# MITRE ATT&CK Çerçevesinin Kullanımı

## Tanım

MITRE ATT&CK (Adversarial Tactics, Techniques, and Common Knowledge), gerçek dünyada gözlemlenmiş saldırgan davranışlarını yapılandırılmış bir bilgi tabanı olarak toplayan, açık kaynaklı bir çerçevedir. ATT&CK'i diğer güvenlik taksonomilerinden ayıran temel nokta şudur: çerçeve, zafiyetlere veya zararlı yazılım imzalarına değil, **davranışlara** odaklanır. Yani "saldırgan hangi CVE'yi kullandı" değil, "saldırgan sisteme girdikten sonra ne yaptı, nasıl kalıcılık sağladı, veriyi nasıl dışarı çıkardı" sorularına cevap verir.

Çerçeve hiyerarşik bir yapıya sahiptir. En üstte **taktikler** (tactics) bulunur; bunlar saldırganın ulaşmak istediği amaçları, yani "neden"i temsil eder (örneğin kalıcılık sağlamak, yetki yükseltmek, veriyi sızdırmak). Her taktiğin altında **teknikler** (techniques) yer alır; bunlar amaca ulaşmanın yollarını, yani "nasıl"ı anlatır. Tekniklerin çoğu **alt tekniklere** (sub-techniques) bölünür; bu, aynı davranışın farklı somut gerçekleşme biçimlerini ayırt etmeyi sağlar. En altta ise **prosedürler** (procedures) vardır; belirli bir tehdit aktörünün veya zararlı yazılımın o tekniği tam olarak nasıl uyguladığına dair gerçek örneklerdir.

ATT&CK tek bir matris değildir. Kurumsal ortamlar için **Enterprise** matrisi (Windows, Linux, macOS, bulut, konteyner, ağ altyapısı), mobil cihazlar için **Mobile** matrisi ve endüstriyel kontrol sistemleri için **ICS** matrisi bulunur. Bu makale ağırlıklı olarak Enterprise bağlamına odaklanır, çünkü kurumsal savunmanın günlük pratiğinde en çok kullanılan budur.

## Kök Neden: ATT&CK Neden Bu Şekilde Tasarlandı

ATT&CK'in davranış odaklı olmasının arkasında somut bir gözlem vardır. Klasik savunma yaklaşımları uzun yıllar **atomik göstergeler** (IOC - Indicators of Compromise) üzerine kuruluydu: belirli bir hash değeri, bir IP adresi, bir domain adı. Sorun şu ki bu göstergeler saldırgan için değiştirilmesi son derece ucuzdur. Bir saldırgan zararlı yazılımını yeniden derleyip hash'ini değiştirebilir, altyapısını bir gecede yeni sunuculara taşıyabilir. David Bianco'nun "Pyramid of Pain" (Acı Piramidi) kavramı bu gerçeği çok net ortaya koyar: hash ve IP gibi göstergeleri engellemek saldırgana neredeyse hiç acı vermezken, saldırganın **taktik, teknik ve prosedürlerini** (TTP) tespit etmek ona en büyük maliyeti çıkarır. Çünkü bir saldırgan çalışma yöntemini, örneğin kimlik bilgisi çalma alışkanlığını değiştirmek zorunda kaldığında, tüm operasyonel modelini yeniden kurgulamak zorunda kalır.

İşte ATT&CK'in kök mantığı budur: savunmayı, saldırganın kolayca değiştirebildiği yüzeysel göstergelerden, değiştirmesi pahalı olan davranışsal örüntülere kaydırmak. Bir tehdit aktörü keşif yapmak, kimlik bilgisi elde etmek, yanlamasına hareket etmek (lateral movement) zorundadır; bunlar amacına ulaşmak için atlamak zorunda olduğu adımlardır. Savunmacı bu zorunlu adımları tespit etmeye odaklandığında, saldırganın manevra alanı ciddi biçimde daralır.

İkinci bir kök neden ise **ortak dil** ihtiyacıdır. ATT&CK öncesinde her güvenlik ekibi, her ürün, her tehdit istihbaratı raporu saldırgan davranışını kendi terminolojisiyle anlatıyordu. Bu, kırmızı takım (red team), mavi takım (blue team), tehdit istihbaratı analistleri ve yönetim arasında iletişim kopukluğuna yol açıyordu. ATT&CK, her davranışa "T1055" gibi kararlı bir kimlik (ID) atayarak herkesin aynı şeyi kastettiğinden emin olmayı sağlayan bir ortak sözlük görevi görür.

## Taktikler ve Teknikler: Yapının Somut İşleyişi

Enterprise matrisinde taktikler, kabaca bir saldırının yaşam döngüsünü izleyen bir sıralamayla düzenlenir. Bunlar arasında keşif (Reconnaissance), kaynak geliştirme (Resource Development), ilk erişim (Initial Access), yürütme (Execution), kalıcılık (Persistence), yetki yükseltme (Privilege Escalation), savunmadan kaçınma (Defense Evasion), kimlik bilgisi erişimi (Credential Access), keşif/içeriden gözlem (Discovery), yanlamasına hareket (Lateral Movement), toplama (Collection), komuta-kontrol (Command and Control), sızdırma (Exfiltration) ve etki (Impact) bulunur.

Burada kritik bir kavram yanılgısını düzeltmek gerekir: taktik sütunlarının soldan sağa dizilmesi, saldırganın her zaman bu sırayı adım adım izlediği anlamına **gelmez**. ATT&CK bir öldürme zinciri (kill chain) değildir; matris bir sıralı akış diyagramı değil, bir "davranış katalogu"dur. Gerçek bir saldırıda aktör taktikler arasında ileri geri hareket edebilir, bazılarını atlayabilir, bazılarını defalarca tekrarlayabilir. Örneğin savunmadan kaçınma, operasyon boyunca sürekli tekrar eden bir davranıştır, tek seferlik bir aşama değil.

Somut bir örnek üzerinden yapıyı görelim. **T1055 - Process Injection** (Süreç Enjeksiyonu) tekniği, savunmadan kaçınma ve yetki yükseltme taktiklerinin altında yer alır. Bu tekniğin altında çok sayıda alt teknik bulunur; bunlardan biri klasik DLL enjeksiyonudur, bir diğeri ise "Process Hollowing" olarak bilinen, meşru bir sürecin belleğinin boşaltılıp yerine zararlı kodun yerleştirilmesi yöntemidir. Bu ayrımın neden önemli olduğunu görmek kolaydır: iki alt tekniğin gözlemlenebilir izleri (telemetry) tamamen farklıdır. DLL enjeksiyonu belirli API çağrılarının bir dizisiyle kendini belli ederken, process hollowing'in imzası bellek bölgelerinin durumundaki anomaliler ve süreç oluşturma bayraklarıdır. Alt teknik ayrımı olmasaydı, savunmacı "süreç enjeksiyonunu tespit ediyorum" diyerek yanlış bir güven duygusuna kapılabilirdi; oysa yalnızca bir alt türü yakalıyor olabilir.

Bir başka önemli örnek **T1053 - Scheduled Task/Job** tekniğidir. Bu teknik hem yürütme, hem kalıcılık, hem de yetki yükseltme taktiklerine hizmet edebilir. Aynı tekniğin birden fazla taktik altında görünmesi tesadüf değildir; bir davranış saldırganın birden fazla amacına aynı anda hizmet edebilir. Zamanlanmış bir görev oluşturmak hem kodu çalıştırır (yürütme), hem sistem yeniden başladığında kalıcılığı sürdürür (kalıcılık), hem de SYSTEM bağlamında çalışacak şekilde ayarlanırsa yetki yükseltir. Bu çoklu eşleme, ATT&CK'i düz bir liste yerine çok boyutlu bir haritaya dönüştürür.

## Kapsama Analizi: Neyi Görebiliyorum, Neyi Göremiyorum

ATT&CK'in kurumsal savunmada en değerli kullanımlarından biri **kapsama (coverage) analizidir**. Buradaki temel soru şudur: mevcut güvenlik kontrollerim ve tespit yeteneklerim, bilinen saldırgan tekniklerinin ne kadarını görebiliyor?

Bu analizin ana aracı **ATT&CK Navigator**'dır. Navigator, matrisi renklendirilebilir bir tablo olarak sunar; her hücre bir teknik veya alt tekniktir. Savunmacı, tespit edebildiği teknikleri yeşil, kısmen görebildiklerini sarı, tamamen kör olduğu teknikleri kırmızı olarak işaretleyerek bir **ısı haritası** (heatmap) oluşturur. Sonuç, savunma duruşunun tek bakışta anlaşılabilir bir görselidir.

Ancak burada çok yaygın ve tehlikeli bir hata vardır: kapsamayı bir "yüzde" olarak ölçmeye çalışmak. "Tekniklerin yüzde 80'ini kapsıyorum" cümlesi neredeyse her zaman yanıltıcıdır. Bunun kök nedeni birkaç katmanlıdır. Birincisi, tüm teknikler eşit önemde değildir; ortamınızla alakasız bir teknik (örneğin hiç Linux sunucunuz yoksa Linux'a özgü bir teknik) için "kapsama yok" demek anlamsızdır. İkincisi, bir tekniği "kapsıyor" saymak muğlaktır; o tekniğin **tek bir prosedürünü** tespit ediyor olabilirsiniz ama aynı tekniğin onlarca farklı gerçekleşme biçimine kör olabilirsiniz. Kapsama, ikili (var/yok) bir değer değil, bir güven derecesi ve bir bağlam meselesidir.

Doğru kapsama analizi, "hangi tekniklere karşı savunmasızım" sorusunu **tehdit modeline** bağlar. Yani "benim sektörümü, benim teknolojilerimi hedefleyen aktörler hangi teknikleri kullanıyor" sorusuyla başlar, ardından "bu teknikleri görebiliyor muyum" sorusuna geçer. Boş bir matrisi baştan sona doldurmaya çalışmak yerine, önceliklendirilmiş bir tehdit görünümünden yola çıkmak hem daha gerçekçi hem de kaynakları çok daha verimli kullanan bir yaklaşımdır.

## Tespit Haritalama: Telemetriyi Davranışa Bağlamak

Tespit haritalama (detection mapping), ATT&CK'in mavi takım için en operasyonel kullanımıdır. Amaç, sahip olunan tespit kurallarını (SIEM korelasyon kuralları, EDR algılama mantığı, Sigma kuralları) ATT&CK teknikleriyle ilişkilendirmektir. Bu ilişkilendirme yapıldığında, ekip "hangi davranışları görebiliyorum" sorusuna somut ve denetlenebilir bir cevap verebilir hale gelir.

Buradaki en kritik kavram **veri kaynağı** (data source) düşüncesidir. Bir tekniği tespit edebilmenin önkoşulu, o tekniğin ürettiği izi yakalayan bir telemetriye sahip olmaktır. ATT&CK, her teknik için hangi veri kaynaklarının ve **veri bileşenlerinin** (data components) o tekniği görünür kıldığını belgeler. Örneğin süreç oluşturma olayları (process creation), komut satırı argümanları, Windows olay günlükleri, DNS sorguları, ağ trafiği akış kayıtları gibi. Mantık şudur: eğer bir tekniğin ürettiği izi hiç toplamıyorsanız, o teknik için ne kadar akıllı bir tespit kuralı yazarsanız yazın, kör kalırsınız. Bu yüzden olgun tespit haritalama, önce "doğru telemetriyi topluyor muyum" sorusuyla başlar, sonra "bu telemetriden doğru sinyali çıkarabiliyor muyum" sorusuna geçer.

MITRE'nin bu alandaki tamamlayıcı çalışmalarını bilmek faydalıdır. **MITRE CAR** (Cyber Analytics Repository) belirli tekniklere yönelik analitik örnekleri sunar. **MITRE D3FEND** ise savunma tekniklerini, tespit ve müdahale önlemlerini yapılandıran, ATT&CK'in savunma tarafındaki karşılığı gibi düşünülebilecek bir bilgi grafiğidir. Bu iki çerçeveyi ATT&CK ile birlikte kullanmak, "saldırgan bunu yapıyor" (ATT&CK) ile "ben buna şöyle karşı koyarım" (D3FEND) arasındaki köprüyü kurar.

Tespit haritalamada olgunluğu değerlendirmek için soyut bir merdiven düşünmek yararlıdır. En alt basamakta hiçbir görünürlük yoktur. Bir üstünde ilgili telemetri toplanır ama analiz edilmez. Daha yukarıda telemetri üzerinde basit, kırılgan tespitler vardır (örneğin sabit bir dosya yoluna dayanan bir kural). En üstte ise davranışın **değişmez özüne** dayanan, saldırganın kolayca atlatamayacağı sağlam tespitler bulunur. Amaç, tespitleri bu merdivende yukarı taşımaktır. İyi bir tespit, saldırganın tekniği uygulamak için zorunlu olarak yapmak durumunda olduğu şeyi yakalar; kötü bir tespit ise saldırganın rahatça değiştirebileceği yüzeysel bir ayrıntıya (belirli bir dosya adı gibi) bağlıdır.

## İstismar Mantığı ve Savunma: İki Tarafı Birlikte Görmek

ATT&CK'in gerçek gücü, hem saldırı hem savunma perspektifini aynı dilde birleştirmesindedir. Bir tekniği hem "saldırgan bunu neden ve nasıl yapar" hem de "ben buna nasıl karşı koyarım" açısından okumak, savunmayı çok daha derinleştirir.

Somut bir örnek: **T1003 - OS Credential Dumping**, özellikle işletim sistemi bellek alanından kimlik bilgisi çıkarma. Saldırgan tarafında mantık şudur: birçok işletim sisteminde, oturum açmış kullanıcıların kimlik bilgileri veya bunların türevleri (hash'ler, bilet gibi yapılar) çalışan bir sistem sürecinin belleğinde tutulur. Saldırgan yeterli yetkiye ulaştığında bu sürecin belleğini okuyarak kimlik bilgilerini ele geçirmeye çalışır. Bunu neden yapar? Çünkü ele geçirdiği tek bir makinede takılıp kalmak istemez; başka sistemlere yanlamasına hareket edebilmek için geçerli kimlik bilgilerine ihtiyacı vardır. Kimlik bilgisi çalma, saldırının "çarpan etkisi"ni sağlayan adımdır.

Savunma tarafında bu davranışa çok katmanlı yaklaşılır. Birinci katman **önleme**dir: hassas kimlik bilgisi süreçlerinin belleğine erişimi zorlaştıran işletim sistemi koruma özelliklerini etkinleştirmek, ayrıcalıklı hesapların sayısını azaltmak, farklı güven seviyelerindeki sistemler arasında kimlik bilgisi paylaşımını engellemek (böylece bir makinede çalınan kimlik bilgisi başka yerde işe yaramaz). İkinci katman **tespit**tir: hassas sürece erişen olağandışı süreçleri, bilinen çıkarma araçlarının davranış imzalarını, beklenmedik yüksek yetkili erişim örüntülerini izlemek. Üçüncü katman **daraltma**dır: bir kimlik bilgisi çalınsa bile etkisini sınırlamak için ayrıcalıklı erişimi katmanlamak ve segmentlemek. Görüldüğü gibi tek bir tekniği anlamak, birbirini tamamlayan bir savunma katmanları dizisini beraberinde getirir.

Bir başka örnek **T1078 - Valid Accounts** (Geçerli Hesaplar). Bu teknik savunmacılar için özellikle sinsidir, çünkü saldırgan burada herhangi bir zararlı yazılım kullanmaz; sadece meşru kimlik bilgileriyle sisteme "normal bir kullanıcı gibi" giriş yapar. İstismar mantığı sadeliğinde yatar: en iyi zararlı yazılım, hiç zararlı yazılım kullanmamaktır. Savunma tarafında bu, imza tabanlı tespitin neden yetersiz kaldığının ders kitabı örneğidir. Buna karşı savunma davranışsal olmak zorundadır: bir hesabın alışılmadık bir zamanda, alışılmadık bir konumdan, alışılmadık kaynaklara erişmesi gibi **anomali temelli** sinyallere ve çok faktörlü kimlik doğrulamaya (MFA) dayanır. Bu örnek, ATT&CK'in neden zararlı yazılım değil davranış üzerine kurulduğunu bir kez daha gösterir: en tehlikeli teknikler çoğu zaman hiç "zararlı dosya" içermez.

Etik bir not gereklidir: bu makalede istismar mantığı, ancak savunmayı doğru kurgulayabilmek için gereken kavramsal derinlikte anlatılmıştır. Bir tekniğin "neden işe yaradığını" anlamayan bir savunmacı, ona karşı yalnızca yüzeysel ve kolayca atlatılabilen önlemler kurar. İstismarın mantığını anlamak, savunmanın önkoşuludur.

## Purple Team: Çerçeveyi Canlı Hâle Getirmek

ATT&CK'in en olgun kullanımı **purple team** (mor takım) pratiğindedir. Purple team, kırmızı takım (saldırıyı taklit eden) ile mavi takımın (savunan) rekabet yerine işbirliği içinde çalıştığı bir yaklaşımdır. Amaç, savunmanın gerçek saldırgan davranışlarına karşı ne kadar dayanıklı olduğunu **kanıta dayalı** biçimde ölçmektir.

Purple team çalışmasının mantığı şudur: ATT&CK bir tekniği tespit edebildiğinizi iddia etmenizi sağlar, ama iddia ile gerçeklik arasında çoğu zaman büyük bir uçurum vardır. Bir tespit kuralının SIEM'de var olması, o kuralın gerçek bir saldırıda tetikleneceği anlamına gelmez. Kural yanlış varsayımlar üzerine kurulmuş olabilir, telemetri beklendiği gibi akmıyor olabilir, ya da saldırganın kullandığı prosedür kuralın kapsamının dışında kalabilir. Purple team, bu boşluğu **gerçek testle** kapatır: kırmızı takım belirli bir ATT&CK tekniğini kontrollü biçimde uygular, mavi takım da tespitin gerçekten çalışıp çalışmadığını gözlemler.

Bu döngü genellikle şöyle işler. Önce bir tehdit modeli veya istihbarat raporundan hareketle test edilecek teknikler seçilir. Ardından kırmızı takım bu teknikleri emüle eder; bunun için **atomik test** yaklaşımı çok yaygındır, yani her tekniği izole, tekrarlanabilir küçük eylemler olarak çalıştırmak. Atomic Red Team gibi açık kaynak kütüphaneler tam da bu amaçla, her ATT&CK tekniğine karşılık gelen küçük test betikleri sunar. Test çalıştırılırken mavi takım telemetriyi ve tespitleri izler. Sonrasında üç olası sonuç ortaya çıkar: tespit çalıştı (yeşil), tespit hiç tetiklenmedi (kırmızı, bir görünürlük boşluğu var), ya da tespit tetiklendi ama gürültülü/yanlış pozitifti (iyileştirme gerekiyor). Her sonuç bir aksiyona dönüşür ve döngü tekrar edilir. Bu, savunmayı zaman içinde ölçülebilir biçimde olgunlaştıran bir geri besleme çevrimidir.

Daha büyük ölçekli senaryolar için MITRE'nin **Adversary Emulation** (düşman emülasyonu) yaklaşımı ve **CALDERA** gibi otomasyon platformları vardır. Emülasyon, atomik testten farklı olarak belirli bir gerçek tehdit aktörünün davranış zincirini baştan sona, o aktörün karakteristik prosedürleriyle taklit etmeyi hedefler. Örneğin belirli bir aktörün tipik olarak hangi ilk erişim yöntemini kullanıp ardından hangi keşif ve yanlamasına hareket adımlarını attığını sırasıyla canlandırmak. Bu, "tekil teknikleri görebiliyor muyum" sorusundan "gerçekçi bir saldırı zincirinin tamamını görebiliyor muyum" sorusuna geçmeyi sağlar; ki savunmadaki en tehlikeli boşluklar çoğu zaman tekniklerin arasındaki geçişlerde gizlidir.

Purple team çalışmasının çıktısı, ATT&CK Navigator üzerinde renklendirilmiş, artık **iddiaya değil kanıta dayanan** bir kapsama haritasıdır. Bir teknik yeşilse, bu artık "tespit kuralımız var" demek değil, "bu tekniği çalıştırdık ve gerçekten yakaladık" demektir. Bu ayrım, güvenlik olgunluğunun tam kalbindedir.

## Yaygın Hatalar

**ATT&CK'i bir kontrol listesi sanmak.** En sık yapılan hata, matrisin tamamını "tamamlanması gereken bir liste" gibi görmektir. Bunun sonucu, ortamıyla alakasız tekniklere kaynak harcayan, buna karşılık kendi tehdit modeli için kritik olan az sayıda tekniği ihmal eden bir savunma programıdır. ATT&CK önceliklendirme aracıdır, bir onay kutuları listesi değil.

**Kapsamayı prosedür körlüğüyle şişirmek.** Bir tekniğin tek bir prosedürünü tespit edip "bu tekniği kapsıyorum" demek, yanlış bir güven yaratır. Aynı teknik onlarca farklı biçimde uygulanabilir. Kapsama, tekniğin ne kadar farklı gerçekleşme biçimine karşı sağlam olduğunuza göre değerlendirilmelidir, teoride bir kuralın var olmasına göre değil.

**Telemetriyi göz ardı ederek tespit yazmak.** Altında toplayan bir veri kaynağı olmayan bir teknik için tespit kuralı yazmak, camsız bir pencereden dışarı bakmaya çalışmaya benzer. Tespit haritalama daima veri kaynağı gerçekliğiyle başlamalıdır.

**Sürüm kaymasını izlememek.** ATT&CK yaşayan bir çerçevedir; teknikler bölünür, birleşir, kimlikleri değişir, yenileri eklenir. Bir kez yapılan haritalamayı güncel varsaymak, zamanla sessizce eskiyen ve gerçeği yansıtmayan bir kapsama görünümüne yol açar. Haritalama periyodik olarak güncel sürümle uyumlanmalıdır.

**Kırmızı ve mavi takımı izole çalıştırmak.** Kırmızı takımın bulgularını mavi takımla paylaşmayan, rekabetçi bir "yakala-kaç" modeli, öğrenmeyi öldürür. ATT&CK'in purple team değeri tam da bu duvarı yıkmasındadır; testler savunmayı iyileştirmek için yapılır, puan tutmak için değil.

**ATT&CK'i tek başına bir strateji sanmak.** Çerçeve güçlü bir ortak dil ve harita sağlar ama kendi başına bir risk yönetimi, önceliklendirme veya iş bağlamı sunmaz. ATT&CK; tehdit istihbaratı, varlık envanteri ve risk değerlendirmesiyle birlikte kullanıldığında değer üretir.

## En İyi Pratikler

**Tehdit modelinden başla, matristen değil.** Önce "beni kim, neden, hangi yeteneklerle hedefliyor" sorusunu cevapla. Sektörünü ve teknoloji yığınını hedefleyen aktörlerin bilinen tekniklerini önceliklendir. Boş bir matrisi doldurmaya çalışmak yerine, tehdit odaklı ve önceliklendirilmiş bir kapsama hedefi belirle.

**Kapsamayı kanıta dayandır.** "Tespit kuralımız var" ile "bu tekniği çalıştırdık ve yakaladık" arasındaki farkı sürekli koru. Navigator haritalarını mümkün olduğunca purple team testleriyle doğrulanmış hâle getir. Doğrulanmamış kapsama, ölçüm değil temenni sayılmalıdır.

**Tespitleri davranışın değişmez özüne demirle.** Bir tekniği uygulamak için saldırganın zorunlu olarak yapmak durumunda olduğu şeyi hedef al. Kolayca değiştirilebilen yüzeysel ayrıntılara (dosya adı, sabit yol, belirli bir hash) dayanan kırılgan kurallardan uzak dur; bunlar Acı Piramidi'nin tabanında yer alır ve saldırgana neredeyse hiç maliyet çıkarmaz.

**Önce görünürlük, sonra tespit.** Her tespit girişimini bir veri kaynağı denetimiyle başlat. Doğru telemetriyi toplamadan yazılan tespit kuralları güvenlik değil, güvenlik yanılsaması üretir.

**Çerçeveyi bir iletişim aracı olarak kullan.** ATT&CK kimliklerini tehdit istihbaratı raporlarında, olay müdahale kayıtlarında, tespit kural belgelerinde ve yönetim sunumlarında ortak referans olarak kullan. Bu, teknik ve yönetsel katmanlar arasında tutarlı bir dil kurar ve "ne kadar korunuyoruz" sorusunun somut, gösterilebilir bir cevabını mümkün kılar.

**D3FEND ve CAR ile eşleştir.** Saldırgan davranışını ATT&CK ile haritaladıktan sonra, karşı önlemleri D3FEND ile, analitikleri CAR ile ilişkilendir. Böylece "saldırgan ne yapıyor" ile "ben ne yapıyorum" arasında izlenebilir bir bağ kurarsın.

**Süreklilik kur, tek seferlik proje yapma.** ATT&CK kapsama analizi ve purple team çalışmaları bir kereye mahsus bir denetim değil, düzenli tekrarlanan bir olgunlaşma döngüsü olmalıdır. Tehdit ortamı, ortamın ve çerçevenin kendisi sürekli değiştiği için, kapsama görünümü de canlı tutulmadıkça hızla gerçeklikten kopar.

## Kapanış

MITRE ATT&CK, güvenliği yüzeysel göstergelerden davranışsal gerçekliğe taşıyan bir zihniyet değişiminin somutlaşmış hâlidir. Değeri, doldurulacak bir matris olmasında değil; saldırganın zorunlu adımlarını görünür kılan, kırmızı ve mavi takımı ortak bir dilde buluşturan ve savunmanın gerçek dünyada işe yarayıp yaramadığını kanıta dayalı biçimde ölçmeyi mümkün kılan bir çerçeve olmasındadır. Doğru kullanıldığında ATT&CK, "kendimizi ne kadar güvende hissediyoruz" sorusunu, "hangi saldırgan davranışlarını gerçekten yakalayabildiğimizi kanıtlayabiliyoruz" sorusuna dönüştürür. Olgun bir güvenlik programı ile temenni arasındaki fark tam olarak buradadır.
