# Homomorfik Şifreleme (Kısmi/Tam - FHE) ve Gizlilik Korumalı Hesaplama

## Giriş ve Neden Önemli

Klasik şifrelemede bir veriyi işlemek istediğinizde onu önce **decrypt** etmeniz gerekir. Yani sunucu, bulut sağlayıcısı ya da hesaplamayı yapan taraf, veriyi açık haliyle (**plaintext**) görür. Bu, çoğu gizlilik ihlalinin kök nedenidir: veri "kullanımda" (**in-use**) korumasızdır. Şifreleme genelde iki durumu korur — veri "durağan" (**at-rest**, diskte) ve "aktarımda" (**in-transit**, ağda) iken. Üçüncü ve en zor durum olan **in-use** koruması, işte homomorfik şifrelemenin çözmeye çalıştığı problemdir.

**Homomorphic Encryption (HE)**, şifreli veri üzerinde şifreyi hiç açmadan matematiksel işlem yapmayı sağlar. Sonuç yine şifrelidir; ancak yalnızca özel anahtara (**secret key**) sahip taraf onu açtığında, sanki açık veriler üzerinde işlem yapılmış gibi doğru sonucu elde eder.

Bu konu bulut hesaplama, gizlilik korumalı makine öğrenmesi (**privacy-preserving ML**), sağlık verisi analizi ve düzenleyici (KVKK, GDPR, HIPAA) kısıtların olduğu senaryolarda giderek daha kritik hale geliyor. Güvenlik uzmanı açısından hem savunma aracı (veriyi işlerken bile ifşa etmemek) hem de doğru anlaşılması gereken bir mekanizma; çünkü yanlış kurgulandığında sağladığı garantiler tamamen çöker.

## Temel Tanımlar

### Homomorfizm nedir?

Matematikte **homomorphism**, bir yapıyı koruyan bir eşleme demektir. Eğer `E` şifreleme fonksiyonu ise ve şu özellik varsa şifreleme homomorfiktir:

```
E(a) ⊕ E(b) = E(a + b)
```

Yani şifreli metinler üzerinde tanımlı bir işlem (`⊕`), açık metinler üzerindeki işleme (`+`) karşılık gelir. Anahtar olmadan işlemi yapan taraf `a` ve `b` değerlerini asla göremez; sadece `E(a)` ve `E(b)` üzerinde çalışır ve `E(a+b)` üretir.

### Türler: PHE, SHE, FHE

Homomorfik şifreleme yeteneğine göre üç kademeye ayrılır:

- **PHE (Partially Homomorphic Encryption)**: Yalnızca **tek tür** işlemi (ya toplama ya çarpma) sınırsız sayıda destekler. Örnekler: **RSA** (çarpımsal homomorfik — ham haliyle, padding olmadan), **ElGamal** (çarpımsal), **Paillier** (toplamsal). Paillier özellikle elektronik oylama ve gizli toplama senaryolarında yaygındır.
- **SHE / SWHE (Somewhat Homomorphic Encryption)**: Hem toplama hem çarpmayı destekler ama **sınırlı derinlikte**. Belirli sayıda işlemden sonra biriken gürültü sonucu bozar. **Leveled HE** de bu kategorinin pratik bir varyantıdır — önceden belirlenen bir devre derinliğine (**circuit depth**) kadar çalışır.
- **FHE (Fully Homomorphic Encryption)**: Hem toplama hem çarpmayı **keyfi (arbitrary) derinlikte** destekler. Teorik olarak şifreli veri üzerinde herhangi bir hesaplamayı (herhangi bir devreyi) çalıştırabilir. İlk uygulanabilir FHE şeması **Craig Gentry** tarafından 2009'da doktora tezinde ortaya konmuştur ve alanın miladıdır.

