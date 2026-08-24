# WebSocket ve Gerçek Zamanlı İletişim

## Tanım

WebSocket, tek bir TCP bağlantısı üzerinden istemci (client) ile sunucu (server) arasında **çift yönlü (full-duplex)**, sürekli açık kalan bir iletişim kanalı kuran bir protokoldür. "Full-duplex" ifadesi burada kritik: iki taraf da aynı anda, birbirini beklemeden mesaj gönderebilir. Bu, klasik HTTP'nin "istemci sorar, sunucu cevaplar, bağlantı kapanır" döngüsünden temelde farklıdır.

WebSocket, bir web standardı olarak IETF tarafından RFC 6455 numarasıyla tanımlanmıştır. Tarayıcı tarafında `ws://` (şifrelenmemiş) ve `wss://` (TLS üzerinden şifreli) şeması ile adreslenir. `wss://`, `https://`'in WebSocket karşılığıdır ve üretim (production) ortamında pratikte tek kabul edilebilir seçenektir.

Gerçek zamanlı iletişim (real-time communication) ise daha geniş bir şemsiye terimdir: kullanıcının bir olayı, olay gerçekleştiği anda ya da algılanamayacak kadar kısa bir gecikmeyle görmesini sağlayan mimarilerin tümünü kapsar. WebSocket bu amaç için en bilinen araçtır ama tek araç değildir; Server-Sent Events (SSE), long polling ve WebTransport gibi alternatifleri de vardır. Bu makale ağırlığı WebSocket'e verir ama "ne zaman WebSocket, ne zaman başka bir şey" sorusunu da yanıtlar.

## Kök Neden: HTTP Neden Gerçek Zamanlı İletişim İçin Yetersizdi

WebSocket'in neden var olduğunu anlamak için önce HTTP'nin doğasındaki kısıtı görmek gerekir. Klasik HTTP/1.1, **request-response** (istek-yanıt) modeli üzerine kuruludur ve bu model tek yönlüdür: iletişimi her zaman istemci başlatır. Sunucunun, istemci sormadan kendiliğinden veri göndermesi (server push) bu modelde mümkün değildir. Bir sohbet uygulamasında karşı taraf mesaj yazdığında sunucu bunu size "itmek" ister, ama HTTP buna izin vermez; siz sormadan konuşamaz.

Bu kısıtı aşmak için yıllarca çeşitli hile (workaround) yöntemleri kullanıldı:

- **Polling**: İstemci her birkaç saniyede bir "yeni bir şey var mı?" diye sorar. Basittir ama israftır. Çoğu istek boş döner, yine de her istek için bir TCP/TLS el sıkışması (handshake), HTTP başlıkları (headers) ve sunucu tarafında işlem maliyeti oluşur. Gecikme (latency) de polling aralığı kadar kötüdür.
- **Long polling**: İstemci sorar, sunucu elinde veri yoksa cevabı bekletir, veri geldiğinde yanıtı gönderir; istemci hemen yeni bir istek açar. Gecikmeyi düzeltir ama her mesaj yeni bir HTTP istek-yanıt döngüsü demektir. Ayrıca sunucuda çok sayıda bekleyen (askıda) bağlantıyı tutmak gerekir.

Bu yöntemlerin ortak sorunu şudur: HTTP başlıklarının **overhead**'i (ek yükü) ve her mesaj için bağlantıyı yeniden kurma maliyeti, sık ve küçük mesajlar için orantısız derecede pahalıdır. Bir "yeni bir şey var mı" sorusu için yüzlerce byte başlık göndermek verimsizdir.

WebSocket bu problemi kökten çözer: **bağlantı bir kez kurulur ve açık kalır**. El sıkışma tamamlandıktan sonra HTTP başlıkları devreden çıkar; her mesaj yalnızca birkaç byte'lık hafif bir çerçeve (frame) başlığı taşır. Böylece hem gecikme minimuma iner hem de yüksek frekanslı iletişim ucuzlar.

## Çalışma Mantığı: El Sıkışmadan Çerçevelere

### HTTP'den Yükseltme (Upgrade Handshake)

