# Mobil API Güvenliği: Mobil-Backend İletişimi, Certificate/Public Key Pinning, API Anahtarı Gizleme ve Reverse-Engineering ile Endpoint Keşfi

## Giriş ve Tehdit Modeli

Web uygulamalarında istemci tarayıcıdır ve saldırgan onu tam olarak kontrol edemez sayılır; ancak mobil dünyada durum köklü biçimde farklıdır. Mobil bir uygulama, saldırganın kendi cihazında, kendi elindeki bir ikilidir (binary). Bu tek gerçek, mobil API güvenliğinin tüm mantığını belirler: **istemci güvenilmezdir (untrusted client)**. Kullanıcı, uygulamayı çalıştıran ortamı tümüyle kontrol edebilir; trafiği araya girip okuyabilir, ikiliyi tersine mühendislikle (reverse engineering) inceleyebilir, çalışma zamanında (runtime) davranışını değiştirebilir.

IDOR, kırık authorization veya zayıf JWT doğrulaması gibi klasik API zafiyetleri mobil backend'lerde de aynen geçerlidir. Ancak mobil istemcinin backend'e *nasıl* konuştuğu ayrı bir saldırı yüzeyidir. Bu yazının konusu tam olarak bu kesişim: TLS'in üstüne inşa edilen pinning, ikilinin içine gömülen sırların (secret) korunması, uygulamanın gerçekliğini kanıtlayan attestation mekanizmaları ve tersine mühendislikle gizli endpoint'lerin keşfi.

Temel ilke şudur: **Mobil istemcide saklanan hiçbir şey mutlak sır değildir.** Savunma, sırrı gizlemekten çok, sırrın ele geçmesinin maliyetini artırmak ve backend tarafında güven kararlarını yeniden vermek üzerine kurulur.

## Mobil-Backend İletişiminin Temeli: TLS ve Yetmediği Nokta

Her ciddi mobil-backend iletişimi TLS (HTTPS) üzerinden yürür. TLS üç şeyi sağlar: gizlilik (confidentiality), bütünlük (integrity) ve sunucu kimliğinin doğrulanması (authentication). Sunucu kimliği, cihazın işletim sistemine gömülü kök sertifika otoritelerine (root CA) olan güven zinciriyle doğrulanır.

Sorun şu: TLS'in güven modeli, cihazın CA store'una güvenmesine dayanır. Saldırgan kendi cihazında bu store'a **kendi CA sertifikasını** ekleyebilir. Ardından bir intercepting proxy (örneğin mitmproxy, Burp Suite, Charles) çalıştırır; proxy her isteği kendi sertifikasıyla imzalar, cihaz buna güvenir ve tüm HTTPS trafiği açık metin gibi okunabilir hale gelir. Buna **MITM (Man-in-the-Middle)** denir. Yani standart TLS, *kullanıcının kendi cihazında* saldırgana karşı koruma sağlamaz; çünkü saldırgan güven kökünü değiştirmiştir.

Android'de bu risk sürüm bazında farklıdır. Android 7 (Nougat) ve sonrasında, uygulamalar varsayılan olarak yalnızca sistem CA'larına güvenir; kullanıcının eklediği CA'lara güvenmek için uygulamanın `network_security_config.xml` içinde açıkça izin vermesi gerekir. Bu, MITM'in önündeki ilk savunma katmanıdır ama pinning'in yerini tutmaz, çünkü saldırgan cihazı root'layıp sistem CA store'una yazabilir.

## Certificate ve Public Key Pinning

### Tanım ve Çalışma Mantığı

Pinning, uygulamanın "ben *yalnızca* şu belirli sertifikaya/anahtara sahip sunucuya güvenirim" demesidir. Cihazın CA store'una değil, uygulamanın içine gömülü bir referansa göre karar verilir. Böylece saldırgan CA eklese bile, sunulan sertifika beklenen pin ile eşleşmediği için TLS el sıkışması (handshake) uygulama katmanında reddedilir.

Pinning'in iki yaygın biçimi vardır:

- **Certificate pinning**: Sunucu sertifikasının tamamının (ya da hash'inin) gömülmesi. En katı biçimdir ama en kırılgandır: sertifika yenilendiğinde (ki genellikle 1 yılda bir, Let's Encrypt'te daha sık) uygulamanın da güncellenmesi gerekir. Yenileme öncesi uygulama güncellenmezse, tüm istemciler backend'e bağlanamaz — kendi kendini DoS'lama riski.

- **Public key pinning (SPKI pinning)**: Sertifikanın değil, içindeki **public key**'in (daha doğrusu SubjectPublicKeyInfo yapısının SHA-256 hash'inin) pinlenmesi. Tercih edilen yöntemdir; çünkü sertifika aynı anahtar çiftiyle yenilenirse pin bozulmaz. Genellikle intermediate CA'nın public key'i pinlenir ki esneklik korunsun.

### Doğru Uygulama ve Tuzaklar

Modern uygulamada pinning genellikle networking kütüphanesi düzeyinde yapılandırılır. Android'de OkHttp'nin `CertificatePinner` sınıfı, ya da Android 7+ için deklaratif `network_security_config.xml` içindeki `<pin-set>` bloğu kullanılır. iOS'ta `URLSession` delegate'inde `didReceiveChallenge` içinde manuel doğrulama ya da TrustKit gibi kütüphaneler tercih edilir.

Kritik kurallar:

1. **Backup pin şart.** Her zaman en az iki pin bulundurun: aktif anahtar ve bir yedek (henüz kullanılmayan) anahtar. Böylece anahtar rotasyonu (key rotation) sırasında istemcileri kilitlemezsiniz. Tek pinli dağıtım, güvenlik camiasında bilinen en yaygın operasyonel felakettir.

2. **Rotasyon planı olmadan pin yapmayın.** Pin, uygulama güncellemesine bağlı bir bağımlılık yaratır. Mobil ekosistemde kullanıcıların önemli bir kısmı güncelleme yapmaz. Bu yüzden pinlerin son kullanma tarihi (`expiration`) ve pinleri uzaktan güncelleyebilecek bir mekanizma (remote config) düşünülmelidir — ancak bu mekanizma da güvenli olmalı yoksa saldırgan pinleri değiştirebilir.

3. **Pinning bir sır değildir.** Pinlenen public key hash'i zaten sunucudan herkese açık gelir; gizli bir şey pinlemiyorsunuz. Pinning'in amacı gizlilik değil, güven kaynağını daraltmaktır.

### Pinning'in Sınırı: Bypass Gerçeği

Dürüst olmak gerekir: pinning, *cihazı kontrol eden* bir saldırganı durdurmaz, yalnızca yavaşlatır. Root'lu bir Android cihazda Frida gibi bir dinamik enstrümantasyon aracıyla, pinning kontrolünü yapan fonksiyon runtime'da hook'lanıp her zaman "geçerli" döndürecek şekilde değiştirilebilir. "objection" gibi hazır araçlar bunu tek komuta indirmiştir.

Bu yüzden pinning'i mutlak bir kalkan değil, **maliyet artırıcı bir katman** olarak konumlandırın. Pinning, sıradan bir kullanıcının kablosuz ağındaki oportünist MITM'i ve kurumsal proxy'leri engeller; kararlı, teknik bir saldırganı ise geciktirir. Değeri buradadır ve azımsanmamalıdır. Ama backend, pinning'in bypass edilebileceğini varsayarak tasarlanmalıdır.

## API Anahtarı ve Sır Gizleme (Secret Management)

### Kök Sorun: İkilideki Sırlar Sır Değildir

Geliştiriciler sıkça API anahtarlarını, üçüncü taraf servis token'larını, HMAC imzalama anahtarlarını uygulama koduna gömer. **Uygulamaya gömülen her sır, tersine mühendislikle çıkarılabilir.** Android APK'sı bir ZIP arşividir; `apktool` ile açılır, `jadx` ile DEX bytecode okunabilir Java'ya çevrilir. iOS ikilisi `class-dump` ve benzeri araçlarla incelenir. String'ler `strings` komutuyla dökülebilir.