Toplama ve çarpma üzerinden her şeyin ifade edilebilmesinin sebebi şudur: her Boolean/aritmetik devre, `+` ve `×` (ya da XOR ve AND) kapılarıyla kurulabilir. İkisini birden keyfi derinlikte yapabiliyorsanız, teorik olarak her programı şifreli çalıştırabilirsiniz.

## Kök Neden ve Çalışma Mantığı

### Neden gürültü (noise) var?

Modern FHE şemaları güvenliğini **lattice-based** (kafes tabanlı) zor problemlere, özellikle **LWE (Learning With Errors)** ve onun halka varyantı **Ring-LWE**'ye dayandırır. Bu şemalarda şifreleme sırasında ciphertext'e kasıtlı olarak küçük bir rastgele **hata / gürültü** eklenir. Bu gürültü güvenliğin temelidir: gürültü olmadan LWE denklemleri kolayca çözülür ve şifre kırılır.

Sorun şu: her homomorfik işlem bu gürültüyü büyütür.

- **Toplama** gürültüyü yaklaşık olarak toplar (yavaş büyür).
- **Çarpma** gürültüyü çok daha hızlı büyütür (çarpımsal etki).

Gürültü belli bir eşiği aşarsa, decrypt sırasında doğru plaintext'i geri kurtaramazsınız. İşte SHE'nin "sınırlı derinlik" kısıtı buradan gelir.

### Bootstrapping: FHE'yi mümkün kılan fikir

Gentry'nin dahiyane katkısı **bootstrapping**'dir. Fikir şudur: gürültü kritik seviyeye ulaşmadan önce, ciphertext'i "yenile". Bunu yapmak için **decryption işleminin kendisini homomorfik olarak çalıştırırsınız**.

Yani decryption devresini, secret key'in **şifrelenmiş halini** (encrypted secret key, `bootstrapping key`) kullanarak ciphertext üzerinde homomorfik olarak işletirsiniz. Sonuç: aynı plaintext'i taşıyan ama gürültüsü sıfırlanmış (aslında sabit, düşük bir seviyeye çekilmiş) yeni bir ciphertext. Bu sayede işlemlere sonsuza dek devam edebilirsiniz — SHE, FHE'ye dönüşür.

Bootstrapping FHE'nin hem kalbi hem de en pahalı adımıdır. Tarihsel olarak inanılmaz yavaştı (tek bir işlem dakikalar sürebiliyordu); bugün **TFHE** gibi şemalarda milisaniyeler seviyesine indi ama hâlâ açık hesaplamaya kıyasla devasa bir yük (overhead) taşır.

### Belli başlı şema aileleri

Farklı şemalar farklı veri türleri ve iş yükleri için optimize edilmiştir:

- **BGV** ve **BFV**: Tamsayı (integer) aritmetiği için uygundur; **batching / SIMD** (tek ciphertext içinde birçok değeri paralel işleme) destekler. Kesin (exact) aritmetik isteyen senaryolarda tercih edilir.
- **CKKS**: **Yaklaşık (approximate)** aritmetik yapar; ondalıklı / gerçek sayılar ve makine öğrenmesi iş yükleri için idealdir. Sonuç bilerek küçük bir hata payı taşır — bu, ML'de genelde kabul edilebilir bir maliyettir. Encrypted inference için en popüler şemadır.
- **TFHE / FHEW**: Çok hızlı bootstrapping ve Boolean/bit düzeyi işlemler, keyfi fonksiyonların **lookup table** ile hesaplanması için güçlüdür. Programlanabilir bootstrapping ile karmaşık aktivasyon fonksiyonları uygulanabilir.

### Anahtar türleri

FHE'de tek bir anahtar yoktur; tipik olarak:

- **Secret key**: Yalnızca veri sahibinde. Decrypt yeteneği verir. Asla sunucuya gitmez.
- **Public key**: Veriyi şifrelemek için (bazı şemalarda symmetric encryption da mümkün).
- **Evaluation / relinearization keys**: Sunucunun homomorfik çarpma sonrası ciphertext boyutunu küçültmesi (relinearization), döndürme (rotation) ve bootstrapping yapması için gereken **açık** yardımcı anahtarlar. Bunlar secret key'i ifşa etmez ama boyutları büyüktür (megabaytlar-gigabaytlar).

