# C2 Çerçeveleri ve Tespiti

## Tanım

C2 (Command and Control, komuta-kontrol) çerçeveleri, bir saldırganın ele geçirdiği makineler üzerinde uzaktan denetim kurmasını, komut çalıştırmasını, veri sızdırmasını ve ağ içinde yanal hareket (lateral movement) yapmasını sağlayan operasyonel altyapılardır. Kırmızı takım (red team) dünyasında Cobalt Strike, Sliver, Mythic, Havoc, Brute Ratel gibi çerçeveler; gerçek tehdit aktörlerinin cephaneliğinde ise bunların çatlatılmış (cracked) sürümleri, özel yazılmış implant'lar ve açık kaynak araçların birleşimi kullanılır.

Bir C2 sisteminin üç temel bileşeni vardır: **team server / C2 server** (operatörün komutları yönettiği merkezi sunucu), **implant / beacon / agent** (kurban makinede çalışan ajan) ve **listener / profile** (implant ile sunucu arasındaki iletişim kanalının nasıl kurulacağını tanımlayan katman). Savunmacı açısından mesele şudur: bu üç bileşen arasındaki trafik, meşru trafiğin içine gizlenmeye çalışılır. Tespitin özü, bu gizlenme çabasının kaçınılmaz olarak bıraktığı istatistiksel ve davranışsal izleri yakalamaktır.

## Kök Neden: Neden Beacon'lar Böyle Çalışır?

C2 tasarımındaki en temel gerilim şudur: implant, operatöre komut almak için sunucuya ulaşmak zorundadır, ama bunu **gürültüsüz** yapmak zorundadır. İki temel mimari seçenek vardır ve ikisi de bu gerilimden doğar.

Birincisi **push (bağlantıyı sunucu başlatır)** modelidir; sunucu kurbana bağlanır. Bu, modern kurumsal ağlarda neredeyse imkânsızdır çünkü firewall'lar ve NAT, dışarıdan içeriye gelen bağlantıları engeller. Bir iş istasyonuna internetten doğrudan bağlanamazsınız.

İkincisi ve baskın olan **pull (bağlantıyı implant başlatır)** modelidir; buna **beaconing** denir. Implant, düzenli aralıklarla sunucuya "bana iş var mı?" diye sorar. Bu çağrıya **check-in** denir. Bu model neden hâkim? Çünkü giden (outbound) trafik neredeyse her ağda serbesttir. Bir kullanıcının HTTPS ile dışarı çıkması meşru kabul edilir, dolayısıyla implant da 443 portundan dışarı çıkarak kalabalığın içine karışır.

İşte tespitin kök noktası da buradadır. Beaconing, doğası gereği **periyodik ve düşük hacimli** bir trafik üretir. İnsan davranışı düzensizdir; bir kullanıcı bir siteye rastgele aralıklarla girer, sayfa boyutları değişir, oturumlar dağınıktır. Ama otomatik bir beacon, örneğin her 60 saniyede bir, neredeyse aynı boyutta küçük bir istek yollar. Bu makinemsi ritim (machine-like periodicity), C2 tespitinin en güvenilir sinyalidir. Saldırganların bunu bozmak için geliştirdiği tüm teknikler (jitter, sleep mask, malleable profiles) aslında bu doğal ritmi kırmak için verilen bir mücadeledir.

### Jitter: Ritmi Bulanıklaştırma Çabası

Saldırganlar bu periyodikliği gizlemek için **jitter** (titreşim / rastgeleleştirme) kullanır. Jitter, check-in aralığına eklenen yüzdesel rastgelelik demektir. Örneğin 60 saniyelik sleep süresine %37 jitter uygulanırsa, implant her seferinde 60 saniyenin bir miktar altında veya üstünde, rastgele bir süre bekler. Amaç, "tam 60 saniyede bir" desenini kırıp analistin ya da tespit motorunun gözüne çarpan düzenli örüntüyü yok etmektir.

