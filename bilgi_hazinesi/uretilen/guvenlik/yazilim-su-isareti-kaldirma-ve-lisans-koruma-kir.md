# Yazılım Su İşareti Kaldırma ve Lisans Koruma Kırma (Keygen/Patch/Crackme Metodolojisi)

> **Eğitim amaçlı referans.** Bu belge, lisans doğrulama ve yazılım koruma mekanizmalarının **nasıl çalıştığını anlamak** ve buna karşı **savunma/tespit** kurmak için yazılmıştır. Amaç, bir savunmacının (yazılım geliştirici, tersine mühendislik eğitmeni, CTF hazırlayıcısı) saldırganın zihniyetini kavrayıp daha dayanıklı koruma tasarlamasıdır. Canlı bir saldırı reçetesi değildir; belirli bir üründeki korumayı adım adım kırma talimatı içermez.

## Konu ve Kapsam

Yazılım koruma kırma; ticari veya akademik yazılımlarda bulunan **lisans doğrulama (license validation)**, **seri numarası kontrolü (serial/registration check)**, **deneme süresi (trial/time-limit)** ve **yazılım su işareti (software watermarking)** gibi mekanizmaların tersine mühendislik (reverse engineering, RE) ile analiz edilmesi ve atlatılmasıdır. Klasik RE eğitiminin çekirdek konularından biridir; çünkü bir programın kontrol akışını (control flow), koşullu dallanmalarını (conditional branches) ve gizli algoritmalarını okumayı öğretir.

Saldırı yüzeyi açısından bu konu, **malware analizinden daha düşük önceliklidir**: sonuç genellikle ihlal edilen bir yazılımdır, uzaktan kod çalıştırma veya sistem ele geçirme değil. Yine de kavramsal olarak değerlidir; aynı beceriler kötü amaçlı yazılım analizinde, güvenlik açığı araştırmasında ve anti-tamper savunması geliştirmede kullanılır.

Bu alanın dört klasik kavramı vardır ve hepsi birbiriyle ilişkilidir:

- **Keygen (key generator)**: Doğrulama algoritmasını tersine çevirip geçerli seri üreten bağımsız araç.
- **Patch (binary patching)**: İkili dosyadaki bir kontrolü kalıcı olarak devre dışı bırakma.
- **Crackme**: Yasal, eğitim amaçlı hazırlanmış "beni kır" bulmacası; gerçek yazılıma dokunmadan RE pratiği için tasarlanır.
- **Software watermark**: İkiliye gömülü, sahibini/lisansını belirleyen gizli işaret; kaldırılması veya bozulması ayrı bir konudur.

---

## 1. Lisans Doğrulama Rutinleri: Çalışma Mantığı

### 1.1 Tanım

Bir lisans doğrulama rutini, kullanıcının girdiği veriyi (seri numarası, lisans anahtarı, aktivasyon kodu) alıp "geçerli mi?" sorusuna bir **boolean** cevap üreten koddur. En basit hâliyle şu iskelete indirgenir:

```
girdi = kullanicidan_al()
if dogrula(girdi) == true:
    kilidi_ac()      // tam sürüm, kayıtlı mod
else:
    reddet()         // deneme, uyarı, çıkış
```

### 1.2 Kök Neden: Kontrol İstemci Tarafında

Bu mekanizmaların temel zayıflığı basittir: **karar, saldırganın tam kontrolündeki makinede veriliyor.** Doğrulama fonksiyonu kullanıcının CPU'sunda çalışıyorsa, o kullanıcı fonksiyonu okuyabilir, izleyebilir (debug) ve değiştirebilir. Bu, "istemci tarafını asla güvenilir sayma" (never trust the client) ilkesinin bir örneğidir. Koruma ne kadar karmaşık olursa olsun, karar noktası yerelde kaldığı sürece teorik olarak atlatılabilir; iş yalnızca "ne kadar zahmetli" sorusuna dönüşür.

Doğrulama mantığı genellikle üç ailede toplanır:

