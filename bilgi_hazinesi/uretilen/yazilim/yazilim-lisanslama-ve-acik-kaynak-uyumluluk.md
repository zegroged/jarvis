# Yazılım Lisanslama ve Açık Kaynak Uyumluluk (License Compliance, Copyleft Riskleri)

## Giriş: Neden Ayrı Bir Disiplin?

Modern bir kurumsal uygulama, yazdığınız kodun çok ötesinde bir varlıktır. Tipik bir projede kod tabanının yüzde 70 ila 90'ı doğrudan sizin yazmadığınız, üçüncü taraf **open source** bileşenlerden oluşur: `npm`, `PyPI`, `Maven Central`, `crates.io` gibi kayıt defterlerinden çekilen kütüphaneler, bunların bağımlılıkları (transitive dependencies) ve onların bağımlılıkları. Bu bileşenlerin her biri bir **lisans** ile gelir ve o lisans, kodu nasıl kullanabileceğinizi, dağıtabileceğinizi ve kendi kodunuza karışmasının hukuki sonuçlarını belirleyen bağlayıcı bir sözleşmedir.

**License compliance** (lisans uyumluluğu), bu bağımlılık ağacındaki tüm lisansların yükümlülüklerini tespit etmek, çelişkileri saptamak ve şirketin bu yükümlülükleri yerine getirmesini sağlamak disiplinidir. Bu, **yazılım tedarik zinciri güvenliği** (supply chain security) ile aynı envanteri (SBOM) paylaşır ama farklı bir soru sorar: güvenlik "bu bileşen zararlı mı, açığı var mı?" derken; uyumluluk "bu bileşeni bu şekilde kullanma hakkım var mı, hangi yükümlülükleri doğuruyor?" diye sorar.

Bu ayrımı anlamak kritiktir çünkü lisans ihlali bir **hukuki risk**tir, bir teknik açık değil. Sonuçları; dava, para cezası, ürünün pazardan çekilmesi, bir satın alma (M&A) sürecinin çökmesi veya en ağırında **tüm tescilli (proprietary) kaynak kodunuzu açıklamak zorunda kalmak** şeklinde gerçekleşebilir.

## Temel Kavramlar ve Lisans Aileleri

Lisansları anlamak için tek bir eksende düşünün: lisans, kodu aldıktan sonra size **ne yapma yükümlülüğü** yükler? Bu eksende üç geniş aile vardır.

### Permissive (İzin Verici) Lisanslar

`MIT`, `BSD` (2-clause/3-clause), `Apache-2.0`, `ISC` bu ailededir. Temel felsefeleri: "Kodu al, istediğin gibi kullan, tek şartım telif ve lisans metnini koru." Yükümlülükler minimaldir:

- **Attribution** (atıf): Orijinal telif bildirimini ve lisans metnini dağıtımınıza dahil etmelisiniz. Çoğu şirketin ihlal ettiği en yaygın yükümlülük tam da budur; kodu kullanmak serbesttir ama `LICENSE` dosyasını dağıtıma koymayı unuturlar.
- **Apache-2.0'ın ek özelliği**: Açık bir **patent grant** (patent lisansı) içerir. Katkıda bulunanlar, katkılarıyla ilgili patentlerini kullanıcılara ücretsiz lisanslar. Bu, `MIT`'te olmayan hukuki bir koruma sağlar ve Apache-2.0'ı kurumsal ortamda tercih edilir kılar.

Permissive lisanslar tescilli yazılıma karıştırılabilir; kendi kaynağınızı açmanız gerekmez.

### Copyleft (Karşılık Bekleyen) Lisanslar

Bu ailenin felsefesi köklü biçimde farklıdır: "Bu özgürlüğü sana veriyorum, ama sen de türettiğin eseri aynı özgürlükle paylaşmak zorundasın." Buna **reciprocity** (karşılıklılık) denir. En bilinen üye `GPL` (GNU General Public License) ailesidir. Copyleft kendi içinde iki alt türe ayrılır ve bu ayrım tüm compliance riskinin merkezindedir.

