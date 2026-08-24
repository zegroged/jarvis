# Cross-Platform Mobil Geliştirme (React Native / Flutter) Mimarisi ve Güvenlik Farkları

## Giriş: Neden Bu Konu Önemli?

Günümüz mobil uygulamalarının önemli bir kısmı artık saf native (Swift/Kotlin) yerine **cross-platform** çatılarla, yani React Native ve Flutter ile yazılıyor. Bu tercih tek bir kod tabanından hem iOS hem Android çıktısı üretme, geliştirme maliyetini düşürme ve hızlı iterasyon vaadinden geliyor. Ancak bu çatılar, native mimarilerden **temelde farklı çalışma modelleri** getirir; bu farklar hem performansı hem de güvenlik yüzeyini (attack surface) doğrudan etkiler.

Bir güvenlik veya tersine mühendislik (reverse engineering) analisti için kritik nokta şudur: bir uygulamanın **React Native mi, Flutter mı yoksa native mi** olduğunu tanımak, ona nasıl yaklaşılacağını belirler. React Native'de iş mantığı çoğunlukla okunabilir JavaScript olarak paketlenirken, Flutter'da her şey Dart'ın AOT (Ahead-of-Time) derlemesiyle native bir binary'e gömülür ve standart araçlarla çok daha zor analiz edilir. Bu makale, iki çatının mimarisini, aralarındaki güvenlik farklarını, tespit (detection) yöntemlerini ve savunma (hardening) önlemlerini kavramsal düzeyde ele alır.

---

## 1. React Native Mimarisi

### Tanım

React Native, Facebook (Meta) tarafından geliştirilen, JavaScript/TypeScript ile yazılan iş mantığının native UI bileşenlerini yönettiği bir çatıdır. Uygulama arayüzü web tabanlı değildir; JavaScript kodu, gerçek native view'ları (iOS'ta `UIView`, Android'de `View`) kontrol eder.

### Çalışma Mantığı: JavaScript Engine ve Bridge

React Native'in kalbi iki katmandan oluşur:

1. **JavaScript katmanı**: Uygulamanın iş mantığı, bir JavaScript motoru içinde çalışır. Geçmişte bu motor JavaScriptCore idi; modern sürümlerde Meta'nın geliştirdiği **Hermes** motoru varsayılan hale geldi. Hermes, JavaScript'i çalışma anında yorumlamak yerine **bytecode**'a önceden derler (precompile), böylece başlangıç süresi ve bellek kullanımı iyileşir.

2. **Native katman**: Gerçek platform bileşenleri, kamera, GPS, dosya sistemi gibi cihaz yeteneklerine erişen native modüller burada yaşar.

Bu iki katman birbirlerinin bellek alanını doğrudan paylaşmaz. Aralarındaki iletişim, tarihsel olarak **Bridge** adı verilen bir mekanizmayla yürütülür.

### Bridge (Köprü) Nedir ve Neden Vardır?

**Bridge**, JavaScript dünyası ile native dünya arasında mesaj taşıyan asenkron bir katmandır. JavaScript tarafı, "şu native fonksiyonu şu argümanlarla çağır" gibi komutları **serialize edilmiş** (genellikle JSON benzeri) mesajlar halinde köprüye verir; native taraf bu mesajları deserialize eder, işi yapar ve sonucu yine serialize ederek geri yollar.

Kök neden (kök neden/root cause) şudur: JavaScript motoru ile native runtime iki ayrı dünyadır ve doğrudan bellek erişimiyle konuşamazlar. Bridge bu ayrımı **asenkron, toplu (batched) ve serileştirilmiş** mesajlaşmayla çözer.

Bridge'in maliyeti de buradan doğar:
- Her geçiş bir **serialization/deserialization** yükü getirir.
- Yüksek frekanslı etkileşimlerde (örneğin her kare animasyon, hızlı kaydırma sırasında sürekli veri akışı) bu köprü bir **darboğaz (bottleneck)** olur.
- Asenkron olduğu için, senkron kesin zamanlı davranış gerektiren senaryolar zorlaşır.