## Somut Örnek

Bir hastane, hasta verilerini bulutta bir ML modeliyle analiz etmek istiyor ama ham veriyi bulut sağlayıcısına açık halde vermek istemiyor (KVKK/HIPAA kısıtı).

Akış şöyle işler:

1. Hastane, hasta özniteliklerini (yaş, tahlil sonuçları vb.) kendi **secret key**'iyle CKKS altında şifreler: `E(veri)`.
2. Yalnızca şifreli veri `E(veri)` ve gerekli **evaluation keys** buluta gönderilir. Secret key hastanede kalır.
3. Bulut, model çıkarımını (**inference**) şifreli veri üzerinde çalıştırır. Matris çarpımları toplama ve çarpma ile; aktivasyonlar polinom yaklaşımlarla (örn. ReLU yerine düşük dereceli polinom) gerçekleştirilir. Bulut sonucu asla açık göremez.
4. Bulut şifreli sonucu `E(tahmin)` hastaneye döndürür.
5. Hastane secret key ile decrypt eder ve `tahmin` değerini elde eder.

Bu süreçte bulut sağlayıcısı ne girdiyi ne çıktıyı ne de ara değerleri açık olarak görür. Gizlilik, kriptografik olarak garanti altındadır — güvene (trust) değil matematiğe dayanır.

Not: Aktivasyon fonksiyonlarının polinomla yaklaşılması FHE-ML'in tipik bir kısıtıdır; keyfi non-lineer fonksiyonlar (dallanma, karşılaştırma) doğrudan verimli değildir ve şemaya göre özel numaralar gerekir.

## Gizlilik Korumalı Hesaplamada FHE'nin Yeri

FHE, **Privacy-Enhancing Technologies (PET)** ailesinin bir üyesidir. Tek başına her sorunu çözmez; sıklıkla diğer tekniklerle karşılaştırılır ya da birlikte kullanılır:

- **Secure Multi-Party Computation (MPC)**: Birden çok tarafın, kendi girdilerini birbirine açmadan ortak bir fonksiyon hesaplaması. FHE genelde tek veri sahibi + güvenilmeyen işlemci senaryosuna, MPC ise çok taraflı senaryoya uyar. İkisi hibrit kullanılabilir.
- **Trusted Execution Environment (TEE)**: (Intel SGX, AMD SEV gibi) donanım tabanlı izole yürütme. Performansı FHE'den çok daha iyidir ama güveni **donanıma ve üreticiye** dayandırır; yan kanal (side-channel) saldırılarına karşı geçmişte kırılganlıklar görülmüştür. FHE ise güvenini donanıma değil matematiğe dayar.
- **Differential Privacy (DP)**: Çıktıya gürültü ekleyerek bireyin gizliliğini korur. FHE hesaplamanın **girdi/ara değerlerini** gizler; DP ise **çıktıdan** birey bilgisinin sızmasını engeller. Bunlar tamamlayıcıdır — FHE, DP'nin çözdüğü çıktı sızıntısını çözmez, DP de veriyi işlemcinin gözünden gizlemez.
- **Zero-Knowledge Proofs (ZKP)**: Bir iddiayı, altındaki veriyi ifşa etmeden ispatlama. FHE ile birleştirilerek hesaplamanın doğruluğu (integrity) ispatlanabilir.

Bu ayrımı bilmek kritik: FHE **gizliliği (confidentiality)** sağlar, tek başına **bütünlüğü (integrity)** garanti etmez. Yani güvenilmeyen sunucu veriyi göremez ama — ek önlem yoksa — yanlış hesaplama yapıp yanlış (ama şifreli) sonuç döndürebilir.

## Tespit ve Savunma