1. **Karşılaştırma tabanlı (comparison-based)**: Girdi, hesaplanan veya sabit bir "doğru cevap" ile karşılaştırılır. Assembly'de sıklıkla bir `cmp` + koşullu atlama (`je`/`jne`/`jz`) örüntüsü olarak görünür.
2. **Dönüşüm tabanlı (transform-based)**: Girdi bir algoritmadan (checksum, hash, bit manipülasyonu, modüler aritmetik) geçirilir; sonucun belirli bir kısıtı sağlaması beklenir (ör. "hesaplanan değer belirli bir kalıba uymalı").
3. **Ağ/aktivasyon tabanlı (server-side)**: Doğrulama uzak sunucuda yapılır; istemci yalnızca sonucu alır. Bu, saldırının doğasını değiştirir (aşağıda 5. bölüm).

### 1.3 Örnek: Karşılaştırma Örüntüsünün Anatomisi

Kavramsal bir C benzeri sözde-kod:

```
int dogrula(char *seri) {
    long beklenen = hesapla_anahtar(kullanici_adi);  // isimden türetilen değer
    long girilen  = seriyi_sayiya_cevir(seri);
    return (girilen == beklenen);                     // tek kritik karşılaştırma
}
```

Derlendiğinde bu, tersine mühendisin aradığı klasik "chokepoint"tir: tek bir koşullu dallanma tüm kararı taşır. Disassembler'da (IDA, Ghidra, radare2/Cutter gibi araçlarla) bu nokta bulunur ve mantık okunur. Saldırganın iki temel yolu ayrılır burada:

- **Anlamak ve taklit etmek** → keygen.
- **Kararı zorla değiştirmek** → patch.

---

## 2. Keygenning: Algoritmanın Tersine Çevrilmesi

### 2.1 Tanım ve Mantık

**Keygen**, doğrulama algoritmasını *anlayıp* aynı kuralları uygulayarak geçerli seriler üreten programdır. Patch'ten felsefî olarak farkıdır: patch korumayı *deler*, keygen korumanın *dilini konuşur*. Bu yüzden keygenning, RE eğitiminde en saygı gören ve en zorlu beceri sayılır; çünkü ikilinin bir bölümünü basitçe atlatmayı değil, algoritmanın matematiğini yeniden kurmayı gerektirir.

### 2.2 Çalışma Süreci (Kavramsal)