Bu bir "eğer" değil, "ne zaman" meselesidir. GitHub ve Play Store analizlerinde binlerce uygulamada açık API anahtarı, AWS credential'ı, Firebase secret'ı düzenli olarak bulunur.

### Yaygın Yanlış Çözümler ve Neden Yetersiz Oldukları

- **String obfuscation (karartma):** Anahtarı XOR'lamak, base64 katmanları, parçalara bölüp runtime'da birleştirmek. Bu, `strings` ile bulmayı zorlaştırır ama runtime'da anahtar bir noktada belleğe açık halde gelmek zorundadır; Frida ile o an yakalanır. Obfuscation, çıkarma maliyetini artırır — çözmez.

- **Native koda (NDK/C++) gömmek:** Java katmanından daha zor okunur ama imkânsız değildir; `.so` dosyaları disassembler'larla (Ghidra, IDA) incelenir. Yine bir engel, mutlak değil.

- **DexGuard / ProGuard / R8:** Kod küçültme ve isimlendirme karartması sağlar. Tersine mühendisliği zorlaştırır, ama gömülü sabit sırları matematiksel olarak koruyamaz.

### Doğru Yaklaşım

1. **Sırları backend'de tutun.** Üçüncü taraf servislere (ödeme, harita, SMS) yapılan çağrıları mümkünse mobilden değil, kendi backend'inizden proxy'leyin. Böylece hassas anahtar hiç mobile inmez. Mobil yalnızca kendi backend'inize konuşur.

2. **Anahtar yerine kısa ömürlü token.** Uzun ömürlü statik sır yerine, kullanıcı kimlik doğrulamasından sonra üretilen kısa ömürlü (short-lived), scope'u dar access token'lar kullanın. Bir token sızsa bile hem süresi dolar hem de sınırlı yetkisi vardır.

3. **Anahtarları kısıtlayın (key restriction).** Kaçınılmaz olarak mobilde bir anahtar bulunacaksa (örn. bir harita SDK anahtarı), o anahtarı servis tarafında package name / bundle ID, imza sertifikası hash'i ve platform bazında kısıtlayın. Sızsa bile başka bir uygulamadan kullanılamaz.

4. **Sızıntı tespiti.** CI/CD hattına secret scanning (gitleaks, truffleHog benzeri) ekleyin. Yayınlanan APK/IPA'yı düzenli olarak kendi araçlarınızla tarayıp gömülü sır olup olmadığını kontrol edin.

## App Attestation: Play Integrity, DeviceCheck/App Attest

### Neden Attestation?

Pinning ve obfuscation "istemci kontrolü" problemini çözmez. Backend'in asıl sorması gereken soru şudur: **"Bu isteği gerçekten benim değiştirilmemiş uygulamam mı, gerçek bir cihazdan mı gönderdi?"** İşte attestation bunu yanıtlamaya çalışır. Güven kararını istemciden alıp platform sağlayıcısına (Google/Apple) ve backend'e taşır.

### Play Integrity API (Android)

Google Play Integrity API, uygulamanın talebi üzerine imzalı bir **integrity verdict** üretir. Bu verdict tipik olarak şu sinyalleri içerir:

- Uygulamanın gerçekten sizin, Play'de yayınlanan, kurcalanmamış (tampered) sürümünüz olup olmadığı (app integrity).
- Cihazın gerçek, Google Play korumalı bir cihaz olup olmadığı, emülatör/root sinyalleri (device integrity).
- Hesabın lisanslı olup olmadığı.

Kritik nokta: verdict **Google tarafından imzalanır** ve mobil uygulama onu doğrulayamaz/üretemez; verdict backend'inize gönderilir, backend Google'ın sunucularıyla (ya da imzayı doğrulayarak) doğrular. Böylece istemci verdict'i sahteleyemez.

### DeviceCheck ve App Attest (iOS)

Apple tarafında iki mekanizma vardır. **DeviceCheck** cihaz başına kalıcı iki bit sunar (örneğin bir denemeyi/fraud işaretini cihaza bağlamak için). **App Attest** ise daha güçlüdür: uygulama, Secure Enclave'de üretilmiş bir donanım destekli anahtar çifti oluşturur; Apple bu anahtarı, isteği gerçek bir cihazdan gelen gerçek uygulamanın gönderdiğine dair bir attestation ile onaylar. Sonraki istekler bu anahtarla imzalanan **assertion**'lar taşır ve backend bunları doğrular.

