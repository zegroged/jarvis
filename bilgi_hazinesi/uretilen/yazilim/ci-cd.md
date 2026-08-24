# CI/CD Pipeline: Otomatik Test, Güvenlik Taraması ve Güvenli Dağıtım Stratejileri

## Tanım

CI/CD, yazılımın kaynak kodundan üretim ortamına giden yolu otomatikleştiren bir mühendislik disiplinidir. İki kavramın birleşiminden oluşur: **Continuous Integration (CI)** ve **Continuous Delivery/Deployment (CD)**.

**Continuous Integration**, geliştiricilerin ürettiği kod değişikliklerini paylaşılan bir ana dala (genellikle `main` veya `trunk`) sık sık, günde birçok kez birleştirme pratiğidir. Her birleştirme, otomatik bir doğrulama zincirini (build, test, lint) tetikler. Amaç, entegrasyon sorunlarını haftalar sonra değil dakikalar içinde yakalamaktır.

**Continuous Delivery**, doğrulamadan geçen her değişikliğin üretime çıkarılmaya *hazır* hale getirilmesidir; son "yayınla" düğmesine bir insan basar. **Continuous Deployment** ise bu son adımı da otomatikleştirir: testlerden geçen her değişiklik insan müdahalesi olmadan üretime gider.

Bir CI/CD pipeline'ı, bu sürecin somutlaşmış hâlidir: kaynak kod deposundaki bir olayla (push, pull request, merge) tetiklenen, sırayla veya paralel çalışan aşamalardan (stages) oluşan otomatik bir iş akışıdır. Tipik bir pipeline şu aşamaları içerir: kaynak kodu çekme, bağımlılıkları kurma, derleme (build), statik analiz (lint), otomatik testler, güvenlik taraması, yapıt (artifact) üretimi ve dağıtım (deploy).

## Kök Neden: CI/CD Neden Var, Neden Böyle Çalışıyor?

CI/CD'nin çözdüğü asıl problem, yazılım geliştirmedeki **entegrasyon acısıdır** (integration pain). Bu acının kök nedenini anlamak, pipeline tasarımının neden bu şekilde olduğunu açıklar.

### Entegrasyon maliyeti zamanla üstel olarak artar

Bir geliştirici bir dalda (branch) haftalarca izole çalıştığında, o dal ana daldan giderek uzaklaşır (drift). Birleştirme anı geldiğinde çözülmesi gereken çakışmalar (merge conflict), test edilmemiş varsayımlar ve uyumsuzluklar birikmiştir. İki geliştirici aynı anda uzaklaştıysa, çakışma matrisi katlanarak büyür. Bu, "entegrasyon cehennemi" denen durumdur.

CI'ın temel içgörüsü şudur: **küçük ve sık entegrasyonların toplam maliyeti, büyük ve seyrek entegrasyonların maliyetinden çok daha düşüktür.** Her değişiklik küçükse, hata yüzeyi küçüktür; bir şey bozulduğunda son commit'e bakmak yeterlidir. Bu yüzden CI, "hızlı geri bildirim" (fast feedback) üzerine kuruludur. Pipeline'ın hızlı olması bir konfor değil, sistemin çalışma mantığının temelidir; on dakikada sonuç veren bir pipeline geliştiriciyi bağlamda tutar, kırk dakikalık bir pipeline ise onu başka işe geçmeye ve geri bildirimi görmezden gelmeye iter.

### Otomasyon, güveni "tekrarlanabilirlik" üzerine kurar

Manuel dağıtımların temel sorunu, insan hafızasına ve o anki ortama bağlı olmalarıdır. "Benim makinemde çalışıyordu" problemi, üretim ortamının geliştirme ortamından farklı olmasından doğar. CI/CD bunu **deterministik ve tekrarlanabilir** bir süreçle çözer: aynı commit, aynı pipeline'dan geçtiğinde her zaman aynı yapıtı üretmeli ve aynı davranışı sergilemelidir. Bu yüzden modern pipeline'lar konteyner (container) tabanlı, izole ve durumsuz (stateless) çalışacak şekilde tasarlanır. Her çalışma temiz bir ortamda başlar ki, önceki bir çalışmadan kalan bir dosya veya ortam değişkeni gizli bir bağımlılığa dönüşmesin.

