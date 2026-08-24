# Modern DNS Protokolleri (DoH / DoT / DNSSEC / DNS-over-QUIC)

## Giriş: Klasik DNS'in Yapısal Sorunu

Klasik DNS (RFC 1035), İnternet'in en eski protokollerinden biridir ve bugün hâlâ omurga
işlevi görür. Temel akış basittir: bir istemci (stub resolver), bir alan adını (örneğin
`ornek.com`) IP adresine çevirmek için genellikle UDP 53 portu üzerinden bir sorgu gönderir,
recursive resolver da yetkili sunuculara (authoritative servers) danışarak yanıtı döner.

Bu tasarımın iki kök zafiyeti vardır ve modern protokollerin tamamı bu iki eksiği kapatmaya
çalışır:

1. **Gizlilik yok (confidentiality yok):** Klasik DNS sorguları düz metindir (cleartext).
   Aradaki herhangi bir cihaz (ISP, kurumsal proxy, kafe Wi-Fi'sindeki bir saldırgan)
   kullanıcının hangi siteleri ziyaret ettiğini birebir okuyabilir. Bu, hem gözetleme
   (surveillance) hem de sansür/filtreleme için birincil kaynaktır.
2. **Kaynak doğrulama yok (integrity/authenticity yok):** İstemci, dönen yanıtın gerçekten
   yetkili sunucudan geldiğini ve yolda değiştirilmediğini kanıtlayamaz. Bu, cache poisoning
   ve on-path (aradaki) yanıt sahteciliğini mümkün kılar.

Önemli bir ayrım hemen kurulmalıdır: **şifreleme (encryption) ile doğrulama (authentication)
farklı problemlerdir.** DoH ve DoT sorguyu *taşıma kanalında* şifreler (istemci ile resolver
arası). DNSSEC ise *verinin kendisini* imzalar (yetkili sunucudan istemciye kadar). İkisi
birbirinin yerine geçmez; birbirini tamamlar. Bu ayrımı karıştırmak, en yaygın kavramsal
hatadır.

---

## DoT — DNS over TLS

### Tanım

DoT (RFC 7858), klasik DNS mesajlarını bir TLS oturumu içine yerleştirir. Yani protokolün
kablo formatı (wire format) hemen hemen aynı DNS mesajıdır; yalnızca TCP + TLS ile sarmalanmış
(wrapped) ve **özel bir porta**, TCP 853'e taşınmıştır.

### Çalışma mantığı

İstemci TCP 853'e bağlanır, TLS el sıkışması (handshake) yapar, resolver'ın sertifikasını
doğrular ve ardından şifreli tünel içinde standart DNS sorgu/yanıtlarını gönderir. Mesaj
başında iki baytlık uzunluk öneki (length prefix) bulunur; bu, TCP tabanlı DNS'in zaten
kullandığı yapıdır.

DoT'un tasarım felsefesi **dürüsttür ve ağ yöneticisi dostudur:** ayrı bir port (853)
kullandığı için ağ üzerinde "bu trafik DNS'tir" diye açıkça tanımlanabilir. Bir kurum isterse
853 portunu toptan engelleyerek DoT kullanımını görebilir ve politika uygulayabilir. Trafik
şifrelidir ama *varlığı* gizli değildir.

### Doğru kullanım ve tuzaklar

- **Sertifika doğrulama şart.** DoT'un güvenlik kazancı, resolver'ın kimliğinin doğrulanmasına
  bağlıdır. RFC 7858, iki profil tanımlar: "opportunistic" (fırsatçı, kimlik doğrulamadan
  şifreleme) ve "strict" (kimlik doğrulamalı). Yalnızca strict profil, aktif MITM'e (aradaki
  adam saldırısı) karşı gerçek koruma sağlar. Opportunistic mod, pasif dinlemeyi engeller ama
  aktif saldırıya açıktır.
- **Yaygın hata:** DoT açtım diye "artık kimse görmüyor" varsaymak. Ağ yöneticisi 853 trafiğini
  görür ve sayabilir; ayrıca resolver'ın *kendisi* tüm sorgularınızı görür. Şifreleme, güveni
  ISP'den resolver operatörüne kaydırır — yok etmez.

