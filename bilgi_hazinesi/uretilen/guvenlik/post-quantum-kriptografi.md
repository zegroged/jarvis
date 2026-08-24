# Post-Quantum Kriptografi (ML-KEM/Kyber, ML-DSA/Dilithium, SLH-DSA/SPHINCS+)

## Tanım

Post-quantum kriptografi (PQC), yeterince güçlü bir kuantum bilgisayarın çalıştırdığı bilinen algoritmalarla dahi kırılamayacak şekilde tasarlanmış, klasik (kuantum olmayan) bilgisayarlarda çalışan kriptografik algoritmalar bütünüdür. Burada kritik bir kavram ayrımı yapmak gerekir: PQC, "kuantum kriptografi" (quantum key distribution gibi fiziksel kuantum fenomenlerine dayanan yöntemler) ile karıştırılmamalıdır. PQC klasik matematiksel problemler üzerine kuruludur; sadece bu problemlerin kuantum algoritmalarına karşı da dirençli olduğu varsayılır.

2024 yılında NIST (Amerikan Ulusal Standartlar ve Teknoloji Enstitüsü), yıllar süren bir yarışma sürecinin ardından üç standardı resmî olarak yayımladı:

- **FIPS 203 — ML-KEM** (Module-Lattice-Based Key-Encapsulation Mechanism), eski adıyla **Kyber**: anahtar değişimi/kapsülleme için.
- **FIPS 204 — ML-DSA** (Module-Lattice-Based Digital Signature Algorithm), eski adıyla **Dilithium**: dijital imza için.
- **FIPS 205 — SLH-DSA** (Stateless Hash-Based Digital Signature Algorithm), eski adıyla **SPHINCS+**: dijital imza için, farklı bir matematiksel temelden.

Bu üçü birlikte, günümüzün RSA ve eliptik eğri kriptografisinin (ECC/ECDSA/ECDH) yerini alacak yeni nesil temel yapı taşlarını oluşturur.

## Kök Neden: Neden Bu Konu Artık Zorunlu?

### Shor algoritması ve klasik kriptografinin matematiksel temelinin çöküşü

RSA'nın güvenliği büyük sayıların asal çarpanlarına ayrılmasının (integer factorization) klasik bilgisayarlarda pratik olarak imkânsız olmasına dayanır. ECC/ECDSA/ECDH ise eliptik eğri üzerindeki ayrık logaritma probleminin (discrete logarithm problem) zorluğuna dayanır. 1994'te Peter Shor'un geliştirdiği kuantum algoritması, yeterince büyük ve kararlı (fault-tolerant) bir kuantum bilgisayarda hem çarpanlara ayırmayı hem de ayrık logaritma problemini **polinomsal zamanda** çözebileceğini matematiksel olarak gösterdi. Bu, "belki kırılır" değil, "kırılacağı ispatlanmış" bir durumdur — tek eksik olan yeterli kalitede kübit'e sahip donanımın inşa edilmesidir.

Burada kök neden şudur: RSA/ECC'nin güvenliği hesaplama zorluğuna (computational hardness) dayanır, ama bu zorluk klasik bilgisayar modeli için geçerlidir. Kuantum hesaplama modeli farklı bir hesaplama sınıfı sunduğu için, "klasik olarak zor" problem, "kuantumda kolay" hale gelebilir. Shor algoritması tam olarak bunu yapar: problemi kuantum Fourier dönüşümü üzerinden periyodiklik bulma problemine indirger ve bu, kuantum paralelliği sayesinde verimli çözülür.

Buna karşılık, **Grover algoritması** simetrik kriptografiye (AES gibi) ve hash fonksiyonlarına karşı yalnızca karesel (quadratic) bir hızlanma sağlar — brute-force arama uzayını N'den √N'e indirir. Bu, AES-128'i AES-64 güvenlik seviyesine düşürür gibi düşünülebilir; pratik çözüm basittir: anahtar uzunluğunu ikiye katlamak (AES-256 kullanmak). Yani simetrik kriptografi PQC'nin asıl endişe alanı değildir; asıl kırılma riski **asimetrik/açık anahtarlı** kriptografidedir (anahtar değişimi ve dijital imza).