### "Shift left" felsefesi

CI/CD'nin arkasındaki ekonomik mantık şudur: bir hatayı yakalamanın maliyeti, o hata sürecin ne kadar ilerisinde bulunursa o kadar artar. Kod yazılırken yakalanan bir hata dakikalar, üretimde patlayan bir hata ise saatler, itibar kaybı ve gelir kaybıyla ölçülür. "Shift left" (sola kaydırma), doğrulama faaliyetlerini (test, güvenlik, kalite) sürecin mümkün olduğunca başına çekme stratejisidir. Pipeline'daki aşamaların sırası bu felsefeyi yansıtır: ucuz ve hızlı kontroller (lint, birim testleri) önce, pahalı ve yavaş olanlar (entegrasyon testleri, uçtan uca testler) sonra çalışır ki hızlı başarısızlık (fail fast) mümkün olsun.

## Otomatik Test, Lint ve Güvenlik Taraması

Bir pipeline'ın doğrulama katmanı üç ana bileşenden oluşur. Bunların doğru sıralanması ve doğru "sıkılık" seviyesinde ayarlanması, pipeline'ın hem güvenilir hem de kullanışlı olmasını belirler.

### Test piramidi ve neden buna uyulmalı

Otomatik testler tek tip değildir; maliyet ve kapsam açısından katmanlıdır. **Test piramidi** kavramı bu katmanların ideal dağılımını anlatır:

- **Birim testleri (unit tests)** piramidin tabanını oluşturur: hızlı, izole, çok sayıda. Tek bir fonksiyonun veya sınıfın mantığını, dış bağımlılıkları taklit ederek (mock) test ederler. Milisaniyeler sürerler.
- **Entegrasyon testleri (integration tests)** ortada yer alır: birkaç bileşenin birlikte çalışmasını, gerçek bir veritabanı veya servis ile test ederler. Daha yavaş, daha az sayıda.
- **Uçtan uca testler (end-to-end, E2E)** tepede, en az sayıda olmalıdır: tüm sistemi kullanıcı gözünden test ederler. Yavaş, kırılgan (flaky olmaya yatkın) ve pahalıdırlar.

Piramidin ters çevrilmesi (çoğunlukla E2E testine dayanmak) yaygın bir başarısızlık kaynağıdır. Yavaş ve kararsız E2E testleri pipeline'ı hem yavaşlatır hem de "flaky test" sorununu büyütür. Flaky test, aynı kodla bazen geçip bazen kalan testtir; kök nedeni genellikle testin zamanlamaya, ağ gecikmesine veya paylaşılan duruma bağımlı olmasıdır. Flaky testler tehlikelidir çünkü ekibin pipeline'a olan güvenini aşındırır: kırmızı sonucu gören geliştirici "muhtemelen yine flaky'dir" deyip tekrar çalıştırır ve gerçek bir hatayı bu şekilde gözden kaçırabilir.

### Lint ve statik analiz: hataları çalıştırmadan yakalamak

Lint araçları, kodu *çalıştırmadan* metin ve yapı düzeyinde inceleyerek stil ihlallerini, potansiyel hataları ve kod kokularını (code smell) yakalar. Statik analiz bunun daha derin bir biçimidir: veri akışını izleyerek kullanılmayan değişkenleri, erişilemez kodu, null referans riskini veya tip uyumsuzluklarını bulur.

Bunların pipeline'da olmasının kök nedeni **tutarlılık ve gürültü azaltmadır**. Otomatik lint olmadan, kod incelemesinde (code review) insanlar boşluk, isimlendirme ve stil tartışmalarına saplanır; asıl önemli olan mantık gözden kaçar. Lint'i otomatikleştirmek, bu tartışmaları makineye devrederek insan incelemesini değerli konulara odaklar. Lint aşaması hızlı olduğu için pipeline'ın başında, testlerden önce çalıştırılır: biçimsel bir hata varsa, on dakikalık test sürecini beklemeden anında geri bildirim verilir.

### Güvenlik taraması: SAST, DAST, SCA ve secret tarama

Güvenlik taraması pipeline'a entegre edildiğinde buna genellikle **DevSecOps** denir. Temel içgörü, güvenliğin dağıtımdan sonra yapılan bir denetim değil, sürecin bir parçası olması gerektiğidir. Başlıca tarama türleri şunlardır:

- **SAST (Static Application Security Testing):** Kaynak kodu statik olarak analiz ederek güvenlik açığı desenlerini arar; örneğin SQL injection'a açık sorgu birleştirmeleri, güvensiz deserialization, veya kriptografik zayıflıklar. Kodu çalıştırmadan, erken aşamada çalışır.
- **DAST (Dynamic Application Security Testing):** Çalışan uygulamaya dışarıdan, saldırgan gözüyle istekler göndererek açık arar. Çalışan bir örnek gerektirdiği için pipeline'ın ilerisinde, bir test ortamına dağıtımdan sonra çalışır.
- **SCA (Software Composition Analysis):** Projenin bağımlılıklarını (kütüphaneler, paketler) bilinen açık veritabanlarıyla karşılaştırır. Modern uygulamaların kodunun büyük bölümü üçüncü parti bağımlılıklardan geldiği için bu kritiktir; bir bağımlılıkta bilinen bir güvenlik açığı varsa SCA bunu raporlar.
- **Secret tarama:** Koda yanlışlıkla işlenmiş API anahtarları, parolalar ve tokenları arar. Bir sır (secret) bir kez depoya girdiğinde, sonradan silinse bile Git geçmişinde kalır; bu yüzden hem push öncesi (pre-commit hook) hem de pipeline düzeyinde taranmalıdır.

Güvenlik taramalarının pratik zorluğu **yanlış pozitiflerdir** (false positive). Bir tarayıcı yüzlerce uyarı ürettiğinde, ekip alarm yorgunluğu (alert fatigue) yaşar ve uyarıları görmezden gelmeye başlar. Bu yüzden olgun bir kurulumda, taramanın çıktısı önem derecesine göre kademelendirilir: yalnızca kritik ve yüksek önem dereceli, sömürülebilir açıklar pipeline'ı durdurur (build fail), düşük seviyeliler ise raporlanır ama engellemez.

### Aşama sıralaması: neden bu sıra?

Aşamaların sırası rastgele değildir; **ucuzdan pahalıya, hızlıdan yavaşa** ilkesine dayanır:

1. Lint ve format kontrolü (saniyeler)
2. Birim testleri (saniyeler-dakikalar)
3. SAST ve secret tarama (dakikalar)
4. Build ve yapıt üretimi
5. Entegrasyon testleri (dakikalar)
6. SCA (bağımlılık taraması)
7. Test ortamına dağıtım
8. DAST ve E2E testleri (dakikalar-saatler)

Bu sıralama sayesinde ucuz bir hata (bir lint ihlali) pahalı aşamaları hiç tetiklemeden yakalanır. Ayrıca bağımsız aşamalar (örneğin lint ile birim testleri) paralel çalıştırılarak toplam süre kısaltılır.

## Dağıtım Stratejileri: Blue-Green ve Canary

Doğrulamadan geçen yapıtı üretime çıkarmak, pipeline'ın en riskli anıdır. Naif yaklaşım, eski sürümü durdurup yenisini başlatmaktır (recreate); bu, kesinti (downtime) yaratır ve yeni sürüm bozuksa geri dönüş yavaştır. Blue-green ve canary, bu riski yönetmek için geliştirilmiş iki temel desendir.

### Blue-Green Deployment

Blue-green stratejisinde iki özdeş üretim ortamı bulundurulur: "blue" (şu an canlı olan) ve "green" (yeni sürümün dağıtıldığı). Süreç şöyledir: yeni sürüm green ortamına dağıtılır ve üzerinde son kontroller (smoke test) yapılır. Her şey yolundaysa, yönlendirici (load balancer veya router) trafiği aniden blue'dan green'e çevirir. Green artık canlıdır; blue ise bir süre bekletilir.

Bu yaklaşımın **kök mantığı**, geçişi atomik ve tersinir kılmaktır. Trafik tek bir noktada (router seviyesinde) değiştiği için geçiş anlıktır ve kesintisizdir. Bir sorun çıkarsa geri dönüş de aynı derecede hızlıdır: trafik tekrar blue'ya çevrilir. Blue ortamı hâlâ ayakta ve eski sürümle çalışır durumda olduğu için rollback, yeniden dağıtım gerektirmez; sadece bir yönlendirme değişikliğidir.

