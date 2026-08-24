# Assumed Breach ve Purple Team Metodolojisi

> Çerçeve: Bu metin YETKİLİ güvenlik testi (pentest / red team engagement) bağlamında yazılmıştır. Amaç, saldırıyı savunma için anlamaktır. Metodoloji ve yargı odaklıdır; canlı ya da izinsiz bir hedefe uygulanacak adım-adım saldırı reçetesi değildir. Değer, "profesyonel burada nasıl düşünür" sorusundadır.

---

## 1. Bu aşama neyi hedefler, engagement'taki yeri

Klasik "dış çeperden içeri sız" pentest modelinin gerçek dünyada bir sorunu var: modern kurumların dış yüzeyi giderek sertleşti. Yama yönetimi, WAF, MFA, e-posta filtreleri ve EDR sayesinde "dışarıdan bir delik bul ve içeri gir" senaryosu çoğu zaman ya çok uzun sürer ya da hiç gerçekleşmez. Sonuçta müşteri, bütçesinin büyük kısmını tek bir phishing tıklaması ya da tek bir açık portun peşinde koşarak harcamış olur ve asıl kritik soru cevapsız kalır: **"Biri içeri girdiğinde ne olur?"**

Assumed Breach (varsayılan ihlal) tam da bu soruyu merkeze alır. Başlangıç noktası verilidir: testçiye kurum içinde düşük yetkili bir dayanak (foothold) sağlanır. Bu genellikle standart bir domain kullanıcısının kimlik bilgileri, yönetilen bir kurumsal laptop, ya da bir sanal makine üzerinde çalışan bir C2 implant'ıdır. Böylece "içeri girme" fazı atlanır ve tüm efor, savunmanın asıl sınandığı yere — **iç yanal hareket, ayrıcalık yükseltme, kalıcılık ve etki** aşamalarına — kaydırılır.

Bunun engagement içindeki yeri şudur: Assumed Breach bir teslimat modeli, Purple Team ise bir çalışma biçimidir. İkisi sıklıkla birlikte kullanılır. Saf red team'de saldırgan sessizdir ve savunma habersizdir; amaç tespit edilmeden hedefe ulaşmaktır. Purple Team'de ise kırmızı ve mavi takım aynı masada oturur; her saldırı tekniği bilinçli olarak çalıştırılır ve **"bu tespit edildi mi, edilmediyse neden"** sorusu gerçek zamanlı olarak yanıtlanır. Assumed Breach, Purple Team için ideal başlangıç çünkü zaman ve efor ilk erişime değil, tespit yeteneğinin ölçülmesine harcanır.

Olgun bir güvenlik programında bu üçü bir merdiven oluşturur: önce kontrollü Purple Team ile tespit kabiliyeti kurulur ve doğrulanır, sonra Assumed Breach ile "en kötü senaryo" modellenir, en son gizlilik ve tespitten kaçış becerisinin sınandığı tam kapsamlı red team gelir. Sırayı atlayıp doğrudan gizli red team'e giren kurum genellikle pahalı bir ders alır: raporda onlarca bulgu vardır ama SOC ekranında hiçbir alarm çalmamıştır ve kimse bundan ders çıkaramamıştır.

---

## 2. Metodoloji ve karar ağacı — asıl değer

Burası işin özü. Acemi bir testçi araçların çıktısına tepki verir; profesyonel bir operatör ise **bir hipotez kurar, onu doğrular ve her bulguyu bir sonraki kararın girdisine çevirir.** Aşağıda profesyonelin zihninden geçen düşünce sırasını anlatıyorum.

### 2.1 İlk 30 dakika: "Ben kimim ve neredeyim?"

Foothold'a düşen operatörün ilk refleksi taramak değil, **yönelmektir (orient)**. Aceminin yaptığı ilk hata genellikle hemen gürültülü bir ağ taraması başlatmaktır. Profesyonel ise önce sessiz, düşük maliyetli sorularla bağlamı çıkarır:

- **Bu makine kim?** Hostname, domain'e bağlı mı yoksa yerel mi, hangi OU'da, hangi işletim sistemi ve yama seviyesinde.
- **Ben kimim?** Hangi kullanıcı, hangi gruplarda, token'ımda hangi ayrıcalıklar var, yerel yönetici miyim.
- **Ağın neresindeyim?** Hangi subnet, DNS sunucusu kim (bu neredeyse her zaman bir Domain Controller'a işaret eder), gateway nerede.
- **Beni ne izliyor?** Çalışan süreçlere bakıldığında bir EDR ajanı var mı, hangi güvenlik ürünü, loglama ne kadar agresif.

Bu son soru kritik karar noktasını belirler. Eğer ortamda olgun bir EDR varsa operatörün tüm oyun planı değişir: LSASS'a doğrudan dokunmak yerine gürültüsüz alternatifler, disk üzerinde araç bırakmak yerine yerleşik araçlar (living-off-the-land), tek seferlik agresif komutlar yerine "yavaş ve alçak" tempo tercih edilir. Purple Team modunda ise tam tersi: kasıtlı olarak gürültülü teknik çalıştırılır çünkü amaç yakalanmaktır.

### 2.2 Merkezî karar ekseni: Active Directory

Kurumsal ağların büyük çoğunluğu Active Directory üzerine kuruludur ve pratikte iç saldırının kalbi AD'dir. Profesyonelin buradaki temel yaklaşımı **grafik düşünmektir**: AD, kullanıcılar, gruplar, makineler ve bunlar arasındaki yetki ilişkilerinden oluşan bir graftır. Saldırganın işi bu grafta "ben buradayım, hedef orada, aradaki en kısa güven yolu ne" sorusunu çözmektir. BloodHound tam da bu graf düşüncesini görselleştirdiği için oyunu değiştirmiştir.

Enumerasyon önceliği şöyle akar:

1. **Domain topolojisi**: Kaç domain, kaç forest, güven ilişkileri (trust) nasıl. Bir tek yönlü / iki yönlü güven, ileride tüm ormanı ele geçirmenin kapısı olabilir.
2. **Ayrıcalıklı gruplar ve yolları**: Domain Admins kim, ama daha önemlisi — *Domain Admins'e giden dolaylı yollar* neler. Nadiren doğrudan "DA olacağım" denir; genellikle "şu servis hesabına, oradan şu delege yetkisine, oradan DA'ya" şeklinde zincir kurulur.
3. **Yanlış yapılandırmalar (misconfig)**: AD'de gerçek değer sıfır-gün açıklarında değil, biriken yapılandırma borcundadır. Aşırı geniş ACL'ler, unutulmuş delegasyonlar, zayıf servis hesabı parolaları, eski protokollerin açık bırakılması.

Profesyonelin kafasındaki karar ağacı kabaca şu mantıkla ilerler — burada teknikleri *ne zaman düşünüleceği* açısından anlatıyorum, uygulanabilir reçete olarak değil:

- **"Zayıf ya da paylaşılmış yerel yönetici parolası görürsem"** → yatay hareket için makineler arası aynı parolanın tekrarını (credential reuse) araştırırım; LAPS gibi bir çözüm yoksa bu genellikle en hızlı yoldur.
- **"Bir servis hesabının kayıtlı SPN'i ve zayıf parolası varsa"** → Kerberos'un yapısal bir özelliğinden yararlanılan offline parola kırma yolunu (Kerberoasting sınıfı) değerlendiririm; bu düşük gürültülüdür çünkü kırma işlemi hedeften uzakta yapılır.
- **"Bir hesabın ön kimlik doğrulaması kapalıysa"** → benzer bir offline kırma vektörünü (AS-REP sınıfı) düşünürüm.
- **"AD'de kendi objeleri üzerinde aşırı yetki (GenericAll, WriteDacl vb.) görürsem"** → doğrudan exploit değil, *meşru AD işlemlerini kötüye kullanma* yolunu ararım; bunlar EDR için genellikle en görünmez vektörlerdir çünkü teknik olarak "normal" AD operasyonlarıdır.
- **"Sertifika servisleri (AD CS) devredeyse"** → şablon yanlış yapılandırmalarının açtığı kalıcı ve güçlü kimlik taklidi yollarını gündeme alırım; bu son yıllarda en yüksek getirili alanlardan biri oldu.

Buradaki asıl ustalık, **hangi yolu seçeceğine karar vermektir.** Aynı anda beş potansiyel yol görünebilir. Profesyonel şu üç eksende tartar:

- **Gürültü / risk**: Bu adım EDR'ı tetikler mi? Tetiklerse yakalanma maliyeti engagement hedefine değer mi?
- **Geri dönülebilirlik ve ortama etki**: Bu adım üretim ortamını bozar mı? (Örneğin bir DC'ye ağır yük bindiren, servisi düşürebilecek işlemlerden kaçınılır. Yetkili testte "ortama zarar verme" birinci kuraldır.)
- **Kanıtlayıcılık**: Bu yol, müşteriye anlatmak istediğim hikâyeyi kanıtlıyor mu? Bazen "en havalı" teknik değil, "en gerçekçi tehdidi gösteren" teknik seçilir.

### 2.3 Ayrıcalık yükseltme ve yanal hareket döngüsü

İç operasyon doğrusal değil, döngüseldir: **enumerasyon → kimlik/yetki topla → yeni konuma hareket et → tekrar enumere et.** Her yeni makine ya da hesap yeni bir bakış açısı, yeni kimlik bilgileri ve grafta yeni kenarlar getirir.

Profesyonel bu döngüde iki şeye takıntılıdır. Birincisi **kimlik bilgisi hijyeni**: her ele geçirilen bağlamda "burada başka kimin izi var" sorusunu sorar. Bir yönetici o makinede oturum açtıysa, onun bağlamı orada erişilebilir olabilir. İkincisi **en kısa yol disiplini**: grafik açıkça DA'ya üç adımda gidileceğini gösteriyorsa, on adımlık "eğlenceli" bir yola sapmak zaman israfıdır — ama Purple Team'de tersi geçerli olabilir, çünkü amaç mümkün olduğunca çok tekniği tespit karşısında sınamaktır.

### 2.4 Hedefe ulaşınca durmak

Olgun operatör "Domain Admin oldum" noktasında zafer ilan edip durmaz; ama gereksiz yere de her yeri ele geçirmez. Sorusu şudur: **"Müşterinin gerçekten korumak istediği şeye ulaştım mı?"** Bu bazen DA değil, belirli bir veritabanı, bir kaynak kod deposu, bir SWIFT terminali ya da bir yönetici e-posta kutusudur. Engagement'ın başında tanımlanan "crown jewels" (taç mücevherler) ve hedefler, ne zaman duracağını belirler. İyi rapor "her yere girdim" demez; "işte sizin en değerli varlığınıza giden gerçekçi yol ve onu zamanında görebildiniz mi" der.

---

## 3. Acemi vs profesyonel: yaygın hatalar ve gözden kaçanlar

**Araç çıktısına köle olmak.** Acemi, bir aracın "vulnerable: true" çıktısını gerçek olarak alır ve raporlar. Profesyonel her bulguyu bağlamda tartar: Bu gerçekten sömürülebilir mi? Sömürülürse etkisi ne? Belki teorik olarak açık ama pratikte bir ağ segmentasyonu ya da bir başka kontrol onu erişilmez kılıyor. Yanlış pozitifi rapora koymak, müşterinin güvenini yakar.

**Gürültü körlüğü.** Acemi tüm ağı agresifçe tarar, LSASS'a kabaca dokunur, her makinede araç bırakır — sonra "neden hemen yakalandım" diye şaşırır. Profesyonel her eylemin bir iz bıraktığını bilir ve **maliyet-fayda hesabı yapar.** Assumed Breach'te bazen gürültü kabul edilebilir; saf red team'de ölümcüldür. Ayrımı bilmek olgunluğun işaretidir.

**Enumerasyonu atlamak.** En sık ve en pahalı hata. Acemi hemen "exploit"e koşar; profesyonel vaktinin belki %70'ini anlamaya harcar. AD'de doğru yolu görmek, on rastgele denemeden daha değerlidir. "Yavaşla, önce grafiği çıkar" tavsiyesi klişe gibi görünse de en çok ihmal edilen şeydir.

**Kalıcılık ve OPSEC ihmali.** Acemi tek bir implant'a bağımlı kalır; o düşünce oyun biter. Profesyonel erişim çeşitliliği kurar ama aynı zamanda **her kalıcılık mekanizmasını kayıt altına alır** ki engagement sonunda hepsi temizlensin. Yetkili testte unutulan bir arka kapı, ciddi bir sorumluluk yüküdür.

**Ortama zarar riskini küçümsemek.** Acemi bir DC'ye ya da üretim veritabanına test amaçlı ağır bir işlem uygular ve servisi düşürür. Profesyonel her yıkıcı-olabilir eylemden önce "bu üretimi etkiler mi" diye sorar ve şüphedeyse müşteriye danışır. Test, savunmayı ölçmek içindir; işi durdurmak için değil.

**Hikâye anlatamamak.** En büyük olgunluk farkı raporlamadadır. Acemi 200 sayfalık ham çıktı teslim eder. Profesyonel **bir anlatı** kurar: "Standart bir çalışan kimliğinden başlayarak, dört adımda, hiçbir sıfır-gün kullanmadan, tamamen yapılandırma hatalarıyla en kritik varlığınıza ulaştım. Bu adımların ikisi loglarınızda görünüyordu ama alarma dönüşmedi. İşte neden ve işte nasıl düzeltilir." Değer, erişimde değil, çıkarılan derste.

**Purple Team'de "kazanma" tuzağı.** Purple Team'in amacı kırmızının maviyi yenmesi değildir. Amacı, tespit boşluklarını birlikte kapatmaktır. Egosunu masaya getiren, "sizi yine geçtim" havasındaki bir operatör Purple Team'in tüm değerini öldürür. Olgun operatör başarısız bir tekniği bile kutlar: "Bunu yakaladınız, harika — şimdi şu varyantını deneyelim, onu da yakalıyor musunuz?"

---

## 4. Savunma köprüsü — mavi takım için ne anlama gelir

Her saldırı eylemi bir yerde iz bırakır. Bu bölüm, aynı metodolojiye savunmacının gözünden bakar — çünkü kırmızı takımın asıl ürünü savunmanın iyileşmesidir.

**Assumed Breach zaten sizin gerçekçi tehdit modelinizdir.** Modern savunma, çeperin er ya da geç aşılacağını varsayar (bunun bir adı da "varsay ki ihlal edildin" felsefesidir). Dolayısıyla mavi takımın asıl sınavı "içeri girmeyi engelledim mi" değil, "içeri giren birini ne kadar hızlı görürüm ve durdururum" sorusudur. Assumed Breach engagement'ı tam olarak bu yeteneği ölçer.

**Bu aşama nerede iz bırakır — tespit yüzeyleri:**

- **Kimlik ve kimlik doğrulama telemetrisi.** İç saldırının kalbi AD olduğu için, en değerli tespit sinyalleri de kimlik katmanındadır. Olağandışı Kerberos bilet talepleri, servis hesaplarının beklenmedik makinelerden kimlik doğrulaması, bir kullanıcının aynı anda çok sayıda makineye erişmesi, ilk kez görülen kullanıcı-makine eşleşmeleri. Windows olay günlükleri (özellikle kimlik doğrulama, süreç oluşturma ve nesne erişim olayları) ve DC üzerindeki denetim kayıtları burada altın değerindedir.
- **Uç nokta davranışı (EDR).** Kimlik bilgisi erişimi denemeleri, şüpheli süreç ebeveyn-çocuk ilişkileri, komut yorumlayıcılarının anormal kullanımı, yerleşik araçların (living-off-the-land binaries) olağandışı bağlamlarda çağrılması. EDR'ın asıl gücü tek bir imzada değil, davranış zincirini görebilmesindedir.
- **Ağ deseni.** Yanal hareket, iç ağda "normalde konuşmayan" makineler arasında yeni bağlantılar üretir. Doğu-batı (east-west) trafiğin görünürlüğü olmayan kurumlar burada kördür. SMB, RPC, WinRM gibi yönetim protokollerinin olağandışı kaynaklardan kullanımı güçlü bir sinyaldir.
- **Bal küpü / kanarya nesneleri.** Savunmanın en asimetrik silahı. Kimsenin dokunmaması gereken sahte bir ayrıcalıklı hesap, sahte bir dosya paylaşımı ya da bir kanarya kimlik bilgisi — bunlara herhangi bir temas neredeyse kesinlikle kötü niyetlidir ve çok düşük yanlış pozitifle yüksek güvenilirlikli alarm üretir.

**Purple Team'in savunmaya asıl armağanı** tespit mühendisliği döngüsüdür. Süreç şudur: kırmızı bilinen bir tekniği çalıştırır → mavi loglarına bakar → tespit var mı? Varsa: alarma dönüşüyor mu, yoksa sadece bir yerde sessizce mi duruyor? Yoksa: neden yok — telemetri mi eksik, kural mı yok, kural var ama eşik mi yanlış? Sonra tespit kuralı yazılır ya da düzeltilir, kırmızı tekniği tekrar çalıştırır ve bu kez yakalanıp yakalanmadığı doğrulanır. Bu **"çalıştır–ölç–kapat–doğrula"** döngüsü, Purple Team'i statik bir rapordan yaşayan bir yetenek geliştirme motoruna çevirir.

Bu çalışmayı bir çerçeveye oturtmak faydalıdır: MITRE ATT&CK, saldırgan davranışlarını taktik ve teknik olarak sınıflandıran ortak bir dildir. Purple Team çıktısı sıklıkla bir ATT&CK "ısı haritasına" dönüştürülür: hangi tekniklerde tespitimiz güçlü, hangilerinde kör noktadayız. Bu harita, savunma yatırımını nereye yapacağını gösteren en dürüst pusuladır. Atlas gibi görünürlük değil, boşlukların haritası değerlidir.

**Savunmacı için kritik olgunluk noktası:** log toplamak tespit değildir. Birçok kurum her şeyi loglar ama hiçbir şeyi *görmez*. Purple Team'in ortaya çıkardığı en yaygın gerçek şudur — saldırının izi zaten loglardaydı, sadece kimse ona bakan bir kural yazmamıştı. Bu yüzden değer, veri toplamada değil, o veriyi **eyleme dönüşen, düşük gürültülü alarmlara** çevirebilmektedir.

---

## 5. Araçlar ve gerçek dünya notları

Aşağıdakiler sektörde yaygın, gerçek araç ve yaklaşımlardır. Amacım hangisinin ne işe yaradığını ve pratik yargıyı aktarmak; komut düzeyinde saldırı reçetesi vermek değil.

**BloodHound / SharpHound (ve topluluk sürümleri).** AD'yi bir grafa dönüştürüp "buradan Domain Admin'e giden yol" sorusunu görselleştiren araç. İç AD operasyonunun düşünce biçimini değiştirdi. Pratik not: veri toplama adımı gürültülüdür ve olgun bir savunma bunu görebilir; toplama kapsamını ve zamanlamasını hedefe göre ayarlamak gerekir. Savunmacı açısından: kendi ortamınızı BloodHound ile taramak, saldırganın göreceği yolları önceden görmenin en iyi yollarından biridir — "mavi takım da BloodHound çalıştırmalı."

**Impacket paketi.** AD ve Windows protokolleriyle konuşan, olgun ve çok yönlü bir Python araç setidir. Kimlik doğrulama, uzaktan komut çalıştırma ve çeşitli AD tekniklerinin çoğu için fiili standarttır. Pratik not: birçok bileşeni davranışsal olarak iyi bilinir ve EDR'lar tarafından yakından izlenir; "kutudan çıktığı gibi" kullanım genellikle tespit edilir.

**C2 çerçeveleri (örn. Cobalt Strike ve açık kaynak muadilleri).** Foothold'u yönetmek, görev vermek ve kalıcılığı koordine etmek için kullanılan komuta-kontrol altyapıları. Pratik not: Cobalt Strike'ın varsayılan profilleri geniş çapta imzalanmıştır; ciddi engagement'ta trafik profili özelleştirilir. Purple Team'de ise tam tersine, tespit edilebilirliği ölçmek için kasıtlı olarak sadeleştirilebilir.

**Yerleşik araçlar (Living-off-the-Land).** İşletim sistemiyle birlikte gelen meşru yönetim araçları. En düşük gürültülü yaklaşım genellikle "dışarıdan araç getirme, zaten orada olanı kullan" felsefesidir çünkü meşru ikililer daha az şüphe çeker. Savunmacı için ders: tespiti sadece "kötü dosya" imzalarına dayandıran program buna kördür; **davranış** izlemek şarttır.

**Atomic Red Team ve saldırı simülasyon çerçeveleri.** Purple Team ve tespit mühendisliği için değerli. Bireysel ATT&CK tekniklerini kontrollü, tekrarlanabilir ve düşük riskli biçimde çalıştırıp "bunu görüyor muyuz" sorusunu test etmeyi sağlarlar. Tam kapsamlı bir insan operatörünün yerini tutmazlar ama tespit kapsamını ölçeklenebilir biçimde ölçmenin en pratik yoludur. Kaldıraç noktası: her sprint'te birkaç yeni tekniği çalıştırıp ısı haritasını güncellemek.

**Sertifika servisleri araçları (AD CS analizi).** Son yıllarda AD CS yanlış yapılandırmaları en yüksek getirili alanlardan biri oldu; bu yüzeyi denetleyen özel araçlar olgunlaştı. Savunmacı için not: CA şablonlarının yapılandırmasını düzenli denetlemek, çoğu kurumun tamamen atladığı ama çok yüksek etkili bir hijyendir.

**Genel pratik yargılar:**

- **Araç sizi düşündürmez, siz aracı yönlendirirsiniz.** Araç bir bulgu verir; onu neyle ilişkilendireceğinize, hangi yola gireceğinize insan karar verir. Otomatikleştirilebilir olan enumerasyondur; değerli olan yargıdır.
- **Ortama saygı birinci kuraldır.** Yetkili testte hiçbir bulgu, üretimi düşürmeye ya da veri kaybına değmez. Şüphedeyseniz durun ve danışın. Kapsam (scope) ve kurallar (rules of engagement) belgesi kutsaldır.
- **Her şeyi kaydedin.** Ne zaman, hangi makinede, hangi eylemi yaptığınızın zaman damgalı kaydı hem raporun temeli hem de mavi takımın "bu alarm sizin miydiniz yoksa gerçek bir saldırgan mı" sorusunu yanıtlamasının yoludur. Purple Team'de bu kayıt, tespit doğrulamasının bel kemiğidir.
- **Temizlik profesyonelliğin işaretidir.** Bıraktığınız her implant, her kalıcılık kancası, her test hesabı engagement sonunda kaldırılmalıdır. Unutulan erişim, sizin adınıza bir güvenlik açığıdır.
- **En iyi engagement, müşteriyi utandırmayan ama uyandıran engagement'tır.** Amaç "sizi yendim" değil, "işte kör noktanız, işte önceliklendirilmiş yol haritası" demektir. Kırmızı takımın başarısı, altı ay sonra aynı tekniğin artık yakalanıyor olmasıdır.

---

### Kapanış

Assumed Breach ve Purple Team, güvenlik testinin ağırlık merkezini "içeri girebilir miyim" sorusundan "içeri girildiğinde bunu görebilir ve durdurabilir miyiz" sorusuna kaydırır — ki gerçek dünyada asıl önemli olan budur. Bu yaklaşımın değeri exotik exploit'lerde değil, üç yerde toplanır: **doğru enumerasyon ve graf düşüncesi**, **her adımda gürültü-fayda-etki üçgeninde verilen olgun karar**, ve **kırmızı ile mavinin birlikte kapadığı tespit boşlukları.** Araçlar değişir, teknikler eskir; ama bu yargı disiplini kalıcıdır ve bir operatörü acemiden profesyonele ayıran şey tam olarak budur.
