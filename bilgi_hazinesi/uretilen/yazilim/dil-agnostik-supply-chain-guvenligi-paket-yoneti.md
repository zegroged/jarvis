# Dil-Agnostik Supply Chain Güvenliği: Paket Yöneticisi Ekosistem Saldırıları

## Giriş: Neden Bu Konu Ayrı Bir Başlık Olmayı Hak Ediyor

Modern yazılım artık kendi başına yazılmıyor; her proje ortalama yüzlerce, bazen binlerce üçüncü parti bağımlılık (dependency) üzerine inşa ediliyor. `npm install`, `pip install`, `composer require`, `bundle install`, `cargo add` gibi tek satırlık komutlar, aslında güvenmediğiniz onlarca insanın yazdığı koda çalıştırma yetkisi vermek anlamına geliyor. Bu güven zincirine **supply chain (tedarik zinciri)** denir ve zincirin en zayıf halkası, saldırganların en çok tercih ettiği hedef haline gelmiştir.

Önemli olan şu: bu saldırı sınıfı **dilden bağımsız (language-agnostic)**. npm (JavaScript/Node.js), PyPI (Python, `pip` üzerinden), RubyGems (Ruby), Packagist (PHP, `composer` üzerinden), crates.io (Rust) ve NuGet (.NET) — hepsi aynı temel mimariye sahip: merkezi bir kayıt defteri (registry), isim bazlı paket çözümleme (resolution) ve kurulum sırasında keyfi kod çalıştırma imkanı. Bu ortak mimari, ortak zafiyet sınıflarını da beraberinde getiriyor. Bir güvenlik mühendisi olarak tek bir ekosistemi değil, bu **ortak deseni** anlamanız gerekiyor; çünkü yarın yeni bir dil (Zig, Deno registry'leri, vs.) çıktığında aynı saldırılar oraya da taşınacak.

Bu makale üç ana saldırı ailesini derinlemesine işliyor: **typosquatting**, **dependency confusion** ve **postinstall/lifecycle script kötüye kullanımı**. Amaç, bu mekanizmaları bir savunmacı gözüyle anlamak ve tespit/önleme stratejileri kurmaktır.

## Kök Neden: Paket Yöneticilerinin Güven Modeli Neden Kırılgan

Tüm bu saldırıların ortak kök nedeni, paket yöneticilerinin tasarım felsefesinde yatıyor: **kolaylık, güvenlikten önce optimize edilmiş**. npm 2010'larda "herkes kolayca paylaşsın" mantığıyla tasarlandı; PyPI da benzer şekilde açık, düşük sürtünmeli bir yayın modeli benimsedi. Bu tasarım kararlarının doğrudan sonuçları şunlar:

1. **İsim benzersizliği var, ama isim *anlamlılığı* doğrulanmıyor.** Bir paketin adı `requests` ise, bu onun gerçekten güvenilir/resmi bir kütüphane olduğu anlamına gelmez — sadece o isim daha önce alınmamış demektir. Marka koruması (trademark) yok, sadece "ilk gelen alır" (first-come-first-served) mantığı var.
2. **Kurulum = kod çalıştırma.** Neredeyse her ekosistem, paket kurulumu sırasında geliştiricinin tanımladığı script'leri çalıştırmaya izin verir: npm'de `postinstall`/`preinstall` (package.json içindeki `scripts` alanı), Python'da `setup.py` içindeki keyfi Python kodu (özellikly eski `sdist` dağıtım formatında), RubyGems'te `extconf.rb` ile native extension derleme, crates.io'da `build.rs` dosyaları. Bu mekanizmalar *meşru* amaçlarla var oldu (native modül derleme, platforma özgü kurulum adımları) ama saldırgan için de bedava bir "kurulum anında kod çalıştırma" kapısı.
3. **Bağımlılık çözümleme (dependency resolution) otomatik ve derin (transitive).** Siz sadece 5 paket eklersiniz ama transitive dependency graph 300 pakete çıkabilir. Kimse bu 300 paketin hepsini elle incelemez — güven, insan denetiminden algoritmaya devredilmiştir.
4. **Registry'ler arası ve iç/dış ayrım genelde isim bazlı çözülüyor, kaynak bazlı değil.** Yani "bu paket şirket içi private registry'den mi, yoksa herkese açık public registry'den mi gelsin" kararı çoğu zaman sadece paket adına bakılarak, akıllıca (ama yanlış) varsayımlarla veriliyor. Dependency confusion tam olarak bu noktadan doğar.

Bu üç mimari gerçeği aklınızda tutarsanız, aşağıdaki tüm saldırı teknikleri "şaşırtıcı" değil, "beklenen" hale gelir.

## Typosquatting: Çalışma Mantığı

### Tanım ve Mekanizma

Typosquatting, saldırganın gerçek/popüler bir paketin adına çok benzeyen ama farklı bir isimle kötü niyetli bir paket yayınlaması ve geliştiricilerin yazım hatası (typo), dikkatsizlik veya kafa karışıklığı yüzünden yanlış paketi kurmasını beklemesidir. Domain squatting'in (örneğin `gooogle.com`) paket yöneticisi dünyasındaki karşılığıdır.

Yaygın varyasyon teknikleri:

- **Karakter ekleme/çıkarma/değiştirme:** `requests` → `requsts`, `reqeusts`, `request` (tekil/çoğul karışıklığı).
- **Ayraç değişimi:** `python-dateutil` → `python_dateutil` veya `pythondateutil`. Bazı ekosistemlerde tire (`-`) ve alt çizgi (`_`) normalize edilir, bazılarında edilmez — bu tutarsızlığın kendisi bir saldırı yüzeyi.
- **Klavye komşuluğu (keyboard proximity):** `colors` → `colros` (QWERTY'de r-l-o-r-s karışıklığı gibi elle yazarken sık yapılan hatalar).
- **Ölçek/marka taklidi (combosquatting):** Gerçek bir organizasyon adını pakete önek/sonek olarak ekleme: `реаl-lodash`, `lodash-utils`, `official-package-x`. Burada amaç yazım hatası değil, meşruiyet hissi vermek.
- **Homoglif saldırıları:** Latin alfabesindeki bir harfi görsel olarak neredeyse aynı görünen Kiril/Yunan karakterle değiştirmek (örn. Latin "a" yerine Kiril "а"). Bu, insan gözüyle fark edilmesi neredeyse imkansız ama byte düzeyinde tamamen farklı bir string üretir.
- **Scope/namespace taklidi:** npm'de `@babel/core` gibi scoped paketlerde, scope'suz bir taklit paket (`babel-core` adında ama resmi olmayan) yayınlamak; ya da benzer görünen ama yetkisiz bir scope (`@babeI/core` — büyük I, küçük l karışıklığı) kullanmak.

### Neden İşe Yarıyor

Kök neden insan dikkatinin sınırlı olması ve otomasyonun (CI/CD, kopyala-yapıştır talimatlar, AI destekli kod önerileri) bu hataları sorgusuz sualsiz çalıştırmasıdır. Bir geliştirici Stack Overflow'dan veya bir AI asistanından `pip install request` gibir hatalı bir komut kopyaladığında, terminal "paket bulunamadı" hatası vermez (çünkü `request` diye gerçek bir paket olabilir) — sessizce yanlış ama var olan bir pakete bağlanır. Son yıllarda LLM tabanlı kod asistanlarının **var olmayan paket adları uydurması (package hallucination)** da bu saldırıya yeni bir vektör eklemiştir: saldırgan, LLM'lerin sık önerdiği hayali paket adlarını önceden kayıt ettirip zararlı içerik koyabilir.

### Tespit ve Savunma

- **İsim benzerliği taraması:** Levenshtein/edit distance ve fonetik benzerlik (Soundex, klavye-mesafesi modelleri) kullanan otomatik araçlarla, kurmayı planladığınız paketin popüler paketlere olan yakınlığını kontrol edin. Birçok registry güvenlik ekibi (npm, PyPI) bu taramayı proaktif olarak yapar ama siz de kendi bağımlılık listenizde periyodik tarama yapmalısınız.
- **Kilitleme dosyalarını (lockfile) commit'leyin ve zorunlu kılın:** `package-lock.json`, `poetry.lock`, `Gemfile.lock`, `composer.lock`, `Cargo.lock`. Bu dosyalar tam sürüm ve genelde bütünlük hash'i (integrity hash) sabitler; "her build'de en son sürümü çek" davranışını engeller, dolayısıyla saldırganın sizi *yeni* bir typosquat pakete yönlendirmesi lock dosyası değişmeden mümkün olmaz.
- **Kopyala-yapıştır disiplinini kurumsallaştırın:** Kurulum komutlarının code review'dan geçmesi, `requirements.txt`/`package.json` değişikliklerinin diff olarak incelenmesi.
- **İç ayna/proxy registry kullanın** (Artifactory, Nexus, verdaccio, devpi gibi): Dış dünyadan gelen her paket bir kere onaylanıp iç registry'ye alınır; geliştiriciler doğrudan public registry'ye değil bu iç aynaya bağlanır. Bu hem typosquatting hem aşağıda anlatılan dependency confusion için güçlü bir savunma katmanıdır.
- **Otomatik SCA (Software Composition Analysis) araçları** (Dependabot, Snyk, Socket.dev, OSV-Scanner gibi) yeni eklenen bağımlılıkları bilinen kötü amaçlı paket listeleriyle ve davranışsal ısı haritalarıyla karşılaştırır.

## Dependency Confusion: Çalışma Mantığı

### Tanım

Dependency confusion (2021'de güvenlik araştırmacısı Alex Birsan'ın yayınladığı çalışmayla geniş kamuoyu farkındalığı kazanan bir teknik), bir şirketin **iç/özel (internal/private)** kullanım için yazdığı ve genelde private bir registry'de barındırdığı paket adlarının, saldırgan tarafından **aynı isimle public registry'ye (npm, PyPI vb.) yayınlanmasıdır**. Amaç, paket çözümleyicinin (resolver) kafasını karıştırıp, geliştiricinin makinesinin veya CI/CD sunucusunun private paket yerine saldırganın public paketini çekmesini sağlamaktır.

### Kök Neden: Çözümleme Önceliği Belirsizliği

Bunun neden mümkün olduğunu anlamak için resolver mantığına bakmak gerekir. Birçok araç yapılandırması, hem private bir registry'yi hem de public registry'yi (npm registry, PyPI) aynı anda kaynak olarak tanımlar — bazen "önce private'a bak, yoksa public'e düş (fallback)" mantığıyla, bazen de **sürüm numarasına göre en yükseği seçme** mantığıyla. İkinci durum çok daha tehlikelidir: saldırgan, şirketin iç paketinin adını public registry'de, kasıtlı olarak çok yüksek bir sürüm numarasıyla (örn. `9.9.9` veya `99.0.0`) yayınlarsa, "en yüksek sürümü al" kuralı işleyen resolver'lar saldırganın paketini "daha yeni" sanıp onu tercih eder — hangi kaynaktan geldiğine bakmaksızın.

Kök neden özetle şudur: **paket adı, güvenin tek dayanağı haline gelmiş; ama isim alanı (namespace) private ve public registry'ler arasında izole değildir.** Şirket içi bir isim seçerken kimse "bu isim public registry'de de var mı, birisi bunu ele geçirebilir mi" diye sormaz; çünkü paket zaten "içeri özel" olarak düşünülür — ama resolver bunu bilmez.

### Saldırı Akışı (Kavramsal, Adım Adım)

1. Saldırgan, hedef şirketin iç paket isimlerini keşfeder. Bu isimler genelde şu şekilde sızar: açık kaynak repolarındaki `package.json`/`requirements.txt` dosyalarında yanlışlıkla bırakılmış iç bağımlılık referansları, hata mesajları, sunum/konferans slaytları, iş ilanları, GitHub'da halka açık iç araçlar, npm/PyPI hata loglarının paylaşılması.
2. Saldırgan bu isimle **public** registry'de bir hesap açıp paket yayınlar; içine genelde zararsız görünen ama telemetri/callback (örneğin dış bir sunucuya "bu şirketten çalıştım" bilgisi gönderen) kod koyar — araştırma amaçlı yapılan etik açıklamalarda genelde sadece "buradan çalıştı" sinyali gönderilir, gerçek saldırılarda ise kötü amaçlı yük (payload) olabilir.
3. Kurban şirketin CI/CD sistemi veya bir geliştirici makinesi bağımlılıkları kurarken, yapılandırma (ör. `.npmrc`, `pip.conf`, `NuGet.config`) private registry önceliğini doğru tanımlamadığı için, ya da "en yüksek sürüm" kuralı yüzünden saldırganın public paketini çeker.
4. Kurulum sırasında (bkz. bir sonraki bölüm) çalışan lifecycle script'ler sayesinde saldırgan kod, CI/CD ortamında veya geliştirici makinesinde çalışır — bu ortamlar genelde gizli anahtarlar (secrets), token'lar, iç ağ erişimi barındırdığı için değeri çok yüksektir.

### Neden Özellikle CI/CD Ortamları Bu Kadar Kritik

CI/CD sunucuları genelde en yüksek ayrıcalıklara sahiptir: bulut sağlayıcı kimlik bilgileri, imzalama anahtarları, iç ağ erişimi, diğer servislere erişim token'ları. Bir geliştiricinin dizüstü bilgisayarına sızmak değerli olabilir, ama CI/CD pipeline'ına sızmak saldırgana genelde **üretim ortamına kadar uzanan** bir yol açar. Bu yüzden dependency confusion, özellikle otomatik build sistemlerini hedef aldığında, etkisi orantısız derecede büyüktür.

### Tespit ve Savunma

- **İsim alanı rezervasyonu (namespace claiming):** İç kullanım için seçtiğiniz her paket adını, kullanmasanız bile **public registry'de de boş bir "placeholder" paket olarak kaydedin.** Bu, saldırganın aynı adı almasını engeller. npm, scoped paketler (`@sirketiniz/paket-adi`) kullanmayı önerir çünkü scope, organizasyon düzeyinde sahiplik doğrulaması gerektirir — bu, dependency confusion'a karşı en güçlü yapısal savunmalardan biridir.
- **Registry yapılandırmasında scope/kaynak sabitleme:** `.npmrc` içinde belirli scope'ları açıkça private registry'ye yönlendirin (`@sirketiniz:registry=https://iç-registry-url`); "fallback to public" davranışını kapatın. Python tarafında `pip.conf`/`pyproject.toml` içinde `--index-url` yerine `--extra-index-url` kullanmanın riskini bilin: `--extra-index-url` ile birden fazla kaynak tanımlarsanız, pip birçok sürümde en yüksek sürüm numarasını seçebilir, kaynağı ayırt etmeden — bu davranış tam olarak dependency confusion'ın istismar ettiği noktadır.
- **Private registry'yi tek gerçek kaynak (source of truth) yapın:** İç paketler için sadece private registry'yi tanımlayıp public'e hiç düşmesin (no fallback); dış paketler için ise private registry'nin kendisini bir proxy/ayna olarak kullanın (yukarıda bahsedilen Artifactory/Nexus/verdaccio yaklaşımı). Böylece geliştirici makinesi hiçbir zaman doğrudan public registry'ye bağlanmaz, her şey tek, denetlenebilir bir kapıdan geçer.
- **Sürüm sabitleme ve bütünlük doğrulama:** Lockfile'lardaki hash tabanlı bütünlük kontrolü (`integrity` alanı npm'de, `--hash` pip'te), paketin beklenen içerikle birebir eşleştiğini garanti eder; saldırganın "aynı isim farklı içerik" numarası burada yakalanır.
- **CI/CD ortamlarında ağ izolasyonu:** Build sürecinin sadece onaylı registry uç noktalarına erişebilmesi (egress filtreleme), bilinmeyen bir kaynaktan paket çekilmesini mimari düzeyde imkansız kılar.

## Postinstall/Lifecycle Script Kötüye Kullanımı

### Tanım ve Mekanizma

Bu, hem typosquatting hem dependency confusion saldırılarının "silahlandığı" (weaponization) asıl noktadır. Paketin kendisi kötü niyetli olsa bile, eğer kurulum sırasında hiçbir kod çalıştırılmasaydı zarar çok sınırlı kalırdı (sadece "import edildiğinde" çalışırdı). Ama modern paket yöneticileri, kurulum **anında** keyfi kod çalıştırmaya izin veren lifecycle hook'ları sunar:

- **npm/Node.js:** `package.json` içindeki `scripts.preinstall`, `scripts.install`, `scripts.postinstall` alanları, `npm install` çalıştığı anda otomatik tetiklenir (kullanıcı ekstra bir onay vermeden).
- **Python:** Klasik `setup.py` tabanlı dağıtımlarda, `setup()` çağrısından önceki herhangi bir Python kodu paket kurulumu sırasında çalışır. Modern `pyproject.toml`/wheel tabanlı dağıtım bu riski bir miktar azaltır çünkü wheel'ler genelde önceden derlenmiş, script çalıştırmayan bir formattır — ama `sdist` (source distribution) hâlâ yaygın ve `setup.py` çalıştırma riski taşır.
- **RubyGems:** Gemspec'lerde native extension derleme adımları (`extconf.rb`) keyfi Ruby/C kodu çalıştırabilir.
- **crates.io (Rust):** `build.rs` dosyaları, `cargo build` sırasında derleme öncesi keyfi Rust kodu çalıştırır.
- **Composer (PHP):** `composer.json` içindeki `scripts` alanı, belirli olaylarda (`post-install-cmd` gibi) komut çalıştırabilir.

### Kök Neden

Bu mekanizmaların hepsi **meşru bir mühendislik ihtiyacına** cevap olarak doğdu: native/derlenmiş bileşenler (C uzantıları, platforma özgü binary'ler) kurulum anında derlenmek ya da indirilmek zorunda. Ama "kurulum = ihtiyaç duyulan derleme adımlarını çalıştır" ile "kurulum = paket yazarının istediği HERHANGİ bir kodu çalıştır" arasında hiçbir teknik ayrım yoktur. Sistem, niyeti ayırt edemez; sadece "bu script tanımlanmışsa çalıştır" der. Bu, **en az yetki (least privilege) ilkesinin ihlalidir**: kurulum işlemi, sadece dosya kopyalama yetkisine ihtiyaç duyarken, tam kod çalıştırma yetkisi almaktadır.

Ayrıca kritik bir detay: bu script'ler **geliştiricinin kendi kullanıcı hesabı yetkisiyle**, yani genelde tam sisteme erişimi olan bir hesapla çalışır (root olmasa bile SSH anahtarlarına, tarayıcı çerezlerine, ortam değişkenlerindeki secret'lara erişebilen bir hesap). CI/CD ortamında ise bu genelde çok daha yüksek yetkili bir servis hesabıdır.

### Saldırganın Bakış Açısından Neden Cazip

- **Sessiz ve otomatik:** Kullanıcı `npm install` dediği anda, hiçbir ek onay istemeden script çalışır. Kullanıcı genelde paketin içindeki dosyaları hiç okumaz.
- **Kısa ömürlü ve iz bırakmayan:** Script genelde ihtiyaç duyduğu bilgiyi (ortam değişkenleri, SSH anahtarları, `.npmrc`/`.pypirc` içindeki token'lar, bulut kimlik bilgileri) topladıktan sonra dış bir sunucuya gönderir ve sessizce kaybolur; paket "işlevsiz" görünebilir çünkü asıl amacı zaten çalışma anında veri sızdırmaktı.
- **Tespit maliyeti yüksek:** Statik kod incelemesi (paketin kaynak kodunu okumak) genelde yapılmaz çünkü transitive dependency sayısı çok yüksektir; kimse yüzlerce paketin `postinstall` script'ini elle okumaz.

### Tespit ve Savunma

- **Lifecycle script'lerini varsayılan olarak kapatın:** Birçok paket yöneticisi bunu artık destekliyor veya destekleyen araçlarla sarmalanabiliyor (örneğin `npm install --ignore-scripts` veya proje genelinde `.npmrc` içinde `ignore-scripts=true`). Bu, native derleme gerektiren az sayıdaki paket için manuel istisna yönetimi gerektirir ama saldırı yüzeyini radikal biçimde daraltır.
- **Sandbox'lı/izole kurulum ortamları:** CI/CD kurulum adımlarını, ağ erişimi kısıtlı (egress filtreleme), sadece gerekli dosya sistemi izinlerine sahip konteynerler içinde çalıştırmak, script çalışsa bile veri sızdırma veya kalıcılık kurma kapasitesini sınırlar.
- **Davranışsal izleme (runtime monitoring):** Kurulum sürecinde beklenmeyen dış ağ bağlantıları, ortam değişkeni okuma girişimleri gibi davranışları tespit eden araçlar (Socket.dev gibi bazı SCA araçları statik + davranışsal analiz birleştirir).
- **Secrets'ı build ortamından izole edin:** CI/CD'de, bağımlılık kurulum adımının (dependency install stage) prensipte imzalama anahtarlarına veya üretim credential'larına erişmesine gerek yoktur; pipeline'ı, secret'ların sadece gerçekten ihtiyaç duyulan sonraki aşamalarda enjekte edildiği şekilde bölümlendirin (stage separation).
- **Kilitli, hash doğrulamalı, mümkünse "vendored" (bağımlılıkları depoya gömme) yaklaşımlar** kritik projelerde ekstra güvenlik katmanı sağlar, çünkü her güncelleme elle/gözden geçirilerek içeri alınır.

## Yaygın Hatalar ve Yanlış Güvenlik Algıları

- **"Popüler paket güvenlidir" varsayımı:** Yüksek indirme sayısı, geçmişte temiz olduğu anlamına gelir; gelecekte bir **hesap ele geçirme (account takeover)** veya **kötü niyetli maintainer devri** yaşanmayacağının garantisi değildir. Popüler bir paketin bakımcısı hesabının çalınıp zararlı bir sürüm yayınlanması (yaygın bir gerçek saldırı deseni), typosquatting'den bile daha tehlikelidir çünkü mevcut, güvenilen bir isim üzerinden gelir.
- **"Sadece `dependencies` önemli, `devDependencies` önemsiz" yanılgısı:** Geliştirme bağımlılıkları da CI/CD ortamında ve geliştirici makinesinde çalışır; aynı riskleri taşır.
- **Lockfile'ı görmezden gelmek veya `.gitignore`'a eklemek:** Bu, sürüm sabitlemesinin tüm faydasını ortadan kaldırır ve her kurulumu "en yeni sürümü güven" riskine açar.
- **`--extra-index-url` ile birden fazla registry tanımlayıp hangisinin öncelikli olduğunu doğrulamamak:** Yukarıda anlatıldığı gibi bu, dependency confusion'a doğrudan davetiye çıkarır.
- **Sadece ilk seviye bağımlılıkları denetleyip transitive (dolaylı) bağımlılıkları hiç incelememek:** Gerçek saldırıların büyük kısmı, doğrudan eklemediğiniz ama bir bağımlılığınızın bağımlılığı olan paketler üzerinden gelir.
- **SCA/tarama araçlarını sadece "CVE var mı" için kullanmak, davranışsal/isim-benzerlik sinyallerine bakmamak:** Typosquatting ve dependency confusion genelde bilinen bir CVE numarasıyla gelmez; bu saldırılar "yeni yayınlanmış, az indirilen, şüpheli isimli paket" gibi davranışsal/ısı-haritası sinyalleriyle yakalanır.
- **"Bir kere denetledik, yeterli" düşüncesi:** Bağımlılık ağacı sürekli değişir; her yeni sürüm, yeni bir lifecycle script veya yeni bir transitive bağımlılık getirebilir. Sürekli/otomatik denetim (continuous monitoring), tek seferlik denetimden çok daha değerlidir.

## Sonuç: Savunmanın Katmanlı Mimarisi

Bu saldırı ailesine karşı tek bir "gümüş kurşun" yoktur; etkili savunma **katmanlı** olmalıdır:

1. **Önleme (prevention):** Namespace rezervasyonu, scoped paketler, doğru registry önceliklendirmesi, `ignore-scripts`.
2. **Tespit (detection):** İsim benzerliği taraması, SCA araçları, davranışsal izleme, sürekli bağımlılık denetimi.
3. **Sınırlama (containment):** Sandbox'lı kurulum ortamları, egress filtreleme, secrets izolasyonu, en az yetki ilkesi.
4. **Doğrulama (verification):** Lockfile + bütünlük hash'i zorunluluğu, code review disiplini, iç proxy/ayna registry.

Dilden bağımsız olarak düşünmenin pratik faydası şudur: bu dört katmanı bir kere, kavramsal düzeyde doğru kurarsanız, yarın ekibiniz yeni bir dile (örneğin Go modülleri veya Deno) geçtiğinde aynı mimariyi—registry proxy'si, script kısıtlaması, lockfile zorunluluğu, isim rezervasyonu—yeniden uygulayabilirsiniz. Paket yöneticisi ekosistemleri sözdizimi düzeyinde farklı görünse de, güven modelindeki kırılganlıklar şaşırtıcı derecede evrenseldir.
