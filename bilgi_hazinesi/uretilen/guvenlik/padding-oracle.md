# Padding Oracle Saldırıları

## Tanım

Padding oracle saldırısı, bir kriptografik sistemin bir şifreli metni (ciphertext) çözerken **padding**'in (dolgu baytlarının) geçerli olup olmadığını saldırgana sızdırmasından faydalanan bir saldırı sınıfıdır. Saldırgan, şifreleme anahtarını hiç bilmeden, yalnızca sistemin "padding geçerli mi, değil mi?" sorusuna verdiği evet/hayır cevabını (bu cevaba **oracle** denir) tekrar tekrar sorgulayarak, blok tabanlı bir şifreleme ile korunan düz metni (plaintext) bayt bayt kurtarabilir. Aynı oracle, tersine çevrilerek istenilen düz metnin geçerli bir şifreli metnini üretmek için de kullanılabilir.

Bu saldırı, kriptografideki en zarif ve öğretici zafiyetlerden biridir; çünkü matematiksel olarak kırılmayan bir şifreleme algoritmasının (örneğin AES), yanlış kullanıldığında pratikte nasıl işe yaramaz hale geldiğini gösterir. Anahtar hiç ele geçmez; ele geçen şey, protokolün davranışıdır.

Klasik hedef, **CBC (Cipher Block Chaining)** modunda çalışan blok şifrelerdir ve **PKCS#7** padding şemasıdır. Bu ikisinin birleşimi, on yıllardır TLS'ten VPN'lere, framework cookie'lerinden mesajlaşma protokollerine kadar her yerde kullanılmıştır ve padding oracle saldırısını mümkün kılan yapısal özellikleri taşır.

## Kök Neden: CBC ve PKCS#7'nin Çalışma Mantığı

Saldırının neden mümkün olduğunu anlamak için önce iki kavramı sağlam oturtmak gerekir: CBC modunun şifre çözme mekaniği ve padding'in ne işe yaradığı.

### Blok şifreleme ve neden padding'e ihtiyaç var

AES gibi blok şifreleri, veriyi sabit boyutlu bloklar halinde işler (AES için 16 bayt = 128 bit). Ancak şifrelenecek düz metin nadiren tam olarak blok boyutunun katıdır. 30 baytlık bir mesajı 16'şar baytlık bloklara böldüğünüzde, ikinci blokta 2 bayt eksik kalır. İşte bu boşluğu doldurmak için **padding** eklenir.

PKCS#7 padding şeması şunu söyler: eksik kalan bayt sayısı kadar, o sayıyı bayt değeri olarak yaz. Yani 1 bayt eksikse `0x01` ekle; 2 bayt eksikse `0x02 0x02` ekle; 5 bayt eksikse `0x05 0x05 0x05 0x05 0x05` ekle. Kritik ve genellikle şaşırtıcı olan kural şudur: eğer veri zaten blok boyutunun tam katıysa, **tam bir blok dolusu padding** eklenir (16 bayt için `0x10` değerinde 16 bayt). Bunun nedeni, çözme tarafının padding'in nerede başladığını her zaman kesin olarak bilebilmesi gerektiğidir; padding hiç yoksa son baytın gerçek veri mi yoksa padding mi olduğu belirsiz kalırdı.

Çözme tarafında sistem son baytı okur, diyelim `0x03`, ve "demek ki son 3 baytın hepsi `0x03` olmalı" der. Bunları kontrol eder ve doğruysa atar. **Geçerli padding budur.** Eğer son bayt `0x03` ama ondan önceki baytlar `0x03` değilse, padding **geçersizdir** ve sistem hata verir. Saldırının bel kemiği tam olarak bu hata sinyalidir.

### CBC şifre çözmenin matematiği

CBC modunda şifreleme zincirlemedir: her düz metin bloğu, şifrelenmeden önce bir önceki şifreli metin bloğu ile XOR'lanır. İlk blok için önceki blok olmadığından, rastgele bir **IV (Initialization Vector)** kullanılır.

Bizi asıl ilgilendiren şifre çözmedir. C[i] i'inci şifreli metin bloğu, P[i] i'inci düz metin bloğu, D() blok şifresinin ham çözme fonksiyonu (anahtarla) olsun. CBC çözme kuralı şudur:

```
P[i] = D(C[i]) XOR C[i-1]
```