WebSocket'in zarif tarafı, yeni bir port ya da yeni bir altyapı gerektirmemesidir. Bağlantı **normal bir HTTP isteği olarak başlar** ve sonra protokolü "yükseltir". İstemci şuna benzer bir istek gönderir:

```
GET /chat HTTP/1.1
Host: sunucu.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

Burada `Upgrade: websocket` ve `Connection: Upgrade` başlıkları sunucuya "bu HTTP bağlantısını WebSocket'e çevirelim" der. Sunucu kabul ederse özel bir yanıt döner:

```
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

`101 Switching Protocols` durum kodu, "artık bu bağlantı HTTP değil, WebSocket" anlamına gelir. Bu andan itibaren aynı TCP soketi üzerinden iki yönlü çerçeveler akmaya başlar.

`Sec-WebSocket-Key` ve `Sec-WebSocket-Accept` başlıklarının amacını anlamak önemlidir, çünkü sık yanlış anlaşılır: **bunlar güvenlik ya da kimlik doğrulama mekanizması değildir.** İstemci rastgele bir anahtar üretir; sunucu bu anahtarı sabit, standartla belirlenmiş bir GUID ile birleştirip SHA-1 hash'ini alır ve base64 ile kodlayıp geri döner. Bunun tek amacı, karşı tarafın gerçekten WebSocket protokolünü anlayan bir sunucu olduğunu doğrulamak ve WebSocket'ten habersiz bir ara katmanın (proxy, cache) yanıtı yanlışlıkla "geçerli" saymasını önlemektir. Kimlik doğrulama işini siz ayrıca yapmak zorundasınız.

### Çerçeveler (Frames) ve Maskeleme

El sıkışmadan sonra veri, **çerçeve (frame)** adı verilen küçük birimler halinde taşınır. Her çerçevenin bir opcode'u vardır: metin (text), ikili (binary), ping, pong ve bağlantı kapatma (close) gibi. Ping/pong çerçeveleri, bağlantının hâlâ canlı olduğunu kontrol etmek (heartbeat) için kullanılır; buna aşağıda döneceğiz.

Protokolün ilginç bir kuralı vardır: **istemciden sunucuya giden her çerçeve maskelenmek (masking) zorundadır**, sunucudan istemciye gidenler ise maskelenmez. Bu, keyfi bir tasarım değildir; kök nedeni bir güvenlik endişesidir. Maskeleme olmasaydı, saldırgan bir tarayıcı istemcisi, ağ üzerindeki eski/uyumsuz proxy'leri kandıracak biçimde HTTP'ye benzeyen veri gönderebilir ve **cache poisoning** (önbellek zehirlemesi) türü saldırılar yapabilirdi. Her çerçevede rastgele bir maske anahtarı kullanmak, gönderilen baytların öngörülemez olmasını sağlar ve bu saldırı sınıfını etkisiz kılar.

## Somut Örnek: Tarayıcıda WebSocket

Tarayıcı tarafında API şaşırtıcı derecede basittir. Karmaşıklık el sıkışma ve çerçevelemede saklıdır; geliştirici olarak bunları görmezsiniz.

```javascript
const soket = new WebSocket("wss://sunucu.example.com/chat");

soket.onopen = () => {
  soket.send(JSON.stringify({ tur: "katil", oda: "genel" }));
};

soket.onmessage = (olay) => {
  const veri = JSON.parse(olay.data);
  console.log("Sunucudan geldi:", veri);
};

soket.onclose = (olay) => {
  console.log("Bağlantı kapandı, kod:", olay.code);
};

soket.onerror = (hata) => {
  console.error("WebSocket hatası:", hata);
};
```

Sunucu tarafında ise (örneğin Node.js ile `ws` kütüphanesi kullanıldığında) mantık şuna benzer:

```javascript
import { WebSocketServer } from "ws";

const sunucu = new WebSocketServer({ port: 8080 });

sunucu.on("connection", (soket, istek) => {
  soket.on("message", (mesaj) => {
    // Gelen mesajı tüm bağlı istemcilere yayınla (broadcast)
    for (const istemci of sunucu.clients) {
      if (istemci.readyState === istemci.OPEN) {
        istemci.send(mesaj.toString());
      }
    }
  });

  soket.on("close", () => {
    // Temizlik: kullanıcıyı odalardan çıkar, kaynakları bırak
  });
});
```