FHE bir "saldırı" değil bir savunma teknolojisidir; bu yüzden buradaki tespit/savunma başlığı, "FHE dağıtımını nasıl güvenli kurar ve doğrularım" ile "sağladığı garantilerin nasıl kırılabileceğini nasıl izlerim" etrafında döner.

### Doğru dağıtım (savunma) ilkeleri

- **Secret key izolasyonu**: Secret key kesinlikle işlemin yapıldığı güvenilmeyen ortama gitmemeli. Mimari gözden geçirmede kanıtlanması gereken birinci madde budur. Anahtar yönetimi (**KMS**, HSM) bu sistemin en zayıf halkasıdır — FHE matematiği kusursuz olsa da anahtar sızarsa her şey biter.
- **Parametre seçimi**: Güvenlik seviyesi (ör. 128-bit), gürültü bütçesi ve devre derinliği tutarlı seçilmeli. Yetersiz parametre, LWE probleminin pratikte çözülebilir hale gelmesi demektir. Standartlaşma için **HomomorphicEncryption.org** topluluğunun parametre güvenlik tavsiyeleri referans alınır. Parametreleri kendiniz uydurmayın; kütüphanenin güvenli varsayılanlarını ve topluluk tablolarını kullanın.
- **Kütüphane seçimi ve güncelliği**: Microsoft **SEAL**, **OpenFHE** (PALISADE'in halefi), IBM **HElib**, Zama **TFHE-rs / Concrete** gibi olgun, denetlenmiş kütüphaneleri tercih edin. Kendi kripto şemanızı yazmayın ("don't roll your own crypto" ilkesi FHE'de kat kat daha geçerlidir).
- **Bütünlük katmanı**: Confidentiality yeterli değilse, sonucun doğru hesaplandığını garanti etmek için verifiable computation / ZKP katmanı ekleyin. Aksi halde kötü niyetli sunucu **malleability**'den (ciphertext'lerin homomorfik olarak değiştirilebilir olması, ki bu şemanın doğası gereği vardır) yararlanarak sonucu manipüle edebilir.

### Bilinen saldırı ve tehdit sınıfları (tespit odaklı)

- **CKKS'e özgü decryption sızıntısı**: CKKS yaklaşık şema olduğundan, decrypt edilmiş sonuç paylaşıldığında içindeki artık gürültü, secret key hakkında bilgi sızdırabilir. Bu, akademik olarak gösterilmiş bir passive saldırı sınıfıdır ("IND-CPA^D" tehdit modeli tartışması). **Savunma**: decrypt sonucuna yayınlamadan önce ek gürültü ekleme (**noise flooding**) ya da sonucu doğrudan güvenilmeyen tarafa açık vermemek. Kütüphanenizin bu azaltmayı uygulayan sürümünü kullandığınızı doğrulayın.
- **Yan kanal (side-channel) saldırıları**: FHE implementasyonu zamanlama, güç tüketimi ya da bellek erişim desenleri üzerinden secret key ya da bootstrapping key hakkında bilgi sızdırabilir. **Tespit/savunma**: constant-time implementasyonlar, denetlenmiş kütüphaneler, hesaplamanın izole ortamda yapılması.
- **Reused randomness / parametre hataları**: Şifreleme sırasındaki rastgeleliğin yeniden kullanımı veya zayıf RNG, güvenliği çökertir. Kod incelemesinde entropi kaynağını denetleyin.
- **Yanlış tehdit modeli varsayımı**: FHE tipik olarak **honest-but-curious (semi-honest)** sunucuya karşı tasarlanmıştır — yani sunucu protokolü doğru izler ama meraklıdır. Sunucu **actively malicious** olabiliyorsa, bütünlük için ek mekanizma şarttır. Kurumun tehdit modelini FHE'nin sağladığı garantiyle eşleştirin.

### İzlenmesi gereken operasyonel sinyaller