Yani bir düz metin bloğu iki şeyin XOR'udur: o bloğun ham çözümü, ve **bir önceki şifreli metin bloğu.** İşte saldırının kaldıraç noktası burasıdır. `D(C[i])` sabittir çünkü anahtar sabittir; saldırgan bunu bilmese de **değiştiremez.** Ama `C[i-1]` şifreli metnin bir parçasıdır ve saldırgan onu **tamamen kontrol edebilir.** Şifreli metin, ağdan geçen ya da cookie'de duran bir veridir; onu istediği gibi değiştirebilir.

Sonuç: saldırgan `C[i-1]`'i istediği gibi oynatarak, `P[i]`'nin çözülen değerini de öngörülemez ama **kontrollü** biçimde değiştirebilir. Belirli bir baytı değiştirdiğinde çözülen düz metnin karşılık gelen baytı da XOR ilişkisiyle değişir. Saldırgan `P[i]`'nin gerçek değerini görmez, ama padding'in geçerli olup olmadığını oracle'dan öğrenir. Bu iki bilgiyi birleştirmek düz metni kurtarmaya yeter.

## Hata Sızıntısı: Oracle Tam Olarak Nedir?

"Oracle" kelimesi burada kritik. Oracle, saldırganın istediği kadar sorgulayabildiği, her seferinde tek bit bilgi (geçerli/geçersiz) döndüren bir kâhindir. Sorun şu ki, uygulamalar bu tek biti farkında olmadan sızdırır. Sızıntının biçimleri çeşitlidir:

- **Açık hata mesajı:** En saf hali. Uygulama "padding hatası" veya "bad decrypt" gibi bir mesaj döndürür; başka bir hatada farklı bir mesaj (örneğin "geçersiz oturum"). Saldırgan bu iki mesajı ayırt edebiliyorsa oracle hazırdır.
- **Farklı HTTP durum kodu:** Padding geçersizse 500, geçerli ama içerik hatalıysa 200 veya 403. Kodların farklılaşması yeterlidir.
- **Zamanlama farkı (timing side channel):** En sinsi olanı. Uygulama padding'i kontrol eder, geçerliyse mesajın devamını (örneğin MAC'i) doğrular. Geçersiz padding erken döner, geçerli padding daha uzun sürer. Saldırgan mesaj içeriğini görmese, hata kodları aynı olsa bile, **cevap süresini** ölçerek oracle'ı yeniden inşa eder. Bu, "generic error message döndürüyorum, güvendeyim" sanan sistemleri de vurur.
- **Bağlantı davranışı:** TLS gibi protokollerde padding hatası bağlantıyı belirli bir aşamada kapatabilir, başka hata farklı aşamada. Fark gözlemlenebiliyorsa oracle vardır.

Buradaki kök sorun mimaridir: sistem **çözme ile bütünlük doğrulamasını (authentication) ayrı ve gözlemlenebilir aşamalar** halinde yapmaktadır. Padding kontrolü, MAC kontrolünden önce ve ondan bağımsız olarak sonuç sızdırır. Doğru tasarım, düz metnin bütünlüğü doğrulanmadan padding hakkında **hiçbir** ayırt edilebilir davranış üretmemektir.

## Düz Metin Kurtarma: Adım Adım Sömürü Mantığı

Şimdi saldırının kalbine, bir baytın nasıl kurtarıldığına gelelim. İki şifreli metin bloğu düşünelim: saldırgan `C1`'i (önceki blok) manipüle ederek `C2`'nin çözülmesini etkiler. Amacımız `P2` bloğunun içeriğini öğrenmek.

Hatırlayalım: `P2 = D(C2) XOR C1`. Saldırgan `D(C2)`'yi bilmez ama sabittir. `C1`'i kontrol eder. Saldırgan araya kendi ürettiği bir `C1'` bloğu koyar (buna hesaplama bloğu diyelim) ve şu şekilde saldırır:

**Son baytı kurtarma.** Saldırgan `C1'`'in son baytını `0x00`'dan `0xFF`'e kadar 256 olası değerin hepsiyle dener ve her denemeyi oracle'a gönderir. Sunucu çözme yaptığında, ara değer diyeceğimiz `I2 = D(C2)` sabit kalır, ama görünen düz metin `P2' = I2 XOR C1'` olur. Saldırgan öyle bir son bayt arar ki, çözülen bloğun son baytı `0x01` olsun — çünkü tek baytlık geçerli PKCS#7 padding budur. Oracle "geçerli padding" dediğinde, saldırgan şunu bilir:

```
I2[son] XOR C1'[son] = 0x01
```