Bu örnek, WebSocket'in tipik kullanım desenini gösterir: sunucu, bağlı istemcilerin bir listesini tutar ve bir olay olduğunda ilgili istemcilere mesajı iter. Sohbet uygulamaları, canlı skor tabloları, ortak (collaborative) doküman editörleri ve finansal fiyat akışları hep bu desenin türevleridir.

## Nerede Kullanılır, Nerede Kullanılmaz

WebSocket'i doğru yere koymak, onu doğru kullanmak kadar önemlidir. Genel kural şudur: **WebSocket, gerçekten iki yönlü ve/veya yüksek frekanslı iletişim gerektiğinde parlar; tek yönlü ya da seyrek güncellemeler için fazla ağırdır.**

WebSocket'in doğal olduğu senaryolar:

- **Sohbet ve mesajlaşma**: İki taraf da her an gönderip alır. Klasik full-duplex ihtiyacı.
- **Çok oyunculu oyunlar**: Düşük gecikme ve sürekli iki yönlü durum senkronizasyonu gerekir.
- **Ortak düzenleme (collaborative editing)**: Google Docs benzeri; her kullanıcının değişikliği anında herkese yansımalı.
- **Canlı işlem/fiyat akışları**: Finansal panolar, spor skorları; hem yüksek frekans hem düşük gecikme.

WebSocket'in **gereksiz** olduğu senaryolar:

- **Yalnızca sunucudan istemciye tek yönlü bildirim** akışı gerekiyorsa (örneğin bir bildirim beslemesi, ilerleme çubuğu, log akışı), Server-Sent Events (SSE) genellikle daha basit ve daha uygundur. Bunu bir sonraki bölümde açacağız.
- **Seyrek, tekil güncellemeler** için (dakikada bir kez değişen bir veri) kalıcı bağlantı tutmak israftır; basit polling ya da normal HTTP isteği yeterlidir.

Buradaki akıl yürütme şudur: kalıcı bir bağlantı bedava değildir. Sunucu, her açık WebSocket bağlantısı için bellek ve dosya tanıtıcısı (file descriptor) ayırır. Bir milyon eşzamanlı kullanıcı, bir milyon açık bağlantı demektir. Bu yükü yalnızca gerçekten gerektiğinde üstlenmek gerekir.

## Ölçekleme: Kalıcı Bağlantıların Bedeli

WebSocket'i ölçeklemek, klasik HTTP servislerini ölçeklemekten kavramsal olarak farklıdır ve bu fark çoğu ekibi hazırlıksız yakalar. Kök neden yine bağlantının **stateful** (durum tutan) ve **uzun ömürlü** oluşudur.

### Bağlantı Yapışkanlığı (Sticky Sessions) Problemi

Klasik HTTP'de bir load balancer, her isteği herhangi bir sunucuya dağıtabilir; istekler bağımsızdır (stateless). WebSocket'te ise bağlantı bir kez belirli bir sunucuyla kurulduktan sonra o bağlantının ömrü boyunca **aynı sunucuya bağlı kalması** gerekir; çünkü o bağlantının durumu (state) o sunucunun belleğindedir. Bu, load balancer'ın "sticky" (yapışkan) davranmasını gerektirir. Ayrıca load balancer'ın `Upgrade` başlığını doğru işleyip WebSocket yükseltmesini desteklemesi şarttır; aksi halde el sıkışma başarısız olur.

### Sunucular Arası Mesaj Yayma (Fan-out) Problemi

İkinci ve daha zor problem şudur: Kullanıcılar birden fazla sunucuya dağıldığında, bir sunucuya bağlı kullanıcının gönderdiği mesajın, başka bir sunucuya bağlı kullanıcılara ulaşması gerekir. Sunucu A'daki kullanıcı bir sohbet odasına yazdığında, Sunucu B'ye bağlı aynı odadaki kullanıcılar bunu görmelidir. Ama Sunucu A, Sunucu B'nin bağlantılarını doğrudan bilmez.