### JSI ve Yeni Mimari (New Architecture)

React Native'in yeni mimarisi bu darboğazı azaltmak için **JSI (JavaScript Interface)** kavramını getirdi. JSI, JavaScript motoruna C++ nesnelerini doğrudan referans olarak tutabilme yeteneği kazandırır. Böylece JavaScript, bir native fonksiyonu köprüden serialize edilmiş mesaj göndermeden, neredeyse doğrudan çağırabilir.

Bu temel üzerine kurulan bileşenler:
- **TurboModules**: Native modüllerin JSI üzerinden tembel (lazy) ve doğrudan çağrılması.
- **Fabric**: Yeni UI katmanı; render işlemini daha verimli ve senkron yapabilen render sistemi.

Güvenlik açısından önemli olan şu: JSI ile geçiş daha hızlı olsa da, iş mantığının büyük kısmı hâlâ JavaScript/bytecode olarak paketlenir. Yani analiz edilebilirlik problemi büyük ölçüde devam eder.

---

## 2. Flutter Mimarisi

### Tanım

Flutter, Google'ın geliştirdiği, **Dart** dili ile yazılan bir çatıdır. React Native'den en temel farkı: Flutter native platform bileşenlerini kontrol etmez; kendi **render motoru** ile (tarihsel olarak Skia, sonraki nesilde Impeller) her pikseli kendisi çizer. UI, işletim sisteminin view'ları değil, Flutter'ın kendi tuvali (canvas) üzerinde oluşturulur.

### Çalışma Mantığı: Dart AOT Derlemesi

Flutter'ın güvenlik profilini belirleyen kritik nokta derleme modelidir:

- **Debug modunda** Dart, JIT (Just-in-Time) ile çalışır; sıcak yeniden yükleme (hot reload) bu sayede mümkündür.
- **Release modunda** Dart kodu **AOT (Ahead-of-Time)** ile **native makine koduna** derlenir. Sonuç, ARM/ARM64 (veya ilgili mimari) makine talimatları içeren bir binary'dir.

Bu, React Native ile Flutter arasındaki en keskin farktır. React Native'de iş mantığı yorumlanabilir/deserialize edilebilir bir bytecode veya JavaScript olarak paketlenirken, Flutter'da iş mantığı **derlenmiş native koda** dönüşür. Bu native kod genellikle Android'de `libapp.so`, ayrıca Flutter motorunu içeren `libflutter.so` gibi paylaşımlı kütüphanelerde taşınır.

### Bridge Yok, Platform Channels Var

Flutter'ın mimarisinde React Native'deki gibi kalıcı bir "bridge over serialization" darboğazı klasik anlamda yoktur, çünkü Dart kodu native koda derlenir ve doğrudan motorla konuşur. Ancak Flutter'ın **kendi başına yapamayacağı** işler (native API'ler, sensörler, platforma özgü SDK'lar) için **Platform Channels** mekanizması vardır. Dart tarafı bir mesajı serialize eder, native (Kotlin/Swift) taraf bunu alır, işler ve yanıtı geri gönderir. Bu, React Native bridge'ine kavramsal olarak benzer bir serileştirme sınırıdır; ancak Flutter'da sadece platform-native işler için kullanılır, tüm UI ve iş mantığı için değil.

---

## 3. Güvenlik Farkları: Analiz Zorluğu Karşılaştırması

Bu, konunun kalbidir. İki çatı, tersine mühendislik ve statik analiz açısından belirgin biçimde ayrışır.

### React Native: İş Mantığı Görece Açıktır

React Native uygulamalarında JavaScript kodu, genellikle tek bir paketlenmiş dosyada taşınır. Android APK içinde bu dosya tipik olarak `assets/index.android.bundle` gibi bir yolda bulunur.

İki durum vardır:

1. **Klasik JavaScript bundle**: Eğer bundle düz (plain) JavaScript ise, `minify` edilmiş olsa bile analist bunu bir metin dosyası olarak okuyabilir. API endpoint'leri, gömülü anahtarlar, iş kuralları, hatta yorumlar bazen doğrudan görünür. Bir `beautifier` ile okunabilirlik önemli ölçüde artar.