---

## DoH — DNS over HTTPS

### Tanım

DoH (RFC 8484), DNS sorgularını HTTPS içine, yani standart **TCP 443** portundaki web
trafiğinin içine yerleştirir. Sorgu, bir HTTP isteği olarak taşınır; genellikle `application/
dns-message` MIME tipiyle POST gövdesinde ya da GET'te base64url ile kodlanmış olarak gider.
Yanıt da aynı MIME tipiyle döner.

### Kök neden / neden 443?

DoH'un kritik tasarım kararı, ayrı bir port yerine 443'ü seçmesidir. Bunun sonucu şudur:
**DoH trafiği, diğer HTTPS web trafiğinden ağ üzerinde ayırt edilemez.** Bir gözlemci için
443'e giden şifreli bir akış, bir web sitesi olabilir de DoH sorgusu olabilir de. Bu, DoH'u
gizlilik ve **sansür atlatma (censorship circumvention)** açısından çok güçlü, ama ağ
yönetimi/kurumsal güvenlik açısından çok zorlayıcı kılar.

### DoH'un savunma/tespit zorluğu (exhaust/detection problemi)

DoH'un "egzoz ve tespit zorluğu" tam da burada yatar. Klasik bir kurumsal senaryoda güvenlik
ekibi, çalışanların DNS sorgularını merkezi resolver üzerinden görür, kötü amaçlı alan adlarını
(malware C2, phishing) DNS seviyesinde bloklar. DoH bu görünürlüğü kırar:

- **DNS tabanlı filtreleme atlatma:** Bir uygulama (hatta tarayıcı, hatta malware) kendi DoH
  sunucusuna doğrudan 443 üzerinden bağlanırsa, kurumun DNS filtresi tamamen devre dışı kalır.
  Bloklu bir alan adı, DoH tüneliyle çözümlenebilir. Buna literatürde "DNS-based security
  controls bypass" denir.
- **Tespit neden zor?** Trafik 443'te ve TLS ile şifreli. Payload görünmüyor. Ayırt etmek için
  içerik değil, **yan sinyaller (side signals)** kullanmak gerekir.

### DoH tespit yaklaşımları (savunma tarafı)

Kavramsal olarak, savunma ekiplerinin DoH'u ağda ayırt etmek için başvurduğu yöntemler:

1. **Bilinen DoH endpoint listeleri:** Büyük public DoH sağlayıcılarının IP adresleri ve alan
   adları kamuya açıktır. Bu listelerle IP/SNI eşleşmesi en pratik ilk savunmadır. Kurum, kendi
   onaylı resolver'ı dışındaki bilinen DoH sunucularına 443'ü engelleyebilir.
2. **TLS SNI / ECH gözlemi:** TLS ClientHello içindeki SNI (Server Name Indication) hâlâ çoğu
   zaman düz metindir ve hedef alan adını açık eder. Ancak ECH (Encrypted Client Hello)
   yaygınlaştıkça bu sinyal de kaybolur — bu, savunma tarafının önündeki büyüyen bir zorluktur.
3. **Trafik/davranış analizi (traffic analysis):** DoH akışlarının paket boyutu dağılımı,
   zamanlama (inter-arrival times) ve akış süresi, normal web taramasından istatistiksel olarak
   farklı olabilir. Makine öğrenmesi tabanlı sınıflandırıcılar bu yönde çalışır; ama bu
   olasılıksaldır (probabilistic), kesin değildir ve false positive riski taşır.
4. **Politika ile yönlendirme:** En sağlam kurumsal yaklaşım tespit değil, **zorlamadır**:
   onaylı DoH resolver'ını kurum çapında dayatmak (örneğin tarayıcı politikaları/MDM ile) ve
   diğer tüm giden DNS/DoH yollarını kapatmak. "Tespit et" yerine "tek meşru yolu bırak"
   stratejisi daha güvenilirdir.

### Doğru kullanım ve tuzaklar

- **Yaygın hata:** DoH'u yalnızca gizlilik özelliği sanıp güvenlik kontrolü yerine koymak. DoH,
  içerik doğrulaması yapmaz; kötü bir resolver seçerseniz yine yalan yanıt alabilirsiniz.