**Strong copyleft (güçlü copyleft):** `GPL-2.0`, `GPL-3.0`, `AGPL-3.0`. Bu lisansların kilit kavramı **derivative work** (türev eser) ve **linking** (bağlama) yorumudur. GPL lisanslı bir kütüphaneyi kendi programınıza **link** ederseniz (statik veya çoğu yoruma göre dinamik olarak), oluşan birleşik eserin tamamı bir türev eser sayılır. Sonuç: dağıttığınızda, **kendi kodunuzu da GPL altında ve kaynak koduyla birlikte** dağıtmak zorundasınız. Bu yüzden GPL, tescilli ürünler için "bulaşıcı" (viral) olarak nitelenir. Terim popülerdir ama teknik olarak yanıltıcıdır; GPL bir virüs gibi kendiliğinden yayılmaz, sadece dağıtım anında yükümlülük doğurur.

**Weak copyleft (zayıf copyleft):** `LGPL`, `MPL-2.0`, `EPL`. Bu lisanslar copyleft yükümlülüğünü **dosya** veya **kütüphane** sınırında tutar. `LGPL` (Lesser GPL) tam da bu amaçla tasarlanmıştır: LGPL bir kütüphaneyi tescilli kodunuza link edebilirsiniz; sadece **kütüphanenin kendisinde** yaptığınız değişiklikleri paylaşmanız gerekir, kendi kodunuzu değil. `MPL-2.0` (Mozilla Public License) benzer şekilde **dosya bazlıdır**: sadece değiştirdiğiniz MPL dosyalarını açık tutmanız yeterlidir.

### Proprietary, Public Domain ve "Source-available"

- **Public domain / CC0 / Unlicense:** Telif hakkından tamamen feragat. Neredeyse hiç yükümlülük yok, ama bazı hukuk sistemleri telif feragatini tanımadığı için hukuki belirsizlik taşır.
- **Source-available (kaynağı görünür ama açık kaynak değil):** `BSL` (Business Source License), `SSPL` (Server Side Public License), `Elastic License` gibi lisanslar. Kaynağı okuyabilirsiniz ama OSI tanımına göre "açık kaynak" değildirler; genellikle ticari rakip olarak kullanmanızı yasaklarlar. MongoDB'nin SSPL'e, HashiCorp'un BSL'e geçişi bu kategorinin son yıllarda büyümesine örnektir. Bunları "açık kaynak" sanıp kurumsal SaaS ürününüzde kullanmak ciddi bir uyumluluk hatasıdır.

## Kök Neden: Copyleft Riski Nereden Doğar?

Riskin çalışma mantığını anlamak için üç faktörün kesişimine bakmak gerekir: **lisans türü + dağıtım biçimi + linking modeli.** Bu üçlü, yükümlülüğün doğup doğmadığını belirler.

### 1. Dağıtım (Distribution) Tetikleyicidir

Klasik GPL yükümlülüğü **yazılımı dağıttığınızda** doğar. Kod tabanınızda GPL bir kütüphane bulunması tek başına ihlal değildir; onu içeren bir binary'yi bir dış tarafa **teslim ettiğinizde** kaynak kodu paylaşma yükümlülüğü aktifleşir. Bu yüzden "içeride kullanıyoruz, dağıtmıyoruz" argümanı klasik GPL için bir kaçış yolu olarak görülür.

### 2. AGPL ve "Network Use" Boşluğunu Kapatma

Yukarıdaki mantık SaaS çağında bir "boşluk" (loophole) yaratmıştı: bir şirket GPL kodunu bir sunucuda çalıştırıp hizmeti ağ üzerinden sunuyorsa, kullanıcıya bir binary "dağıtmadığı" için kaynağı açmak zorunda kalmıyordu. **`AGPL-3.0`** tam bu boşluğu kapatmak için tasarlandı: AGPL, yazılımı **bir ağ üzerinden hizmet olarak sunmayı da** kaynak paylaşımını tetikleyen bir olay sayar. Yani AGPL bir bileşeni backend'inizde kullanıp SaaS olarak sunuyorsanız, kullanıcılarınıza o hizmetin **tüm kaynak kodunu** sunmak zorunda kalabilirsiniz. Bu, AGPL'i kurumsal SaaS için en yüksek riskli lisanslardan biri yapar ve birçok şirketin **kesin yasak (deny-list)** listesine koyduğu lisanstır.