- Beklenmedik yerlerde secret key materyalinin bulunması (log, config, evaluation key paketleri içinde).
- Evaluation/bootstrapping anahtarlarının yanlışlıkla secret key içermesi veya sızması.
- Gürültü bütçesinin izlenmemesi sonucu sessizce yanlış (ama şifreli) sonuçlar üretilmesi.
- Kütüphane sürümünün, bilinen bir kriptografik zafiyet için yamalanmamış olması.

## Yaygın Hatalar ve Yanılgılar

- **"FHE her şeyi çözer, artık hiçbir şeyi açmama gerek yok."** Yanlış. FHE confidentiality sağlar; integrity, çıktı gizliliği (DP), erişim kontrolü ve anahtar yönetimi ayrı problemlerdir. Tek başına bütüncül güvenlik değildir.
- **"FHE bugün için yeterince hızlı, her yerde kullanabilirim."** Aşırı iyimserlik. FHE, açık hesaplamaya kıyasla tipik olarak binlerce ila milyonlarca kat overhead getirir (iş yüküne ve şemaya göre değişir). Basit skorlama gibi dar iş yükleri pratik; ağır, dallanma yoğun genel amaçlı hesaplama çoğunlukla değil.
- **"CKKS kesin sonuç verir."** Hayır, CKKS **yaklaşık** aritmetik yapar. Kesin tamsayı sonucu istiyorsanız BGV/BFV ailesini düşünün.
- **"Evaluation key'i paylaşmak secret key'i sızdırır."** Hayır, bu anahtarlar tam da secret key'i ifşa etmeden hesaplamayı mümkün kılmak için tasarlanmıştır. Ancak boyutları büyüktür ve yanlış üretim/paylaşım hâlâ risk taşır.
- **"FHE = blockchain / kuantum-güvenli sihir."** FHE bağımsız bir tekniktir. Lattice-based şemaların birçoğu **post-quantum** dayanıklı adaylardır (LWE'nin kuantum bilgisayarlarca da zor olduğu varsayılır) ama bu otomatik bir "kuantum-güvenli" garantisi değildir; parametre ve şemaya bağlıdır.
- **"Bootstrapping opsiyoneldir."** Leveled/SHE senaryolarında önceden bilinen sığ devreler için bootstrapping'siz çalışabilirsiniz; ama **keyfi derinlikte** hesaplama (gerçek FHE) için bootstrapping zorunludur.
- **Parametreleri elle "optimize etmek."** Performans için güvenlik parametrelerini düşürmek, LWE'yi pratikte kırılabilir hale getirebilir. Bu, en sık yapılan ve en tehlikeli hatadır.

## Özet

Homomorfik şifreleme, verinin **kullanımdayken (in-use)** bile şifreli kalmasını sağlayarak klasik şifrelemenin bıraktığı en zor boşluğu doldurur. PHE tek işlem, SHE sınırlı derinlik, FHE ise **bootstrapping** sayesinde keyfi derinlikte hesaplama sunar. Güvenliği LWE/Ring-LWE lattice problemlerine dayanır ve her işlem gürültüyü büyütür — bu, hem güvenliğin kaynağı hem de mühendislik zorluğunun sebebidir.

Bir güvenlik uzmanı için doğru zihniyet şudur: FHE güçlü bir **gizlilik** aracıdır ama sihirli değildir. Sağladığı garantiyi (semi-honest'a karşı confidentiality) kurumun tehdit modeliyle eşleştirin, anahtar yönetimini birinci öncelik yapın, olgun kütüphaneleri ve topluluk-onaylı parametreleri kullanın, ve gerektiğinde bütünlük (ZKP/verifiable computation) ile çıktı gizliliği (DP) katmanlarını ekleyin. Performans overhead'i hâlâ gerçek bir kısıttır; teknolojiyi dar, yüksek değerli gizlilik senaryolarına uygulamak — her yere serpiştirmek yerine — bugün için en gerçekçi yaklaşımdır.