2. **Hermes bytecode**: Hermes etkinse, bundle artık düz metin değil, Hermes **bytecode**'udur. Bu okunması daha zordur ancak imkânsız değildir; topluluk tarafından geliştirilmiş **Hermes bytecode disassembler / decompiler** araçları bu bytecode'u geri okunabilir hale getirmeye çalışır. Yine de saf makine koduna kıyasla, yapılandırılmış bir bytecode olması analizi kolaylaştırır.

**Sonuç**: React Native'de iş mantığını çıkarmak, iyi bir savunma katmanı yoksa görece kolaydır. Tespit için ipucu: APK/IPA içinde `index.android.bundle`, `main.jsbundle` benzeri dosyaların ve React Native'e özgü native kütüphanelerin varlığı.

### Flutter: Binary Analizi Belirgin Biçimde Zordur

Flutter'da iş mantığı Dart AOT çıktısı olan native koda gömüldüğü için:

- Kod, standart bir Java/Kotlin decompiler ile **okunamaz** (çünkü DEX değil, native `.so`'dur).
- Dart AOT snapshot'ı, Dart runtime'ının kendine özgü iç yapılarını kullanır; genel amaçlı disassembler'lar (örneğin bir native binary'i ARM assembly'ye çevirebilir) sizi assembly seviyesine indirir ama Dart nesne modelini, sınıf ve fonksiyon isimlerini kolayca vermez.
- Fonksiyon/sembol isimleri release derlemede büyük ölçüde silinmiş veya anlamsızlaştırılmış olabilir.

Flutter analizinde bilinen ek bir zorluk, ağ trafiği yakalama (traffic interception) ile ilgilidir: Flutter, işletim sisteminin sistem proxy ayarlarını ve sistem sertifika deposunu (system trust store) React Native / native uygulamaların çoğu gibi otomatik kullanmaz; kendi ağ yığınına daha bağımsız yaklaşır. Bu yüzden bir güvenlik testinde, standart bir MITM proxy kurulumu Flutter uygulamasında "hiç trafik görmeme" ile sonuçlanabilir. Bu bir güvenlik özelliği değil, mimari bir yan etkidir; ancak pratikte analiz eşiğini yükseltir.

Topluluk, Flutter'ın Dart AOT snapshot'ını çözümlemek için özel araçlar geliştirmiştir (örneğin Dart runtime yapılarını yeniden inşa etmeye çalışan reverse-engineering projeleri). Bunlar Flutter/Dart sürümüne sıkı bağımlıdır; sürüm değiştikçe iç yapılar değişebildiği için araçlar sürekli güncellenmek zorunda kalır. Bu da Flutter analizini **kırılgan ve emek yoğun** kılar.

**Özet karşılaştırma**:

| Boyut | React Native | Flutter (release/AOT) |
|---|---|---|
| İş mantığı formatı | JavaScript veya Hermes bytecode | Native makine kodu (Dart AOT) |
| Statik okunabilirlik | Görece yüksek (bundle çıkarılabilir) | Düşük (native, sembolsüz) |
| Standart decompiler işe yarar mı | Kısmen (JS/Hermes araçları) | Genel decompiler'lar yetersiz |
| Trafik yakalama | Genellikle standart proxy yeterli | Sistem proxy/trust store'u atlayabilir |
| Analiz eşiği | Daha düşük | Daha yüksek |

Buradan çıkan yaygın bir **yanlış çıkarım**: "Flutter analiz zor, o yüzden güvenli." Bu hatalıdır. Analiz zorluğu bir **obscurity** (belirsizlikle koruma) katkısıdır, gerçek bir güvenlik kontrolü değildir. Kararlı bir analist yine de gömülü anahtarları, endpoint'leri ve zayıf kripto kullanımını çıkarabilir.

---

## 4. Ortak Güvenlik Sorunları (Her İki Çatıda)

Mimari farklardan bağımsız olarak, mobil uygulamalarda tekrar eden temel sorunlar iki çatıyı da etkiler:

### Gömülü Sırlar (Hardcoded Secrets)

En yaygın hatalardan biri, API anahtarlarını, gizli token'ları veya şifreleme anahtarlarını doğrudan koda gömmektir.
- React Native'de bunlar JavaScript bundle içinde neredeyse düz metin bulunabilir.
- Flutter'da native koda gömülüdür ama yine string tarama (`strings` benzeri) ile açığa çıkabilir.

**Doğru kullanım**: İstemci (client) hiçbir zaman gerçek anlamda sır saklayamaz. Cihazdaki her şey çıkarılabilir kabul edilmelidir. Kritik sırlar sunucuda kalmalı; istemci sadece kısa ömürlü, kapsamı dar token'lar taşımalıdır.

### Güvensiz Veri Depolama

Hassas verinin (oturum token'ı, kişisel veri) düz metin olarak yerel depolamada tutulması. Doğru yaklaşım, platformun güvenli depolama alanlarını kullanmaktır: iOS'ta **Keychain**, Android'de **Keystore** destekli çözümler. Cross-platform çatılarda bu genellikle bir kütüphane aracılığıyla sağlanır; kütüphanenin gerçekten platform güvenli deposunu kullandığından emin olunmalıdır.

### Zayıf/Eksik Certificate Pinning

Ağ iletişiminin MITM'e karşı korunması için certificate/public key pinning kritik bir savunmadır. React Native'de pinning yapılandırması yanlış katmanda kalırsa atlatılabilir. Flutter'da pinning Dart tarafında uygulanabilir; doğru uygulandığında Flutter'ın kendi ağ yığını sayesinde bazı basit MITM denemeleri zaten zorlaşır, ama bu tesadüfi koruma bir tasarım kararının yerini tutmaz.

### Native Modüllerin Genişlettiği Yüzey

Her iki çatıda da native modüller/eklentiler (plugins) üçüncü taraf koddur. Bir React Native native modülü veya bir Flutter plugin'i, uygulamaya kendi güvenlik açıklarını getirebilir. Bağımlılık zinciri (supply chain) riski cross-platform ekosistemlerde özellikle yüksektir çünkü paket sayısı ve geçişli bağımlılıklar (transitive dependencies) çoktur.

---

## 5. Tespit (Detection): Bir Uygulamanın Hangi Çatı Olduğunu Anlamak

Savunma ve analiz için ilk adım parmak izi (fingerprinting) çıkarmaktır. Uygulama paketini (APK/IPA) açarak şu ipuçlarına bakılır:

- **React Native işaretleri**: `index.android.bundle` / `main.jsbundle` benzeri bundle dosyaları, React Native'e ait native kütüphaneler ve Hermes kullanılıyorsa Hermes'e özgü kütüphane/dosya izleri.
- **Flutter işaretleri**: `libflutter.so` motor kütüphanesi, uygulama Dart kodunu taşıyan `libapp.so`, ve Flutter varlıklarının (assets) bulunduğu klasör yapısı (`flutter_assets` benzeri).
- **Native (saf) işaretleri**: Bu bundle/motor izlerinin yokluğu, iş mantığının doğrudan DEX/Swift ikili yapılarında olması.

Bu tespit, hem savunucunun kendi envanterini çıkarması hem de bir analistin doğru araç setini seçmesi için gereklidir.

---

## 6. Savunma ve Hardening: Doğru Kullanım

Amacımız mekanizmayı anlayıp **savunma** kurmak olduğundan, uygulanabilir savunma ilkeleri şunlardır:

1. **Sunucu tarafı otorite**: İş kurallarının ve yetkilendirmenin (authorization) son sözü sunucuda olmalı. İstemci koda gömülü kontroller (örneğin "premium mi" bayrağı) tek başına güvenilmezdir; her ikisi de tersine çevrilip atlatılabilir.

2. **Sır minimizasyonu**: İstemcide uzun ömürlü sır tutmamak. Token'lar kısa ömürlü, kapsamı dar ve yenilenebilir olmalı.

3. **Güvenli depolama**: Keychain/Keystore destekli çözümler; hassas veriyi düz metin dosyalarında veya basit key-value depolarında tutmamak.

4. **Certificate/Key pinning**: Doğru katmanda, doğru şekilde uygulanmış pinning. Yalnızca "Flutter ağ yığını proxy'i atlıyor" tesadüfüne güvenmemek.

5. **Kod sağlamlaştırma**:
   - React Native tarafında Hermes bytecode kullanımı, düz JS bundle'a kıyasla okunabilirliği düşürür (tam koruma değil, eşik yükseltir).
   - Genel obfuscation ve isim karıştırma, analiz maliyetini artırır ama tek savunma olmamalı.
   - Kök/jailbreak tespiti, debugger tespiti, bütünlük (integrity) kontrolleri ek katman olarak eklenebilir; bunların da atlatılabileceği bilinerek "katmanlı savunma" (defense in depth) mantığıyla kurgulanmalı.

6. **Bağımlılık hijyeni**: Native modül ve plugin'lerin güvenilir kaynaklardan gelmesi, sürüm sabitleme (pinning), bilinen açıklara karşı düzenli tarama.

7. **Runtime bütünlüğü**: Uygulamanın değiştirilip yeniden paketlenmediğini (repackaging) doğrulayan kontroller; imza doğrulama.

---

## 7. Yaygın Hatalar ve Tuzaklar

- **"Cross-platform = daha az güvenli / daha çok güvenli" genellemesi**: Yanlış. Güvenlik, çatının kendisinden çok, geliştiricinin sır yönetimi, sunucu otoritesi ve hardening kararlarına bağlıdır.

- **"Flutter'ı kimse çözemez" yanılgısı**: Analiz zorluğu obscurity'dir; kararlı analistler ve topluluk araçları Dart AOT'yi çözümleyebilir. Obscurity'yi güvenlik kontrolü sanmak temel bir hatadır.

- **Bundle içine sır gömmek**: React Native bundle'ının okunabilirliğini hafife almak. `minify` edilmiş JS bile bir sırrı gizlemez.

- **Bridge'i güvenlik sınırı sanmak**: React Native bridge bir güvenlik izolasyonu değil, sadece bir iletişim/serialization katmanıdır. Native tarafına gelen mesajların doğrulanması gerekir; JS tarafına güvenilmemelidir.

- **Yeni mimariyi (JSI) güvenlik güncellemesi sanmak**: JSI/TurboModules/Fabric performans içindir; iş mantığının paketlenme ve analiz edilebilme problemini kökten çözmez.

- **Trafik görünmüyor diye "güvenli" varsaymak**: Flutter'da standart proxy ile trafik görmemek, uygulamanın MITM'e dayanıklı olduğu anlamına gelmez; sadece test kurulumunun uyumsuz olduğu anlamına gelebilir.

- **Platform güvenli depolamasını atlamak**: "Basit olsun" diye token'ı düz dosyaya yazmak; Keychain/Keystore varken kullanmamak.

---

## Sonuç

React Native ve Flutter, aynı hedefe (tek kod tabanı, çok platform) farklı mimari felsefelerle ulaşır. React Native, JavaScript iş mantığını native bileşenlerle bir **bridge/JSI** üzerinden buluşturur; bu, iş mantığını görece **analiz edilebilir** bırakır. Flutter, Dart'ı **AOT ile native koda** derler ve kendi render motorunu kullanır; bu, binary analizini belirgin biçimde **zorlaştırır** ama bunu bir güvenlik garantisine dönüştürmez.

Güvenlik açısından altın kural değişmez: **istemci güvenilmez bir ortamdır.** İki çatıda da gerçek koruma; sunucu tarafı otoriteden, sır minimizasyonundan, güvenli depolamadan, doğru pinning'den ve katmanlı hardening'den gelir. Çatının analiz zorluğu yalnızca saldırganın maliyetini artıran bir eşiktir, tek başına bir savunma değildir. Bir analist için ilk beceri, uygulamayı doğru **fingerprint** edip doğru araç setini ve doğru savunma modelini seçmektir.