### "Harvest Now, Decrypt Later" (HNDL) tehdidi — asıl aciliyetin nedeni

Burada asıl "neden şimdi?" sorusunun cevabı yatıyor. Kuantum bilgisayarların RSA-2048'i kırabilecek olgunluğa erişmesi muhtemelen daha yıllar alacak. Ama bu, konunun ertelenebileceği anlamına gelmez, çünkü saldırganların stratejisi zaten değişti:

1. Bir istihbarat servisi veya düşman aktör, bugün internet trafiğini (TLS oturumları, VPN el sıkışmaları, e-posta) toplu halde kaydeder ve depolar.
2. Bu veri şu an RSA/ECC ile şifrelenmiş olduğu için okunamaz.
3. Yıllar sonra kriptografik olarak anlamlı bir kuantum bilgisayar (CRQC — Cryptographically Relevant Quantum Computer) ortaya çıktığında, saklanan bu trafiğin şifrelemesi geriye dönük olarak kırılır ve içerik deşifre edilir.

Bu saldırı modeline **"harvest now, decrypt later"** denir. Kök neden analizinde kritik nokta şudur: bu tehdit, bugünkü şifreleme algoritmasının bugün kırılmasını gerektirmez — sadece verinin **gizlilik ömrü** (confidentiality lifetime) kuantum bilgisayarın olgunlaşma süresini aşıyorsa risk gerçektir. Devlet sırları, tıbbi kayıtlar, uzun vadeli fikri mülkiyet, kimlik belgeleri gibi 10-30 yıl gizli kalması gereken veriler için bu süre çoktan dolmuş sayılabilir; bu yüzden geçiş "bugünden" başlamalıdır, kuantum bilgisayar ortaya çıktığı gün değil.