- **Yaygın hata:** DoH'u DNSSEC'in yerine koymak. DoH kanalı korur, veriyi imzalamaz.

---

## DNSSEC — DNS Security Extensions

### Tanım

DNSSEC (RFC 4033/4034/4035), DNS *verisinin* kaynağını ve bütünlüğünü kriptografik imzalarla
doğrulayan bir uzantı ailesidir. Amacı gizlilik değildir — DNSSEC sorguları şifrelemez;
herkes okuyabilir. Amacı, dönen yanıtın gerçekten o alan adının sahibi tarafından üretildiğini
ve yolda değiştirilmediğini kanıtlamaktır.

### Çalışma mantığı: güven zinciri (chain of trust)

DNSSEC'in kalbi, kök bölgeden (root zone) hedef alan adına kadar uzanan bir **imza zinciridir.**
Temel kayıt tipleri:

- **RRSIG:** Bir kayıt kümesinin (RRset) dijital imzası.
- **DNSKEY:** Bölgenin imzalama anahtarını (public key) taşır. Pratikte iki rol vardır: ZSK
  (Zone Signing Key, kayıtları imzalar) ve KSK (Key Signing Key, DNSKEY setini imzalar).
- **DS (Delegation Signer):** Bir üst bölgede tutulan ve alt bölgenin KSK'sinin hash'ini
  içeren kayıt. Bu, zincirin halkalarını birbirine bağlar.
- **NSEC / NSEC3:** "Bu kayıt yok" (nonexistence) durumunu **doğrulanabilir** şekilde ispatlar.

Doğrulama şöyle işler (kavramsal): Doğrulayıcı resolver, kök bölgenin public anahtarına
("trust anchor") baştan güvenir. Kök, `.com` bölgesinin DS kaydını imzalar; `.com`, `ornek.com`
bölgesinin DS kaydını imzalar; `ornek.com` da kendi kayıtlarını RRSIG ile imzalar. Her halkada
resolver, bir üstteki DS/DNSKEY üzerinden imzayı doğrular. Zincirdeki herhangi bir halka
kırılırsa (imza yanlış, süresi geçmiş, DS eşleşmiyor), yanıt "bogus" (geçersiz) sayılır ve
güvenli resolver bunu istemciye vermez — SERVFAIL döner.

### NSEC vs NSEC3: bir tasarım tuzağı

NSEC, "yok" ispatı için bölgedeki komşu adları açık eder; bu, tüm bölgenin adlarının
sıralanmasına (zone walking / enumeration) izin verir. NSEC3, adları hash'leyerek bunu
zorlaştırmak için tasarlanmıştır ama tam çözüm değildir; offline hash kırma ile kısmen
enumerate edilebilir. Bu, "bir güvenlik özelliği başka bir bilgi sızıntısı doğurabilir"
prensibinin iyi bir örneğidir.

### Doğru kullanım ve tuzaklar

- **En büyük operasyonel tuzak: anahtar döndürme (key rollover) ve imza süresi (RRSIG
  expiration).** RRSIG'lerin geçerlilik penceresi vardır; yenilenmezse bölge, teknik olarak
  hatasız görünse bile bir anda doğrulanamaz hale gelir ve DNSSEC doğrulayan resolver'lar için
  alan adı **erişilemez** olur. Birçok gerçek kesinti, saldırı değil, süresi geçmiş imza
  yüzündendir.
- **DS güncelleme koordinasyonu:** KSK değiştiğinde, üst bölgedeki DS kaydı da güncellenmelidir.
  Bu iki adımın zamanlaması yanlışsa zincir kopar.
- **Yaygın hata: DNSSEC'i gizlilik çözümü sanmak.** DNSSEC verinin doğruluğunu garanti eder,
  gizliliğini değil. Gerçek gizlilik + doğrulama için DoT/DoH (kanal) ile DNSSEC (veri)
  *birlikte* kullanılır.
- **Yaygın hata:** "DNSSEC açık, artık cache poisoning imkânsız" demek. DNSSEC doğrulaması
  yalnızca **doğrulayan resolver'da** işe yarar; istemci ile resolver arası (last mile)
  imzalanmış veriyi taşımıyorsa, o segment hâlâ savunmasız olabilir. Bu yüzden last-mile için
  DoT/DoH önemlidir.