Ancak burada savunmacının elinde güçlü bir koz vardır: jitter, dağılımı genişletir ama tamamen ortadan kaldıramaz. Yeterince uzun bir zaman penceresinde (örneğin 24 saat) toplanan check-in zaman damgalarının aralıkları hâlâ belirli bir ortalama etrafında kümelenir. İstatistiksel yöntemler (aralıkların varyans analizi, otokorelasyon, Fourier dönüşümüyle frekans analizi) jitter'lı beacon'ları bile ayırt edebilir. Yani jitter, tespiti zorlaştırır ama imkânsız kılmaz; bu yüzden savunmada uzun pencereli davranışsal analiz esastır.

## Cobalt Strike ve Sliver: İki Farklı Felsefe

**Cobalt Strike**, uzun yıllar hem kırmızı takımların hem de gerçek tehdit aktörlerinin en çok kullandığı ticari çerçevedir. Merkezinde **Beacon** adı verilen implant vardır. Cobalt Strike'ı esnek ve tehlikeli kılan şey **Malleable C2 profilleri**dir. Bu profiller, operatöre beacon'ın ağ üzerindeki trafiğini nasıl göstereceğini nerdeyse tamamen özelleştirme imkânı verir: HTTP istek başlıkları, URI yolları, User-Agent değeri, veri kodlaması, hatta trafiği meşru bir uygulamanın (örneğin bir CDN veya bir bulut servisi) trafiğine benzetme. Amaç, beacon trafiğini imza tabanlı tespitin gözünde masum göstermektir.

Cobalt Strike'ın operasyonel gücü, **bellek içi işleyişinden** de gelir. Beacon, komutlarını çoğunlukla yeni process açmadan, mevcut process içinde çalıştırmaya çalışır (fork-and-run yerine in-process çalıştırma seçenekleri). Ayrıca **sleep mask** teknikleriyle, beacon uyku (sleep) durumundayken kendi bellek bölgesini şifreler; böylece bellek taraması yapan bir EDR, uyku anında beacon'ın imzalarını okuyamaz. Uyanınca çözer, işini yapar, tekrar uyurken şifreler.

**Sliver** ise BishopFox tarafından geliştirilen, Go diliyle yazılmış, açık kaynak bir çerçevedir. Cobalt Strike'ın çatlatılmış sürümlerine ve artan tespit oranına bir alternatif olarak popülerleşti. Sliver'ın öne çıkan özellikleri: birden fazla taşıma protokolünü desteklemesi (mTLS, HTTP(S), DNS, WireGuard gibi), implant'larının derleme zamanında (compile-time) benzersiz üretilmesi ve bu sayede statik imzalardan kaçması, ve mTLS kullanıldığında sunucu ile implant arasındaki trafiğin karşılıklı sertifika doğrulamasıyla korunmasıdır.

İki felsefe arasındaki fark önemlidir. Cobalt Strike, esneklik ve trafik özelleştirmede üstündür ama çok yaygın kullanıldığı için savunma tarafı onun davranışlarını (varsayılan profiller, bilinen bellek desenleri, named pipe isimlendirme kalıpları) iyi tanır. Sliver ise nispeten daha yeni, her derlemede farklılaşan yapısıyla imza tabanlı tespiti zorlar ama açık kaynak olduğu için savunmacılar da kaynağını inceleyip davranışsal tespit kuralları yazabilir. Sonuç: iki çerçeve de "mükemmel gizlilik" sağlamaz; yeterince olgun bir savunma programı ikisini de davranışsal olarak yakalayabilir.

## Domain Fronting ve Alan Adı Gizleme

**Domain fronting**, C2 trafiğinin gerçek hedefini gizlemek için kullanılan bir tekniktir ve çalışma mantığı, HTTPS protokolünün katmanları arasındaki tarihsel bir tutarsızlıktan doğar.

Bir HTTPS bağlantısında iki yerde alan adı bilgisi bulunur. Birincisi TLS el sıkışması (handshake) sırasında açıkça gönderilen **SNI (Server Name Indication)** alanıdır; bu, şifreleme kurulmadan ÖNCE gönderildiği için ağı izleyen herkes tarafından görülebilir. İkincisi ise TLS şifrelemesi kurulduktan SONRA gönderilen HTTP **Host** başlığıdır; bu, şifrelenmiş tünelin içindedir ve dışarıdan görülemez.

