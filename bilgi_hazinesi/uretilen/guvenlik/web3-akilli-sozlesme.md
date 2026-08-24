# Web3 ve Akıllı Sözleşme Güvenliği: Derin Bir Referans

Akıllı sözleşme güvenliği, geleneksel yazılım güvenliğinden temelde farklı bir disipline dönüşür; çünkü burada hata bir "yamayla" düzeltilebilecek bir kusur değildir. Bir smart contract, EVM (Ethereum Virtual Machine) gibi bir sanal makineye deploy edildikten sonra çoğu durumda **değiştirilemez (immutable)** olur ve genellikle doğrudan para taşır. Bu iki özelliğin birleşimi güvenlik denklemini kökten değiştirir: kodunuz aynı anda hem herkese açık (public), hem değiştirilemez, hem de milyonlarca dolar tutan bir kasadır. Saldırgan kaynak kodu okur, mantığı tersine çevirir ve tek bir işlemle (transaction) fonları boşaltabilir. Bu makale, bu alanın en kritik zafiyet sınıflarını kök nedenleriyle, istismar mantığıyla ve savunma yöntemleriyle birlikte ele alıyor.

## Reentrancy (Yeniden Giriş) Zafiyeti

### Tanım ve kök neden

Reentrancy, bir sözleşmenin harici bir adrese kontrol akışını (control flow) devretmesi ve bu harici adresin, ilk çağrı henüz tamamlanmadan aynı sözleşmeye geri çağrı yapabilmesinden doğar. Kök neden EVM'in çalışma mantığında yatar: bir sözleşme başka bir adrese Ether gönderdiğinde (`call`, `send`, `transfer`) veya harici bir sözleşme fonksiyonunu çağırdığında, kontrol o harici adresteki koda geçer. Eğer o adres bir sözleşmeyse, onun `receive()` veya `fallback()` fonksiyonu tetiklenir. İşte bu an, saldırganın kontrolü ele geçirdiği andır.

Asıl sorun, çağrı yapan sözleşmenin **iç durumunu (state) güncellemeden önce** dışarıya kontrol vermesidir. Yani sözleşme "önce parayı gönder, sonra bakiyeyi sıfırla" sırasıyla çalışıyorsa, saldırgan "para gönderildi ama bakiye henüz sıfırlanmadı" penceresinde tekrar çekim fonksiyonunu çağırarak aynı bakiyeyi defalarca çekebilir.

### Somut örnek

Klasik zafiyetli çekim fonksiyonu şu mantıktadır:

```solidity
function withdraw() public {
    uint256 amount = balances[msg.sender];
    // ZAFİYET: harici çağrı, state güncellemesinden ÖNCE
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success);
    balances[msg.sender] = 0; // çok geç
}
```

Saldırganın sözleşmesi şu şekilde davranır: `withdraw()` çağrılır, `call` ile Ether saldırgana gönderilir, saldırganın `receive()` fonksiyonu tetiklenir, o fonksiyon içinden **tekrar** `withdraw()` çağrılır. `balances[msg.sender]` henüz sıfırlanmadığı için ikinci çağrı da aynı miktarı gönderir. Bu döngü, sözleşmenin bakiyesi tükenene veya gas bitene kadar sürer.

### İstismar mantığı ve savunma

İstismar tarafında saldırgan, `receive()`/`fallback()` içine özyinelemeli (recursive) bir çağrı yerleştirir. Modern varyantlarda saldırı sadece aynı fonksiyona değil, **farklı fonksiyonlar arası (cross-function reentrancy)** ve hatta **farklı sözleşmeler arası (cross-contract)** biçimde de gerçekleşebilir. Örneğin `withdraw()` içinden geri girişte `transfer()` fonksiyonu çağrılarak tutarsız state okunabilir. Son yıllarda ERC-777 ve benzeri "hook" mekanizmalı token standartları bu yüzeyi genişletti; çünkü token transferi sırasında alıcıya otomatik callback verilir ve bu callback beklenmedik reentrancy noktaları yaratır (read-only reentrancy dahil).

Savunma iki katmanlıdır:

**1. Checks-Effects-Interactions (CEI) deseni.** Bu, en temel ve en güçlü savunmadır. Fonksiyon önce kontrolleri (checks) yapar, sonra iç durumu (effects) günceller, en son harici etkileşime (interactions) girer. Yukarıdaki örnekte `balances[msg.sender] = 0;` satırının `call`'dan **önce** gelmesi, ikinci girişte bakiyeyi zaten sıfır göstererek saldırıyı etkisiz kılar.

**2. Reentrancy guard (mutex).** Bir kilit değişkeni ile fonksiyonun kendisine yeniden girilmesi engellenir. OpenZeppelin'in `ReentrancyGuard` sözleşmesindeki `nonReentrant` modifier'ı bu deseni uygular: fonksiyona girişte bir bayrak set edilir, çıkışta temizlenir; bayrak set iken yapılan yeni girişler `revert` eder. Guard, özellikle CEI'yi tam uygulamanın zor olduğu karmaşık fonksiyonlarda ek güvenlik sağlar. Ancak guard'ın tek başına yeterli olduğunu varsaymak hatadır; cross-contract senaryolarda farklı sözleşmelerdeki guard'lar birbirini görmez.

Ek olarak, Ether göndermek için `transfer`/`send` gibi gas'ı 2300'e sabitleyen yöntemlerin bir zamanlar reentrancy'ye karşı doğal koruma sağladığı düşünülürdü. Ancak bu yaklaşım artık **önerilmez**, çünkü EVM'in gas maliyetleri (opcode fiyatları) zaman içinde değişebilir ve bu sabit gas varsayımı gelecekte işlemlerin kırılmasına yol açar. Doğru yaklaşım `call` kullanıp CEI ve guard ile korunmaktır.

## Integer (Tamsayı) Zafiyetleri: Overflow ve Underflow

### Tanım ve kök neden

Tamsayı taşması, bir aritmetik işlemin sonucunun değişkenin tutabileceği maksimum veya minimum değeri aşmasıyla oluşur. EVM'de tamsayılar sabit bit genişliğine sahiptir (örneğin `uint256`, 0 ile 2^256−1 arası değer tutar). Kök neden, düşük seviyeli aritmetiğin "modüler" davranmasıdır: `uint8` bir değişkende 255'e 1 eklerseniz sonuç 0'a döner (overflow); 0'dan 1 çıkarırsanız sonuç maksimuma sıçrar (underflow). Bu davranış donanım seviyesinde normaldir ama finansal mantıkta felakettir.

### Somut örnek ve istismar

Bir token sözleşmesinde bakiye kontrolünün eksik olduğu bir transfer düşünün:

```solidity
// Solidity 0.8 ÖNCESİ mantık — checked aritmetik yoktu
function transfer(address to, uint256 value) public {
    balances[msg.sender] -= value; // underflow riski
    balances[to] += value;
}
```

Eğer `msg.sender`'ın bakiyesi `value`'dan küçükse, `balances[msg.sender] -= value` işlemi underflow yaparak bakiyeyi neredeyse `2^256`'ya çıkarır. Saldırgan böylece hiç sahip olmadığı devasa bir bakiye elde eder. Benzer şekilde, arz (supply) hesaplamalarında overflow, sınırsız token basımına (mint) yol açabilir.

### Savunma

Burada kritik bir dönüm noktası vardır: **Solidity 0.8.0 sürümünden itibaren** aritmetik işlemler varsayılan olarak "checked" hale geldi; yani overflow/underflow durumunda işlem otomatik olarak `revert` eder. Bu, integer zafiyetlerinin büyük çoğunluğunu dil seviyesinde ortadan kaldırdı. 0.8 öncesi için endüstri standardı **SafeMath** kütüphanesiydi (OpenZeppelin), her aritmetik işlemi taşma kontrolüyle sarmalar.

Ancak "0.8 kullanıyorum, güvendeyim" varsayımı fazla rahat bir tutumdur. Şu durumlar hâlâ risklidir:

- **`unchecked { }` blokları.** Gas tasarrufu için geliştiriciler bilinçli olarak checked kontrolü kapatır. Bu blok içinde overflow tekrar mümkün olur ve buradaki mantık dikkatle doğrulanmalıdır.
- **Tip küçültme (downcasting).** `uint256`'dan `uint128`'e dönüştürme, değer sığmıyorsa sessizce kesme (truncation) yapar ve bunu Solidity **revert etmez**. `SafeCast` gibi kütüphaneler bu tehlikeye karşı kullanılır.
- **Düşük seviye assembly (Yul).** `assembly` blokları içindeki aritmetik hiçbir checked korumaya sahip değildir.
- **Çarpma/bölme sırası ve hassasiyet kaybı.** Overflow olmasa bile önce bölüp sonra çarpmak, tamsayı bölmesinin ondalıkları attığı için ciddi yuvarlama hatalarına (rounding) yol açar. Kural: önce çarp, sonra böl.

## Access Control (Erişim Kontrolü) Zafiyetleri

### Tanım ve kök neden

Erişim kontrolü, "hangi adresin hangi fonksiyonu çağırabileceğinin" doğru şekilde kısıtlanmasıdır. Zafiyet, kritik bir fonksiyonun korumasız bırakılması veya yetki kontrolünün yanlış yapılmasından doğar. Kök neden çoğunlukla insan hatasıdır: geliştirici bir `onlyOwner` modifier'ı eklemeyi unutur, ya da yetkilendirme mantığını hatalı kurar. Blockchain bağlamında bu ölümcüldür, çünkü tüm fonksiyonlar varsayılan olarak dışarıdan çağrılabilir ve saldırgan her fonksiyonu deneyebilir.

### Somut örnekler ve istismar

En yaygın senaryolar:

- **Korumasız kritik fonksiyon.** Bir `initialize()`, `setOwner()`, `mint()` veya `withdraw()` fonksiyonu yetki kontrolü olmadan `public` bırakılırsa, herhangi biri sahipliği devralabilir veya fonları çekebilir. Özellikle upgradeable (yükseltilebilir) proxy desenlerinde, implementation sözleşmesinin `initialize()` fonksiyonunun herkes tarafından çağrılabilir kalması ve saldırganın kendini owner yapması meşhur bir hata sınıfıdır. Bazı yüksek profilli olaylarda, initialize edilmemiş bir implementation sözleşmesinin ele geçirilip `selfdestruct` ile yok edilmesi tüm proxy'yi kullanılmaz hale getirmiştir.
- **`tx.origin` ile yetkilendirme.** Yetki kontrolünü `require(tx.origin == owner)` ile yapmak klasik bir hatadır. `tx.origin` işlemi başlatan ilk adrestir; araya giren bir kötü niyetli sözleşme, kurbanı kandırıp kendi üzerinden çağrı yaptırırsa `tx.origin` hâlâ kurbanı gösterir ve yetki kontrolü aşılır (phishing benzeri bir saldırı). Doğrusu her zaman `msg.sender` kullanmaktır.
- **Yanlış rol atamaları.** Rol tabanlı sistemlerde (RBAC) bir rolün admin'inin yanlış ayarlanması, yetkisiz rol yükseltmeye (privilege escalation) izin verebilir.

### Savunma

Savunmanın temeli **açık ve merkezi bir yetkilendirme modelidir.** OpenZeppelin'in `Ownable` (tek sahip) ve `AccessControl` (rol tabanlı) sözleşmeleri endüstri standardıdır. Her state değiştiren, para taşıyan veya yapılandırma değiştiren fonksiyon mutlaka bir yetki modifier'ı ile korunmalıdır. Ek pratikler:

- **En az yetki ilkesi (principle of least privilege).** Her rol yalnızca ihtiyaç duyduğu yetkiye sahip olmalı.
- **Multisig ve timelock.** Tek bir özel anahtarın (private key) tüm sistemi kontrol etmesi tek nokta hatasıdır. Kritik yetkiler bir multisig cüzdana verilmeli, tehlikeli işlemler bir zaman kilidi (timelock) arkasında gecikmeli çalışmalı; böylece topluluk kötü niyetli bir işlemi görüp tepki verebilir.
- **Sahiplik devrinde iki adımlı desen.** `Ownable2Step` gibi desenler, sahipliğin yanlışlıkla erişilemez bir adrese devredilmesini engeller: yeni sahibin devri açıkça kabul etmesi gerekir.
- **Proxy'lerde initializer koruması.** Upgradeable sözleşmelerde `initializer` modifier'ı ve `_disableInitializers()` çağrısı ile implementation'ın tekrar initialize edilmesi engellenmelidir.