---

## DNS-over-QUIC (DoQ) ve HTTP/3 boyutu

### Tanım

DoQ (RFC 9250), DNS mesajlarını **QUIC** taşıma protokolü üzerinden gönderir. QUIC, UDP
üzerinde çalışan, TLS 1.3'ü içine gömülü (built-in), akış çoğullamalı (multiplexed streams)
modern bir taşıma katmanıdır. DoQ genellikle UDP 853 portunu kullanır (DoT'un TCP 853'üne
paralel bir tercih).

### Neden QUIC? Kök neden

DoT (TCP+TLS) ve DoH/2 (TCP+TLS+HTTP) belirli sorunlar taşır:

- **Head-of-line blocking:** TCP'de kaybolan tek bir paket, arkasındaki tüm verinin işlenmesini
  bekletir. DNS gibi çok sayıda küçük, bağımsız sorgu için bu verimsizdir. QUIC, her sorguyu
  ayrı bir stream'e koyarak bir stream'deki kaybın diğerlerini bloklamasını önler.
- **El sıkışma gecikmesi (handshake latency):** QUIC, taşıma ve TLS el sıkışmasını birleştirir;
  0-RTT/1-RTT ile bağlantı kurulumunu hızlandırabilir. Gecikmeye duyarlı DNS için bu değerlidir.