1. **Doğrulama fonksiyonunu bulma**: Genellikle "geçersiz anahtar" gibi bir string'e referans arayarak veya girdi okuma çağrılarından geriye izleyerek.
2. **Algoritmayı çıkarma**: Fonksiyonun girdiyi hangi dönüşümlerden geçirdiğini (byte kaydırma, XOR, modüler aritmetik, tablo aramaları) statik okuma ve dinamik izleme ile belirleme.
3. **Kısıtı tanımlama**: "Geçerli" olmanın matematiksel koşulunu formülleştirme (ör. bir checksum'ın belirli bir değere eşit olması).
4. **Ters çözme**: Kısıtı sağlayan girdileri üreten kodu yazma. Eğer algoritma tek yönlü (hash gibi) ise, tam tersi yerine kısıtı sağlayan girdiler *aranır* veya üretilir.

### 2.3 Neden Bazı Şemalar Keygen'lenemez

Doğrulama; saldırganın sahip olmadığı bir **özel anahtara (private key)** dayalı imza doğrulaması yapıyorsa, keygen matematiksel olarak infeasible hâle gelir. Örneğin lisans, üreticinin özel anahtarıyla imzalanıp istemcide **açık anahtarla (public key)** doğrulanıyorsa, saldırganın geçerli imza üretmesi asimetrik kriptografiyi kırmayı gerektirir. Bu durumda saldırgan keygen'den vazgeçip **doğrulamanın kendisini patch'lemeye** yönelir; çünkü matematiği kırmak yerine kararı atlamak daha ucuzdur. Bu gözlem, savunma tasarımının anahtarıdır: güçlü kripto bile, karar noktası yerelde ve korumasızken tek başına yetmez.

---

## 3. Binary Patching: Kararı Zorla Değiştirme

### 3.1 Tanım

**Binary patching**, ikili dosyadaki (veya bellekteki) makine kodunu değiştirerek doğrulama kararını atlamaktır. Klasik örüntü, kritik koşullu atlamayı etkisiz hâle getirmektir: "geçersizse reddet" dallanmasını "her zaman geçerli say" hâline dönüştürmek. Bu genellikle bir koşullu atlamayı koşulsuza çevirerek, tersine çevirerek veya doğrulama çağrısını `NOP` (no-operation) ile boşa çıkararak yapılır; ya da fonksiyonun doğrudan "başarı" değeri döndürmesi sağlanır.

### 3.2 Kök Neden ve Kavram

Patch mümkündür çünkü doğrulama sonucu tek bir dallanmaya bağlıdır ve o dallanma değiştirilebilir. Kavramsal olarak: eğer "geçerli/geçersiz" kararı programın kontrol akışında **izole edilebilir tek bir noktaysa**, o nokta bir tek arıza noktasıdır (single point of failure). Patching iki biçimde olur:

- **Statik patch**: Diskteki dosya kalıcı olarak değiştirilir. Bu, dosyanın kriptografik bütünlük özetini (checksum/imza) bozar — tespit için önemli bir iz.
- **Runtime/bellek patch**: Program belleğe yüklendikten sonra bir loader veya enjekte edilen kod tarafından değiştirilir. Diskteki dosya bozulmaz; bu yüzden statik bütünlük kontrolünü atlatabilir ama process belleğinde iz bırakır.

### 3.3 Örnek: Kavramsal Dönüşüm

Sözde-assembly düzeyinde fikir:

```
; ÖNCE
call  dogrula          ; eax = 0 (geçersiz) veya 1 (geçerli)
test  eax, eax
jz    reddet           ; sıfırsa reddet dalına git

; PATCH SONRASI FİKRİ (kavramsal)
; - jz atlamasını kaldırmak/tersine çevirmek, veya
; - dogrula'yı her zaman 1 döndürecek şekilde kısaltmak
```

Buradaki eğitim noktası tek bir talimatın nasıl yazılacağı değil; **tek bir kontrol noktasının tüm güvenlik varsayımını taşımasının ne kadar kırılgan olduğudur.** Savunma, bu noktayı çoğaltmayı ve gizlemeyi gerektirir (bkz. 6. bölüm).

---

## 4. Crackme: Yasal Eğitim Ortamı

**Crackme**, RE öğrenmek için özel olarak hazırlanmış, telif hakkı sorunu olmayan bir bulmacadır. Yazarı bilerek bir koruma yerleştirir ("şu seriyi bul" veya "şu kontrolü atla") ve öğrenci bunu yasal biçimde çözer. Zorluk seviyeleri artar: basit string karşılaştırmasından, sanal makine tabanlı obfuscation'a (VM-based obfuscation) kadar.

Crackme'ler eğitimde kritiktir çünkü:

- Gerçek ticari yazılıma dokunmadan, **hukukî ve etik risk olmadan** beceri geliştirmeye izin verirler.
- Belirli bir tekniği (anti-debugging, packing, self-modifying code) izole edip öğretirler.
- CTF'lerin RE kategorisinin temelini oluştururlar.

Savunmacı için crackme yazmak da öğreticidir: kendi korumanı bir crackme gibi tasarlayıp saldırıya açık noktalarını görmek, tehdit modellemenin (threat modeling) pratik bir biçimidir.

---

## 5. Sunucu Tarafı Aktivasyon ve Sınırları

Karar sunucuya taşındığında (online activation, floating license, license server), saldırganın "kararı yerelde değiştirme" işi zorlaşır ama yeni yüzeyler doğar:

- **Emülasyon (server emulation)**: Saldırgan, gerçek lisans sunucusunun cevaplarını taklit eden sahte bir sunucu kurar; istemci "geçerli" cevabını yerelden alır.
- **Yanıt patch'leme**: İstemci, sunucudan gelen "geçersiz" cevabını "geçerli" olarak işleyecek şekilde patch'lenir — yani karar yine yerelde ele geçirilir.
- **Çevrimdışı kırma**: Sadece ilk aktivasyonda ağ gerektiren, sonra tamamen yerel çalışan yazılımlarda, aktivasyon-sonrası kontrol noktası hedeflenir.

Buradaki temel ders: sunucu tarafı doğrulama güvenliği artırır, ama yalnızca **kararın anlamlı bir kısmı gerçekten sunucuda kalıyorsa.** İstemci sonucu yerelde bir "if" ile yorumluyorsa, koruma yine o if'e indirgenir. Sağlam mimarilerde sunucu, sadece "evet/hayır" değil, programın çalışması için gereken **gerçek bir varlık** (veri, hesaplama sonucu, deşifre anahtarı) sağlar; böylece taklit veya patch tek başına yetmez.

---

## 6. Yazılım Su İşareti (Software Watermarking)

### 6.1 Tanım

**Software watermark**, bir ikiliye gömülen ve sahibini, alıcısını veya lisansını gizlice belirleyen işarettir. İki türü vardır:

- **Statik watermark**: Koda veya veriye gömülü, çalışmadan da tespit edilebilen işaret (ör. belirli sabitler, string düzenleri, veri yapıları).
- **Dinamik watermark**: Yalnızca program belirli bir girdiyle çalıştığında ortaya çıkan işaret (ör. özel bir seri girildiğinde oluşan bir bellek durumu veya çıktı).

Amaç genellikle **korsan kopyanın kaynağını izlemektir** (fingerprinting): sızan kopyada gömülü alıcı kimliği, ihlali kimin yaptığını gösterir.

### 6.2 Kaldırma Saldırıları ve Kök Neden

Watermark kaldırma dört kavramsal saldırıya karşı test edilir:

- **Subtractive (çıkarıcı)**: İşareti bulup silme.
- **Additive (ekleyici)**: İşaretin üstüne başka işaretler ekleyip orijinali belirsizleştirme.
- **Distortive (bozucu)**: Programı semantiğini bozmadan dönüştürüp (obfuscation, optimizasyon) işareti tanınmaz hâle getirme.
- **Collusion (birleşme)**: Aynı yazılımın farklı işaretli kopyalarını karşılaştırıp farkı — yani işareti — izole etme.

Kök neden: watermark, programın **çalışması için zorunlu olmayan** bir ek bilgiyse, teorik olarak çıkarılabilir. Dayanıklı watermark tasarımı, işareti programın doğru çalışması için gerekli mantıkla **iç içe geçirmeyi** hedefler; böylece kaldırma, işlevi de bozar. Bu "tamper-proofing" ile birleşen zor bir problemdir ve mükemmel çözümü yoktur.

---

## 7. Tespit ve Savunma

Savunma tarafında amaç, kırmayı *imkânsız* kılmak değil (yerel yürütmede bu mümkün değildir), **maliyeti fayda üstüne çıkarmak** ve **kırılma/ihlal olduğunda bunu tespit edebilmektir.**

### 7.1 Tespit (Detection)

- **İkili bütünlük kontrolü (integrity check / checksum)**: Program kendi kodunun kriptografik özetini çalışma anında hesaplar; statik patch bozulmayı ortaya çıkarır. Kontrolün kendisi de korunmalıdır (yoksa o da patch'lenir).
- **İmza doğrulama (code signing)**: İşletim sistemi düzeyinde imza kontrolü, değiştirilmiş ikilileri işaretler; kurumsal ortamda değiştirilen binary'leri tespit için değerlidir.
- **Anti-debugging telemetrisi**: Debugger varlığı, zamanlama anomalileri (timing checks) veya bilinen RE araçlarının izleri tespit edilip loglanabilir. Bunlar atlatılabilir ama saldırıyı yavaşlatır ve iz üretir.
- **Telemetri ve anomali tespiti**: Aynı lisans anahtarının imkânsız sayıda/coğrafyada kullanımı, sunucu tarafında keygen veya paylaşımı ele verir. Bu, en güçlü *pratik* tespitlerden biridir çünkü yerel korumaya değil, kullanım desenine bakar.
- **Watermark izleme**: Sızan kopyalarda gömülü fingerprint, kaynağı belirlemeye ve hukukî sürece kanıt sağlamaya yarar.
- **Honeypot serileri / canary değerler**: Bilerek "geçerli görünen ama işaretli" anahtarlar dağıtıp keygen çıktısıyla ayırt etmek.

### 7.2 Savunma (Defense-in-Depth)

- **Kararı tek noktadan dağıtma**: Doğrulamayı tek bir if'e bağlamak yerine, sonucu programın birden çok yerinde, gecikmeli ve dolaylı biçimde kullanmak. Böylece tek patch yetmez.
- **Sunucuya anlamlı iş taşıma**: Kritik veriyi/hesaplamayı/deşifre anahtarını sunucuda tutmak; istemcinin çalışması gerçekten sunucuya bağlı olsun.
- **Asimetrik kripto ile lisans imzalama**: Lisansı özel anahtarla imzalayıp istemcide açık anahtarla doğrulamak, keygen'i matematiksel olarak zorlaştırır (yeter ki doğrulama noktası da korunsun).
- **Obfuscation ve anti-tamper**: Kontrol akışını gizlemek, kritik mantığı VM'e taşımak, self-checking eklemek — hiçbiri kesin değildir ama maliyeti yükseltir.
- **Katmanlı yaklaşım**: Tek bir tekniğe güvenmemek. Her katman aşılabilir; birlikte pratik caydırıcılık sağlarlar.
- **İş modeli savunması**: Teknik korumanın sınırlarını kabul edip, güncelleme/bulut hizmeti/destek gibi *kopyalanamayan değer* etrafında model kurmak çoğu zaman en dayanıklı savunmadır.

---

## 8. Yaygın Hatalar

- **"Güçlü şifreleme = güçlü koruma" yanılgısı**: Kripto ne kadar iyi olursa olsun, "doğru/yanlış" kararını yerelde bir if ile veriyorsan, saldırgan kriptoyu değil o if'i hedefler. Kritik olan karar noktasının konumudur.
- **Tek kontrol noktası**: Tüm lisans mantığını tek bir fonksiyona/dallanmaya toplamak, saldırgana tek bir hedef verir. Dağıtık ve dolaylı kontrol daha dayanıklıdır.
- **Bütünlük kontrolünü korumamak**: Checksum eklemek ama checksum kontrolünün kendisini patch'lenebilir bırakmak, korumayı görünürde artırıp gerçekte artırmaz.
- **Anti-debug'a aşırı güven**: Anti-debugging ve packing, saldırıyı yavaşlatır ama kararlı bir analist için engel değildir; caydırıcılık aracı olarak görülmelidir, çözüm olarak değil.
- **Hata mesajı sızıntısı**: "Geçersiz seri" gibi benzersiz string'ler, saldırgana doğrulama fonksiyonuna giden doğrudan bir işaret sunar. Mesajları dolaylandırmak küçük ama etkili bir zorlaştırmadır.
- **Tespit yerine yalnız engellemeye odaklanma**: Yerel yürütmede engelleme sonlu; asıl kaldıraç, ihlali *tespit edip* (telemetri, watermark, anahtar paylaşımı analizi) yanıt verebilmektir.
- **Yasal/etik sınırı unutmak**: Eğitim ve savunma amacıyla RE öğrenmek meşrudur; başkasının yazılımının korumasını izinsiz kaldırıp dağıtmak birçok ülkede telif ve sözleşme ihlalidir. Pratik için **crackme** ve sahip olunan/izinli yazılımlar kullanılmalıdır.

---

## Özet

Yazılım lisans koruması kırma metodolojisi, tek bir kavram etrafında döner: **karar saldırganın makinesinde veriliyorsa, o karar teorik olarak değiştirilebilir.** Keygen algoritmayı anlayıp taklit eder, patch kararı zorla değiştirir, crackme bunları yasal olarak öğretir, watermark ise ihlalin kaynağını izler. Savunmacı için doğru zihniyet, kırılamazlık peşinde koşmak değil; **maliyeti yükseltmek, kararı yerelden anlamlı biçimde uzaklaştırmak ve her koşulda ihlali tespit edip yanıt verebilecek** katmanlı bir sistem kurmaktır. En dayanıklı koruma çoğu zaman teknik değil, kopyalanamayan hizmet değerine dayalı iş modelidir.