Blue-green'in **bedeli**, aynı anda iki tam üretim ortamının kaynak maliyetidir. Ayrıca **veritabanı** bu desenin en zor noktasıdır: iki uygulama sürümü çoğu zaman tek bir veritabanını paylaşır. Bu, veritabanı şema değişikliklerinin (migration) her iki sürümle de uyumlu (geriye dönük uyumlu, backward-compatible) olmasını zorunlu kılar. Yeni sürüm bir sütunu silen bir migration çalıştırırsa ve rollback gerekirse, eski sürüm o sütunu bulamayıp çöker. Bu yüzden şema değişiklikleri "expand/contract" (genişlet/daralt) deseniyle, yani önce ekleyip sonraki bir dağıtımda temizleyerek yapılmalıdır.

### Canary Deployment

Canary stratejisi (adını, madencilerin zehirli gazı erken fark etmek için kullandığı kanaryadan alır) daha kademeli bir yaklaşımdır. Yeni sürüm, trafiğin yalnızca küçük bir yüzdesine (örneğin %1, sonra %5, sonra %25) sunulur. Bu küçük dilimde hata oranları, gecikme (latency) ve iş metrikleri izlenir. Metrikler sağlıklıysa yüzde kademeli olarak artırılır; bozulma görülürse trafik geri çekilir.

Canary'nin blue-green'e göre **temel üstünlüğü**, riski gerçek üretim trafiğiyle ama sınırlı bir kitleyle test etmesidir. Blue-green'de geçiş anında %100 trafik yeni sürüme gider; sürüm smoke testlerden geçse de gerçek yükte ortaya çıkan bir sorun tüm kullanıcıları etkiler. Canary'de aynı sorun yalnızca kullanıcıların %1'ini etkiler ve otomatik olarak yakalanabilir.

Canary'nin **çalışması için şart olan** unsur, iyi bir **gözlemlenebilirlik** (observability) altyapısıdır. Canary dilimini "sağlıklı" ilan etmek için ölçülebilir metrikler gerekir: hata oranı, p99 gecikme, CPU/bellek, iş metrikleri (örneğin ödeme başarı oranı). Bu metrikler otomatik değerlendirilip (analysis) kararlar buna göre verildiğinde buna "progressive delivery" denir. Metrik olmadan yapılan canary, körlemesine kademeli dağıtımdan ibarettir ve asıl değerini vermez.

Canary'nin **tuzağı**, istatistiksel anlamlılıktır. %1 trafiğe sunulan bir sürümde, nadir görülen bir hatayı yakalamak için yeterli örnek toplanana kadar beklemek gerekir. Çok hızlı ilerlenirse sorun küçük dilimde fark edilmeden %100'e ulaşabilir; çok yavaş ilerlenirse dağıtım saatlerce sürer. Ayrıca "session affinity" sorunu vardır: bir kullanıcı bir istekte yeni, sonrakinde eski sürüme düşerse tutarsız deneyim yaşayabilir; bu yüzden yönlendirme genellikle kullanıcı bazında sabitlenir.

### İki stratejinin karşılaştırması

Blue-green, hızlı ve atomik geçiş ile hızlı rollback isteyen, ama tam üretim yükünde risk almaya hazır durumlar için uygundur. Canary ise riski gerçek trafikte kademeli sınamak ve otomatik metrik değerlendirmesiyle güvenliği artırmak isteyen durumlar için üstündür; bedeli daha karmaşık bir yönlendirme ve gözlemlenebilirlik altyapısıdır. Pratikte ikisi birleştirilebilir: yeni sürüm önce küçük bir canary olarak sunulur, güven oluşunca blue-green tarzı tam geçişe çevrilir.

## Rollback: Geri Dönüş Stratejisi

Rollback, dağıtılan bir sürümün bozuk olduğu anlaşıldığında sistemi bilinen iyi bir duruma döndürme yeteneğidir. CI/CD kültüründeki kritik ilke şudur: **her ileri dağıtımın (roll-forward) güvenli bir geri dönüş yolu olmalıdır.** Rollback planı olmayan bir dağıtım, riskin kabul edildiği değil, görmezden gelindiği bir dağıtımdır.

### Neden rollback her zaman "eski koda dönmek" değildir

