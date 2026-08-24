# Yazılım Tedarik Zinciri Güvenliği (SBOM, SLSA, Bağımlılık İmzalama, Sigstore/cosign)

## Giriş: Neden Ayrı Bir Alan?

Zafiyet yönetimi (CVE/vuln management) sorusu şudur: "Kullandığım kodda bilinen bir açık var mı?" Tedarik zinciri güvenliği ise çok daha temel bir soruyu sorar: "Bu kodun gerçekten iddia ettiği kişi tarafından, iddia ettiği kaynak koddan, iddia edildiği gibi üretildiğini nasıl bilebilirim?" Bu ikinci soru cevapsız kaldığında, CVE taramasının hiçbir anlamı kalmaz — çünkü tarttığınız paket sahte olabilir, derleme sürecine bir saldırgan sızmış olabilir ya da bağımlılık grafiğinizdeki bir isim başkası tarafından ele geçirilmiş olabilir.

Bu alanın kritikleşmesinin somut nedeni, gerçek dünyada yaşanan olaylardır: yaygın kullanılan bir sıkıştırma kütüphanesine yıllar süren bir güven inşa sürecinin ardından arka kapı (backdoor) yerleştirilmesi, CI/CD sağlayıcılarının derleme sunucularının ele geçirilerek binlerce müşteriye zararlı güncelleme dağıtılması gibi vakalar, endüstriyi "kodun kendisi güvenli olsa bile, onu bana ulaştıran zincirin her halkası güvenilir mi?" sorusuyla yüzleştirdi. Modern bir uygulama, kendi yazdığınız kodun çoğunlukla küçük bir yüzdesini oluşturur; geri kalanı açık kaynak bağımlılıklar, taban imajlar (base image), derleme araçları ve CI/CD boru hatlarıdır. Saldırganlar artık doğrudan hedefe saldırmak yerine, o hedefin güvendiği tedarikçiyi (upstream) hedef alıyor — çünkü bir tedarikçiyi ele geçirmek, o tedarikçinin binlerce müşterisine aynı anda erişim sağlıyor.

## Kök Neden: Güven Zincirinin Doğrulanamaması

Tedarik zinciri saldırılarının kök nedeni, yazılım geliştirme ve dağıtım sürecindeki her adımın (kaynak kod → derleme → paketleme → dağıtım → kurulum) varsayılan olarak *örtük güvene* dayanmasıdır. Geleneksel model şuydu: "Bu paket resmi paket deposundan geldi, o zaman güvenilirdir." Ama bu varsayım, aşağıdaki sorulara cevap vermez:

- Bu paketin kaynak kodu, deponun gösterdiği git commit'iyle gerçekten eşleşiyor mu?
- Bu paketi derleyen makine, iddia edilen CI sistemi miydi, yoksa saldırganın kendi makinesi miydi?
- Derleme sırasında ekstra bir bağımlılık ya da script sessizce çalıştırıldı mı?
- Bu paketin yayıncısı, gerçekten yetkili bakımcı (maintainer) mı, yoksa hesabı ele geçirilmiş biri mi?
- İç ağınızda kullandığınız "iç-paket-adı" ile aynı isimde herkese açık bir paket var mı ve o paket sizin bağımlılık çözücünüz tarafından yanlışlıkla mı çekiliyor?