### 3. Linking Yorumu Belirsizdir

Statik linking (kod binary'ye gömülür) neredeyse evrensel olarak türev eser sayılır. Dinamik linking ve özellikle **ayrı süreçler arası iletişim** (IPC, REST API çağrısı, ayrı process'ler) daha tartışmalıdır. Bir GPL programını bir subprocess olarak çağırmak (örneğin komut satırından `ImageMagick` çalıştırmak) çoğu yoruma göre türev eser oluşturmaz. Bu ayrımlar hukukidir, teknik değildir; nihai karar için hukuk müşavirliği gerekir, mühendisin sezgisi değil.

## License Compliance Otomasyonu Nasıl Çalışır?

Manuel lisans incelemesi, binlerce transitive bağımlılık karşısında imkânsızdır. Bu yüzden compliance otomasyonu **SCA** (Software Composition Analysis) araçlarıyla yapılır. Çalışma mantığı katmanlıdır.

### Adım 1: Envanter Çıkarma (SBOM Üretimi)

Araç, projenizin bağımlılık ağacını çözümler. Bunu iki yöntemle yapar:

- **Manifest tabanlı:** `package-lock.json`, `poetry.lock`, `go.sum`, `Cargo.lock`, `pom.xml` gibi dosyaları parse ederek tam bağımlılık listesini ve sürümlerini çıkarır. Lock dosyaları burada kritiktir çünkü transitive bağımlılıkların kesin sürümlerini içerir.
- **Binary/dosya tabanlı:** Manifest yoksa, derlenmiş artefaktları tarar; dosya hash'lerini bilinen bileşen veritabanlarıyla eşleştirir. Bu, "vendored" (kaynak ağacına kopyalanmış) kodu ve manifestte görünmeyen bileşenleri yakalar.

Çıktı, standart bir **SBOM** formatında verilir: **SPDX** veya **CycloneDX**. Bu SBOM, hem güvenlik hem de lisans analizi için ortak veri kaynağıdır.

### Adım 2: Lisans Tespiti (License Detection)

Her bileşen için lisans belirlenir. Bu, göründüğünden zordur:

- **Metadata'dan okuma:** Paket yöneticisinin bildirdiği lisans alanı (`package.json`'daki `license`) okunur. Ama bu alan yanlış, eksik veya boş olabilir.
- **Dosya tarama:** `LICENSE`, `COPYING`, `NOTICE` dosyaları ve kaynak dosyalardaki lisans başlıkları taranır.
- **Metin eşleştirme:** Bulunan lisans metni, bilinen lisanslarla karşılaştırılır. Burada **SPDX License List** ve onun standart tanımlayıcıları (`MIT`, `Apache-2.0`, `GPL-3.0-only`) kullanılır. Modern araçlar metin benzerliği için istatistiksel skorlama uygular çünkü lisans metinleri sıklıkla küçük değişikliklerle gelir. Bu alanda **ScanCode Toolkit** gibi araçlar referans kabul edilir.

Tespitteki en zor durumlar: birden fazla lisanslı (dual-licensed) bileşenler, `SPDX license expression`'lar (`(MIT OR Apache-2.0)`), ve hiç lisans beyanı olmayan kod (ki bu "tüm hakları saklı" varsayılarak en riskli durumdur, çünkü hiç lisans = kullanma izni yok).

### Adım 3: Policy Değerlendirmesi (Policy Enforcement)

Otomasyonun kalbi burasıdır. Şirket, bir **lisans politikası** tanımlar. Tipik olarak lisanslar renk kodlarıyla sınıflandırılır:

- **Yeşil (izinli):** MIT, Apache-2.0, BSD, ISC gibi permissive lisanslar. Otomatik onay.
- **Sarı (incelemeye tabi):** LGPL, MPL, EPL gibi weak copyleft. Kullanım biçimine bağlı; hukuki/mimari inceleme gerekir.
- **Kırmızı (yasak):** GPL, AGPL, SSPL, lisanssız kod. Genellikle kurumsal tescilli üründe otomatik ret.

SCA aracı, bulunan her bileşenin lisansını bu politikaya karşı denetler ve ihlalleri raporlar.

### Adım 4: CI/CD Entegrasyonu (Shift-Left)

