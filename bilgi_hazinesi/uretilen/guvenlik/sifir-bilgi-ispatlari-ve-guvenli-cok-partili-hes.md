# Sıfır Bilgi İspatları (zk-SNARK / zk-STARK) ve Güvenli Çok Partili Hesaplama (MPC)

## Giriş: Neden Ayrı Bir Derinlik Gerektirir?

Modern gizlilik-korumalı sistemlerin (blockchain ölçekleme, anonim kimlik doğrulama, gizli oy, özel veri paylaşımı) altında iki büyük kriptografik aile yatar: **Zero-Knowledge Proofs (ZKP — Sıfır Bilgi İspatları)** ve **Secure Multi-Party Computation (MPC — Güvenli Çok Partili Hesaplama)**. Bu iki alan, Web3 veya "akıllı sözleşme" başlığı altında yüzeysel geçilirse yanlış anlaşılır. Çünkü bunlar sadece "blockchain aracı" değildir; **bir tarafın, karşı tarafa gizli bilgisini vermeden bir iddiayı kanıtlaması** (ZKP) ve **birden çok tarafın, kendi girdilerini gizli tutarak ortak bir fonksiyonu hesaplaması** (MPC) gibi temel problemleri çözerler.

Bu makale mekanizmayı anlamaya, hataları görmeye ve savunma/tespit kurmaya odaklanır. Amaç saldırı reçetesi değil; sistemin nasıl çalıştığını, nerede kırıldığını ve nasıl doğrulanacağını kavramaktır.

---

## Bölüm 1: Sıfır Bilgi İspatları (Zero-Knowledge Proofs)

### 1.1 Tanım

Bir ispat sisteminde iki rol vardır: **Prover (İspatlayan)** ve **Verifier (Doğrulayan)**. Prover, bir ifadenin doğru olduğunu Verifier'a kanıtlamak ister. Örnek ifade: "Bu hash değerinin ön-görüntüsünü (preimage) biliyorum" ya da "Bakiyem transferi karşılıyor" gibi.

Bir ispat sistemi **zero-knowledge** ise üç özelliği sağlar:

- **Completeness (Tamlık):** İfade gerçekten doğruysa, dürüst bir Prover, dürüst bir Verifier'ı ikna edebilir.
- **Soundness (Sağlamlık):** İfade yanlışsa, hileci bir Prover, Verifier'ı ancak ihmal edilebilir bir olasılıkla kandırabilir. Kriptografik sistemlerde çoğu zaman "computational soundness" geçerlidir; yani sağlamlık, saldırganın hesaplama gücünün sınırlı olduğu varsayımına dayanır.
- **Zero-Knowledge (Sıfır Bilgi):** Verifier, ifadenin doğru olduğu gerçeği dışında **hiçbir ek bilgi** öğrenemez. Bu, biçimsel olarak bir **simulator** ile tanımlanır: Verifier'ın gördüğü her şey, gizli tanığı (witness) bilmeyen bir simülatör tarafından üretilebiliyorsa, ispat hiçbir bilgi sızdırmıyor demektir.

Anahtar kavram **witness (tanık)**: İfadeyi doğru kılan gizli veridir (şifre, özel anahtar, ön-görüntü). ZKP'nin bütün amacı, witness'ı ifşa etmeden onun varlığını kanıtlamaktır.

### 1.2 Kök Neden / Çalışma Mantığı

Sezgisel örnek — **Ali Baba mağarası**: Halka biçiminde bir mağaranın ortasında sihirli sözcükle açılan bir kapı var. Prover, kapının şifresini bildiğini kanıtlamak ister ama şifreyi söylemez. Verifier dışarıda bekler, Prover içeri girer; Verifier hangi koldan (sol/sağ) çıkmasını istediğini söyler. Prover şifreyi biliyorsa her seferinde doğru koldan çıkabilir. Bilmiyorsa yalnızca %50 şansla doğru olur. Bu turu defalarca tekrarlayınca (n kez), hilecinin başarı olasılığı 2^(-n) düzeyine iner. İşte **soundness** budur; ve Verifier şifreyi hiç öğrenmez — **zero-knowledge**.

