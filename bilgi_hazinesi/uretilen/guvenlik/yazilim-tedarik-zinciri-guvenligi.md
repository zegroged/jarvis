# Yazılım Tedarik Zinciri Güvenliği (SBOM, SLSA, Bağımlılık Zehirleme, Reproducible Builds, CI/CD, İmza/Attestation)

## Giriş: Neden Bu Konu Kritik

Modern bir yazılım ürünü artık kendi yazdığınız kodun küçük bir kısmıdır. Ortalama bir uygulama, üzerine inşa edildiği yüzlerce hatta binlerce açık kaynak bağımlılığın, bu bağımlılıkları derleyen CI/CD boru hattının, bu boru hattını çalıştıran build sunucularının ve nihayetinde son kullanıcıya ulaşan paket/imaj dağıtım kanallarının toplamıdır. Saldırgan açısından bakıldığında bu, tek bir hedefi kırmak yerine, o hedefin **beslendiği kaynağı** kirletmenin çok daha yüksek kaldıraçlı olduğu anlamına gelir: bir kütüphaneyi zehirlerseniz, o kütüphaneyi kullanan binlerce alt sistemi aynı anda etkilersiniz.

Bu tehdit modelinin gerçekliğini kanıtlayan üç olay farklı katmanları temsil eder:

- **SolarWinds (Orion, 2020)**: Saldırgan, ürünün kaynak kodunu değil, **build sürecini** ele geçirdi. Derleme sırasında zararlı kod meşru imzalı ikili dosyanın içine enjekte edildi. Sonuç: binlerce kurum, resmi ve imzalı bir güncellemeyi indirerek arka kapı kurmuş oldu. Bu olay "build pipeline'ı da tehdit yüzeyidir" gerçeğini endüstriye kazandırdı.
- **XZ Utils (2024)**: Saldırgan, yıllar süren sosyal mühendislikle proje bakıcılığına sızdı ve zararlı kodu **test dosyaları ve build script'lerinin** içine, insan gözünden kaçacak şekilde gizledi (obfuscated linker script, sahte test binary'leri). Kaynak kodun kendisi "temiz" görünüyordu; zehir derleme zincirinde saklıydı. Bu, "insan güvenilirliği de tedarik zincirinin bir parçasıdır" dersini verdi.
- **npm/PyPI tiposquatting ve dependency confusion**: Saldırganlar meşru paket adlarına çok benzeyen (`requessts` gibi) veya iç kurumsal paket adlarıyla aynı isimde ama daha yüksek versiyonlu genel paketler yayınlayarak, geliştiricilerin veya otomatik build sistemlerinin yanlışlıkla zararlı paketi çekmesini sağladı.

Bu üç örnek, tedarik zincirinin üç farklı halkasını gösterir: **kaynak/bakım katmanı** (XZ), **build/derleme katmanı** (SolarWinds), **dağıtım/isimlendirme katmanı** (npm/PyPI). Savunma da bu üç halkanın her birinde ayrı ayrı kurulmalıdır — tek bir kontrol yeterli değildir.

---

## Kavramsal Çerçeve: Tedarik Zinciri Nedir, Nerede Kırılır

Bir yazılımın "tedarik zinciri" şu adımlar dizisidir:

1. **Kaynak** — geliştiricinin yazdığı kod + kullanılan üçüncü taraf bağımlılıklar (transitive dependency ağacı dahil).
2. **Build** — kaynağın derlenip/paketlenip artefakta (binary, container image, wheel, jar) dönüştürüldüğü CI/CD ortamı.
3. **Paketleme ve imzalama** — artefaktın sürümlenip, imzalanıp bir registry'ye (npm, PyPI, Docker Hub, Maven Central) yüklenmesi.
4. **Dağıtım** — son kullanıcının veya başka bir sistemin bu artefaktı çekip kurması.