Domain fronting'in özü şudur: saldırgan, SNI alanına büyük ve meşru bir alan adı (örneğin bir büyük CDN veya bulut sağlayıcının güvenilir bir domain'i) yazar, ama şifrelenmiş HTTP Host başlığına asıl C2 sunucusunun adresini yazar. Ağı izleyen savunmacı ya da güvenlik cihazı, sadece SNI'yi görür ve "kullanıcı güvenilir bir servise bağlanıyor" diye düşünür. Ancak CDN'in kenar sunucusu, şifreyi çözdükten sonra Host başlığına bakar ve isteği asıl C2 sunucusuna yönlendirir. Yani dışarıdan masum, içeriden zararlı bir yönlendirme gerçekleşir.

Bu tekniğin çalışabilmesi için CDN altyapısının, SNI ile Host başlığının farklı olmasına izin vermesi gerekir. Büyük bulut ve CDN sağlayıcıları son yıllarda bu davranışı büyük ölçüde kısıtladı; SNI ile Host uyuşmazlığını reddetmeye başladılar. Bu yüzden klasik domain fronting eskisi kadar kolay değildir. Buna karşılık saldırganlar **domain borrowing**, **CDN üzerinden meşru servislerin kötüye kullanımı** ve giderek **encrypted SNI / ECH (Encrypted Client Hello)** gibi SNI'yi de şifreleyen yeni mekanizmaları istismar etme yollarına yöneldi. ECH yaygınlaştıkça, SNI temelli tespit savunmacılar için zorlaşacaktır; bu, savunmanın neden tek bir sinyale (örneğin sadece SNI'ye) bağlı kalmaması gerektiğinin iyi bir örneğidir.

Domain fronting'e akraba bir teknik de **domain fronting olmayan ama benzer amaç güden C2-over-legitimate-service** yaklaşımlarıdır: saldırgan, C2 kanalı olarak meşru bir bulut depolama, sohbet servisi ya da kod barındırma platformunu kullanır. Burada trafik gerçekten o meşru servise gider, ama içindeki veri C2 komutlarıdır. Bunun tespiti daha da zordur çünkü SNI de Host da tutarlıdır ve gerçekten meşru bir hedefe gidilir; ayrım ancak trafiğin davranışsal deseninden (o servise beklenmedik bir makinenin düzenli, otomatik erişimi) yapılabilir.

## Somut Örnek: Bir Beacon'ın Yaşam Döngüsü

Tipik bir senaryoyu adım adım düşünelim, çünkü tespit noktalarını görmek için akışı anlamak gerekir.