Bu tur tur "interaktif" yapı pratikte hantaldır. Modern sistemler **Fiat–Shamir dönüşümü** ile bunu **non-interactive (etkileşimsiz)** hale getirir: Verifier'ın rastgele meydan okuması (challenge) yerine, ispatın o ana kadarki içeriğinin bir hash'i challenge olarak kullanılır. Böylece Prover, tek bir ispat nesnesi üretip yayınlar; herkes bağımsızca doğrular. **Uyarı:** Fiat–Shamir'in güvenliği, hash'in **tüm** ilgili public girdileri kapsamasına bağlıdır. Eksik/yanlış transkript hash'lenirse tüm sistem kırılabilir — buna geçmişte gerçek sistemlerde rastlanan "**Frozen Heart**" sınıfı zafiyetler örnek gösterilir.

### 1.3 zk-SNARK ve zk-STARK Farkı

Modern ZKP'ler genellikle bir hesaplamayı önce bir **arithmetic circuit** veya **R1CS / AIR** gibi bir kısıtlama sistemine çevirir, sonra bunun sağlandığını kısa bir ispatla gösterir.

**zk-SNARK** (Succinct Non-interactive ARgument of Knowledge):
- **Succinct:** İspat çok küçüktür (çoğu şemada birkaç yüz bayt) ve doğrulama çok hızlıdır — hesaplamanın boyutundan bağımsız, neredeyse sabit.
- **Trusted setup (güvenilir kurulum):** Klasik SNARK'lar (ör. Groth16) bir başlangıç parametre kümesi (**Common Reference String / CRS**) gerektirir. Bu üretilirken ortaya çıkan gizli değer — **toxic waste** — imha edilmezse, saldırgan **sahte ispat** üretebilir. Bu yüzden **MPC tabanlı "ceremony" (tören)** ile üretilir: Birçok katılımcıdan **en az biri** dürüst olup payını yok ederse toxic waste kurtarılamaz. (İki ekosistemin bilinen büyük törenleri bu prensibe dayanır.) PLONK gibi şemalar "universal / updatable" setup ile bunu yumuşatır.
- **Kripto varsayımı:** Genellikle **elliptic curve pairing** ve ilgili sertlik varsayımlarına dayanır. Bu, **quantum bilgisayarlara** karşı kırılgan kabul edilir.

**zk-STARK** (Scalable Transparent ARgument of Knowledge):
- **Transparent:** Trusted setup **yoktur**; toxic waste riski yoktur. Rastgelelik herkese açık şekilde üretilir.
- **Post-quantum dayanıklı:** Yalnızca **hash fonksiyonlarının** güvenliğine (collision resistance) dayanır; bilinen kuantum saldırılarına karşı daha dirençlidir.
- **Bedel:** İspat boyutu SNARK'a göre çok daha büyüktür (kilobayt–onlarca kilobayt) ve doğrulama daha maliyetlidir. Buna karşılık **prover** çok büyük hesaplamalarda iyi ölçeklenir.

Özet tablo:

| Özellik | zk-SNARK | zk-STARK |
|---|---|---|
| İspat boyutu | Çok küçük | Büyük |
| Doğrulama hızı | Çok hızlı | Daha yavaş |
| Trusted setup | Gerekir (bazı şemalarda) | Gerekmez (transparent) |
| Kuantum direnci | Genelde zayıf (pairing) | Daha güçlü (hash tabanlı) |
| Temel varsayım | Pairing / eliptik eğri | Collision-resistant hash |

### 1.4 Gerçek Kullanım Örneği

**Gizli transfer:** Bir gizlilik-korumalı zincirde kullanıcı, "gönderdiğim tutar bakiyeme eşit veya küçük ve toplam korunuyor" ifadesini bir ZKP ile kanıtlar; miktarlar ve adresler açığa çıkmaz. **Rollup (ölçekleme):** Bir zk-rollup, binlerce işlemi zincir dışında işler ve "bu işlemler kurallara uygun uygulandı" diye tek bir kısa ispat sunar; ana zincir tüm işlemleri tekrar çalıştırmak yerine sadece küçük ispatı doğrular — hem ölçek hem bütünlük. **Kimlik / yaş kanıtı:** "18 yaşından büyüğüm" ifadesi, doğum tarihini ifşa etmeden kanıtlanabilir.