Bu problemi çözmenin standart yolu, sunucuların arasına bir **mesaj yayın katmanı (pub/sub)** koymaktır. Redis'in yayınla/abone ol (publish/subscribe) özelliği ya da özel bir mesaj kuyruğu (message broker) sık kullanılan çözümlerdir. Mimari şöyle işler: bir sunucu mesaj alır, bunu ortak pub/sub kanalına yayınlar; tüm sunucular bu kanalı dinler ve kendi bağlı istemcilerine iletir. Böylece yatay ölçekleme (horizontal scaling) mümkün olur.

### Bağlantı Sayısı Sınırları

Tek bir sunucunun taşıyabileceği eşzamanlı bağlantı sayısı; bellek, dosya tanıtıcısı limitleri (işletim sistemindeki `ulimit` benzeri ayarlar) ve olay döngüsünün (event loop) verimliliği ile sınırlıdır. Modern, olay tabanlı (event-driven, non-blocking) sunucular tek makinede on binlerce hatta yüz binlerce bağlantı tutabilir; ama bu sayı iş yükünüze, mesaj frekansınıza ve her bağlantı başına tuttuğunuz duruma bağlı olarak ciddi biçimde değişir. Kesin bir sayı vermek yanıltıcı olur; doğru yaklaşım, gerçek yük altında ölçüm yapmaktır (load testing).

## Yaygın Hatalar ve Tuzaklar

### Yeniden Bağlanmayı (Reconnection) Ele Almamak

En sık yapılan hata budur. WebSocket bağlantıları **kopar**: mobil ağlarda hücre değişimi, Wi-Fi'den mobil veriye geçiş, ara proxy'lerin zaman aşımı, sunucu yeniden başlatması... Bağlantının sonsuza dek açık kalacağını varsaymak temel bir yanılgıdır. Uygulama, `onclose` olayında otomatik yeniden bağlanma mantığı içermelidir.

Ancak burada da bir tuzak vardır: Sunucu çöktüğünde tüm istemciler aynı anda yeniden bağlanmaya çalışırsa, sunucu ayağa kalkar kalkmaz **thundering herd** (gürleyen sürü) etkisiyle tekrar çöker. Çözüm, **üstel geri çekilme (exponential backoff)** ve rastgele bir gecikme (jitter) eklemektir: her başarısız denemede bekleme süresini artırın ve üzerine küçük bir rastgelelik koyun ki tüm istemciler tam olarak aynı anda tekrar denemesin.

### Ölü Bağlantıları Tespit Etmemek (Heartbeat Eksikliği)

TCP bağlantısı bazen sessizce ölür: karşı taraf gitmiştir ama bunu bildiren bir paket gelmez ("half-open connection"). Bu durumda sunucu, aslında gitmiş bir istemci için kaynak tutmaya devam eder. Çözüm, düzenli aralıklarla **ping/pong** çerçeveleri göndermektir. Bir tarafın ping'ine belirli süre içinde pong gelmezse, o bağlantı ölü sayılıp kapatılır. Bu, hem hayalet bağlantıları temizler hem de aradaki proxy'lerin boşta kalan bağlantıyı zaman aşımıyla kapatmasını önler.

### Kimlik Doğrulamayı Yanlış Konumlandırmak

Sık görülen bir güvenlik zaafı, WebSocket bağlantısının el sıkışma anında kimlik doğrulamasını (authentication) atlamaktır. `wss://` yalnızca taşımayı şifreler; kimin bağlandığını doğrulamaz. Kimlik doğrulama genellikle el sıkışma sırasındaki HTTP isteğinde yapılır (çerez/cookie ya da bir token ile). Burada dikkat edilmesi gereken bir başka nokta, tarayıcı WebSocket API'sinin özel HTTP başlıkları eklemeye izin vermemesidir; bu yüzden token'ı taşımak için ya cookie'ye ya da bir alt protokol / sorgu parametresi gibi dolaylı yollara başvurulur. Sorgu parametresine token koymak, URL'lerin loglara düşmesi riski taşıdığı için dikkatli değerlendirilmelidir.

### Origin Kontrolünü Atlamak (CSWSH)