Bu sorulardan her biri farklı bir saldırı sınıfına karşılık gelir: kaynak kod bütünlüğü sorunu, derleme (build) bütünlüğü sorunu, bakımcı hesabı ele geçirme, ve **dependency confusion**. Tedarik zinciri güvenliği araçları (SBOM, SLSA, imzalama, Sigstore) bu sorulara *kriptografik olarak doğrulanabilir* cevaplar üretmeyi hedefler — yani "güven bana" yerine "doğrula" (trust but verify → verify, don't trust) paradigmasına geçiş.

## SBOM (Software Bill of Materials): Envanterin Kendisi

### Tanım ve Amaç

SBOM, bir yazılım ürününün içindeki tüm bileşenlerin (doğrudan ve geçişli bağımlılıklar, sürümleri, lisansları, kaynakları) makine tarafından okunabilir bir dökümüdür. Fiziksel üretimdeki "malzeme listesi" kavramının yazılıma uyarlanmış hâlidir: bir arabanın hangi parçalardan, hangi tedarikçilerden geldiğini bilmek nasıl bir geri çağırma (recall) durumunda hayati ise, bir yeni CVE duyurulduğunda "bu zafiyet bende var mı, hangi üründe, kaç yerde?" sorusuna dakikalar içinde cevap verebilmek de SBOM ile mümkün olur.

İki yaygın format vardır: **SPDX** (Linux Foundation kökenli, lisans uyumluluğu odaklı köklerden geldi, ISO standardı hâline geldi) ve **CycloneDX** (OWASP kökenli, güvenlik odaklı doğdu, zafiyet ve zarar-analizi alanlarına daha zengin destek verir). İkisi de JSON/XML tabanlı, birbirine kısmen dönüştürülebilir yapılardır; hangisinin seçileceği genelde müşteri/regülasyon talebine bağlıdır.

### Neden Önemli — Kök Neden Perspektifi

SBOM olmadan, bir kuruluşun "log4j tarzı" kritik bir zafiyet duyurusuna verebileceği ilk tepki genelde şudur: elle, panik hâlinde, tüm repoları grep'lemek. Bu hem yavaştır hem de geçişli bağımlılıkları (bağımlılığın bağımlılığı) kaçırır — çünkü çoğu zaman zafiyetli kütüphane sizin `package.json` ya da `pom.xml` dosyanızda görünmez, üç seviye aşağıda gizlidir. SBOM, bu görünürlüğü *önceden* üretilmiş bir envanter hâline getirir; olay anında yapılan iş, aramak değil, sorgulamaktır.

Ayrıca SBOM iki farklı zaman noktasında üretilebilir ve bunların anlamı farklıdır:
- **Build-time SBOM**: Derleme sürecinin kendisi tarafından üretilir, gerçekte derlenen şeyi yansıtır (en doğru olanı).
- **Kaynak taraması (source-scan) SBOM**: Manifest dosyalarından (package.json, requirements.txt) statik olarak çıkarılır; hızlıdır ama derleme zamanı koşullu bağımlılıkları, dinamik olarak çekilen paketleri kaçırabilir.

### Yaygın Tuzaklar

1. **"SBOM üretmek yeterli" yanılgısı**: SBOM tek başına bir güvenlik kontrolü değildir, bir *görünürlük* aracıdır. Üretip hiç kimsenin bakmadığı, otomatik zafiyet eşleştirmesine (vuln matching) beslenmeyen bir SBOM, arşivde duran bir PDF'den farksızdır.
2. **Statik ve bir kereye mahsus üretim**: Bağımlılıklar sürekli güncellendiği için SBOM'un da CI/CD'nin her build'inde yeniden üretilmesi, sürümlenmesi ve saklanması gerekir. Eski bir SBOM, yanlış güven verir.
3. **Geçişli bağımlılıkların eksik yakalanması**: Özellikle derin bağımlılık ağaçlarında (Java, JavaScript ekosistemleri tipik örnektir) araçlar bazen sadece birinci seviyeyi listeler; bu, en tehlikeli zafiyetlerin (derinlerde gizlenen) kaçırılmasına yol açar.
4. **Lisans/güvenlik karışıklığı**: SBOM'un asıl gücü hem lisans uyumluluğu hem güvenlik için kullanılabilmesidir, ama bazı kuruluşlar sadece hukuki amaçla üretip güvenlik ekibiyle paylaşmaz — silo oluşur.

### En İyi Pratikler

- SBOM üretimini CI/CD boru hattına gömün; her artefakt (imaj, ikili dosya, paket) için otomatik üretilsin.
- Build-time üretimi tercih edin, sadece manifest taramasına güvenmeyin.
- SBOM'u imzalayın (aşağıda değineceğiz) ki dağıtım sırasında değiştirilmediği doğrulanabilsin.
- SBOM'u bir zafiyet veritabanıyla (CVE/OSV besleme) otomatik eşleştiren bir süreç kurun; SBOM'un değeri, sorgulanabilir olmasındadır.

## SLSA (Supply-chain Levels for Software Artifacts): Derleme Bütünlüğü Çerçevesi

### Tanım

SLSA ("salsa" diye okunur), bir yazılım artefaktının nasıl üretildiğine dair *güvence seviyelerini* tanımlayan bir çerçevedir. SBOM "içinde ne var" sorusuna cevap verirken, SLSA "bu nasıl üretildi ve bu süreç kurcalamaya karşı ne kadar dayanıklı" sorusuna cevap verir. SLSA seviyeleri kabaca artan sıkılıkta güvence sağlar: en alt seviyeler "derleme sürecinin belgelendiğini ve tekrarlanabilir olduğunu" doğrularken, üst seviyeler "derlemenin izole, tek-kullanımlık, saldırıya dayanıklı bir sistemde, insan müdahalesi olmadan, kriptografik olarak doğrulanabilir bir kanıt (provenance) üreterek" yapıldığını garanti eder.

### Kök Neden / Çalışma Mantığı

SLSA'nın çözmeye çalıştığı temel problem şudur: geleneksel CI/CD sistemlerinde, derleme sunucusuna erişimi olan biri (ya da o sunucuyu ele geçiren bir saldırgan), "kaynak kod deposunda görünen kod" ile "gerçekte derlenip yayınlanan ikili dosya" arasına sessizce fark koyabilir. Yani git deposundaki kod temiz görünse bile, çalışan derleme adımı arasına enjekte edilen bir script, son üründe kötü niyetli davranış ekleyebilir — ve kaynak kod incelemesi (code review) bunu asla yakalayamaz çünkü incelenen şey derlenen şeyle aynı değildir.

SLSA'nın çözümü **provenance**: derleme sisteminin, "bu artefakt, şu kaynak kod commit'inden, şu derleme tarifi (build recipe) ile, şu derleme sisteminde üretildi" bilgisini kriptografik olarak imzalanmış bir belge (attestation) hâlinde üretmesidir. Bu belge daha sonra tüketici tarafından (ör. bir dağıtım sistemi ya da Kubernetes admission controller) doğrulanabilir: "bu imaj, beklediğim kaynak depodan, beklediğim CI sistemiyle mi üretildi, yoksa biri elle mi push etti?"

Üst SLSA seviyelerinin özellikle önem verdiği nokta **derleme izolasyonudur**: eğer derleme, her seferinde temiz, tek kullanımlık (ephemeral) bir ortamda, ağ erişimi kısıtlı, önceki derlemenin kalıntılarından etkilenmeyecek şekilde çalışıyorsa, bir saldırganın "bir derlemeyi zehirleyip sonraki tüm derlemeleri etkileme" ihtimali büyük ölçüde ortadan kalkar. Bu, gerçek dünyada yaşanan büyük bir CI/CD tedarik zinciri saldırısının tam olarak istismar ettiği zayıflıktı: derleme sistemine sızıp, üretilen her artefakta zararlı kod ekleyen bir enjeksiyon.

### Yaygın Tuzaklar

- **"SLSA seviyesi = güvenlik puanı" yanılgısı**: Yüksek SLSA seviyesi, derleme sürecinin bütünlüğünü garanti eder; kaynak kodun kendisinin güvenli/zafiyetsiz olduğunu garanti etmez. Bu iki farklı endişe (build integrity vs. code quality) karıştırılmamalı.
- **Provenance üretilip hiç doğrulanmaması**: Provenance belgesi üretmek yarı iştir; tüketici tarafında bu belgenin *doğrulanması* (beklenen kaynak/builder ile eşleşip eşleşmediğinin kontrolü) yapılmazsa, saldırgan sahte bir artefaktı yine de dağıtabilir — imzasız ya da eşleşmeyen bir provenance'ı kimse kontrol etmiyorsa.
- **Kendi kendini imzalayan (self-attested) düşük seviyelerle yetinmek**: Alt seviyelerde derleme süreci hâlâ tek bir kişinin/makinenin kontrolünde olabilir; bu, "belgeleme var ama güvence zayıf" durumudur. Kritik yazılımlar için hedef, bağımsız doğrulanabilir, izole derleme seviyelerine ulaşmak olmalı.

### En İyi Pratikler

- CI/CD sisteminizin provenance/attestation üretme yeteneği olup olmadığını kontrol edin (modern CI sistemlerinin çoğu bunu destekler ya da eklenti ile destekleyebilir).
- Dağıtım/deploy aşamasında provenance doğrulamasını *zorunlu* hâle getirin (politika olarak: "imzasız ya da beklenmeyen kaynaktan gelen artefakt reddedilir").
- Derleme ortamlarını mümkün olduğunca izole ve tek-kullanımlık tutun; kalıcı, elle yönetilen "altın" derleme sunucuları büyük bir tek nokta zafiyettir.

## Bağımlılık ve Paket İmzalama: Kimliğin Kriptografik Kanıtı

### Temel Mantık

İmzalama, "bu paketi ben yayınladım ve yayınlandığından beri değişmedi" iddiasını kriptografik olarak kanıtlanabilir hâle getirir. Klasik model, bir bakımcının özel anahtarıyla paketi imzalaması ve tüketicinin bu imzayı bakımcının herkese açık anahtarıyla doğrulamasıdır (asimetrik imza — public/private key). Bu, iki farklı tehdidi engeller: (1) paketin dağıtım sırasında (CDN, ayna sunucu, man-in-the-middle) değiştirilmesi, (2) paket deposunun kendisinin ele geçirilip sahte bir sürümün yüklenmesi (imza olmadan depo kontrolü tek başına yeterli değildir).

### Kök Neden Sorusu: Anahtar Yönetimi Neden Zordur?

Geleneksel imzalama modelinin en büyük pratik sorunu **anahtar yönetimidir**. Bir bakımcının özel anahtarı çalınırsa, saldırgan o bakımcı adına sonsuza kadar geçerli imzalar üretebilir — ve bu çalınma fark edilene kadar hiçbir doğrulama sistemi bunu yakalayamaz çünkü imza kriptografik olarak "geçerli" görünür. Ayrıca bireysel açık kaynak katkıcılarından "kendi özel anahtarını güvenle sakla, asla kaybetme, asla sızdırma" beklemek gerçekçi değildir — çoğu katkıcı güvenlik uzmanı değildir, anahtarlar kişisel bilgisayarlarda, bazen yedeksiz, bazen zayıf korumalı olarak durur.

### Sigstore ve Cosign: "Anahtarsız" (Keyless) İmzalama Yaklaşımı

Sigstore, bu anahtar yönetimi problemine yanıt olarak geliştirilmiş bir açık kaynak proje/altyapı setidir. Temel fikri şu: uzun ömürlü, kaybolabilir/çalınabilir bir özel anahtar tutmak yerine, imzalayan kişi/sistem kimliğini bir OpenID Connect (OIDC) sağlayıcısı üzerinden (ör. kurumsal e-posta ya da CI sisteminin kimliği) kanıtlar; Sigstore anlık, kısa ömürlü bir sertifika/anahtar çifti üretir, imzayı bu geçici anahtarla atar, sonra bu geçici anahtarı atar. İmzanın kendisi ve "kim, ne zaman, hangi kimlikle imzaladı" bilgisi ise **şeffaf bir günlüğe (transparency log — Rekor)** kalıcı, değiştirilemez şekilde kaydedilir.

Bunun mantığı şudur: uzun ömürlü anahtar olmadığı için çalınacak bir sır kalmaz; imza doğrulaması "bu anahtar geçerli mi" sorusundan "bu OIDC kimliği ile bu imza gerçekten şu zaman diliminde, şu şeffaf günlük kaydıyla eşleşiyor mu" sorusuna kayar. **Cosign** ise bu Sigstore altyapısını kullanarak konteyner imajlarını (ve genel olarak artefaktları) imzalamak/doğrulamak için kullanılan pratik bir araçtır; imzayı ve isteğe bağlı olarak provenance/SBOM gibi ek attestation'ları artefaktla ilişkilendirip şeffaf günlüğe işler.

Şeffaf günlüğün (transparency log) önemi, kök neden açısından şudur: bir saldırgan geçici bir kimlik doğrulamasını ele geçirse bile, attığı sahte imza *kalıcı olarak, herkese açık, değiştirilemez bir günlükte* görünür hâle gelir — yani saldırı sessizce, iz bırakmadan yapılamaz. Bu, tespit (detection) imkânını temelden değiştirir: güvenlik ekipleri bu günlüğü izleyerek beklenmeyen imzalama olaylarını (ör. beklenmeyen bir kimlikle, beklenmeyen saatte imzalanan artefaktlar) tespit edebilir.

### Yaygın Hatalar ve Tuzaklar

1. **İmzalama var ama doğrulama zorunlu değil**: En sık görülen hata budur. Bir kuruluş imajlarını imzalar ama Kubernetes/deploy hattında "imzasız imaj çalıştırılamaz" politikasını uygulamaz. İmzalama, uygulanan bir *politika* olmadan süs kalır.
2. **"İmzalandı = güvenli" yanılgısı**: İmza, sadece "bu içerik, imzalayanın onayladığı içerikle aynı ve değişmemiş" der; imzalayanın kendisinin kötü niyetli ya da ele geçirilmiş olma ihtimalini ortadan kaldırmaz. İmza kimlik ve bütünlük garantisi verir, *niyet* garantisi vermez.
3. **Şeffaf günlüğün izlenmemesi**: Sigstore/Rekor gibi bir şeffaf günlük varlığı, kimse onu izlemiyorsa tespit değeri üretmez; günlüğe düşen anomalilerin (beklenmeyen kimlik, beklenmeyen zaman, beklenmeyen depo) izlenmesi ayrı bir operasyonel disiplin gerektirir.
4. **Geçiş döneminde karışık güven modelleri**: Bazı ekipler eski geleneksel anahtar tabanlı imzalama ile yeni keyless modeli aynı anda, tutarsız politikalarla kullanır; bu, doğrulama mantığının karmaşıklaşmasına ve bazı yolların kazayla atlanmasına yol açar.

## Dependency Confusion: İsim Uzayının Silahlaşması

Bu saldırı sınıfı, kurumların hem herkese açık (public) hem özel/iç (private/internal) paket depoları kullandığı, paket yöneticisinin bu ikisini aynı isim uzayında aradığı senaryolarda ortaya çıkar. Kök neden: birçok bağımlılık çözücü, "aynı isimde paket hem özel depoda hem herkese açık depoda varsa hangisini çeker" sorusuna varsayılan olarak *daha yüksek sürüm numarasını* ya da *herkese açık depoyu* öncelikli tutacak şekilde davranabilir. Bir saldırgan, bir kurumun iç paket isimlerini (ör. sızıntı, çalışan LinkedIn profili, hata mesajları üzerinden) tahmin edip herkese açık depoya aynı isimde, çok daha yüksek sürüm numaralı zararlı bir paket yüklerse, kurumun derleme sistemi otomatik olarak bu zararlı paketi "güncelleme" sanıp çeker.

Savunma: paket yöneticisi yapılandırmasında iç kapsamlar (scoped packages) için açıkça hangi deponun kullanılacağını sabitlemek (private registry'yi öncelikli/tek kaynak olarak tanımlamak), iç paket isimlerini herkese açık depoda da rezerve etmek (boş "koruyucu" paket olarak), ve bağımlılık çözücünün "hangi kaynaktan geldi" bilgisini loglayıp anormal kaynak değişimlerini tespit etmektir.

## Tespit ve Savunma: Bütüncül Bakış

Tedarik zinciri güvenliği tek bir araçla çözülmez; katmanlı bir savunma gerektirir:

- **Görünürlük katmanı**: SBOM ile "elimde ne var" sorusuna her an cevap verebilme.
- **Bütünlük katmanı**: SLSA provenance ile "bu nasıl üretildi" sorusunu doğrulama.
- **Kimlik katmanı**: İmzalama (Sigstore/cosign dâhil) ile "bunu gerçekten iddia edilen taraf mı yayınladı" sorusunu kanıtlama.
- **Politika uygulama katmanı**: Yukarıdakilerin hepsi, dağıtım noktasında *zorunlu kılınmadıkça* (admission control, CI gate) sadece belgeleme kalır — asıl güvenlik değeri, doğrulamanın otomatik ve atlanamaz olmasından gelir.
- **İzleme katmanı**: Şeffaf günlükler, bağımlılık kaynak değişiklikleri, beklenmeyen yayıncı/imzalayıcı kimlikleri sürekli izlenmeli; tedarik zinciri saldırıları genelde yavaş, sabırlı ve "normal görünen" adımlarla ilerler, bu yüzden anomali tespiti kritik önem taşır.

## Sonuç

Yazılım tedarik zinciri güvenliği, "kodum zafiyetsiz mi" sorusunun ötesine geçip "bu kodun bana ulaşana kadar geçtiği her adıma güvenebilir miyim" sorusunu sorar. SBOM envanteri, SLSA süreç bütünlüğünü, imzalama (özellikle Sigstore'un keyless modeli) kimlik ve değişmezliği, dependency confusion savunması ise isim uzayı hijyenini kapsar. Bu araçların ortak paydası, örtük güveni açık, kriptografik olarak doğrulanabilir kanıtlarla değiştirmektir — ve bu kanıtların değeri, yalnızca biri onları *doğrulamayı zorunlu kıldığında* ortaya çıkar. Üretmek yetmez; tüketim noktasında uygulamak gerekir.