Olgun bir uyumluluk sürecinde bu denetim **CI/CD pipeline**'ına gömülür. Bir geliştirici kırmızı-listeli bir bağımlılık eklerse, **pull request** aşamasında build **kırılır** (fail). Bu "shift-left" yaklaşımı, sorunu üretime çıkmadan, hatta kod merge edilmeden yakalar; sorunlu bir GPL bağımlılığı ürünle birlikte müşteriye gittikten sonra temizlemek katbekat pahalıdır. `FOSSA`, `Snyk`, `Black Duck`, `ScanCode`, `OSS Review Toolkit (ORT)` bu alanda yaygın araçlardır.

### Adım 5: Attribution ve NOTICE Üretimi

Uyumluluk sadece "yasakları engellemek" değildir; **pozitif yükümlülükleri yerine getirmek**tir. Araçlar, kullanılan tüm permissive lisansların telif ve lisans metinlerini toplayıp otomatik bir **attribution / NOTICE dosyası** üretir. Bu dosya ürünle birlikte dağıtılır (mobil uygulamalardaki "Açık Kaynak Lisansları" ekranı bunun tipik tezahürüdür). Bu adımı atlamak, en yaygın ve en kolay önlenebilir ihlal türüdür.

## Örnek Senaryo: Bir SaaS Ürününde Riskin İzi

Bir ekip, log analizi için popüler bir kütüphane arar ve bir GitHub reposu bulur. Kod mükemmel çalışır, hızlıca entegre edilir. Aylar sonra hukuk ekibi bir uyumluluk taraması başlatır:

1. **SBOM üretilir**, kütüphane ve 40 transitive bağımlılığı listelenir.
2. **Lisans tespiti**, ana kütüphanenin `AGPL-3.0` olduğunu ortaya çıkarır.
3. **Policy motoru** bunu kırmızı işaretler; çünkü ürün internete açık bir SaaS'tır.
4. **Sonuç:** AGPL, ağ üzerinden sunulan hizmet için de kaynak paylaşımı tetikler. Şirket ya tüm tescilli backend kodunu açık kaynak yapacak, ya bir **ticari lisans** için yazara ödeme yapacak, ya da kütüphaneyi tümüyle söküp permissive bir alternatifle değiştirecektir. Üçüncü seçenek genellikle tek makul yoldur ve aylar önce bir CI kontrolüyle önlenebilecek olan bu iş, artık pahalı bir yeniden mühendislik projesine dönüşmüştür.

Bu senaryo neden **shift-left** ve otomasyonun kritik olduğunu gösterir: risk, kodun ilk eklendiği anda tespit edilebilseydi maliyeti sıfıra yakındı.

## Doğru Kullanım ve Yaygın Tuzaklar

### Doğru Uygulamalar

- **Lock dosyalarını tara, sadece manifesti değil.** Manifest sürüm aralıkları içerir (`^1.2.0`); gerçek çözümlenmiş sürümler lock dosyasındadır. Transitive bağımlılıkların çoğu ancak lock dosyasında görünür.
- **Transitive bağımlılıkları asla göz ardı etme.** En büyük copyleft riski, sizin doğrudan eklediğiniz permissive kütüphanenin, derinlerde bir GPL bağımlılığı çekmesidir. Risk genellikle ağacın dibinde saklıdır.
- **Politikayı kullanım bağlamına göre kur.** Bir CLI aracı ile bir SaaS backend'i ile bir dağıtılan mobil uygulama farklı risk profillerine sahiptir. AGPL bir SaaS için felakettir ama internal, dağıtılmayan bir batch job için yorumlanabilir.
- **NOTICE üretimini otomatikleştir.** Attribution yükümlülüğünü manuel takip etmeyin.
- **M&A ve release öncesi tam tarama yapın.** Bir şirketi satın alan taraf mutlaka bir "open source due diligence" yapar; lisans temizliği bir varlık değeridir.

### Yaygın Hatalar