En basit rollback, önceki yapıtı yeniden dağıtmaktır. Blue-green'de bu bir yönlendirme değişikliği kadar kolayken, düz (rolling) bir dağıtımda önceki sürümü yeniden yaymak gerekir. Ancak asıl zorluk kod değil, **durumdur (state)**. Kod geri alınabilir ama yeni sürümün veritabanında yaptığı değişiklikler (silinen sütunlar, dönüştürülen veriler) her zaman geri alınamaz. Bir migration verileri geri döndürülemez biçimde dönüştürdüyse, koda dönmek yeterli olmaz.

Bu yüzden olgun ekipler genellikle **roll-forward** stratejisini tercih eder: geriye dönmek yerine, sorunu düzelten yeni bir dağıtımı hızla ileri sürmek. Roll-forward, özellikle veritabanı değişiklikleri söz konusu olduğunda daha güvenlidir çünkü geriye dönük uyumluluk zaten korunmuştur. Rollback ile roll-forward arasındaki seçim, değişikliğin durum üzerindeki etkisine bağlıdır.

### Rollback'i mümkün kılan tasarım ilkeleri

Rollback'in çalışması, dağıtım anında değil çok önce, tasarım aşamasında belirlenir:

- **Geriye dönük uyumlu değişiklikler:** Her sürüm, hem kendinden bir önceki hem de bir sonraki sürümle birlikte çalışabilmelidir. Bu, blue-green ve canary'de zaten iki sürümün eş zamanlı çalışmasından ötürü zorunludur.
- **Expand/contract migration:** Şema değişiklikleri iki adıma bölünür. Önce genişletme (yeni sütun ekle, iki yeri de yaz), sürüm kararlı olunca daraltma (eski sütunu kaldır). Böylece herhangi bir anda rollback güvenlidir.
- **Feature flag ile ayrıştırma:** En güçlü tekniklerden biri, dağıtım ile özelliği açmayı birbirinden ayırmaktır. Kod üretime dağıtılır ama yeni özellik bir bayrağın (feature flag) arkasında kapalı durur. Sorun çıkarsa yeniden dağıtım yapmadan, bayrağı kapatarak anında "rollback" yapılır. Bu, dağıtım riskini kod dağıtımından çalışma zamanı yapılandırmasına taşır ve en hızlı geri dönüş yoludur.
- **Immutable artifacts:** Her sürüm için değişmez, sürümlenmiş bir yapıt üretilir. Rollback, "önceki koddan yeniden derle" değil, "önceki sürümlenmiş yapıtı yeniden çalıştır" olmalıdır; yeniden derleme, farklı bir bağımlılık sürümü çekerek rollback'i deterministik olmaktan çıkarabilir.

### Otomatik rollback

Olgun pipeline'larda rollback otomatikleştirilir. Canary sürecinde metrikler (hata oranı, gecikme) tanımlı eşikleri aşarsa, sistem insan müdahalesi beklemeden trafiği geri çeker. Bunun işlemesi için sağlıklılık kriterlerinin önceden ve ölçülebilir biçimde tanımlanmış olması gerekir. Otomatik rollback, ortalama düzeltme süresini (MTTR, mean time to recovery) dramatik biçimde düşürür; çünkü gece yarısı bir insanın uyanıp durumu değerlendirmesini beklemez.

## Yaygın Hatalar

**Yavaş pipeline'a katlanmak.** Kırk dakikalık bir pipeline, geliştiricileri değişiklikleri biriktirip toplu göndermeye iter; bu da CI'ın "küçük ve sık" ilkesini bozar. Pipeline süresi ürünün bir parçası gibi izlenmeli ve optimize edilmelidir.

**Flaky testleri tolere etmek.** Kararsız testler pipeline'a olan güveni yok eder. "Yeşile dönene kadar tekrar çalıştır" alışkanlığı, gerçek hataların gözden kaçmasına yol açar. Flaky bir test ya düzeltilmeli ya karantinaya alınmalıdır; asla görmezden gelinmemelidir.

**Güvenlik taramasını "engellemeyen uyarı" olarak bırakmak.** Hiçbir tarama sonucu build'i durdurmuyorsa, uyarılar zamanla birikir ve kimse bakmaz. Öte yandan her uyarıyı engelleyici yapmak da alarm yorgunluğu yaratır. Doğru denge, önem derecesine göre kademelendirmedir.