Ek olarak dijital imzalar için farklı bir risk vektörü vardır: imzalar genellikle *anlık* doğrulama içindir (geçmişe dönük gizlilik sorunu yoktur) ama **uzun ömürlü güven zincirleri** (kod imzalama sertifikaları, kök CA'lar, firmware imzaları) kuantum sonrası dönemde sahtecilik riskiyle karşı karşıyadır. Bir saldırgan gelecekte kuantum bilgisayarla bir CA'nın özel anahtarını türetebilirse, geçmişte imzalanmış her şeyin güvenilirliği de sorgulanır hale gelir.

### Neden NIST bir yarışma yaptı ve neden üç farklı algoritma ailesi seçildi?

NIST 2016'da açık bir çağrı başlattı çünkü tek bir "kazanan" matematiksel yapıya güvenmek riskliydi — RSA/ECC tekelinin kuantumla birden çökmesi tam olarak bu riski gösterdi. Bu yüzden NIST, birbirinden **bağımsız matematiksel varsayımlara** dayanan çoklu aile seçti:

- **Kafes tabanlı (lattice-based)** kriptografi: ML-KEM ve ML-DSA'nın temeli. Module-LWE (Learning With Errors) ve Module-LWR gibi problemlere dayanır — yüksek boyutlu kafes yapılarında en yakın vektörü bulmanın klasik ve kuantum bilgisayarlar için de zor olduğu varsayımına dayanır.
- **Hash tabanlı (hash-based)** kriptografi: SLH-DSA'nın temeli. Güvenliği sadece kriptografik hash fonksiyonlarının (SHA-2/SHAKE gibi) çarpışma direncine dayanır — kafes problemleri gibi yeni ve göreceli az test edilmiş varsayımlara değil, onlarca yıldır incelenen hash güvenliğine dayanır.

Bu çeşitlendirme kasıtlıdır: eğer gelecekte kafes tabanlı problemlere karşı beklenmedik bir kriptanalitik kırılma bulunursa (ki 2022'de SIKE algoritmasının çarpıcı biçimde klasik bir bilgisayarda kırılması tam olarak böyle bir "sürpriz" oldu), hash tabanlı SLH-DSA farklı bir matematiksel temelde durduğu için etkilenmez. Bu, güvenlik mühendisliğinde "tek hata noktasından kaçınma" (defense in depth / algorithm diversity) ilkesinin kriptografi standardizasyonuna uygulanmasıdır.

## Çalışma Mantığı (Kavramsal)

### ML-KEM (Kyber) — Anahtar Kapsülleme Mekanizması

ML-KEM, TLS el sıkışması gibi senaryolarda kullanılan Diffie-Hellman benzeri bir anahtar değişimi *yerine* geçer, ama farklı bir yapıdadır: klasik DH gibi "her iki taraf da aynı hesaplamayı yapıp ortak bir sırra ulaşır" değil, bir **KEM (Key Encapsulation Mechanism)** modelidir:

1. Alıcı bir açık/gizli anahtar çifti üretir; açık anahtarı gönderir.
2. Gönderen, alıcının açık anahtarını kullanarak rastgele bir simetrik anahtar (paylaşılan sır) üretir ve bunu "kapsülleyerek" (encapsulate) bir şifre metni (ciphertext) oluşturur, bunu alıcıya gönderir.
3. Alıcı kendi gizli anahtarıyla bu şifre metnini "açar" (decapsulate) ve aynı paylaşılan sırra ulaşır.

Matematiksel temel **Module-LWE** problemidir: kabaca, `A*s + e = b` şeklinde bir denklemde, `A` ve `b` bilindiği halde `s` (gizli vektör) ve `e` (küçük rastgele "gürültü/hata" vektörü) bilinmiyorsa, `s`'yi bulmanın kafes yapıları üzerinde hesaplama olarak zor olduğu varsayılır. Gürültünün varlığı problemi zorlaştıran anahtar unsurdur — gürültü olmasaydı bu basit bir doğrusal cebir problemi olur ve kolayca çözülürdü.

ML-KEM üç güvenlik seviyesinde tanımlanır (ML-KEM-512/768/1024), sayı arttıkça kafes boyutu ve dolayısıyla güvenlik marjı artar, anahtar/şifre metni boyutu da büyür.

### ML-DSA (Dilithium) — Dijital İmza

ML-DSA da kafes tabanlıdır ama imza üretimi/doğrulaması için "Fiat-Shamir with Aborts" adı verilen bir yapı kullanır. Kavramsal olarak: imzalayan, gizli anahtarına bağlı bir kafes denklemi kullanarak bir imza üretir, ancak bu imzanın gizli anahtar hakkında istatistiksel bilgi sızdırmamasını garantilemek için üretim sürecinde bazı adaylar "reddedilip" (rejection sampling) yeniden denenir. Bu, imza boyutunu ve hesaplama süresini klasik ECDSA'ya kıyasla artırır ama yan kanal güvenliğini kolaylaştırır.

### SLH-DSA (SPHINCS+) — Hash Tabanlı İmza

SLH-DSA'nın çalışma mantığı tamamen farklıdır ve kafes matematiği içermez. Temel fikir: hash fonksiyonlarının tek yönlülüğünden (one-wayness) yararlanarak "tek kullanımlık imza" (one-time signature, örn. WOTS+ — Winternitz One-Time Signature) yapılarını, bir **Merkle ağacı** hiyerarşisiyle birleştirmektir:

- Alt seviyede WOTS+ gibi tek-kullanımlık imza şemaları, her biri sadece bir mesajı güvenle imzalayabilir.
- Bu tek kullanımlık anahtarların açık anahtarları bir Merkle ağacında yapraklar olarak düzenlenir; ağacın kökü asıl açık anahtardır.
- Çok katmanlı (hypertree) yapı sayesinde pratikte "çoklu kullanım" imza şemasına dönüştürülür.

Güvenliği sadece hash fonksiyonunun çarpışma ve ön-görüntü direncine dayandığı için matematiksel olarak en "muhafazakâr"/güvenilir seçenektir, ama imza boyutu (genellikle onlarca KB) ML-DSA'ya göre çok daha büyüktür ve imzalama/doğrulama daha yavaştır. Bu yüzden "yüksek güvenlik marjı gerektiren ama performans kısıtı az olan" senaryolar (örn. firmware imzalama, kök sertifikalar) için tercih edilir; yüksek hacimli TLS trafiği gibi performans kritik senaryolarda ML-DSA daha uygundur.

## Tespit ve Savunma

Bu konuda "tespit", geleneksel saldırı tespitinden farklı bir çerçevede ele alınmalı: burada asıl mesele **kripto-çeviklik (crypto-agility)** durumunun tespiti ve geçiş sürecinin doğru yönetilmesidir.

### Envanter ve tespit (kriptografik varlık keşfi)

- **Kriptografik envanter çıkarımı**: Organizasyonun hangi sistemlerde RSA/ECC kullandığını bilmeden PQC geçişi planlanamaz. TLS sertifikalarını, SSH host key'lerini, kod imzalama sertifikalarını, VPN yapılandırmalarını, gömülü/IoT cihaz firmware imzalama zincirlerini tarayan otomatik keşif araçları (certificate transparency logs taraması, iç ağ TLS handshake analizi, sertifika deposu taraması) kullanılmalı.
- **"Harvest now" maruziyetinin tespiti**: Hangi trafiğin/verinin uzun süreli gizlilik gereksinimi olduğunu belirlemek (veri sınıflandırması + gizlilik ömrü etiketleme). Örneğin 20 yıl gizli kalması gereken bir belge bugün klasik ECDH ile korunuyorsa, bu yüksek öncelikli bir risktir.
- **Protokol düzeyinde tespit**: Ağ trafiği analizinde TLS 1.3 el sıkışmalarında kullanılan `key_share` uzantısında hangi grupların (`x25519`, `secp256r1` veya hibrit `X25519MLKEM768` gibi) kullanıldığı gözlemlenebilir; bu, bir kuruluşun PQC geçişinde nerede olduğunu ölçmenin somut bir yoludur.

### Savunma stratejisi

- **Hibrit (hybrid) mod önceliklendirme**: Geçiş döneminde önerilen yaklaşım, klasik algoritma (örn. X25519) ile PQC algoritmasını (örn. ML-KEM) **birlikte** kullanmaktır — paylaşılan sır her iki yöntemin çıktısının birleşiminden türetilir. Mantık şudur: eğer ML-KEM'de gelecekte beklenmedik bir zayıflık bulunursa klasik bileşen güvenliği korur; eğer kuantum bilgisayar klasik bileşeni kırarsa PQC bileşeni korur. Bu, "yeni ve az test edilmiş algoritmaya tek başına güvenmeme" ilkesinin savunma karşılığıdır ve pek çok büyük tarayıcı/sunucu uygulaması (TLS 1.3 uzantıları üzerinden) bu hibrit modeli varsayılan hale getirmeye yöneliyor.
- **Kripto-çeviklik mimarisi**: Algoritmaları uygulama mantığına sabit kodlamak yerine, değiştirilebilir/soyutlanmış bir kriptografi katmanı (crypto provider abstraction) kullanmak. Böylece gelecekte bir algoritma revize edildiğinde (parametre değişikliği, yeni saldırı bulunması) tüm sistemi yeniden yazmadan geçiş yapılabilir.
- **Önceliklendirme prensibi**: Her sistemi aynı anda göçe zorlamak yerine, risk temelli sıralama yapılmalı: (1) uzun ömürlü gizlilik gerektiren veri kanalları, (2) kök güven noktaları (root CA'lar, firmware imzalama anahtarları — bunların değiştirilmesi yıllar sürebilir ve tedarik zincirine yayılır), (3) yüksek hacimli ama kısa ömürlü oturum trafiği (örn. günlük web trafiği; HNDL riski düşüktür çünkü veri hızla değersizleşir).
- **Anahtar/imza boyutu etkisinin test edilmesi**: PQC anahtarları ve imzaları klasik muadillerinden belirgin şekilde büyüktür (ML-KEM açık anahtarı ~1-1.5 KB, SLH-DSA imzası onlarca KB olabilir). Bu, MTU sınırlarını aşan TLS handshake'leri, IoT cihazlarında bellek/bant genişliği kısıtları, DNSSEC gibi paket boyutuna duyarlı protokollerde ciddi operasyonel sorunlara yol açabilir — geçiş öncesi performans/kapasite testi savunmanın bir parçası olmalıdır.
- **Tedarikçi ve kütüphane doğrulaması**: Kullanılan TLS kütüphanesi, HSM (donanım güvenlik modülü) ve bulut sağlayıcısının FIPS 203/204/205'i ne zaman ve nasıl desteklediğini doğrulamak; kendi PQC implementasyonunu yazmamak (yan kanal dirençli, sabit-zamanlı implementasyon uzmanlık ister, hatalı bir uygulama teorik güvenliği pratikte geçersiz kılar).

## Yaygın Hatalar

- **"Kuantum bilgisayar yok, o zaman acele yok" yanılgısı**: HNDL tehdidi göz ardı edilerek geçişin kuantum bilgisayarın fiilen var olmasına kadar ertelenmesi. Oysa risk, verinin gizlilik ömrüne göre değerlendirilmelidir; bugün toplanan veri gelecekte deşifre edilebilir.
- **Sadece anahtar değişimini (KEM) değiştirip imzaları unutmak**: Pek çok geçiş projesi TLS anahtar değişimini hibrit PQC'ye taşır ama sertifika zincirlerindeki imza algoritmalarını (X.509 sertifikalarının kendisi) klasik bırakır. Kimlik doğrulama/imza tarafı da aynı derecede risk altındadır, özellikle uzun ömürlü kök sertifikalar için.
- **Yalnızca PQC'ye geçip hibrit modu atlamak**: Yeni standartlaşan algoritmalara olan güvenin henüz RSA/ECC'nin onlarca yıllık kriptanaliz geçmişiyle kıyaslanamayacağını unutmak. Hibrit yaklaşım olmadan doğrudan "saf PQC"ye geçmek, henüz keşfedilmemiş bir kafes tabanlı zayıflığa karşı tüm güvenliği tek noktaya bağlar.
- **Simetrik kriptografiyi de "kuantum tehdidi" kapsamında RSA ile aynı aciliyette görmek**: AES-256 gibi yeterli anahtar uzunluğuna sahip simetrik şifreleme, Grover'ın karesel hızlanmasına karşı zaten yeterli marja sahiptir; kaynakları yanlış önceliklendirip asimetrik kriptografi geçişini geciktirmek hataya yol açar.
- **Performans/boyut etkilerini test etmeden üretime almak**: Büyük anahtar/imza boyutlarının ağ katmanında (fragmentasyon, MTU, timeout'lar), gömülü sistemlerde (bellek/depolama kısıtı) ve üçüncü taraf entegrasyonlarda (eski istemcilerle uyumsuzluk) yaratabileceği kesintileri öngörmemek.
- **Kendi implementasyonunu yazmaya kalkışmak**: Kafes tabanlı şemalar sabit-zamanlı olmayan (non-constant-time) işlemler, örnekleme hataları veya yanlış gürültü dağılımı gibi ince hatalara karşı hassastır; bu hatalar teorik güvenliği pratikte geçersiz kılabilecek side-channel açıklarına yol açabilir. Standart, denetlenmiş kütüphaneler (üreticilerin FIPS onaylı implementasyonları) kullanılmalı.
- **Envanter çıkarmadan geçiş planlamak**: Hangi sistemlerin nerede hangi algoritmayı kullandığını bilmeden "PQC'ye geçtik" demek — genellikle görünmeyen eski sistemler (gömülü cihazlar, eski entegrasyonlar, üçüncü taraf servisler) geçişin dışında kalır ve kör nokta oluşturur.

## Özet

Post-quantum kriptografiye geçişin kök nedeni iki katmanlıdır: (1) Shor algoritmasının matematiksel olarak kanıtlanmış biçimde RSA/ECC'nin temelini oluşturan problemleri kuantum bilgisayarda verimli çözebilmesi, ve (2) "harvest now, decrypt later" stratejisiyle bu riskin kuantum bilgisayar henüz var olmadan bugün gerçek bir tehdide dönüşmesi. NIST'in FIPS 203/204/205 standartları (ML-KEM, ML-DSA, SLH-DSA) farklı matematiksel varsayımlara (kafes ve hash tabanlı) dayanan çoklu algoritma ailesi sunarak tek-hata-noktası riskini azaltır. Savunma tarafında asıl iş, saldırı imzası aramak değil, kriptografik envanter çıkarmak, risk temelli önceliklendirme yapmak, hibrit geçiş stratejileri uygulamak ve kripto-çeviklik mimarisi kurmaktır — çünkü bu alanda "geç kalmak", geçmişte şifrelenmiş verinin gelecekte toptan deşifre edilmesi anlamına gelebilir.