- **"Açık kaynak = bedava = istediğim gibi kullanırım" yanılgısı.** Açık kaynak, telif haklarından feragat değildir; koşullu bir sözleşmedir. Koşulları ihlal ederseniz lisans hakkınız düşer ve sıradan bir telif ihlali durumuna geri dönersiniz.
- **GPL'i "içeride kullanıyoruz, sorun yok" diye geçiştirmek — AGPL'i unutarak.** Klasik GPL için dağıtım-tetikleyici mantığı bir dereceye kadar geçerlidir; ama AGPL ağ kullanımını da tetikleyici saydığı için bu argüman AGPL'de tamamen çöker.
- **Source-available lisansları açık kaynak sanmak.** SSPL, BSL, Elastic License kaynağı görünür yapar ama ticari kısıtlar getirir. Bunları rakip bir ürün olarak kullanmak lisans ihlalidir.
- **Lisanssız kodu "izinli" saymak.** Lisans beyanı olmayan kod, varsayılan olarak **tüm hakları saklı**dır; onu kullanma hakkınız yoktur. Boş lisans, en izin verici değil en kısıtlayıcı durumdur.
- **Lisans değişikliklerini (relicensing) takip etmemek.** Bir bağımlılık bir major sürümde lisansını MIT'ten BSL'e çevirebilir (son yıllarda sıkça oldu). Sürüm yükseltirken lisansın da değişmediğini doğrulamalısınız. Bu yüzden compliance bir "bir kere yap-bitir" işi değil, sürekli bir süreçtir.
- **SBOM'u güvenlik ve lisans için ayrı ayrı üretmek.** Aynı envanter her ikisini de besler; tek bir SBOM üretip iki farklı politika motoruna vermek hem verimli hem tutarlıdır.
- **License detection çıktısına körü körüne güvenmek.** Otomatik tarayıcılar metin benzerliğine dayanır ve değiştirilmiş veya çift lisanslı bileşenlerde yanılabilir. Kırmızı-listeli bir bulgu, aksiyon almadan önce insan doğrulaması gerektirir; ama false-negative (kaçırılan risk) daha tehlikelidir, o yüzden şüpheli/tespit edilemeyen lisanslar da "riskli" kovasına konmalıdır.

## Güvenlikle İlişki ve Ayrım

Lisans uyumluluğu ve tedarik zinciri güvenliği aynı **SBOM** altyapısını paylaşır ve genellikle aynı SCA araçlarıyla birlikte çalışır; ama yönetsel olarak ayrılmalıdırlar:

- **Güvenlik** sorar: Bu bileşende bilinen bir zafiyet (CVE) var mı? Bakımı yapılıyor mu? Zararlı bir paket mi (typosquatting, dependency confusion)?
- **Uyumluluk** sorar: Bu lisansın yükümlülüklerini yerine getiriyor muyum? Bu kullanım biçimi hukuki risk doğuruyor mu?

Bir bileşen güvenlik açısından tertemiz olup lisans açısından felaket olabilir (örneğin bakımlı, açığı olmayan ama AGPL bir kütüphane). Tersi de doğrudur. Bu yüzden iki disiplin ayrı politika motorları ve ayrı sorumlu ekipler (güvenlik ekibi vs. hukuk/uyumluluk ekibi) gerektirir, ortak veri kaynağını paylaşsalar da.

## Özet

License compliance, tescilli yazılımın açık kaynak tsunamisi içinde hukuki olarak savunulabilir kalmasını sağlayan disiplindir. Merkezi kavram **copyleft**tir: permissive lisanslar yalnızca atıf ister, weak copyleft (LGPL, MPL) değişiklikleri dosya/kütüphane sınırında paylaşmayı ister, strong copyleft (GPL) türev eserin tamamını açmayı, AGPL ise bunu ağ üzerinden sunulan hizmetlere de genişletmeyi dayatır. Risk; lisans türü, dağıtım biçimi ve linking modelinin kesişiminde doğar. Savunma mekanizması otomasyondur: SBOM üret, lisansları tespit et, bir renk-kodlu politikaya karşı denetle, bu denetimi CI/CD'ye göm ve NOTICE dosyalarını otomatik üret. En büyük tuzaklar transitive bağımlılıklarda saklı copyleft, source-available lisansları açık kaynak sanmak, lisanssız kodu izinli saymak ve lisans değişikliklerini takip etmemektir. Uyumluluk bir kerelik denetim değil, sürekli bir süreçtir.