## Oracle (Kâhin) Manipülasyonu

### Tanım ve kök neden

Oracle, blockchain dışındaki verileri (özellikle varlık fiyatlarını) zincire taşıyan mekanizmadır. DeFi protokolleri fiyat bilgisine bağımlıdır: teminat değeri, likidasyon eşiği, takas oranı hep fiyata dayanır. Oracle manipülasyonu, bu fiyat kaynağının saldırgan tarafından çarpıtılmasıyla protokolün yanlış fiyat üzerinden işlem yapmaya kandırılmasıdır.

Kök neden, birçok protokolün fiyatı **anlık olarak bir on-chain kaynaktan** (örneğin bir DEX likidite havuzunun o andaki rezerv oranından) okumasıdır. Bir AMM (Automated Market Market, otomatik piyasa yapıcı) havuzundaki `x * y = k` formülü gereği, havuza yapılan büyük bir takas anlık fiyatı ciddi şekilde kaydırır. Eğer protokol bu anlık spot fiyatı doğrudan güveniyorsa, saldırgan fiyatı geçici olarak manipüle edip protokolü sömürebilir.

### Somut örnek ve istismar: flash loan ile fiyat manipülasyonu

Klasik saldırı şablonu şöyledir. Saldırgan tek bir işlem içinde:

1. Bir **flash loan** (teminatsız, aynı işlem içinde geri ödenmesi gereken anlık kredi) ile devasa miktarda token ödünç alır.
2. Bu tokenları bir DEX havuzuna boşaltarak o havuzdaki fiyatı yapay olarak yukarı veya aşağı iter.
3. Fiyatını bu havuzdan okuyan kurban protokole gider. Örneğin manipüle edilmiş yüksek teminat fiyatı sayesinde olması gerekenden çok daha fazla borç alır, ya da manipüle edilmiş düşük fiyatla varlıkları ucuza satın alır.
4. Flash loan'ı geri öder, kâr saldırganda kalır.

Buradaki incelik, tüm bunların **tek bir atomik işlemde** olması ve saldırganın kendi sermayesini riske atmamasıdır. Flash loan, sermaye engelini ortadan kaldırdığı için oracle zafiyetlerini teorik riskten günlük gerçekliğe dönüştürmüştür.

### Savunma

Savunma stratejisi "anlık, manipüle edilebilir bir fiyat kaynağına asla doğrudan güvenme" ilkesine dayanır:

- **TWAP (Time-Weighted Average Price, zaman ağırlıklı ortalama fiyat).** Spot fiyat yerine belli bir zaman penceresindeki ortalama fiyatı kullanmak, tek bir işlemle yapılan manipülasyonu zorlaştırır; çünkü saldırganın fiyatı birden fazla blok boyunca bozuk tutması gerekir ki bu çok daha pahalı ve riskli olur. Uniswap benzeri protokollerin sunduğu TWAP oracle'ları bu amaçla kullanılır.
- **Merkeziyetsiz oracle ağları.** Chainlink gibi sağlayıcılar, fiyatı birçok bağımsız kaynaktan toplayıp toplulaştırarak (aggregation) tek bir havuzun manipülasyonuna karşı dayanıklı hale getirir. Bu tür oracle'lar genellikle sapkın (outlier) değerleri filtreler ve güncellik (staleness) kontrolü içerir.
- **Fiyatın makullüğünü doğrulama.** Okunan fiyatın belli sınırlar içinde olduğunu kontrol etmek, birden fazla oracle kaynağını karşılaştırmak (deviation check) ve fiyatın çok eski olmadığını (`updatedAt` zaman damgası) doğrulamak önemli katmanlardır.
- **Spot fiyatı hesaplama girdisi olarak kullanmaktan kaçınmak.** Özellikle likidite havuzu bakiyelerini (`balanceOf`) doğrudan fiyat türetmek için kullanmak tehlikelidir; bu değerler bağış (donation) veya flash loan ile kolayca şişirilebilir.