### 1.5 Yaygın Hatalar ve Zafiyet Sınıfları

- **Under-constrained circuit (eksik kısıtlanmış devre):** ZKP'de en sık ve en tehlikeli hata sınıfı. Devre, kanıtlaması gereken kuralın **tamamını** kısıtlamazsa, Prover geçerli görünen ama aslında yalan söyleyen bir witness bulabilir. Örneğin bir boolean değişkenin gerçekten 0 veya 1 olduğunu zorlamayı unutmak, ya da bir bölme/ters alma işleminde 0'a bölmeyi engellememek. İspat "doğrulanır" ama semantik yanlıştır.
- **Fiat–Shamir eksik transkript:** Challenge hash'ine tüm public girdileri katmamak (yukarıda anıldı).
- **Nullifier / double-spend eksikliği:** Gizli sistemlerde her gizli notun bir kez harcanmasını sağlayan **nullifier** mekanizması yanlış tasarlanırsa çift harcama olur.
- **Trusted setup'a körü körüne güven:** Toxic waste'in gerçekten yok edildiğini varsaymak; törene katılımı ve şeffaflığını doğrulamamak.
- **Randomness / soundness bariyerini yanlış ayarlamak:** STARK/FRI gibi sistemlerde güvenlik parametrelerini (query sayısı, alan boyutu) yetersiz seçmek.

### 1.6 Tespit ve Savunma

- **Circuit audit ve formal verification:** Devrelerin bağımsız denetimi; mümkünse kısıtlamaların eksiksizliğini kanıtlayan biçimsel araçlar. "Her kısıtlama gerçekten gerekli mi ve **yeterli mi**?" sorusu merkezdedir.
- **Constraint coverage / negative testing:** Kasıtlı geçersiz witness'lerle test ederek "kabul edilmemesi gerekeni kabul ediyor mu?" kontrolü. Sadece "geçerli girdi geçiyor mu" testi yetmez.
- **Trusted setup şeffaflığı:** Ceremony katılımcı sayısı, katkı kayıtları ve doğrulanabilir transkript. Mümkünse transparent (STARK/PLONK-benzeri universal) şemaları tercih etmek.
- **Bilinen zafiyet kütüphaneleri:** Fiat–Shamir eksikliği, under-constrained devre kalıpları gibi bilinen anti-pattern'lere karşı statik analiz.
- **Post-quantum planlama:** Uzun ömürlü sistemler için pairing-tabanlı SNARK'ların kuantum kırılganlığını göz önünde bulundurmak.

---

## Bölüm 2: Güvenli Çok Partili Hesaplama (Secure Multi-Party Computation, MPC)

### 2.1 Tanım

MPC, birden çok tarafın, her birinin **özel girdisini** (x1, x2, … xn) gizli tutarak ortak bir fonksiyon **f(x1,…,xn)** hesaplamasını sağlar. Sonuç herkesçe (ya da izin verilenlerce) öğrenilir ama **hiçbir taraf diğerinin girdisini** öğrenmez — sonuçtan çıkarsanabilen kısım hariç.

Klasik örnek **Yao'nun milyonerler problemi:** İki milyoner, servetlerinin miktarını birbirine söylemeden hangisinin daha zengin olduğunu öğrenmek ister. MPC, tam olarak bunu çözer: Yalnızca "A > B" sonucu ortaya çıkar, rakamlar gizli kalır.

### 2.2 Çalışma Mantığı — İki Ana Yaklaşım

**a) Secret Sharing (Sır Paylaşımı) tabanlı MPC.**
Bir sır, örneğin **Shamir Secret Sharing** ile parçalara (shares) bölünür. Fikir: Bir polinomun sabit terimi sırdır; sırrı **t+1** paydan aşağısı hiçbir bilgi vermez, **t+1** pay ile tam olarak yeniden kurulur (threshold). Taraflar payları üzerinde işlem yaparak sonucu hesaplar. **Toplama** paylar üzerinde doğrudan yapılabilir; **çarpma** ise ekstra protokol (ör. Beaver triple denen önceden hazırlanmış rastgele çarpımlar) gerektirir. BGW/GMW gibi klasik protokoller bu ailedendir.