### Attestation'ın Doğru Kullanımı ve Sınırları

- **Doğrulama backend'de yapılır.** Attestation'ın tüm değeri sunucu tarafı doğrulamadadır. İstemcinin "geçtim" demesine güvenmek, mekanizmanın tümünü anlamsız kılar — sık yapılan ölümcül hata.

- **Attestation ≠ kimlik doğrulama.** Uygulamanın gerçekliğini kanıtlar, kullanıcının kim olduğunu değil. authentication/authorization yerine geçmez; onları tamamlar.

- **Yumuşak başarısızlık (fail-open vs fail-closed) kararı.** Attestation servisleri kesintiye uğrayabilir, eski cihazlarda desteklenmeyebilir, ağ hataları olabilir. Attestation başarısız olunca isteği tümüyle reddetmek (fail-closed) meşru kullanıcıları dışlayabilir; her zaman kabul etmek (fail-open) korumayı yok eder. Doğru tasarım genellikle attestation'ı bir *sinyal* olarak risk skorlamasına katmaktır: yüksek riskli işlemlerde (para transferi, hesap değişikliği) sıkı, düşük riskli okumalarda esnek.

- **Bypass gerçeği.** Attestation sinyalleri güçlü ama mutlak değildir; saldırganların bu mekanizmaları atlatma çabaları sürekli evrilir. Google ve Apple bunları güncelleyerek yarışı sürdürür. Attestation'ı risk azaltıcı güçlü bir sinyal olarak görün, tek başına yeterli bir kapı olarak değil.

## Reverse-Engineering ile Endpoint Keşfi

### Nasıl Çalışır ve Neden Önemlidir

Bir mobil uygulama, backend API'sinin canlı bir dokümantasyonudur. Saldırgan iki yolla endpoint'leri keşfeder:

1. **Statik analiz:** İkiliyi açıp (jadx, apktool, Ghidra) string'lerde URL'leri, path'leri, API şablonlarını arar. Retrofit/Ktor gibi kütüphanelerin annotation'ları, gömülü base URL'ler, feature flag'ler, hatta yorum satırları ele geçer. Kaldırılmış (deprecated) ama sunucuda hâlâ açık endpoint'ler, admin/debug path'leri, versiyonlanmamış eski API'ler bu yolla bulunur.

2. **Dinamik analiz:** Pinning bypass edilmiş bir cihazda proxy ile canlı trafik izlenir. Gerçek istek/yanıt yapıları, header'lar, imza şemaları, parametre isimleri ortaya çıkar. Statikte gizli kalan runtime davranışı burada görünür.

### Neyin Ortaya Çıktığı ve Riski

Bu keşifle saldırgan; UI'da hiç sunulmayan "gizli" endpoint'leri, henüz yayınlanmamış özelliklerin API'lerini, iç (internal) yönetim uçlarını ve — en tehlikelisi — **client-side güvenlik varsayımlarını** bulur. Örneğin uygulama bir işlemi UI'da engelliyorsa ama backend aynı kontrolü yapmıyorsa, saldırgan doğrudan endpoint'e istek atarak kontrolü atlar. Burada mesele mobil değil, backend'in "istekler yalnızca benim uygulamamdan gelir" yanılgısıdır.

### Savunma ve Tespit

- **Security through obscurity'ye güvenmeyin.** Gizli olduğunu sandığınız endpoint gizli değildir. Her endpoint kendi başına yetkilendirme, girdi doğrulama ve rate limiting uygulamalıdır. UI'da bir şeyi gizlemek onu korumaz.

- **Sunucu tarafı otorizasyon zorunludur.** İstemcinin gönderdiği hiçbir alan (fiyat, rol, user_id, "isAdmin" gibi) doğrulanmadan kabul edilmemeli. Client-side kontroller yalnızca UX içindir.