## Denetim (Audit): Süreç, Kapsam ve Sınırları

### Denetim neden gereklidir ve ne yapar

Bir güvenlik denetimi (audit), deploy öncesi kodun bağımsız uzmanlarca sistematik incelenmesidir. Amacı, yukarıdaki zafiyet sınıflarını ve iş mantığı (business logic) hatalarını canlıya çıkmadan yakalamaktır. Denetim önemlidir çünkü akıllı sözleşmelerin değiştirilemezliği "sonra düzeltiriz" seçeneğini ortadan kaldırır; hata canlıya çıktığında düzeltmenin yolu ya karmaşık bir upgrade ya da fonların kaybıdır.

### Denetim yöntemleri

Kaliteli bir denetim birden çok tekniği katmanlar:

- **Manuel kod incelemesi.** Deneyimli denetçilerin satır satır okuması, özellikle **iş mantığı hatalarını** yakalamada vazgeçilmezdir. Otomatik araçlar "bu fonksiyon yanlış ekonomik teşvik yaratıyor" ya da "bu iki fonksiyonun etkileşimi tutarsız state bırakıyor" türü sorunları göremez; bunları ancak protokolün amacını anlayan bir insan görür.
- **Statik analiz (static analysis).** Slither gibi araçlar kodu çalıştırmadan tarayıp reentrancy, korumasız fonksiyon, tehlikeli düşük seviye çağrı gibi bilinen desenleri işaretler. Hızlıdır ama yanlış pozitif (false positive) üretebilir.
- **Sembolik çalıştırma / fuzzing.** Mythril, Echidna, Foundry'nin fuzz test yetenekleri gibi araçlar, geniş girdi uzayını otomatik deneyerek beklenmedik girdilerle bozulan invariant'ları (değişmez kalması gereken koşulları) ortaya çıkarır. Invariant testing özellikle güçlüdür: "toplam arz her zaman bakiyeler toplamına eşit olmalı" gibi bir kuralı milyonlarca rastgele senaryoda sınar.
- **Formal doğrulama (formal verification).** Kritik özelliklerin matematiksel olarak kanıtlanması. Pahalı ve zaman alıcıdır ama en yüksek güvence seviyesini sağlar; genellikle en kritik çekirdek mantık için kullanılır.

### Denetimin sınırları — dürüst bir değerlendirme

Denetim bir güvence katmanıdır, **garanti değildir.** Denetlenmiş sözleşmeler de hacklenmiştir. Bunun nedenleri: denetim belli bir kod anlık görüntüsünü kapsar, sonraki değişiklikler kapsam dışı kalır; denetçi belli bir zaman bütçesiyle çalışır ve her yolu tüketemez; bazı zafiyetler ancak canlı ekonomik koşullarda (örneğin belirli bir likidite durumunda) ortaya çıkar. Bu yüzden denetim tek başına değil, bir güvenlik programının parçası olarak düşünülmelidir: **bug bounty** programları (canlı sistemde zafiyet bulan araştırmacıyı ödüllendirir), kademeli dağıtım (staged rollout) ve fon limitleri, gerçek zamanlı izleme (monitoring) ve acil durdurma mekanizmaları (pausable, circuit breaker) bu programı tamamlar.

## Sıkça Yapılan Hatalar

Alan genelinde tekrar eden hataları tek yerde toplamak faydalıdır:

- **Harici çağrı sonrası state güncellemek.** CEI ihlali; reentrancy'nin ana kaynağı.
- **`tx.origin` ile yetki kontrolü.** Her zaman `msg.sender` kullanılmalı.
- **`transfer`/`send`'in sabit gas'ına güvenmek.** Gelecekteki opcode fiyat değişimlerine kırılgan; `call` + guard tercih edilmeli.
- **Dönüş değerlerini kontrol etmemek.** Düşük seviye `call` başarısız olsa bile revert etmez; `success` değeri mutlaka kontrol edilmelidir.
- **Rastgelelik için on-chain kaynaklar kullanmak.** `block.timestamp`, `blockhash`, `block.prevrandao` madenciler/validator'lar tarafından bir dereceye kadar manipüle edilebilir; kritik rastgelelik için doğrulanabilir bir kaynak (örneğin Chainlink VRF) gerekir.
- **Spot fiyatı doğrudan oracle olarak kullanmak.** Flash loan manipülasyonuna açık kapı.
- **`unchecked` bloklarını gereksiz kullanmak veya downcast risklerini görmezden gelmek.**
- **Erişim kontrolünde varsayılan görünürlüğe güvenmek.** Fonksiyon görünürlüğü (visibility) açıkça belirtilmeli; kritik fonksiyonlar korunmalı.
- **Front-running / MEV'i hesaba katmamak.** Mempool herkese açıktır; işlemler sıralanmadan önce görülebilir. Fiyata duyarlı işlemlerde slippage koruması ve gerekirse commit-reveal desenleri düşünülmelidir.
- **Storage layout'u bozan upgrade'ler.** Proxy desenlerinde yeni implementation'ın storage düzenini kaydırması, verilerin bozulmasına yol açar.

## En İyi Pratikler

Sağlam bir akıllı sözleşme güvenlik duruşu şu prensipler üzerine kurulur:

**Denenmiş kütüphaneleri kullanın.** Kendi `ERC20`, `AccessControl` veya matematik kütüphanenizi yazmak yerine OpenZeppelin gibi geniş çapta denetlenmiş, savaşta test edilmiş (battle-tested) kodu temel alın. Kendi yazdığınız her satır yeni bir saldırı yüzeyidir.

**Basitlik güvenliktir.** Karmaşıklık, denetlenemez ve öngörülemez etkileşimler doğurur. Az kod, az hata demektir. Gereksiz esneklik ve genellik eklemek yerine yalnızca ihtiyaç duyulanı yazın.

**Savunmacı programlama.** Girdileri doğrulayın, invariant'ları açıkça `require` ile ifade edin, beklenmedik durumda revert edin. Fonların hareket ettiği her yolu "saldırgan burada ne yapabilir?" sorusuyla inceleyin.

**Kapsamlı test ve invariant tabanlı doğrulama.** Yüksek test kapsamı (coverage) tek başına yetmez; asıl değerli olan, sistemin hiçbir koşulda ihlal etmemesi gereken kuralları invariant testleriyle sınamaktır. Foundry gibi modern araç zincirleri bunu erişilebilir kılar.

**Derinlemesine savunma (defense in depth).** Tek bir korumaya bel bağlamayın. CEI + reentrancy guard, denetim + bug bounty, timelock + multisig gibi katmanları üst üste koyun; bir katman atlansa bile diğeri tutar.

**Acil müdahale hazırlığı.** Duraklatılabilirlik (pausable), fon çekim limitleri, anormallik izleme ve önceden hazırlanmış bir olay müdahale (incident response) planı, kaçınılmaz olan "kötü gün" için hazırlık sağlar. En iyi kod bile canlıdayken izlenmeli ve gerektiğinde durdurulabilmelidir.

**Değişiklikleri yeniden denetleyin.** Denetim sonrası yapılan her değişiklik, denetlenmemiş kod demektir. Küçük görünen bir düzeltme yeni bir zafiyet açabilir; kapsam disiplinini koruyun.

Sonuç olarak Web3 güvenliği, tek bir aracın ya da tek bir denetimin sağlayabileceği bir durum değil, tasarımdan dağıtıma ve dağıtım sonrası izlemeye uzanan sürekli bir disiplindir. Kodun değiştirilemezliği ve doğrudan para taşıması, hata payını sıfıra yaklaştırma zorunluluğu getirir; bu yüzden her zafiyet sınıfını kök nedeniyle anlamak, hem saldırganın hem savunmacının bakış açısını aynı anda taşımak ve katmanlı savunma kurmak bu alandaki uzmanlığın temelidir.