- **Bağlantı taşınabilirliği (connection migration):** QUIC, connection ID kullandığı için IP
  değişse bile (Wi-Fi'den mobil ağa geçiş gibi) bağlantıyı sürdürebilir.

### Gizlilik/tespit açısından

DoQ, DoT gibi ayrı bir port (853) tercih ettiğinde ağda tanımlanabilir. Ancak **DNS-over-HTTP/3
(DoH3)** — yani DoH'un HTTP/3 üzerinden çalışan biçimi — 443/UDP'de web trafiğiyle karışır ve
DoH ile aynı tespit zorluğunu QUIC dünyasına taşır. Savunma tarafı açısından kritik nokta: pek
çok eski güvenlik cihazı ve firewall, UDP 443 (QUIC) trafiğini derinlemesine denetleyemez.
Bunun pratik ve yaygın bir savunma refleksi, **QUIC'i (UDP 443) bloklayıp trafiği görünür
TCP/443 HTTPS'e (TLS denetlenebilir yola) düşürmektir.** Bu, gizliliği bir miktar azaltır ama
görünürlük kazandırır; bir denge (trade-off) kararıdır.

### 0-RTT'nin tuzağı

QUIC'in 0-RTT hızlandırması, **replay saldırılarına** (replay attack) karşı hassastır: 0-RTT
verisi tekrar oynatılabilir. Bu yüzden yalnızca idempotent (tekrarı zararsız) işlemler 0-RTT'de
gönderilmelidir. DoQ tasarımı bu riski dikkate alır; uygulamada yanlış konfigürasyon güvenlik
zafiyeti doğurabilir.

---

## Karşılaştırma Tablosu (Kavramsal)

| Özellik | Klasik DNS | DoT | DoH | DNSSEC | DoQ / DoH3 |
|---|---|---|---|---|---|
| Kanal şifreleme | Yok | Var (TLS) | Var (HTTPS) | Yok | Var (QUIC/TLS1.3) |
| Veri imzalama/doğrulama | Yok | Yok | Yok | **Var** | Yok |
| Tipik port | UDP 53 | TCP 853 | TCP 443 | (taşıma-bağımsız) | UDP 853 / UDP 443 |
| Ağda ayırt edilebilir mi | Evet | Evet (ayrı port) | Zor (443'te gizli) | Evet | DoQ: evet, DoH3: zor |
| Asıl derdi | — | Gizlilik | Gizlilik + atlatma | Bütünlük/kaynak | Gizlilik + performans |

Bu tablonun en önemli okuması: **hiçbir satır tek başına "güvenli DNS" değildir.** DNSSEC
sütunu doğrulama sağlar ama gizlilik vermez; DoT/DoH/DoQ sütunları gizlilik verir ama veriyi
imzalamaz. Gerçek güvenlik, "doğrulayan resolver + şifreli last-mile kanal" bileşimidir.

---

## Savunma ve Tespit İçin Pratik Çerçeve

Savunma mimarisi kurarken kavramsal öncelik sırası:

1. **Onaylı resolver dayatın:** Kurumun kendi (tercihen DoT/DoH destekli, DNSSEC doğrulayan)
   resolver'ını tek meşru yol yapın. İstemcilerin kendi başına harici resolver seçmesini
   politika ile kapatın. Bu, tespit uğraşının çoğunu gereksiz kılar.
2. **Rogue DoH'u sınırlayın:** Bilinen public DoH endpoint listelerini engelleyin; onaylı olan
   dışındaki DoH sunucularına 443'ü kapatın. Bu asla %100 değildir (yeni endpoint'ler çıkar),
   ama saldırı yüzeyini (attack surface) ciddi düşürür.
3. **QUIC görünürlüğü:** UDP 443 denetlenemiyorsa, politika olarak QUIC'i bloklayıp TCP/443'e
   düşürmeyi değerlendirin — böylece en azından SNI ve TLS meta verisi gözlemlenebilir kalır.
4. **DNSSEC doğrulamasını resolver'da açın:** Doğrulamayı istemciye değil, güvenli
   resolver'a yaptırın; bogus yanıtları düşürün. Ama last-mile'ı da DoT/DoH ile koruyun.
5. **Log ve telemetri:** Onaylı resolver üzerindeki sorgu loglarını (NXDOMAIN oranı, nadir/uzun
   alt alan adları — DNS tünelleme sinyali, ani beacon'lama) izleyin. DoH atlatmasını içerik
   yerine bu davranışsal anomalilerle yakalarsınız.

### En sık yapılan kavramsal hatalar (özet)

- **Şifreleme ile doğrulamayı karıştırmak:** DoH/DoT ≠ DNSSEC. Biri kanalı, öteki veriyi korur.
- **"DoH açtım, artık güvendeyim" yanılgısı:** DoH güveni resolver operatörüne devreder; kötü
  resolver seçilirse gizlilik ve doğruluk ikisi de kaybolur.
- **DoH'u güvenlik kontrolü sanmak:** DoH, malware alan adlarını *bloklamaz*; aksine kötü
  yazılım onu filtre atlatmak için kullanabilir.
- **DNSSEC'i "aç, unut" sanmak:** İmza süresi ve anahtar döndürme aktif operasyon ister; ihmal,
  saldırı olmadan kesinti doğurur.
- **QUIC/DoH3'ü göz ardı etmek:** Yalnızca 443/TCP HTTPS'i denetleyen eski savunmalar, 443/UDP
  QUIC üzerinden akan DoH3'ü tamamen kaçırır.

---

## Sonuç

Modern DNS protokolleri, klasik DNS'in iki kök zafiyetine — gizlilik yokluğu ve doğrulama
yokluğu — iki farklı cepheden yanıt verir. DoT, DoH ve DoQ **taşıma kanalını** şifreleyerek
gizliliği; DNSSEC ise **verinin kendisini** imzalayarak bütünlüğü ve kaynağı hedefler. Bu iki
grubu birbirinin alternatifi sanmak, en verimli hatadır: doğru mimari, DNSSEC doğrulayan bir
resolver'a şifreli bir last-mile kanalla (DoT/DoH/DoQ) bağlanmaktır.

Savunma açısından asıl zorluk DoH ve DoH3'ün 443 üzerindeki görünmezliğidir; bu, klasik DNS
filtrelemesini atlatabilir. Cevap, kusursuz bir tespit hayali kurmak değil, **onaylı tek yolu
dayatıp geri kalanı daraltmak** ve davranışsal telemetriyle anomalileri izlemektir. Protokolün
iç yapısını — güven zinciri, port seçimleri, QUIC'in stream modeli, imza süreleri — anlamak,
hem sağlam bir savunma kurmanın hem de gerçek risklerle sahte güven hislerini ayırt etmenin ön
koşuludur.