**Sırları koda gömmek.** API anahtarlarını veya parolaları koda ya da pipeline yapılandırmasına düz metin yazmak yaygın ve tehlikelidir. Sırlar bir secret yönetim sisteminde tutulmalı, pipeline'a çalışma anında enjekte edilmelidir. Log'lara sır sızmaması da ayrıca korunmalıdır.

**Rollback'i test etmemek.** Rollback yolu, ihtiyaç duyulduğu ilk an değil, önceden test edilmelidir. Hiç denenmemiş bir rollback planı, kriz anında çalışmayabilir. Geriye dönük uyumluluk varsayımları düzenli olarak doğrulanmalıdır.

**Veritabanı migration'larını dağıtım riskine dahil etmemek.** Ekipler çoğu zaman kod dağıtımını dikkatle planlar ama şema değişikliklerini düşünmeden çalıştırır. Geriye dönük uyumsuz bir migration, en özenli blue-green veya canary stratejisini bile işe yaramaz hale getirir.

**Ortamlar arası tutarsızlık.** Test ortamının üretimden farklı olması, "test ortamında geçti ama üretimde patladı" durumunu yaratır. Ortamlar mümkün olduğunca aynı (konteyner, altyapı-kod, infrastructure as code) tutulmalıdır.

## En İyi Pratikler

**Pipeline'ı kod olarak yönetin.** Pipeline tanımı depoda, kodla birlikte versiyonlanmalıdır (pipeline as code). Böylece pipeline değişiklikleri de incelemeden geçer ve geçmişi izlenebilir.

**Hızlı geri bildirimi önceliklendirin.** Ucuz kontrolleri öne alın, bağımsız aşamaları paralelleştirin, bağımlılık ve derleme çıktılarını önbelleğe (cache) alın. Hedef, geliştiriciyi bağlamda tutacak kadar kısa bir çevrimdir.

**Her aşamayı deterministik ve izole tutun.** Temiz ortamda, sürümlenmiş bağımlılıklarla, dış duruma minimum bağımlılıkla çalıştırın. Aynı commit her zaman aynı sonucu vermelidir.

**Güvenliği sürece gömün (shift left).** SAST, SCA ve secret taramayı pipeline'ın erken aşamalarına, ideal olarak pre-commit hook'lara kadar taşıyın. Güvenliği en sondaki bir kapı değil, sürekli bir kontrol yapın.

**Dağıtımı özellik açmaktan ayırın.** Feature flag kullanarak koda dağıtmayı, özelliği kullanıcıya açmaktan bağımsızlaştırın. Bu, hem güvenli rollback hem de kademeli sunum sağlar.

**Gözlemlenebilirliğe yatırım yapın.** Canary ve otomatik rollback, iyi metrikler olmadan çalışmaz. Hata oranı, gecikme ve iş metriklerini dağıtım kararlarına bağlayın.

**Şema değişikliklerini expand/contract ile yapın.** Geriye dönük uyumluluğu her zaman koruyun ki blue-green, canary ve rollback güvenli kalsın.

**Rollback'i birinci sınıf bir yetenek olarak tasarlayın.** Her dağıtım için geri dönüş yolunu önceden belirleyin, test edin ve mümkünse otomatikleştirin. En iyi dağıtım stratejisi, en kötü senaryoyu ucuz kılan stratejidir.

## Sonuç

CI/CD, tek bir araç değil, yazılımın güvenilir biçimde üretime akmasını sağlayan bir mühendislik disiplinidir. Otomatik test, lint ve güvenlik taraması, hataları ucuz oldukları erken aşamada yakalayarak güven inşa eder. Blue-green ve canary gibi dağıtım stratejileri, üretime çıkışın kaçınılmaz riskini yönetilebilir kılar; blue-green atomik geçiş ve hızlı geri dönüş sunarken, canary riski gerçek trafikte kademeli olarak sınar. Rollback ise, en dikkatli sürecin bile başarısız olabileceğini kabul ederek sisteme dayanıklılık kazandırır. Tüm bu parçaların ortak felsefesi şudur: hızlı geri bildirim, küçük ve tersinir adımlar ve her kararın ölçülebilir kanıta dayanması.