Kök neden mantığı şudur: **güven, zincirin her halkasında zımnen devredilir** ama doğrulanmaz. Geliştirici "bu bağımlılığı çektim, güvenilir" der; CI sistemi "bu commit'i derliyorum, kaynak temiz" varsayar; kullanıcı "bu paket registry'de yayınlanmış, demek ki incelenmiş" düşünür. Hiçbir aşamada kriptografik olarak doğrulanabilir bir **kanıt zinciri (chain of custody)** yoksa, zincirin herhangi bir halkasına sızan saldırgan, sonraki tüm halkaları "meşru" görünümüyle zehirleyebilir. Tedarik zinciri güvenliğinin tüm araç seti (SBOM, SLSA, imzalama, reproducible build) aslında bu tek soruna cevap arar: **"Elimdeki bu artefaktın gerçekten iddia ettiği kaynaktan, iddia ettiği süreçle üretildiğini nasıl kanıtlarım?"**

---

## SBOM (Software Bill of Materials)

### Tanım ve Kök Neden

SBOM, bir yazılım artefaktının içinde hangi bileşenlerin (doğrudan ve transitive bağımlılıklar, sürüm numaraları, lisanslar, bazen hash'ler) bulunduğunu listeleyen makine tarafından okunabilir bir envanterdir (yaygın formatlar: SPDX, CycloneDX).

Kök neden: Log4Shell gibi bir zafiyet çıktığında kurumların çoğu "biz Log4j kullanıyor muyuz, hangi sürümde, kaç uygulamada?" sorusuna **saatler hatta günler içinde** cevap veremedi. Sebep, hiçbir yerde bağımlılık envanterinin merkezi ve güncel tutulmamasıydı. SBOM, bu "bilmiyorum" durumunu ortadan kaldırmayı hedefler — zafiyet duyurulduğu an, etkilenen tüm sistemleri saniyeler içinde sorgulayabilme yeteneği.

### Nasıl Çalışır (Kavramsal)

Build sürecinin bir adımı olarak, derleme aracı (veya ayrı bir tarayıcı) bağımlılık grafiğini çıkarır ve bunu yapılandırılmış bir belgeye (JSON/XML) yazar. Bu belge idealde imzalanır ve artefaktla birlikte, hatta artefaktın içine gömülü olarak dağıtılır.

**Tespit/Kullanım açısından**: SBOM'un asıl değeri üretim anında değil, **kullanım anında** ortaya çıkar. Bir CVE duyurulduğunda, kurum kendi SBOM deposunu (SBOM'ları merkezi toplayan bir envanter/CMDB) sorgulayarak "bu bileşeni içeren hangi imajlar/servisler var" sorusuna anında cevap alır. Bu, olay müdahalesinde (incident response) kritik zaman kazandırır.

**Savunma açısından kurulum**:
- Build pipeline'ına SBOM üretimini zorunlu adım yapın; SBOM'suz artefaktın yayınlanmasını engelleyin (policy gate).
- SBOM'u artefaktla birlikte imzalayın — yoksa saldırgan artefaktı değiştirip sahte/eski bir SBOM'u yanına koyabilir, SBOM'un kendisi de bir güven nesnesidir.
- Transitive bağımlılıkları da içerdiğinden emin olun; çoğu gerçek zafiyet doğrudan değil, dolaylı (nested) bağımlılıklarda çıkar.
- SBOM'ları merkezi bir sorgulanabilir depoda toplayın (sadece dosya olarak arşivlemek yeterli değildir).

### Yaygın Hatalar

- SBOM'u yalnızca "uyumluluk kutucuğu işaretlemek" için üretip hiç sorgulamamak — envanter sadece aranırsa değerlidir.
- Yalnızca doğrudan bağımlılıkları listeleyip transitive ağacı atlamak.
- SBOM'u build sonrası elle/periyodik üretmek, böylece her sürüm için güncel olmayan, drift'e uğramış bir belge ortaya çıkar.

---

## SLSA (Supply-chain Levels for Software Artifacts)

### Tanım ve Kök Neden

SLSA, bir artefaktın **nasıl üretildiğine** dair güven seviyelerini tanımlayan bir olgunluk çerçevesidir (kabaca: kaynağın izlenebilirliği, build sürecinin izole ve tekrarlanabilir olması, üretim çıktısının kriptografik olarak imzalı ve doğrulanabilir olması gibi kademeli gereksinimler).