**b) Garbled Circuits (Karıştırılmış Devreler) — Yao protokolü.**
Fonksiyon bir boolean devreye çevrilir. Bir taraf (**garbler**) devrenin her kapısının doğruluk tablosunu şifreleyip karıştırır; diğer taraf (**evaluator**) kendi girdisine karşılık gelen anahtarları **Oblivious Transfer (OT)** ile alır. OT'nin sihri şudur: Evaluator ihtiyacı olan anahtarı alır ama garbler hangisini aldığını **bilmez**; evaluator da diğer anahtarları **göremez**. Böylece devre değerlendirilir, ara değerler ifşa olmaz.

**Homomorphic Encryption** (özellikle FHE) da MPC ile ilişkili ama ayrı bir araçtır: Şifreli veri üzerinde şifre çözmeden hesap yapmayı sağlar; MPC protokollerinde yapıtaşı olarak kullanılabilir.

### 2.3 Tehdit Modelleri — Bu Ayrım Kritik

MPC'nin güvenliği, **saldırganın modeline** göre tanımlanır. Yanlış model seçmek en yaygın kavramsal hatadır:

- **Semi-honest (honest-but-curious / passive):** Bozuk taraflar protokolü **dürüstçe uygular** ama gördükleri her şeyden gizli bilgi çıkarmaya çalışır. Daha ucuz protokoller yeterlidir.
- **Malicious (active):** Bozuk taraflar protokolden **sapabilir** — yanlış mesaj gönderebilir, hesabı bozabilir. Bunlara karşı savunma çok daha pahalıdır; genelde ispat/doğrulama katmanları (ör. authenticated shares, MAC'ler) gerekir.
- **Covert:** Sapan taraf belli bir olasılıkla **yakalanır**; caydırıcılığa dayanır.

Ek boyut: **honest majority** (tarafların çoğu dürüst) mü, yoksa **dishonest majority** (çoğunluk bozuk olabilir) mi varsayılıyor? Örneğin klasik Shamir tabanlı bazı protokoller honest majority varsayarken, SPDZ ailesi dishonest majority + malicious modelde çalışır ama daha ağırdır.

### 2.4 Gerçek Kullanım Örnekleri

- **Threshold signatures / MPC wallet:** Özel anahtar **hiçbir zaman tek bir yerde bütün olarak var olmaz**; paylara bölünür ve imza, taraflar bir araya gelip anahtarı **yeniden kurmadan** üretilir. Kripto saklama (custody) sektöründe yaygındır. HSM'e alternatif veya tamamlayıcı bir güven dağıtımı sağlar.
- **Gizli ihale / açık artırma:** Teklifler ifşa olmadan kazanan belirlenir.
- **Gizli istatistik / benchmark:** Farklı kurumlar (ör. bankalar, hastaneler) ham verilerini paylaşmadan ortak bir toplam, ortalama veya model eğitimi hesaplar (privacy-preserving analytics).
- **Anahtar üretimi (DKG — Distributed Key Generation):** Ortak açık anahtar, karşılık gelen özel anahtar hiç tek elde toplanmadan üretilir.

### 2.5 Yaygın Hatalar ve Zafiyet Sınıfları

- **Yanlış tehdit modeli:** Gerçek ortam malicious iken semi-honest protokol kullanmak. Bozuk taraf sapıp hem sonucu bozar hem de bilgi sızdırabilir.
- **Output leakage (çıktı sızıntısı):** MPC girdiyi gizler ama **çıktının kendisi** bilgi sızdırabilir. Örneğin bir fonksiyonun sonucu, bir tarafın girdisini tersine çıkarmaya yetiyorsa, protokol "doğru" çalışsa bile gizlilik ihlal olur. Fonksiyonun kendisi güvenli tasarlanmalı (differential privacy gibi ek katmanlar gerekebilir).
- **Collusion (gizli anlaşma):** Threshold varsayımını aşan sayıda taraf gizlice birleşirse (ör. t+1 pay sahibi anlaşırsa) sır açığa çıkar. Payların gerçekten **bağımsız** taraflarda/altyapılarda durması şarttır; hepsi aynı bulut hesabında ise threshold anlamını yitirir.
- **Zayıf randomness:** Secret sharing ve OT güçlü rastgeleliğe dayanır; tahmin edilebilir rastgelelik payları çözülebilir kılar.
- **Side-channel:** Zamanlama, mesaj boyutu, ağ desenleri protokol dışı bilgi sızdırabilir.
- **Rollback / replay:** Durumlu protokollerde eski mesajların tekrar oynatılması hesabı bozabilir.

### 2.6 Tespit ve Savunma

- **Doğru tehdit modeli seçimi ve belgelenmesi:** "Bu sistem hangi saldırgana karşı güvenli?" sorusunun açık yanıtı olmalı. Yüksek değerli (ör. cüzdan) sistemlerde **malicious-secure** protokol tercih edilir.
- **Actively-secure protokoller ve doğrulama:** MAC/authenticated secret sharing ile sapan tarafların yakalanması; hesabın sonunda **consistency check**.
- **Pay dağıtımının bağımsızlığı:** Payları farklı yönetim alanlarına, farklı operatörlere, farklı donanıma dağıtmak; collusion yüzeyini azaltmak. Threshold'u risk iştahına göre ayarlamak.
- **Output policy analizi:** Hesaplanan fonksiyonun ne kadar bilgi sızdırdığını önceden değerlendirmek; gerekiyorsa gürültü ekleme (differential privacy) veya çıktı kısıtlama.
- **Denetim ve loglama:** Protokol adımlarının (kimlik doğrulanmış) kayıtları; anomali tespiti için mesaj desenlerini izleme. Not: loglar da gizliliği bozmamalı — hassas ara değer loglanmamalı.
- **Anahtar rotasyonu / proactive secret sharing:** Payları periyodik yenileyerek, saldırganın uzun sürede yeterli pay toplamasını engellemek.

---

## Bölüm 3: İki Alanın Birlikte Kullanımı ve Genel İlkeler

ZKP ve MPC sık sık **birlikte** kullanılır. Örneğin bir MPC protokolünde her taraf, "hesabı doğru yaptım" diye bir **ZKP** üreterek malicious güvenliği sağlayabilir. Ya da bir zk-rollup'ta ispat üretimi (proving) dağıtık bir MPC ile yapılabilir. Trusted setup törenleri de aslında bir MPC uygulamasıdır.

**Ortak savunma ilkeleri:**

- **Kendi kripton yazma (don't roll your own crypto):** Denetlenmiş, akademik incelemeden geçmiş kütüphane ve şemaları kullan. Bu alandaki hatalar sessizdir; "çalışıyor gibi görünmek" güvenli olmak demek değildir.
- **Varsayımları açık yaz:** Hangi sertlik varsayımı, hangi tehdit modeli, hangi threshold, hangi setup güveni? Belgesiz varsayım kırılacak varsayımdır.
- **Bağımsız denetim ve formal verification:** Özellikle circuit'ler ve protokol implementasyonları için.
- **Negatif test kültürü:** "Geçmesi gerekenler geçiyor" yetmez; "geçmemesi gerekenler gerçekten reddediliyor mu?" asıl sorudur — soundness burada yaşar.
- **Kuantum ufkunu hesaba katmak:** Uzun ömürlü gizlilik için post-quantum dayanıklılığı planlamak.

## Özet

ZKP, "bilgiyi vermeden bilgiye sahip olduğunu kanıtlama" problemini; MPC, "girdini gizli tutarak birlikte hesaplama" problemini çözer. zk-SNARK küçük/hızlı ama çoğu zaman trusted setup ve pairing bağımlıdır; zk-STARK setup gerektirmez ve kuantuma daha dirençlidir ama ispatları büyüktür. MPC'nin güvenliği tehdit modeline (semi-honest / malicious) ve threshold + collusion varsayımlarına bağlıdır. Her iki alanda da en tehlikeli hatalar **sessizdir**: eksik kısıtlanmış devreler, eksik Fiat–Shamir transkripti, yanlış tehdit modeli, çıktı sızıntısı ve collusion. Savunmanın kalbi denetim, formal verification, negatif test, varsayımların açık belgelenmesi ve güvenin gerçekten dağıtılmış olmasıdır.