- **Attack surface temizliği.** Deprecated endpoint'leri gerçekten kapatın. Eski API sürümlerini emekliye ayırın. Debug/staging endpoint'lerini production'da yayınlamayın. Keşfedilecek yüzeyi küçültün.

- **Anomali tespiti.** Şu sinyalleri izleyin: beklenmedik User-Agent'lar, hiç UI akışına uymayan çağrı sıraları (örneğin login olmadan doğrudan bir ödeme endpoint'i), olağandışı yüksek istek hızları, attestation sinyali olmayan ya da başarısız istekler. Bu telemetriyi WAF/API gateway ve backend loglarıyla birleştirin.

- **Rate limiting ve abuse detection.** Endpoint bazında hız sınırları, hesap ve IP bazında eşikler, tekrarlayan başarısız yetkilendirmelerde kademeli yavaşlatma (throttling) koyun.

## Katmanlı Savunma: Bütünsel Bakış

Mobil API güvenliğinde tek bir mekanizma yeterli değildir; her biri belirli bir saldırgan sınıfını yükseltir:

| Katman | Neyi engeller | Sınırı |
|---|---|---|
| TLS | Pasif dinleme, ağ MITM | Kullanıcı CA store'unu kontrol ederse aşılır |
| Pinning | Proxy tabanlı MITM, kurumsal araya girme | Root + Frida ile bypass |
| Secret yönetimi | Sabit sırların sızması | Runtime'da her sır yakalanabilir |
| Obfuscation | Kolay/oportünist tersine mühendislik | Kararlı analizle çözülür |
| App attestation | Sahte/kurcalanmış istemci, emülatör, bot | Sinyal güçlü ama mutlak değil |
| Backend authz + rate limit | Endpoint kötüye kullanımı, IDOR | Her endpoint'te tutarlı uygulanmalı |

Bu tabloyu okurken ana ders şudur: **savunma çevresi (perimeter) backend'dir, mobil istemci değil.** Pinning, obfuscation ve attestation saldırıyı pahalılaştırır ve gürültüyü artırır — böylece tespit kolaylaşır. Ama nihai güvenlik kararı her zaman, istemciye asla güvenmeyen, her isteği bağımsızca doğrulayan sunucu tarafı mantığında verilmelidir.

## Yaygın Hatalar Özeti

- Tek pinli dağıtım yapıp anahtar rotasyonunda tüm kullanıcıları backend'den kesmek.
- Pinning'i "kırılamaz" sanıp backend otorizasyonunu ihmal etmek.
- API anahtarlarını doğrudan koda gömüp obfuscation'ı yeterli sanmak.
- Üçüncü taraf servis anahtarlarını mobilde tutup backend proxy'lememek.
- Attestation verdict'ini istemcide "doğrulayıp" backend'e sadece bir boolean göndermek.
- UI'da gizlenen endpoint'i "korunmuş" varsaymak; deprecated/debug uçlarını production'da açık bırakmak.
- Client'tan gelen role/fiyat/kimlik alanlarına doğrulamadan güvenmek.
- Attestation'ı fail-open yapıp korumayı fiilen kapatmak, ya da fail-closed yapıp meşru cihazları dışlamak — risk bazlı orta yolu kurmamak.

## Sonuç

Mobil API güvenliği, "istemci güvenilmezdir" ilkesinin mühendislik pratiğine dönüşmüş halidir. TLS temeldir ama tek başına kullanıcının cihazındaki saldırganı durdurmaz. Pinning güven kökünü daraltır, obfuscation ve secret yönetimi sızma maliyetini artırır, attestation istemcinin gerçekliğine dair güçlü bir sinyal sunar. Ancak bunların hiçbiri mutlak değildir ve tümü bypass edilebilir. Gerçek güvenlik, bu katmanları saldırıyı pahalılaştıran ve tespit edilebilir kılan araçlar olarak kullanıp, her yetki kararını istemciye güvenmeden sunucuda yeniden veren bir mimaride yatar. Doğru zihniyet: mobil istemciyi bir kalkan değil, dikkatle izlenmesi gereken düşman toprağı olarak görmek.