Bir kullanıcı, oltalama (phishing) e-postasındaki bir makro içeren belgeyi açar. Makro, bir loader çalıştırır; loader, C2 sunucusundan asıl beacon payload'unu (shellcode) indirir ve bunu genellikle **process injection** ile meşru bir process'in (örneğin bir tarayıcı ya da bir sistem process'i) bellek alanına yerleştirir. Bu aşamada diske hiç zararlı dosya yazılmamış olabilir; buna **fileless** (dosyasız) çalışma denir ve klasik antivirüsün dosya taramasını atlatmayı amaçlar.

Beacon uyanır ve ilk check-in'ini yapar: 443 portundan, meşru görünen bir User-Agent ve URI ile C2 sunucusuna küçük bir HTTPS isteği gönderir. Sunucudan "iş yok" cevabı gelir. Beacon, sleep süresi + jitter kadar uyur. Bu döngü saatlerce, komut gelene kadar sürer. Operatör komut verdiğinde (örneğin bir dizin listeleme), beacon bir sonraki check-in'de komutu alır, çalıştırır, çıktıyı bir sonraki istekte sunucuya yollar.

Bu akıştaki tespit noktalarını sayalım: (1) makronun bir loader çalıştırması — anormal parent-child process ilişkisi; (2) process injection — bir process'in başka bir process'in belleğine yazması; (3) beacon'ın periyodik HTTPS check-in'i — beaconing deseni; (4) küçük ve tekdüze istek/cevap boyutları; (5) uzun ömürlü, düşük hacimli, düzenli bir dış bağlantı. Her biri tek başına yanlış alarm üretebilir, ama bir arada değerlendirildiğinde güçlü bir C2 sinyali oluştururlar. Tespit felsefesinin özü budur: tek imza değil, sinyallerin birleşimi.

## Sömürü / İstismar Mantığı (Saldırgan Perspektifi)

Saldırgan, tespitten kaçmak için katmanlı bir strateji izler ve her katman bir savunma sinyalini hedef alır.

**Ağ katmanında** amaç, trafiği kalabalığa karıştırmaktır. Bunun için 443 gibi yaygın portlar seçilir, gerçek TLS sertifikaları (örneğin ücretsiz sertifika otoritelerinden) kullanılır, Malleable profillerle istekler meşru uygulamalara benzetilir, jitter ile periyodiklik bulanıklaştırılır ve domain fronting benzeri tekniklerle asıl hedef gizlenir. Ayrıca **beacon interval'ı uzatmak** (örneğin dakikalar yerine saatler) tespiti ciddi biçimde zorlaştırır çünkü davranışsal analiz için gereken veri noktası sayısı azalır ve trafik daha da seyrekleşir.

**Ana bilgisayar (host) katmanında** amaç, EDR ve bellek taramasından kaçmaktır. Sleep mask ile uyku anında bellek şifrelenir; process injection ile meşru process'lerin içine saklanılır; **indirect syscall / API unhooking** gibi tekniklerle EDR'ın kanca (hook) koyduğu API çağrıları atlatılmaya çalışılır; **AMSI ve ETW atlatma** ile betik tarama ve telemetri mekanizmaları körleştirilir. Amaç, host üzerinde bırakılan iz miktarını minimuma indirmektir.

**Altyapı katmanında** amaç, dayanıklılık ve atfedilemezliktir. Redirector'lar (araya konan yönlendirici sunucular) kullanılarak asıl team server IP'si gizlenir; domain kategorilendirmesi manipüle edilerek C2 domain'i "iş / teknoloji" gibi zararsız bir kategoride görünür; birden fazla C2 kanalı (primary + fallback, örneğin HTTPS düşerse DNS'e geçme) ile dayanıklılık sağlanır.

Bu istismar mantığını anlamak savunmacı için hayatidir çünkü her kaçınma tekniği, aslında bir savunma sinyalinin varlığını itiraf eder. Saldırgan sleep mask kullanıyorsa, bellek taramasının işe yaradığını biliyor demektir; jitter kullanıyorsa periyodiklik analizinden korkuyor demektir. Savunmacı bu mantığı tersine okuyarak nereye bakması gerektiğini anlar.

## Savunma ve Tespit (Savunmacı Perspektifi)

Etkili C2 tespiti, tek bir katmana değil, ağ, host ve istihbarat katmanlarının birleşimine dayanır.

### Ağ Tabanlı Tespit