Buradan `I2[son] = C1'[son] XOR 0x01` çıkar. Ara değerin son baytı artık bilinmektedir. Ve gerçek düz metin baytı da `P2[son] = I2[son] XOR C1[son]` (C1 gerçek, orijinal önceki bloktur). Böylece **anahtarı hiç bilmeden bir düz metin baytı kurtarıldı.**

**Bir önceki baytı kurtarma.** Şimdi saldırgan iki baytlık geçerli padding'i, yani `0x02 0x02`'yi hedefler. Bilinen son bayt için `C1'`'in son baytını, çözülen son baytı `0x02` yapacak şekilde ayarlar (`C1'[son] = I2[son] XOR 0x02`; `I2[son]` artık bilindiği için bu hesaplanabilir). Sonra sondan bir önceki baytı yine 256 değerle dener, ta ki oracle geçerli padding (`0x02 0x02`) diyene kadar. Aynı XOR mantığıyla ara değerin o baytı da çözülür.

Bu döngü blok boyunca soldan sağa değil, sağdan sola ilerler; her adımda hedef padding değeri bir artar (`0x03 0x03 0x03`, `0x04...` diye) ve her yeni bayt için en fazla 256 sorgu gerekir. Bir bloğu (16 bayt) kurtarmak ortalama olarak 16 x 128 civarı sorgu, en kötü ihtimalle 16 x 256 = 4096 sorgu ister. Tüm mesaj için bu, blok sayısıyla çarpılır. Bu, kriptografik olarak devasa bir zafiyettir: pratikte dakikalar içinde, tam otomatik araçlarla tüm düz metin dökülür.

Dikkat edilmesi gereken bir incelik: son baytı ararken bazen `0x01` yerine tesadüfen daha uzun bir geçerli padding'e denk gelinebilir (örneğin çözülen son iki bayt zaten `0x02 0x02` çıkarsa). Sağlam saldırı kodu bunu, bir önceki baytı da oynatıp geçerliliğin bozulup bozulmadığını test ederek eler. Bu detay, saldırının pratikte neden bazen ekstra sorgu gerektirdiğini açıklar.

### Sömürünün ikinci yüzü: seçilmiş düz metin şifreleme

Aynı oracle tersine de çalışır. Saldırgan bir bloğun ara değerini `I2 = D(C2)` tamamen kurtardıysa, **istediği** bir düz metin `P*` için geçerli bir önceki blok üretebilir: `C1* = I2 XOR P*`. Bu, saldırganın anahtar olmadan **kendi seçtiği içeriği şifreleyip** sisteme geçerli, imzalıymış gibi kabul ettirebilmesi demektir. Örneğin bir yetkilendirme cookie'sinde `role=user`'ı `role=admin`'e çevirebilir. Bu yönü genellikle küçümsenir ama bazen düz metin okumaktan daha yıkıcıdır; çünkü doğrudan yetki yükseltmeye (privilege escalation) yol açar.

## Somut Örnekler ve Tarihsel Bağlam

Padding oracle kavramı 2002'de Serge Vaudenay tarafından formel olarak ortaya konuldu ve yıllar içinde büyük gerçek dünya saldırılarına dönüştü:

- **Web framework cookie'leri:** Şifreli ve seri hale getirilmiş (serialized) durum verisini CBC ile cookie'de taşıyan uygulama çatıları, klasik hedeftir. Meşhur bir vakada, bir web platformunun şifreli view state / hata sayfası davranışı bir padding oracle sunuyordu; saldırgan bununla makine anahtarını dolaylı olarak kötüye kullanacak seviyede içerik üretebiliyordu. **POET / "Padding Oracle Exploit Tool"** türü araçlar bu sınıfı otomatikleştirdi.

- **TLS'te Lucky 13:** TLS'in CBC cipher suite'lerinde, MAC-then-encrypt yapısı ve HMAC hesaplamasındaki zamanlama farkları nedeniyle bir zamanlama tabanlı padding oracle keşfedildi. Sabit zamanlı düzeltmeler bile kusursuz uygulanması çok zor olduğu için, bu, CBC cipher suite'lerinin modern TLS'te terk edilmesinin bir sebebidir.

- **POODLE (SSL 3.0):** SSL 3.0'ın padding'in içeriğini değil yalnızca uzunluğunu doğrulaması, bir downgrade saldırısıyla birleşince, HTTPS oturumlarından bayt bayt veri (örneğin oturum cookie'leri) sızdırılmasına imkân verdi. Bu, SSL 3.0'ın nihai olarak devre dışı bırakılmasının doğrudan nedeni oldu.

Bu vakaların ortak dersi nettir: zafiyet AES veya RSA'da değil, **modun ve padding'in bütünlük doğrulamasından kopuk biçimde uygulanmasındadır.** Algoritma sağlamdır; protokol katmanı sızdırır.

Not: Yukarıdaki isimler (Lucky 13, POODLE, Vaudenay 2002) yerleşik ve doğrulanmış kavramlardır. Belirli ürün sürüm numaralarını veya kesin CVE kimliklerini burada bilerek anmıyorum; çünkü saldırının öğretici değeri mekanizmadadır, spesifik numaralarda değil ve yanlış numara vermektense mekanizmayı anlatmak daha doğrudur.

## Savunma: Neden ve Nasıl

Padding oracle saldırısına karşı savunmanın tek bir sağlam felsefesi vardır: **çözme, düz metnin bütünlüğü kriptografik olarak doğrulanana kadar hiçbir gözlemlenebilir bilgi üretmemelidir.** Bunu sağlamanın somut yolları şunlardır.

### 1. Authenticated Encryption (AEAD) kullan

En doğru ve modern çözüm, CBC + ayrı MAC ikilisini tamamen bırakıp **AEAD** modlarına geçmektir: **AES-GCM** veya **ChaCha20-Poly1305.** Bu modlar şifreleme ile bütünlüğü tek bir kriptografik işlemde birleştirir. Çözme, doğrulama etiketini (authentication tag) kontrol eder; etiket geçmezse çözme daha padding aşamasına **hiç gelmeden** başarısız olur ve tek tip bir "doğrulama başarısız" cevabı döner. Padding kavramı GCM'de bloğa dayalı biçimde yoktur (stream benzeri çalışır), dolayısıyla klasik padding oracle yüzeyi ortadan kalkar. "Neden AEAD?" sorusunun cevabı budur: zafiyeti yamalamak yerine, zafiyetin doğduğu tasarım boşluğunu kapatır.

### 2. CBC kullanılıyorsa: Encrypt-then-MAC

Mevcut bir sistem CBC'den vazgeçemiyorsa, düzen **Encrypt-then-MAC** olmalıdır: önce düz metin şifrelenir, sonra **şifreli metnin tamamının** (IV dahil) üzerinden bir MAC (örneğin HMAC-SHA-256) hesaplanır. Çözme tarafında **önce MAC doğrulanır;** MAC geçmezse mesaj daha çözülmeden reddedilir, padding'e hiç bakılmaz. Saldırganın manipüle ettiği her şifreli metin, doğru anahtar olmadan geçerli bir MAC üretemeyeceği için oracle'a hiç ulaşamaz. MAC-then-encrypt (önce MAC'le sonra şifrele) ve Encrypt-and-MAC yapıları bu güvenceyi vermez ve Lucky 13 türü sorunlara zemin hazırlar; sıra önemlidir.

### 3. Sabit zamanlı ve tek tip hata davranışı

Eğer bir sebeple MAC doğrulaması çözmeden önce yapılamıyorsa (ki bundan kaçınılmalıdır), padding kontrolü ile diğer tüm doğrulamalar **sabit zamanlı (constant-time)** olmalı ve tüm başarısızlık yolları **ayırt edilemez** tek bir cevaba yönelmelidir: aynı hata mesajı, aynı HTTP kodu, aynı işlem süresi, aynı bağlantı davranışı. Bu son derece kırılgan bir yaklaşımdır çünkü zamanlamayı gerçekten sabitlemek işlemci önbelleği, dallanma tahmini ve çalışma zamanı optimizasyonları yüzünden pratikte neredeyse imkânsızdır. Bu yüzden bu, birincil savunma değil, ancak son çare bir katman olmalıdır.

### 4. IV yönetimi ve anahtar hijyeni

CBC için IV her mesajda rastgele ve öngörülemez olmalı, MAC kapsamına dahil edilmeli ve asla tekrar kullanılmamalıdır. Farklı amaçlar için farklı anahtarlar kullanılmalı (şifreleme anahtarı ile MAC anahtarı ayrı olmalı, key separation), böylece bir katmandaki zafiyet diğerine sıçramaz.

## Yaygın Hatalar

Padding oracle zafiyetleri genellikle iyi niyetli ama yanılgılı kararlardan doğar. En sık görülenler:

- **"Generic error mesajı döndürüyorum, güvendeyim" yanılgısı.** Hata mesajını tek tipleştirmek gerekli ama yeterli değildir. Zamanlama, bağlantı davranışı ve kaynak tüketimi hâlâ sızdırabilir. Oracle'ı yok etmenin yolu mesajı gizlemek değil, saldırganın manipüle ettiği veriyi **daha çözmeden reddetmektir.**

- **Şifreleme var ama bütünlük doğrulaması yok.** MAC veya AEAD olmadan sadece CBC ile şifrelemek, en yaygın ve en tehlikeli hatadır. Şifreleme gizlilik sağlar, bütünlük sağlamaz; ikisi ayrı güvence gerektirir. "Şifrelidir öyleyse güvenlidir" cümlesi kriptografide yanlıştır.

- **Yanlış sıra: MAC-then-encrypt veya Encrypt-and-MAC.** Bütünlük eklendiği halde sıralama yanlış olduğunda, çözme yine de saldırgan verisi üzerinde padding kontrolü yapmak zorunda kalır ve zamanlama oracle'ı geri gelir.

- **IV'nin öngörülebilir veya sabit olması.** Öngörülebilir IV, ilk blok üzerinde ek saldırı yüzeyi açar ve chosen-plaintext saldırılarını kolaylaştırır.

- **Kendi kripto katmanını yazmak.** Padding kontrolünü, MAC karşılaştırmasını veya IV üretimini elle yazmak, sabit zamanlı karşılaştırma gibi incelikleri kaçırmaya çok müsaittir. Örneğin MAC'i basit bir bayt bayt eşitlik döngüsüyle karşılaştırmak, erken çıkış nedeniyle yeni bir zamanlama oracle'ı yaratır.

- **Zafiyeti sadece "hata mesajını kapatarak" kapattığını sanmak.** Log'lara düşen, ölçülebilen ya da davranışsal her fark potansiyel bir oracle'dır. Kapsamlı düşünmek gerekir.

## En İyi Pratikler

Özetle, sağlam bir kriptografik mesaj işleme katmanı şu ilkelere yaslanmalıdır:

1. **Varsayılan olarak AEAD.** Yeni sistemlerde AES-GCM veya ChaCha20-Poly1305 seç. CBC + manuel padding'e ancak zorunlu uyumluluk sebebiyle dokun.
2. **Bütünlüğü asla ayrı düşünme.** Her şifreli metin, çözülmeden önce kriptografik olarak doğrulanmalı. AEAD bunu içerir; CBC kullanılıyorsa Encrypt-then-MAC ile açıkça sağla.
3. **Saldırgan verisini çözmeden reddet.** MAC doğrulaması, çözme ve padding kontrolünden **önce** gelmeli; böylece oracle'a giden yol daha başında kapanır.
4. **Olgun kütüphanelere güven.** İyi denetlenmiş kriptografi kütüphanelerinin yüksek seviyeli AEAD API'lerini kullan; padding, IV, sabit zamanlı karşılaştırma gibi detayları elle uygulama.
5. **Hata yollarını tek tipleştir — ama tek savunman bu olmasın.** Mesaj, kod, süre ve davranış açısından ayırt edilemez başarısızlık, derinlemesine savunmanın (defense in depth) bir katmanı olarak kalsın.
6. **IV ve anahtar hijyeni.** Rastgele IV, IV'yi MAC kapsamına al, tekrar kullanma; şifreleme ve MAC için ayrı anahtarlar.
7. **Eski protokolleri devre dışı bırak.** SSL 3.0 ve TLS'in CBC tabanlı cipher suite'leri gibi bilinen zafiyetli yapıları kapat; modern TLS ve AEAD suite'lerini zorunlu kıl.
8. **Sömürüyü zihninde çift yönlü düşün.** Bir oracle sadece düz metin okumaya değil, seçilmiş düz metin şifrelemeye (yetki yükseltmeye) de yol açar. Tehdit modelini iki yönü de kapsayacak biçimde kur.

Sonuç olarak padding oracle saldırısı, "güçlü algoritma seçmek yeterli değildir; onu doğru moda, doğru bütünlük güvencesiyle ve gözlemlenebilir davranış sızdırmadan uygulamak asıldır" dersinin en somut kanıtıdır. Modern reçete kısadır: **şifrele-sonra-doğrula veya doğrudan AEAD kullan, ve saldırganın dokunduğu hiçbir veriyi bütünlüğünü ispatlamadan çözme.**