WebSocket, tarayıcının **same-origin policy** kısıtına HTTP kadar sıkı tabi değildir; farklı bir origin'deki kötü niyetli bir sayfa, kurbanın cookie'leri ile sizin WebSocket sunucunuza bağlanmayı deneyebilir. Buna **Cross-Site WebSocket Hijacking (CSWSH)** denir. Korunmak için sunucu, el sıkışmadaki `Origin` başlığını doğrulamalı ve yalnızca beklenen origin'lerden gelen bağlantıları kabul etmelidir. Kimlik doğrulamayı yalnızca cookie'ye dayandırmak, bu saldırıya kapı aralar; bu yüzden ek bir token doğrulaması güvenliği artırır.

### Arka Basınç (Backpressure) İhmali

Sunucu, istemcinin alabileceğinden daha hızlı mesaj gönderirse, gönderilmeyi bekleyen veriler sunucu belleğinde birikir (buffer şişer) ve sonunda bellek tükenir. Yüksek hacimli akışlarda, istemcinin tampon (buffer) doluluğunu izlemek ve gerektiğinde göndermeyi yavaşlatmak ya da mesaj atlamak gerekir. Tarayıcı tarafında `bufferedAmount` özelliği bu izleme için kullanılır.

## Alternatif: Server-Sent Events (SSE)

WebSocket her problem için doğru araç değildir ve en önemli alternatifi Server-Sent Events'tir. İkisini karşılaştırmak, "gerçek zamanlı" derken aslında neye ihtiyacınız olduğunu netleştirir.

**SSE, tek yönlüdür**: yalnızca sunucudan istemciye veri akıtır. İstemciden sunucuya iletişim için normal HTTP istekleri kullanılır. SSE, düz HTTP üzerinde çalışır; `text/event-stream` içerik türüyle sunucu, açık kalan bir yanıt gövdesine (response body) olayları peş peşe yazar. Tarayıcı tarafında `EventSource` API'si ile tüketilir.

SSE'nin WebSocket'e göre avantajları, kök nedenini basitliğinden alır:

- **Otomatik yeniden bağlanma yerleşiktir**: `EventSource`, bağlantı koptuğunda kendiliğinden yeniden bağlanır ve `Last-Event-ID` başlığı sayesinde kaldığı yerden devam edebilir. WebSocket'te bu mantığı elle yazmanız gerekir.
- **Sıradan HTTP'dir**: Var olan HTTP altyapısı, proxy'ler, load balancer'lar ve kimlik doğrulama mekanizmalarıyla sorunsuz çalışır. WebSocket'in `Upgrade` el sıkışmasının yol açtığı proxy/altyapı sorunlarını yaşamazsınız.
- **Daha basittir**: Çerçeveleme, maskeleme, ping/pong gibi ayrıntılar yoktur.

SSE'nin kısıtları da vardır:

- **Yalnızca metin taşır** (ikili veri için doğal değildir; base64 ile kodlamak gerekir, bu da ek yük demektir).
- **HTTP/1.1 üzerinde tarayıcı başına eşzamanlı bağlantı sayısı sınırlıdır** (tarihsel olarak alan adı başına altı bağlantı civarı). Birden çok sekme açan kullanıcılarda bu limit sorun çıkarabilir; HTTP/2 ile bu sorun büyük ölçüde hafifler çünkü bağlantılar çoğullanır (multiplexing).

**Doğru seçim kuralı**: Eğer akış esasen **sunucudan istemciye tek yönlü** ise (bildirimler, canlı feed, ilerleme durumu, log akışı) SSE genellikle daha az uğraşla daha sağlam bir çözümdür. Gerçekten **çift yönlü ve düşük gecikmeli** iletişim (sohbet, oyun, ortak düzenleme) gerekiyorsa WebSocket doğru araçtır.

### Diğer Alternatifler

Tabloyu tamamlamak için birkaç seçenek daha:

- **Long polling**: Ne WebSocket ne SSE kullanılamadığında (çok eski istemciler, kısıtlı ağlar) yedek (fallback) olarak hâlâ kullanılır. Kütüphaneler (örneğin çeşitli gerçek zamanlı çatılar) genellikle önce WebSocket dener, başarısız olursa long polling'e düşer.
- **WebTransport**: HTTP/3 ve QUIC üzerine kurulu, daha yeni bir standart. Güvenilir ve güvenilmez (unreliable) veri akışlarını destekler ve baş-of-line (head-of-line) tıkanıklığı gibi TCP kaynaklı sorunları hafifletmeyi hedefler. Oyun gibi gecikmeye çok duyarlı uygulamalar için gelecek vaat eder, ama tarayıcı ve altyapı desteği WebSocket kadar olgun değildir.
- **HTTP/2 & HTTP/3 server push kavramları**: Bunlar WebSocket'in yerine geçen genel amaçlı çift yönlü mesajlaşma çözümleri değildir; farklı problemlere hitap ederler ve bu yüzden gerçek zamanlı uygulama katmanı iletişiminde doğrudan ikame sayılmazlar.

## En İyi Pratikler

Bu makale boyunca dağınık halde geçen ilkeleri bir arada toplayalım; bunlar üretim ortamında WebSocket kullanan sistemlerin ortak paydasıdır:

1. **Her zaman `wss://` kullanın.** Şifrelenmemiş `ws://`, üretimde kabul edilemez; hem gizlilik hem de aradaki proxy'lerin bağlantıyı bozması açısından risklidir. TLS ayrıca WebSocket trafiğinin ara katmanlarca yanlış yorumlanmasını da azaltır.

2. **Yeniden bağlanmayı üstel geri çekilme ve jitter ile tasarlayın.** Bağlantının kopacağını baştan kabul edin ve thundering herd'ü önleyin.

3. **Ping/pong heartbeat kurun.** Ölü bağlantıları tespit edin, hayalet bağlantıların kaynak sızdırmasını (resource leak) engelleyin ve ara proxy zaman aşımlarını önleyin.

4. **Kimlik doğrulamayı el sıkışma anında ve sağlam biçimde yapın; `Origin` başlığını doğrulayın.** `wss://` şifreler ama yetkilendirmez; CSWSH'e karşı korunun.

5. **Ölçeklemeyi baştan planlayın.** Sticky session gerektiğini ve sunucular arası mesaj yayımı için bir pub/sub katmanına ihtiyaç duyacağınızı en baştan varsayın; tek sunucu için yazılmış bir kod, ikinci sunucu eklendiğinde sessizce bozulur.

6. **Arka basıncı (backpressure) izleyin.** Yavaş istemcilerin sunucu belleğini şişirmesine izin vermeyin; `bufferedAmount` benzeri göstergeleri takip edin.

7. **Doğru aracı seçin.** İhtiyaç tek yönlü ise SSE'yi, seyrek güncellemeler ise basit polling'i ciddi biçimde değerlendirin. WebSocket güçlüdür ama her kalıcı bağlantının bir maliyeti vardır ve gereksiz kullanıldığında bu maliyet ölçekte katlanır.

8. **Mesaj formatını ve versiyonlamayı düşünün.** Tarafların aynı mesaj şemasını konuştuğundan emin olun; protokolünüze bir sürüm alanı ekleyin ki istemci ve sunucu farklı sürümlerdeyken zarifçe uyum sağlayabilsin.

## Özet

WebSocket, HTTP'nin tek yönlü istek-yanıt modelinin gerçek zamanlı iletişim için yetersiz kalması sorununa verilmiş temiz bir yanıttır: tek bir kalıcı TCP bağlantısı üzerinden, düşük ek yükle, çift yönlü mesajlaşma sağlar. Gücü, bu kalıcılıktan ve full-duplex doğasından gelir; zorlukları da yine aynı yerden. Kalıcı ve durum tutan bağlantılar, ölçeklemede sticky session ve pub/sub gerektirir; kırılganlıkları yeniden bağlanma ve heartbeat mantığını zorunlu kılar; güvenlik açısından `Origin` doğrulaması ve sağlam kimlik doğrulaması ister. Buna karşılık ihtiyacınız yalnızca sunucudan istemciye tek yönlü akışsa, Server-Sent Events çoğu zaman daha basit ve daha dayanıklı bir seçimdir. Uzman yaklaşım, "her yerde WebSocket" reflekssinden kaçınıp problemin gerçekten çift yönlü mü yoksa tek yönlü mü olduğunu doğru teşhis etmek ve aracı buna göre seçmektir.
