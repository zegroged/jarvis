# Ağ Protokolü Fuzzing ve Ters Mühendislik (Özel/Bilinmeyen Protokoller)

## Tanım ve Kapsam

**Ağ protokolü fuzzing**, bir ağ servisine (client veya server) sistematik olarak bozuk, sınır-dışı veya beklenmedik veri gönderip yazılımın bu girdiler karşısında çökme, bellek bozulması, sonsuz döngü veya mantık hatası gösterip göstermediğini araştıran bir güvenlik test yöntemidir. **Protokol ters mühendisliği** (protocol reverse engineering) ise dokümante edilmemiş, özel (proprietary) veya kapalı bir protokolün yapısını — mesaj çerçeveleri, alan sınırları, tipler, durum makinesi — dışarıdan gözlemleyerek yeniden inşa etme çalışmasıdır.

Bu iki disiplin birbirini besler: kapalı bir protokolü etkili biçimde fuzzing yapabilmek için önce onun **gramerini** (mesaj yapısını) yeterince anlamak gerekir; körlemesine rastgele bayt göndermek genellikle daha ilk paritede reddedilir. Bu makale mekanizmayı anlamaya, zayıflıkların **neden** oluştuğunu kavramaya ve savunma/tespit tarafını kurmaya odaklanır; canlı bir hedefe yönelik operasyonel saldırı talimatı vermez.

Genel "fuzzing" başlığından farkı şudur: dosya-formatı veya API fuzzing çoğunlukla **stateless** ve tek atımlıktır. Ağ protokolleri ise **stateful**'dur — anlamlı bir test için önce el sıkışma (handshake), kimlik doğrulama, oturum kurulumu gibi adımlardan geçmek gerekir. Bu durumsallık, ağ protokolü fuzzing'ini ayrı bir uzmanlık alanı yapar.

## Kök Neden: Protokol Ayrıştırıcıları Neden Kırılgandır?

Bir ağ servisi, karşıdan gelen ham baytları alıp anlamlı yapıya çeviren bir **parser** (ayrıştırıcı) içerir. Bu ayrıştırma katmanı, güvenlik açıklarının yoğunlaştığı yerdir. Kök nedenler:

- **Uzunluk alanına körü körüne güven:** Protokoller sıklıkla "sonraki alan N bayt" biçiminde bir length-prefixed yapı kullanır. Kod, gelen `N`'i doğrulamadan `malloc(N)` veya `memcpy(dst, src, N)` yaparsa; saldırgan `N`'i devasa (integer overflow'a yol açacak) veya gerçek payload'dan büyük gösterip **heap overflow** ya da **out-of-bounds read** tetikler. Heartbleed sınıfı hatalar tam olarak bu kalıptandır: istenen uzunluk, sağlanan veriden fazladır ve fazlası bellekten sızar.
- **Durum makinesi ihlali:** Protokol "önce AUTH, sonra DATA" bekler; ama parser bir durumu atlayan mesajı reddetmek yerine yarı-başlatılmış bir yapı üzerinde işlem yaparsa, use-after-free veya null-deref oluşur. Bu **stateful** hatalar, yalnızca doğru sıra bozulduğunda ortaya çıkar.
- **Tip karışıklığı ve TLV ayrıştırma:** Type-Length-Value kodlamalarında (ASN.1, TLV tabanlı protokoller) bir alanın tipi ile o tip için beklenen uzunluğun tutarsız olması, yanlış cast'e ve bellek bozulmasına yol açar.
- **Recursion / iç içe yapı:** İç içe geçmiş yapılar (örneğin iç içe TLV) derinlik sınırı yoksa **stack exhaustion** veya kaynak tükenmesi (DoS) üretir.
- **İşaretli/işaretsiz karışıklığı:** `int16_t` olarak okunan bir uzunluğun negatif yorumlanması, sonraki hesaplarda sınır kontrolünü baypas eder.

Fuzzing'in gücü, bu kalıpların insan gözünden kaçan kombinasyonlarını otomatik ve yorulmadan denemesidir.

## Kapalı Protokolü Anlamak: Ters Mühendislik Yöntemi

Dokümante edilmemiş bir protokolü çözümlemenin merkezinde **trafik gözlemi** vardır. Yasal ve etik zeminde bu, kendi sahip olduğunuz ya da açıkça izin verilen bir sistemin trafiğini incelemek anlamına gelir.

### 1. PCAP Toplama ve İlk İnceleme

Trafik `tcpdump` veya Wireshark ile PCAP dosyasına kaydedilir. İlk soru şudur: protokol **TCP** üzerinde mi (stream, mesaj sınırları belirsiz) yoksa **UDP** üzerinde mi (datagram, doğal mesaj sınırı var) çalışıyor? TCP'de "mesaj çerçeveleme" (framing) bir problemdir — bir okuma çağrısında birden çok mesaj ya da bir mesajın yarısı gelebilir.

### 2. Alan Sınırlarını Çıkarma (Field Inference)

Aynı işlemin (örneğin login) tekrar tekrar kaydedilen paketleri hizalanıp (align) baytlar karşılaştırılır. Buradaki temel sezgi:

- **Değişmeyen baytlar** genellikle magic number, sürüm, opcode veya sabit ayraçlardır.
- **Her seferinde değişen baytlar** sequence number, timestamp, session ID veya payload'dır.
- **Girdiyle orantılı değişen baytlar** çoğu kez **uzunluk alanıdır** — kullanıcı adını 1 karakter uzatınca hangi baytın 1 arttığına bakmak, length field'ı çıplak gözle ortaya çıkarır.

Bu diff temelli hizalama, klasik ters mühendislik sezgisidir. Otomatik yaklaşımlar (örneğin akademik **Netzob**, tarihsel **PI Project** çalışmaları) bu hizalamayı **sequence alignment** algoritmalarıyla (biyoinformatikten ödünç alınan Needleman-Wunsch benzeri) yaparak mesaj tiplerini kümeler ve alan sınırlarını istatistiksel olarak tahmin eder.

### 3. Entropi ve Yapı Analizi

Bir alanın **entropisi** (bayt dağılımının rastgeleliği), o alanın ne olduğuna dair güçlü ipucu verir. Yüksek entropi → şifreli/sıkıştırılmış veri ya da rastgele nonce/token. Düşük entropi → ASCII metin, sabit değerler, sayaçlar. TLS/SSL ile şifrelenmiş bir protokolde payload büyük ölçüde yüksek entropilidir; bu durumda ters mühendislik ya endpoint'te (şifrelemeden önce/sonra, örneğin instrumentation ile) yapılır ya da yalnızca dış çerçeve analiz edilebilir.

### 4. Durum Makinesini Çıkarma

Farklı oturumların mesaj sıraları karşılaştırılarak protokolün **state machine**'i tahmin edilir: hangi mesaj hangi mesajdan sonra gelir, hangi yanıt hangi isteği tetikler. Akademik alanda buna **active automata learning** denir (örneğin **L\*** algoritması / **LearnLib** kütüphanesi): sisteme sistematik sorgular gönderip yanıtlardan bir sonlu durum makinesi (Mealy machine) öğrenilir. Bu çıkarılan model, hem hatayı anlamak hem de sağlam bir fuzzer kurmak için altyapıdır.

## Stateful Protocol Fuzzing: Çalışma Mantığı

Ağ fuzzing araçlarının çoğunun ortak fikri, protokolü bir **model/gramer** olarak tanımlayıp bu modelin belirli alanlarını sistematik olarak bozmaktır.

### Model Tabanlı (Generation-Based) Fuzzing

Tarihsel olarak **Peach** ve hâlen aktif olan **boofuzz** (eski **Sulley**'in devamı) bu yaklaşımın temsilcileridir. Fikir şudur: kullanıcı, protokolün bir mesajını "bloklar" hâlinde tarif eder — burası 4 baytlık magic, burası 2 baytlık length (otomatik hesaplanır), burası string payload. Araç sonra:

- **Alan bazında mutasyon uygular:** string alanına aşırı uzun diziler, format string belirteçleri (`%n`, `%s`), null bayt, Unicode sınır durumları; sayısal alanlara `0`, `-1`, `MAX_INT`, `MAX_INT+1` gibi **sınır değerleri** (boundary values) enjekte eder.
- **Length ile payload'ı kasıtlı tutarsız kılar:** length alanı otomatik hesaplanabilir olduğu için, aracı length'i sabit tutup payload'ı değiştirmeye ya da tersini yapmaya zorlamak, uzunluk-güven hatalarını ortaya çıkarır.
- **Durumu yönetir:** boofuzz'un ayırt edici özelliği, bir mesaj dizisini (handshake → auth → hedef mesaj) tanımlayıp fuzzing'i yalnızca hedef adımda uygulayabilmesidir. Böylece parser'ın derin durumlarına ulaşılır — yüzeysel bir fuzzer'ın asla göremeyeceği kod yolları.

Generation-based yaklaşımın gücü: protokolü bildiği için geçerli çerçeveler üretir, derinlere iner. Zayıflığı: modeli **elle yazmak** emek ister ve modelin eksikleri kör noktalar yaratır.

### Kapsam Güdümlü (Coverage-Guided) Mutasyon Fuzzing

Diğer aile, AFL/**AFLNet**, **libFuzzer** benzeri **coverage-guided** araçlardır. Burada protokol modeli yerine, hedef ikili dosya **instrumente** edilir (derleme sırasında sanitizer + kapsam sayaçları eklenir). Fuzzer rastgele mutasyonlar dener; hangi girdi **yeni kod yolu** açtıysa onu tohum (seed) havuzunda tutar ve üzerine mutasyon yapar. AFLNet, bu fikri ağ protokollerine taşır: PCAP'lerden çıkarılan gerçek mesaj dizilerini tohum alır, yanıt kodlarını durum göstergesi olarak kullanıp durum makinesinde ilerlemeyi ödüllendirir.

**Sanitizer'lar** bu düzenekte kritik rol oynar: ASan (AddressSanitizer) out-of-bounds ve use-after-free'i, UBSan tanımsız davranışı, MSan başlatılmamış bellek okumasını çöküş olmadan bile **yakalar**. Fuzzing'in bulduğu değer çoğu kez "çöktü mü" değil, "sanitizer ne raporladı"dır.

### İki Yaklaşımın Kıyaslanması

| Boyut | Generation-based (boofuzz/Peach) | Coverage-guided (AFLNet) |
|---|---|---|
| Ön koşul | Protokol modeli elle yazılır | Kaynak/ikili instrumente edilir |
| Derin duruma erişim | Model sayesinde güçlü | Tohum + geri besleme ile öğrenir |
| Bilinmeyen protokol | Model çıkarmak gerekir (RE) | PCAP tohumlarıyla başlar |
| Kör nokta | Modelin eksikleri | Anlamsız çerçevelerde takılabilir |

Pratikte olgun bir çalışma ikisini harmanlar: ters mühendislikle çıkarılan gramer, coverage-guided fuzzer'a **akıllı tohumlar** ve **çerçeve farkındalığı** kazandırır.

## Somut Örnek: Uzunluk-Öncüllü Bir Mesajı Fuzzing Etmek

Kavramı somutlaştıralım. Farz edin ki ters mühendislikle şu çerçeveyi çıkardınız:

```
[ 2 bayt magic = 0xAB 0xCD ]
[ 1 bayt opcode ]
[ 2 bayt length (big-endian, payload uzunluğu) ]
[ length bayt payload ]
```

Bir generation-based modelde bunu bloklarla tanımlarsınız; length bloğu payload bloğundan otomatik hesaplanacak biçimde bağlanır. Fuzzer'ın üreteceği ilginç test durumları:

- **length = 0xFFFF ama payload = 3 bayt:** Sunucu 65535 bayt okumaya/kopyalamaya çalışırsa OOB read; okumayı bloklarsa hang.
- **length = 0 ama payload dolu:** Sıfır-uzunluk özel durum işleme hatası.
- **opcode = tanımsız bir değer:** default/else dalının eksikliği null-deref üretebilir.
- **magic doğru, sonra akış yarıda kesiliyor:** TCP framing'de yarım mesajın nasıl işlendiği (timeout, buffer state) sınanır.
- **length'te integer overflow:** `length + header_size` hesabı taşarsa küçük buffer ayrılıp büyük veri yazılır.

Fuzzer bu durumları binlerce varyasyonla, durum makinesinin doğru adımında (örneğin auth sonrası) otomatik dener. İnsan bunların hepsini elle test edemez; asıl kazanım budur.

## Doğru Kullanım İlkeleri ve Tuzaklar

**Doğru kullanım:**

- **Yetki ve izole ortam:** Fuzzing yalnızca sahip olduğunuz veya yazılı izinli sistemlerde, üretimden ayrılmış bir laboratuvarda yapılır. Fuzzing doğası gereği hedefi çökertir; canlı sisteme uygulamak DoS ve veri kaybı demektir.
- **Instrumentation'ı en baştan kur:** Hedefi ASan/UBSan ile derlemek, "sessiz" bellek hatalarını görünür kılar. Çıplak çökme beklemek, bulguların çoğunu kaçırır.
- **Crash triyajı ve tekrar-üretilebilirlik:** Bir çöküşü değerli kılan, onu deterministik olarak **yeniden üretebilmektir**. Ağ fuzzing'de zamanlama, oturum durumu ve sıralama çökmeye karışır; tetikleyen tam mesaj dizisini kaydetmek şarttır. **Corpus minimization** (afl-tmin benzeri) ile tetikleyici girdiyi en küçük hâline indirmek analizi kolaylaştırır.
- **Reprodüksiyon harness'ı:** İdeal olarak protokol katmanını soyutlayıp parser'ı doğrudan bir bellek buffer'ıyla besleyen bir harness kurmak, ağ katmanının gürültüsünü ve yavaşlığını ortadan kaldırır (in-memory / persistent-mode fuzzing). Bu, throughput'u yüzlerce kat artırabilir.

**Yaygın tuzaklar:**

- **Handshake'i geçememek:** En sık hata, fuzzer'ın kimlik doğrulama veya el sıkışmayı doğru yapamaması; böylece tüm testler daha kapıda reddedilir ve derin kod hiç çalışmaz. Stateful araç kullanmanın veya durum modelini doğru kurmanın önemi buradan gelir.
- **Checksum/CRC duvarı:** Protokolde her mesajın sonunda bir checksum varsa ve fuzzer bunu güncellemezse, bozduğunuz her paket "geçersiz checksum" ile reddedilir. Fuzzer'a checksum'ı **otomatik yeniden hesaplat** ya da (kaynağa erişimin varsa) doğrulamayı test için devre dışı bırak. Aynı mantık şifreleme/imza için de geçerlidir — şifreli katman fuzzing'i kör eder; ya şifreleme öncesine enjekte et ya da instrumentation ile katmanı aş.
- **Length-otomasyonunu kapatmayı unutmak:** Model, length'i her zaman payload'a göre "düzeltirse" length-güven hatalarını asla test edemezsiniz. Kasten tutarsızlık üretecek modlar açılmalı.
- **State'i sıfırlamamak:** Her test durumundan sonra sunucu temiz bir duruma dönmezse (bağlantı resetlenmezse), çökmeler önceki testlerin kalıntısına karışır ve triyaj imkânsızlaşır. Her iterasyonda temiz oturum kurmak yavaş ama doğru olandır.
- **Yalnızca çökmeye bakmak:** Mantık hataları (auth baypası, yetki yükseltme) çökme üretmez. Fuzzing bunları doğrudan bulmaz; kapsamı bunun için abartmayın.

## Savunma ve Tespit Tarafı

Bu yöntemleri anlamanın asıl amacı, savunulabilir yazılım ve ağ kurmaktır.

**Yazılım tarafında (proaktif):**

- **Kendi protokolünüzü kendiniz fuzzing yapın:** Bir parser yazan ekip, onu CI hattında sürekli fuzzing altında tutmalı. OSS-Fuzz benzeri modeller, sürekli fuzzing'in gerçek hataları yakaladığını yıllardır gösteriyor. Fuzzing bir kez değil, regresyon koruması olarak süreklidir.
- **Parser'ı savunmacı yaz:** Her uzunluk alanını **okumadan önce** üst sınıra karşı doğrula; işaretli/işaretsiz dönüşümlere dikkat et; iç içe yapılara derinlik limiti koy; ayrıştırmayı bellek-güvenli bir dilde (Rust vb.) veya **parser combinator** / resmi grammer araçlarıyla üretmeyi düşün. Elle yazılmış ad-hoc parser'lar hata mıknatısıdır.
- **Yüzey alanını daralt:** Kimlik doğrulanmamış istemcinin ulaşabildiği parser kodu ne kadar azsa, saldırı yüzeyi o kadar küçüktür. Ağır ayrıştırmayı auth sonrasına ertele.

**Ağ tarafında (tespit):**

- **Protokol farkında IDS/IPS:** Zeek (eski adıyla Bro) gibi araçlar trafiği protokol seviyesinde ayrıştırıp anormallikleri (beklenmeyen opcode, tutarsız length, geçersiz durum geçişleri) loglar. Fuzzing trafiği tipik olarak **yüksek oranda geçersiz/anormal paket** ve **sık bağlantı reset'i** üretir; bu imza tespit için kullanılabilir.
- **Rate limiting ve anomaly detection:** Tek bir kaynaktan gelen olağandışı yüksek hacimli hatalı istek, hem fuzzing hem keşif göstergesidir.
- **Çökme telemetrisi:** Servisin tekrar tekrar restart etmesi, crash dump üretmesi ya da bellek hatası logu — bunlar aktif bir parser saldırısının en net erken uyarısıdır. Crash monitoring ile güvenlik izlemeyi birleştirmek değerlidir.
- **Fuzzing'i savunma değerlendirmesinde kullanmak:** Kırmızı takım, satın alınan üçüncü-parti kapalı bir cihazın/protokolün sağlamlığını fuzzing ile değerlendirir; bulgular tedarikçiye sorumlu açıklama (responsible disclosure) ile iletilir.

## Sık Yapılan Kavramsal Hatalar

- **"Fuzzing = rastgele veri göndermek" sanmak.** Modern fuzzing yönlendirilmiştir: coverage geri beslemesi, gramer bilgisi ve durum modeli olmadan verim çok düşüktür. Kör rastgelelik protokol duvarını aşamaz.
- **Ters mühendislikle fuzzing'i ayrı sanmak.** Kapalı protokolde ikisi tek bir döngüdür: gözlemle → modelle → boz → gözlemle.
- **Şifreli protokol fuzzing'lenemez sanmak.** Şifreleme katmanının **altına** (instrumentation ile) veya **öncesine** (endpoint'te) inilerek plaintext parser yine test edilebilir; şifreleme yalnızca ağdan pasif RE'yi zorlaştırır.
- **Bir çöküşü otomatik "exploit edilebilir" saymak.** Çoğu çöküş DoS düzeyindedir; bellek yazımına dönüşüp dönüşmediği ayrı bir analiz (root-cause + exploitability triage) ister. Abartılı iddia, mühendislik dürüstlüğüne aykırıdır.

## Özet

Ağ protokolü fuzzing ve ters mühendislik, birbirini besleyen iki uzmanlıktır: kapalı protokolü PCAP gözlemi, alan hizalama, entropi analizi ve durum makinesi çıkarımıyla anlarsınız; sonra bu modeli generation-based (boofuzz/Peach) veya coverage-guided (AFLNet) bir fuzzer'a vererek parser'ın derin, stateful kod yollarını sistematik olarak sınarsınız. Kırılganlığın kökü neredeyse hep aynıdır: uzunluk alanına güven, durum ihlali, tip karışıklığı. Doğru kullanım izinli/izole ortam, sanitizer'lı instrumentation ve tekrar-üretilebilir triyaj gerektirir; checksum, şifreleme ve handshake en sık tuzaklardır. Amaç saldırı değil; savunulabilir parser yazmak, protokol-farkında tespit kurmak ve sürekli fuzzing'i CI'ya yerleştirerek hataları saldırgandan önce bulmaktır.