En güçlü sinyal **beaconing analizi**dir. Uzun bir zaman penceresinde bir kaynak-hedef çiftinin bağlantı zaman damgaları toplanır; bu bağlantıların aralıkları arasındaki düzenlilik istatistiksel olarak ölçülür. Düşük varyanslı, belirli bir ortalama etrafında kümelenen aralıklar (jitter'a rağmen) beaconing'e işaret eder. Buna ek olarak veri boyutlarının tekdüzeliği, oturumların anormal uzun ömrü ve düşük hacimli sürekli trafik de değerlendirilir. Zeek/Bro tabanlı bağlantı günlükleri ve RITA benzeri açık araçlar bu analizi kolaylaştırır.

**TLS parmak izi (JA3/JA3S, JA4)** güçlü bir başka sinyaldir. Bir TLS istemcisinin el sıkışma sırasında kullandığı şifre paketleri, uzantılar ve sıralamalar, o istemciyi üreten kütüphaneye özgü bir parmak izi oluşturur. Belirli C2 implant kütüphanelerinin ürettiği JA3 parmak izleri, meşru tarayıcılarınkinden farklıdır. Bu, şifreli trafiğin içeriğini görmeden bile istemcinin türü hakkında ipucu verir. Not: parmak izleri tek başına kesin kanıt değildir çünkü meşru yazılımlar da aynı kütüphaneleri kullanabilir; ama anomali tespitinde değerlidir.

**DNS analizi**, DNS üzerinden C2 (DNS tunneling) için kritiktir. DNS beacon'ları, verileri subdomain'lerin içine kodlar; sonuç olarak alışılmadık derecede uzun subdomain'ler, yüksek entropili (rastgele görünen) etiketler, tek bir domain'e anormal yüksek sayıda benzersiz sorgu ve TXT/NULL gibi az kullanılan kayıt türlerinin yoğunluğu ortaya çıkar. Bunlar DNS tunneling'in klasik izleridir.

**SNI ile Host uyuşmazlığı** ve genel olarak sertifika anomalileri (çok yeni oluşturulmuş domain'ler, self-signed sertifikalar, sertifika ile SNI'nin tutarsızlığı) domain fronting ve benzeri tekniklere işaret edebilir. TLS'i kenar sağlayıcıda sonlandıran (TLS inspection) ortamlarda Host başlığı ile SNI karşılaştırılabilir.

### Host Tabanlı Tespit

EDR telemetrisi burada belirleyicidir. Aranacak davranışlar: anormal **parent-child process ilişkileri** (bir ofis uygulamasının bir komut yorumlayıcısı ya da script host başlatması), **process injection** izleri (bir process'in başka bir process'e uzaktan bellek yazması, uzaktan thread oluşturması), **imzasız veya beklenmedik bellek bölgelerinde çalıştırılabilir kod** (RWX bellek, imzasız modül), ve C2 çerçevelerinin **named pipe** kullanım kalıpları. Sleep mask'e karşı ise **periyodik bellek taraması**, uyanma anlarını yakalamaya çalışır; beacon uyanıp belleğini çözdüğü an tarama denk gelirse imzalar okunabilir. Bu bir kedi-fare oyunudur ve mükemmel değildir, ama saldırganı sürekli riske sokar.

### İstihbarat ve Avlanma (Threat Hunting)

Bilinen C2 altyapılarına dair tehdit istihbaratı (IP, domain, sertifika hash'i, JA3 parmak izi göstergeleri) besleme olarak kullanılabilir; ancak saldırganlar altyapıyı sık değiştirdiği için bu tek başına yetersizdir. Bu yüzden **hipotez temelli avlanma** kritiktir: "ağımızda periyodik dış bağlantı yapan, düşük hacimli, uzun ömürlü oturumlar var mı?" gibi bir hipotezle proaktif arama yapılır. İmza değil, davranış avlanır.

## Yaygın Hatalar

Savunma tarafında en sık görülen hataların çoğu, C2 trafiğinin **doğasını yanlış anlamaktan** kaynaklanır.

Birinci hata, **yalnızca imza tabanlı tespite güvenmektir.** IP kara listeleri ve statik imzalar, altyapısını her operasyonda yenileyen ve her derlemede farklılaşan implant'lar karşısında hızla eskir. İmza gerekli ama yeterli değildir; davranışsal katman şarttır.

İkinci hata, **kısa gözlem pencereleridir.** Beaconing tespiti istatistikseldir ve yeterli veri noktası ister. Uzun interval'lı (saatlik) bir beacon'ı birkaç dakikalık pencerede yakalamak imkânsıza yakındır. Uzun pencereli, uzun süreli veri saklama gerekir.

Üçüncü hata, **giden (egress) trafiği ihmal etmektir.** Birçok kurum gelen trafiğe odaklanır, oysa C2 beaconing tanımı gereği giden trafiktir. Egress filtreleme, çıkış noktalarının denetimi ve giden bağlantıların loglanması çoğu zaman zayıf kalır.

Dördüncü hata, **şifreli trafiği "göremiyoruz, o hâlde vazgeçelim" diye bırakmaktır.** TLS içeriğini görmeseniz bile üstveri (metadata) — zamanlama, boyut, süre, parmak izi, hedef — bol miktarda sinyal taşır. İçeriği çözemeden de C2 yakalanabilir.

Beşinci hata, **DNS'i güvenli varsaymaktır.** DNS neredeyse hiçbir ağda engellenmez ve tam da bu yüzden gizli bir C2 kanalıdır. DNS telemetrisi toplanmayan ortamlar büyük bir kör noktaya sahiptir.

Saldırgan/kırmızı takım tarafında da yaygın hatalar vardır: **varsayılan yapılandırmaları değiştirmeden kullanmak** (varsayılan Malleable profiller, varsayılan sertifikalar, bilinen named pipe isimleri) neredeyse anında yakalanmaya yol açar. Ayrıca **çok agresif interval** (kısa sleep) beaconing'i belirginleştirir; **operasyonel güvenlik hatası** olarak test altyapısını üretim operasyonuyla karıştırmak, tüm kampanyanın atfedilmesine yol açabilir.

## En İyi Pratikler

Savunmacı için en iyi pratikler, tespiti tek bir sinyalden çok, **katmanlı ve davranışsal** bir yapıya oturtmak etrafında toplanır.

**Ağ görünürlüğünü tam sağlayın:** giden trafiği loglayın, mümkünse Zeek benzeri bir sensörle bağlantı üstverisini toplayın, DNS sorgularını merkezi olarak kaydedin ve TLS parmak izlerini çıkarın. Görünmeyen trafiği tespit edemezsiniz; ilk yatırım görünürlüğe olmalı.

**Beaconing analizini bir yetenek hâline getirin:** düzenli aralıkta çalışan, uzun pencerede aralık düzenliliğini ölçen bir tespit mekanizması kurun. Jitter'a karşı dayanıklı olması için istatistiksel (varyans, otokorelasyon) yaklaşımlar kullanın, sabit eşiklere değil.

**Egress kontrolü uygulayın:** iş istasyonlarının doğrudan internete keyfî portlardan çıkmasını kısıtlayın; giden trafiği bir proxy üzerinden zorlayarak hem görünürlük hem denetim kazanın. Beklenmedik hedeflere giden trafiği anomali olarak işaretleyin.

**Host ve ağ telemetrisini ilişkilendirin (correlation):** tek başına zayıf olan sinyaller birleştiğinde güçlenir. Bir process injection olayı ile aynı hosttan çıkan periyodik bir dış bağlantı, ayrı ayrı gürültü, birlikte yüksek güvenli bir C2 alarmıdır. SIEM/XDR düzeyinde bu ilişkilendirmeyi kurun.

**Proaktif avlanın:** yalnızca alarm beklemeyin. Düzenli threat hunting seansları düzenleyerek "bilinmeyen bilinmezleri" arayın; hipotez temelli, davranış odaklı avlanma en yeni C2 tekniklerini bile açığa çıkarabilir.

**Tehdit istihbaratını doğru konumlandırın:** IOC beslemelerini bir başlangıç noktası olarak kullanın ama tek dayanak yapmayın. Altyapı hızla değişir; kalıcı olan davranıştır.

**Savunmayı sürekli test edin (purple team):** kendi ortamınızda kontrollü C2 simülasyonları çalıştırarak tespit yeteneklerinizin gerçekten çalışıp çalışmadığını doğrulayın. Bir tespit kuralının varlığı, çalıştığı anlamına gelmez; ancak test edilmiş tespit gerçek tespittir.

Kapanışta hatırlanması gereken temel fikir şudur: C2 çerçeveleri ne kadar gelişse de, bir implant'ın operatörle iletişim kurma zorunluluğu değişmez. Bu iletişim, ne kadar gizlenirse gizlensin, ağda bir iz bırakır. Savunmanın sanatı, o izi imzada değil davranışta, tek olayda değil örüntüde, kısa pencerede değil zamanın bütününde aramaktır.