Kök neden mantığı: SolarWinds saldırısı, kaynağın kendisi hiç değişmeden, sadece **build ortamının** ele geçirilmesiyle gerçekleşti. Kod incelemesi (code review), imza kontrolü ya da SBOM'un hiçbiri bunu tek başına yakalayamazdı çünkü hepsi "build çıktısı"na güveniyordu, "build sürecinin bütünlüğüne" değil. SLSA, tam olarak bu boşluğu kapatır: "artefaktın kaynağı ile üretim süreci arasındaki bağın kanıtlanabilir, taklit edilemez olması" gerekliliğini standartlaştırır.

### Nasıl Çalışır (Kavramsal)

SLSA'nın kademeli mantığı şöyle işler:
- **Düşük seviye**: Build sürecinin belgelenmiş ve tekrarlanabilir olması yeterlidir (elle build'e karşı otomatik build).
- **Orta seviye**: Build, izole ve güvenilir bir CI sisteminde, insan müdahalesi olmadan (script tabanlı) gerçekleşir; kaynak geçmişi (version control) korunur.
- **Üst seviye**: Build ortamının kendisi "ephemeral" (tek kullanımlık, sonra imha edilen) ve izole olur, çıktı için **provenance attestation** (üretim kanıtı — hangi kaynak commit'inden, hangi build tanımından, hangi zamanda üretildiğine dair imzalı bir belge) otomatik üretilir ve bu belge doğrulanmadan artefakt kabul edilmez.

Buradaki temel fikir "build sunucusunu da sıfır güven ilkesiyle ele almak"tır: build makinesi, üzerinde çalışan her job'a güvenmemeli, her job izole edilmeli, ve çıktı için "bunu ben, şu kaynaktan, şu şekilde ürettim" diyen imzalı bir kanıt üretmelidir.

**Tespit/Doğrulama**: Tüketici tarafında (bir CI/CD, bir Kubernetes admission controller, bir paket yöneticisi) artefaktı kullanmadan önce provenance attestation'ı doğrulayan bir politika motoru çalıştırılır — "bu imaj gerçekten bizim CI'ımızdan mı geldi, beklenen kaynak deposundan mı, beklenen build tanımıyla mı üretildi" sorularına otomatik cevap verir. Beklenmeyen bir kaynaktan gelen ya da provenance'ı olmayan artefaktlar reddedilir.

**Savunma açısından kurulum**:
- CI/CD sistemini "her build izole, geçici ortamda çalışsın, secrets sadece gerektiği kadar erişilebilir olsun" ilkesiyle tasarlayın.
- Provenance üretimini build pipeline'ının zorunlu, atlanamaz bir parçası yapın (build script'i değiştirse bile provenance CI platformunun kendisi tarafından, dışarıdan üretilmeli — yoksa saldırgan build script'ini değiştirip sahte provenance da üretebilir).
- Dağıtım/deploy aşamasında provenance doğrulamasını "gate" (geçit) olarak zorunlu kılın; doğrulanamayan artefakt production'a giremesin.

### Yaygın Hatalar

- Provenance'ı build script'inin kendi içinde üretmek — bu, saldırganın build script'ini ele geçirdiği senaryoda sahte provenance üretebilmesi anlamına gelir. Provenance, build sisteminin **dışından, güvenilir bir kontrol düzleminden** gelmelidir.
- "SLSA uyumluyuz" demek ama üretilen provenance'ı hiçbir yerde doğrulamamak — üretmek yeterli değildir, tüketim noktasında zorunlu doğrulama olmalıdır.

---

## Bağımlılık / Paket Zehirleme (Dependency Confusion, Tiposquatting, Typosquatting, Maintainer Takeover)

### Tanım ve Kök Neden

Bu saldırı ailesi, geliştiricinin veya otomatik sistemin **yanlış paketi** güvenilir sanıp çekmesini hedefler. Üç ana varyant:

1. **Typosquatting**: Popüler bir paket adına çok benzeyen (tek harf farkı, karakter değişimi) zararlı bir paket yayınlamak; geliştirici yazım hatası yapınca zararlı paketi kurar.
2. **Dependency confusion**: Kurumun iç (private) registry'de kullandığı bir paket adıyla aynı isimde, ama daha yüksek sürüm numaralı bir paketi **genel (public)** registry'ye yüklemek. Birçok paket yöneticisi, yapılandırma hatası nedeniyle iç ve dış registry'yi birlikte tarayıp "en yüksek sürümü" tercih eder — bu da genel/zararlı paketin çekilmesine yol açar.
3. **Maintainer/hesap ele geçirme**: Meşru, uzun süredir var olan bir paketin bakıcı hesabının ele geçirilmesi (çalınan kimlik bilgisi, sosyal mühendislik, ya da XZ Utils örneğinde olduğu gibi yıllar süren güven inşası ile projeye ortak bakıcı olarak sızma) yoluyla zararlı kodun meşru paketin **yeni bir sürümüne** enjekte edilmesi.

Kök neden: Paket registry ekosistemleri (npm, PyPI, RubyGems, crates.io vb.) tasarım gereği **açık ve düşük sürtünmelidir** — herkes hesap açıp paket yayınlayabilir. Bu, açık kaynağın gücünün kaynağıdır ama aynı zamanda "isim" ve "sürüm numarası"nın tek başına güven ifade etmediği anlamına gelir. Sistemler bu ikisine körü körüne güvendiğinde saldırı yüzeyi doğar.

### Nasıl Çalışır (Kavramsal) + Tespit + Savunma

**Typosquatting**: Saldırgan popüler paket adının varyasyonlarını toplu olarak kayıt altına alır, içine (çoğunlukla install-time script'lerde çalışan) bilgi çalan veya arka kapı kod koyar. Kurulum anında (`postinstall` gibi mekanizmalarla) kod otomatik çalışır — geliştirici paketi hiç "kullanmasa" bile enfekte olur.

- *Tespit*: CI/CD içinde bağımlılık adlarını bilinen popüler paketlerle Levenshtein mesafesi/benzerlik skoruna göre karşılaştıran otomatik taramalar; kurulum script'i çalıştıran (`postinstall`, `preinstall` benzeri hook'lar) yeni/az bilinen paketleri flag'leyen politikalar.
- *Savunma*: Bağımlılık ekleme sürecini gözden geçirmeye tabi tutmak (yeni bağımlılık = kod review konusu); mümkünse kurulum script'lerini varsayılan olarak devre dışı bırakan/izole bir kurulum modu kullanmak; kilitli sürüm dosyaları (lockfile) ve hash doğrulamasını zorunlu kılmak.

**Dependency confusion**: Saldırgan, kurbanın iç paket adını (genelde sızdırılmış CI loglarından, hata mesajlarından veya paket.json/requirements dosyalarından) öğrenir, aynı adla genel registry'de daha yüksek sürümlü bir paket yayınlar. Yanlış yapılandırılmış paket yöneticisi, iç registry yerine (ya da onunla karışık şekilde) genel registry'den "en güncel" sürümü çeker.

- *Kök neden mekaniği*: Sürüm çözümleme (resolution) mantığı, adı aynı olan paketler arasında **kaynağı değil, sürüm numarasını** önceliklendirir.
- *Tespit*: Build loglarında beklenmeyen kaynaktan (private registry değil, public registry'den) çekilen iç isimli paketleri izleyen kontroller; SBOM'da her bileşenin "origin/source registry" alanının beklenenle eşleşip eşleşmediğini doğrulamak.
- *Savunma*: Paket yöneticisini, iç paket adları için **yalnızca** iç registry'yi sorgulayacak şekilde scope/namespace ile yapılandırmak (ör. adlandırma alanı ayırma); genel registry'de kendi iç paket adlarınızı da (boş içerikle olsa dahi) önceden rezerve etmek; registry önceliklendirmesini kesin ve tek yönlü tanımlamak, "en yüksek sürüm kazanır" davranışını iç kaynaklar için kapatmak.

**Maintainer takeover**: Saldırgan zaman içinde (aylar/yıllar) meşru katkıda bulunan olarak güven kazanır, bakım yükü ağır bir projede "yardımcı bakıcı" statüsü elde eder, sonra zararlı değişikliği küçük, sıradan görünen commit'ler halinde ana dala sokar (XZ Utils'te olduğu gibi, test dosyaları ve build script'leri gibi az incelenen yerlerde).

- *Tespit*: Bağımlılık güncellemelerinde ani/açıklanamayan davranış değişikliklerini izleyen davranışsal analiz (build süresinin anormal uzaması, yeni ağ bağlantıları, yeni binary/test dosyalarının eklenmesi); bakıcı hesap değişikliklerini ve yeni bakıcı eklenmesini izleyen uyarı mekanizmaları.
- *Savunma*: Kritik bağımlılıkları hemen güncellememek, bir "olgunlaşma penceresi" (ör. yayınlandıktan belli süre sonra güncelleme) uygulamak; kritik/az bakıcılı açık kaynak projeleri için topluluk düzeyinde çoklu-bakıcı ve imzalı commit zorunluluğu gibi uygulamaları teşvik etmek; bağımlılık güncellemesi PR'larında diff'i (özellikle build/test dosyalarındaki) otomatik ve insan gözüyle incelemek.

### Yaygın Hatalar

- "Biz sadece resmi registry kullanıyoruz, güvenliyiz" varsayımı — resmi registry'nin kendisi açık ve herkese yayın izni veren bir sistemdir, "resmi" olmak "incelenmiş" anlamına gelmez.
- Lockfile'ları (kilitli sürüm/hash dosyaları) commit etmemek veya CI'da doğrulamamak, böylece her build farklı (ve potansiyel olarak zehirlenmiş) bir sürüm ağacı çekebilir.
- Bağımlılık güncellemelerini otomatik ve incelemesiz merge eden bot politikaları — hız için güvenlik incelemesini atlamak.

---

## Reproducible Builds (Tekrarlanabilir Derlemeler)

### Tanım ve Kök Neden

Reproducible build, aynı kaynak kod ve aynı build tanımından, **farklı zamanlarda, farklı makinelerde, farklı kişiler tarafından** derlendiğinde **bit-bit özdeş** bir çıktı üretilmesi anlamına gelir.

Kök neden: SBOM ve SLSA "bu kaynaktan, bu süreçle üretildi" der ama bunun **doğru** olduğunu nasıl bilirsiniz? Provenance belgesinin kendisi de sahte olabilir (build sistemi ele geçirilmişse). Reproducible build, bağımsız üçüncü taraflara "iddia edilen kaynaktan gerçekten bu ikili çıkar mı" sorusunu **kendi ortamlarında tekrar derleyerek** doğrulama imkânı verir — güveni tek bir merkezi otoriteden alıp, dağıtık/bağımsız doğrulamaya yayar.

### Nasıl Çalışır (Kavramsal)

Normalde derleme sürecine zaman damgaları, dosya sistemi sıralaması, ortam değişkenleri, derleyici sürüm farklılıkları gibi "deterministik olmayan" unsurlar karışır ve aynı kaynaktan her seferinde biraz farklı bir ikili çıkar. Reproducible build, bu deterministik olmayan girdileri build sürecinden temizler (sabit zaman damgaları, sıralı dosya işleme, sabitlenmiş toolchain sürümleri) böylece çıktı yalnızca kaynağın ve build tanımının bir fonksiyonu olur.

**Tespit/doğrulama mantığı**: Bağımsız taraflar (topluluk, denetim firmaları, farklı kurumlar) aynı kaynağı kendi izole ortamlarında derler ve elde ettikleri hash'i, resmi yayınlanan ikilinin hash'iyle karşılaştırır. Eşleşmiyorsa, ya build süreci deterministik değildir ya da resmi dağıtım kanalı kaynaktan sapmıştır (yani SolarWinds tipi bir müdahale gerçekleşmiş olabilir) — bu fark tek başına bir alarm sinyalidir.

**Savunma açısından kurulum**:
- Build ortamını mümkün olduğunca "hermetic" (dış dünyadan izole, sabit girdili) hale getirin.
- Zaman damgası, ortam değişkeni, dosya sırası gibi deterministik olmayan unsurları build script'lerinden temizleyin.
- Yayınlanan her ikili için, bağımsız doğrulayıcıların tekrar derleyip karşılaştırabileceği açık build talimatları ve sabit toolchain sürümleri yayınlayın.

### Yaygın Hatalar

- Reproducible build'i yalnızca "teorik" bir hedef sayıp hiç bağımsız doğrulama sürecine bağlamamak — kimse tekrar derleyip karşılaştırmıyorsa, tekrarlanabilirlik güven sağlamaz.
- Build sürecindeki gizli deterministik olmayan bağımlılıkları (ör. derleyicinin kendi sürümü, sistem saatine bağlı optimize etme) gözden kaçırmak, "neredeyse tekrarlanabilir ama asla tam eşleşmeyen" build'lerle sonuçlanmak.

---

## CI/CD Pipeline Güvenliği

### Tanım ve Kök Neden

CI/CD pipeline, kaynak kodun otomatik olarak test edilip derlendiği ve dağıtıldığı sistemdir. Tedarik zinciri açısından bu, saldırganın en yüksek kaldıraçlı hedeflerinden biridir çünkü pipeline genellikle **secrets'e (imzalama anahtarları, deploy kimlik bilgileri, bulut erişim token'ları) ve production'a doğrudan erişime** sahiptir; SolarWinds saldırısının özünde tam olarak bu vardı.

Kök neden: CI/CD sistemleri tarihsel olarak "geliştirme kolaylığı" için tasarlanmıştır — geniş yetkili servis hesapları, paylaşılan runner'lar, pull request'lerden tetiklenen otomatik script çalıştırma. Bu rahatlık, aynı zamanda saldırı yüzeyidir: bir pull request üzerinden (hatta dışarıdan bir katkıcının PR'ı üzerinden) çalıştırılan CI job'ı, imzalama anahtarına erişebilen bir ortamda kod çalıştırıyorsa, bu neredeyse doğrudan bir arka kapı fırsatıdır.

### Nasıl Çalışır (Kavramsal) + Tespit + Savunma

**Yaygın zafiyet noktaları**:
- **Fork/PR tetiklemeli workflow'lar**: Dışarıdan biri PR açtığında CI, o PR'ın içeriğindeki script'i (ör. CI yapılandırma dosyasının kendisi de kod deposunun bir parçasıdır) çalıştırıyorsa ve bu ortamda secrets erişilebilirse, kötü niyetli bir PR doğrudan secrets sızdırabilir.
- **Aşırı geniş yetkili servis hesapları**: CI'ın "her şeye" erişebilen tek bir token kullanması, bir job'ın ele geçirilmesini tüm sistemin ele geçirilmesine dönüştürür.
- **Paylaşılan/kalıcı (persistent) runner'lar**: Bir build'in bıraktığı kalıntı (cache, ortam değişkeni, dosya sistemi izi) sonraki build'i etkileyebilir — izolasyon eksikliği, yanal hareket imkânı doğurur.
- **Yapılandırma dosyası enjeksiyonu**: CI yapılandırma dosyasının kendisi (ör. workflow tanımı) kod deposunun içindeyse ve bu dosyayı değiştirme yetkisi gereğinden geniş insanlara veya otomasyona açıksa, saldırgan doğrudan pipeline davranışını değiştirebilir.

**Tespit**:
- Pipeline loglarında beklenmeyen ağ çıkışlarını (özellikle build sırasında dışarıya veri gönderen bağlantıları) izleyen ağ tabanlı anomali tespiti.
- Secrets erişim loglarını (hangi job, ne zaman, hangi secret'a eriştiği) düzenli denetlemek; beklenmeyen zamanlarda/job'larda secret erişimini alarma bağlamak.
- Workflow/pipeline tanım dosyalarındaki değişiklikleri, kod değişikliğinden ayrı ve daha sıkı bir onay sürecine tabi tutup izlemek.

**Savunma**:
- **En az yetki**: Her pipeline job'ına, sadece o job'ın ihtiyaç duyduğu minimum secret ve erişim kapsamını vermek (imzalama anahtarına yalnızca release job'ı erişsin, test job'ı erişmesin).
- **İzolasyon**: Her build'i geçici (ephemeral), tek kullanımlık ortamda çalıştırmak; build bitince ortamı tamamen imha etmek.
- **Fork/dış katkı PR'larını farklı güven seviyesinde çalıştırmak**: Dışarıdan gelen PR'ları, secrets'a erişimi olmayan izole bir ortamda test etmek; secrets gerektiren adımları (deploy, imzalama) yalnızca onaylanmış/merge edilmiş kod için tetiklemek.
- **Pipeline tanımını da kod incelemesine tabi tutmak**: CI yapılandırma dosyasındaki değişiklikleri normal kod değişikliğinden daha sıkı incelemek (çünkü bu dosya "neyin çalıştırılacağını" tanımlar).
- **İkili onay (two-person rule)**: Kritik pipeline değişikliklerinde ve release süreçlerinde tek kişinin tek başına değişiklik yapıp deploy edememesi.

### Yaygın Hatalar

- CI/CD'yi "sadece geliştirici verimliliği aracı" olarak görüp, production erişimine sahip bir sistem olarak güvenlik mimarisine dahil etmemek.
- Test ortamı ile production imzalama/deploy yetkilerini aynı pipeline'da, aynı servis hesabıyla karıştırmak.
- Uzun ömürlü (kalıcı) build runner'ları kullanmak, böylece bir build'in bulaşması sonraki tüm build'leri etkileyebilir.

---

## İmzalama ve Attestation (Signing & Attestation)

### Tanım ve Kök Neden

İmzalama, bir artefaktın (kod, container image, paket) kriptografik olarak "bunu ben ürettim, içeriği değiştirilmedi" iddiasını taşımasıdır. Attestation ise bir adım ileri gider: sadece "kimin imzaladığı" değil, "hangi süreçle, hangi kaynaktan, hangi koşullarda üretildiği" gibi ek iddiaları da imzalı olarak taşır (SLSA'daki provenance, aslında bir attestation türüdür).

Kök neden: SolarWinds saldırısında zararlı ikili, **meşru şirketin gerçek imzalama anahtarıyla imzalanmıştı** — çünkü saldırgan build sürecine sızmıştı ve imzalama, build sürecinin normal bir adımıydı. Bu, kritik bir dersi ortaya koyar: **imza, "değiştirilmedi" der ama "doğru süreçle üretildi" demez.** İmza tek başına, imzalayan anahtarın kendisinin ele geçirilmediği varsayımına dayanır — bu varsayım, build sistemi güvenli değilse çöker.

### Nasıl Çalışır (Kavramsal) + Tespit + Savunma

**Mekanizma**: Artefaktın hash'i, özel bir anahtarla imzalanır; tüketici, karşılık gelen açık anahtarla imzayı doğrulayıp hem bütünlüğü (içerik değişmedi) hem kimliği (beklenen taraf imzaladı) teyit eder. Attestation'da imzalanan şey sadece hash değil, yapılandırılmış bir iddiadır (ör. "bu imaj, şu commit'ten, şu CI job'ında, şu tarihte üretildi").

**Kritik zayıf halka — anahtar yönetimi**: İmzalama anahtarının kendisi nerede saklanıyor, kim/hangi sistem erişebiliyor? Anahtar build sunucusunda düz metin duruyorsa, build sunucusunu ele geçiren saldırgan doğrudan meşru imza üretebilir (tam olarak SolarWinds senaryosu). Bu nedenle modern yaklaşımlar:
- Anahtarı donanım güvenlik modülü (HSM) veya benzeri korumalı bir ortamda tutmak, imzalama işlemini build sürecinden **ayrı, izole bir imzalama servisine** devretmek.
- "Keyless" imzalama yaklaşımları: uzun ömürlü statik anahtar yerine, her imzalama işlemi için kısa ömürlü, kimlik doğrulamalı (ör. CI kimliğine bağlı) geçici anahtar/sertifika üretip, imzalama olayının kendisini şeffaf, herkese açık bir kayıt defterinde (transparency log) damgalamak — böylece "ne zaman, kim tarafından, hangi kimlikle imzalandı" dışarıdan denetlenebilir hale gelir.

**Tespit**:
- İmza doğrulamasını dağıtım/deploy zincirinin **zorunlu** bir geçidi yapmak; imzasız veya beklenmeyen anahtarla imzalanmış artefaktları otomatik reddetmek.
- Transparency log kullanılıyorsa, beklenmeyen zamanlarda/kimliklerle yapılan imzalama olaylarını izlemek — meşru olmayan bir imzalama isteği burada görünür hale gelir.

**Savunma**:
- İmzalama anahtarını build ortamından fiziksel/mantıksal olarak ayırmak.
- İmzalama iznini, sadece belirli, onaylanmış pipeline adımlarına (release job'ı gibi) kısıtlamak; geliştirici iş istasyonlarından veya test job'larından imzalama yapılamamasını sağlamak.
- Tüketici tarafında (deploy, admission controller, paket yöneticisi) imza + provenance doğrulamasını birlikte zorunlu kılmak — sadece imza yeterli değildir, "doğru süreçle üretildi mi" sorusu da cevaplanmalı.

### Yaygın Hatalar

- İmzalama anahtarını CI ortam değişkeni olarak düz metin saklamak — bu, anahtarı build'e erişen herkese/her job'a açık hale getirir.
- "İmzalı" olmayı tek başına yeterli güven kanıtı saymak, provenance/attestation doğrulamasını atlamak.
- İmza doğrulamasını yalnızca "uyarı" seviyesinde bırakmak, başarısız doğrulamada dağıtımı durdurmamak (gate yerine log).

---

## Bütüncül Savunma Mimarisi: Katmanları Birlikte Düşünmek

Bu kontrollerin hiçbiri tek başına yeterli değildir çünkü her biri zincirin farklı bir halkasını korur:

- SBOM, **"içinde ne var"** sorusuna cevap verir (envanter/tespit).
- SLSA + provenance, **"nasıl üretildi"** sorusuna cevap verir (süreç bütünlüğü).
- Bağımlılık zehirleme savunmaları, **"doğru kaynaktan mı geldi"** sorusuna cevap verir (kaynak bütünlüğü).
- Reproducible build, **"iddia edilen kaynaktan gerçekten bu mu çıkıyor"** sorusunu bağımsız doğrulanabilir kılar (üçüncü taraf doğrulama).
- CI/CD pipeline güvenliği, yukarıdaki tüm kontrollerin **uygulandığı ortamın kendisinin** güvenilir olmasını sağlar (altyapı bütünlüğü).
- İmzalama/attestation, tüm bunları **taşınabilir, doğrulanabilir bir kanıta** dönüştürür (iddiayı mühürleme).

Savunmacı gözüyle pratik öncelik sırası genellikle şöyledir: önce CI/CD ortamını izole edip en az yetki ilkesini uygulayın (çünkü burası ele geçirilirse üstündeki her şey anlamsızlaşır), sonra SBOM ile görünürlük kazanın, sonra bağımlılık kaynaklarını sıkılaştırın (dependency confusion, typosquatting savunmaları), sonra imzalama+attestation ile tüketim noktasında doğrulanabilir geçitler kurun, ve olgunluk arttıkça SLSA seviyelerini ve reproducible build hedeflerini yükseltin.

Sonuç olarak tedarik zinciri güvenliği, "bir aracı kurup unutmak" değil, **her yeni bağımlılığın, her build'in, her imzanın sürekli sorgulandığı bir güven doğrulama disiplinidir.** SolarWinds, XZ Utils ve dependency confusion olayları, bu disiplinin eksik olduğu her noktanın gerçek dünyada istismar edildiğini göstermiştir.
