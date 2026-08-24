# 12-Factor App: Bulut-Doğal Uygulamalar İçin Metodoloji

## Tanım

**12-Factor App**, modern web uygulamalarını nasıl inşa etmemiz gerektiğini tarif eden bir metodoloji ve ilkeler bütünüdür. 2011 yılında Heroku ekibinden Adam Wiggins ve arkadaşları tarafından yayımlanmıştır. O dönemde Heroku, üzerinde binlerce farklı uygulamanın çalıştığı bir Platform-as-a-Service (PaaS) idi; ekip, hangi uygulamaların sorunsuz ölçeklendiğini, hangilerinin sürekli operasyonel dert çıkardığını yakından gözlemleyebiliyordu. 12 faktör, işte bu gözlemlerin damıtılmış hâlidir: "Sorunsuz çalışan uygulamalar şu ortak özelliklere sahip, dert çıkaranlar ise şunları ihlal ediyor" tespitidir.

Metodolojinin özü tek bir cümlede toplanabilir: uygulamayı, altında çalıştığı işletim sistemine ve altyapıya olabildiğince gevşek bağlı (loosely coupled), taşınabilir (portable) ve öngörülebilir kılmak. Böyle bir uygulama; farklı ortamlar arasında (geliştirici makinesi, test, staging, production) minimum farkla taşınabilir, yatay olarak (horizontal) ölçeklenebilir ve otomatik dağıtım (deployment) süreçlerine girebilir.

12 faktörün tamamı önemli olsa da, bu makale bulut-doğal (cloud-native) mimarinin bel kemiğini oluşturan beş faktöre odaklanır: **config (yapılandırma), statelessness (durumsuzluk), log stream (log akışı), disposability (atılabilirlik)** ve bunların hepsini bir arada tutan **bulut-doğal düşünce biçimi**.

## Kök Neden: Neden Böyle Bir Metodolojiye İhtiyaç Duyuldu?

Bir uygulamanın "iyi" olmasını sağlayan şeyi anlamak için önce neyin bozulduğunu görmek gerekir. Geleneksel uygulama dağıtımında sunucu, uzun ömürlü ve elle bakımı yapılan bir varlıktı. Sistem yöneticisi sunucuya SSH ile bağlanır, dosyaları elle düzenler, bir servisi yeniden başlatır, log dosyalarını `/var/log` altında biriktirir ve zamanla bu sunucu, dünyada benzeri olmayan, kar tanesi gibi (snowflake server) biricik bir yapıya dönüşürdü. Sorun şuydu: bu sunucu çökerse veya çoğaltılması gerekirse, kimse tam olarak nasıl kurulduğunu bilmiyordu.

Bulutun getirdiği paradigma değişimi tam olarak burayı hedef alır. Bulutta sunucular **cattle, not pets** (evcil hayvan değil, sürü hayvanı) felsefesiyle ele alınır. Bir instance hastalanırsa onu iyileştirmeye çalışmazsınız; öldürüp yerine aynısından yeni bir tane koyarsınız. Bu felsefenin çalışabilmesi için uygulamanın **her instance'ının birbirinin tıpatıp aynı ve değiştirilebilir** olması gerekir. İşte 12 faktörün kök nedeni budur: uygulamayı, altında çalıştığı makinenin biricikliğinden kurtarıp, kolayca çoğaltılabilir ve atılabilir kılmak. Odaklandığımız beş faktörün her biri bu ana hedefin farklı bir yüzüdür.

## Faktör III: Config — Yapılandırmayı Ortamda Sakla

### İlke ve Çalışma Mantığı

Config faktörünün merkezindeki ayrım şudur: **kod, ortamdan ortama değişmez; config ise her ortamda değişir.** Aynı derlenmiş kod (aynı Docker image, aynı JAR, aynı binary) geliştirici makinesinde de production'da da çalışmalıdır. Aralarındaki tek fark config olmalıdır: veritabanı bağlantı adresi, üçüncü parti servislerin API anahtarları, harici servislerin URL'leri, feature flag'ler ve benzeri ortama özgü değerler.

12-Factor'ın bu noktadaki kesin testi çok pratiktir: **"Uygulamanın kod tabanını (codebase) şu an açık kaynak yapabilir misiniz, herhangi bir gizli bilgi (credential) sızmadan?"** Eğer cevap "hayır, çünkü şu dosyada veritabanı şifresi gömülü" ise, config'iniz kodun içine sızmış demektir.

Peki config nerede saklanmalı? 12-Factor'ın önerisi **environment variable** (ortam değişkeni) kullanmaktır. Bunun tesadüfi olmayan güçlü gerekçeleri vardır. Environment variable'lar işletim sistemi seviyesinde standarttır; her dilde, her platformda okunabilir. Yanlışlıkla version control'e (Git gibi) commit edilme riskleri düşüktür çünkü kod dosyalarının içinde değil, çalışma zamanı ortamında yaşarlar. Ve en önemlisi, dilden/framework'ten bağımsızdırlar — Java da Python da Go da aynı `DATABASE_URL` değişkenini okur.

### Yaygın Bir Yanlış Anlama: config-grup ile mücadele

12-Factor, config'i gruplayan yaklaşımlara açıkça karşı çıkar. Klasik anti-pattern şudur: `config/development.yml`, `config/staging.yml`, `config/production.yml` gibi ortam adıyla isimlendirilmiş dosyalar oluşturmak. Buna 12-Factor "config grupları" (config groups) der ve neden zararlı olduğunu şöyle açıklar: bu yaklaşım ölçeklenmez. Bugün üç ortamınız vardır, yarın her müşteri için ayrı bir instance açtığınızda, ya da bir geliştirici kendi kişisel test ortamını istediğinde, yeni bir dosya adı icat etmeniz gerekir. Ortamlar birer "sabit isim" değil, sürekli çoğalan bir sürüdür.

Doğru zihniyet: config'i ortam adına göre değil, **her bir ayarı bağımsız bir değişken** olarak ele almaktır. `DATABASE_URL`, `REDIS_URL`, `STRIPE_API_KEY`... Her biri ayrı, granüler ve ortamdan ortama bağımsız olarak değiştirilebilir.

### Somut Örnek

Kötü örnek — config koda gömülü:

```python
# config.py — ANTI-PATTERN
DATABASE_URL = "postgres://admin:s3cr3t@prod-db.internal:5432/app"
STRIPE_KEY = "sk_live_abc123..."
```

Bu dosya Git'e commit edilirse şifre kalıcı olarak geçmişe kaydolur; ileride silseniz bile Git history'de durur. Ayrıca test ortamında farklı bir veritabanı kullanmak için kodu değiştirmeniz gerekir.

Doğru örnek — config ortamdan okunur:

```python
# config.py
import os

DATABASE_URL = os.environ["DATABASE_URL"]
STRIPE_KEY = os.environ["STRIPE_KEY"]
```

Artık aynı kod, farklı ortam değişkenleriyle her yerde çalışır. Local'de `.env` dosyası (Git'e eklenmeyen, `.gitignore`'da olan), production'da ise container orchestrator'ın (Kubernetes gibi) inject ettiği değerler kullanılır.

### Tuzaklar ve Modern Nüanslar

Environment variable önerisi 2011'de son derece yerindeydi, ancak günümüzde önemli bir nüans doğdu: **secret'lar (gizli bilgiler) için düz environment variable yeterince güvenli olmayabilir.** Bir process'in tüm environment variable'ları, aynı makinedeki bazı süreçler tarafından, crash dump'larda veya loglarda yanlışlıkla görünür hâle gelebilir. Bu yüzden modern pratik, hassas secret'ları **Vault, AWS Secrets Manager, Kubernetes Secrets** gibi özel secret yönetim sistemlerinde tutmak ve uygulamaya çalışma zamanında güvenli biçimde ulaştırmaktır. 12-Factor'ın ruhu (config'i koddan ayır) korunur, ancak taşıma mekanizması olgunlaşmıştır. Buradaki temel prensibi hatırlamak gerekir: 12-Factor kesin bir kural kitabı değil, bir düşünce çerçevesidir; ilkeleri bağlama göre uyarlanır.

## Faktör VI: Süreçler — Stateless (Durumsuz) Çalış

### İlke ve Çalışma Mantığı

Bu faktör, bulut-doğal mimarinin belki de en kritik köşe taşıdır. İlke şudur: **uygulama, bir veya birden çok stateless (durum tutmayan) process olarak çalışmalıdır.** Kalıcı olması gereken her veri, dışarıdaki bir stateful backing service'te (veritabanı, Redis, S3 gibi) saklanmalıdır.

"Stateless" ne demek? Bir process'in bir isteği işlerken bellekte veya diskte tuttuğu hiçbir verinin, bir sonraki isteğin doğru işlenmesi için gerekli olmaması demektir. Her istek, hiçbir önceki isteğe dair yerel hafızaya güvenmeden, kendi başına işlenebilmelidir. Process bellekte veya lokal diskte bir şey tutabilir (örneğin bir hesaplama cache'i), ama bu **asla kalıcı olduğu varsayılamaz** — process her an ölebilir, yeniden başlayabilir veya istek başka bir instance'a gidebilir.

### Kök Neden: Neden Durumsuzluk Ölçeklenmenin Ön Şartıdır?

Durumsuzluğun neden bu kadar hayati olduğunu anlamak için yatay ölçeklendirmeyi (horizontal scaling) düşünelim. Trafik arttığında yapmak istediğiniz şey, uygulamanızın 3 kopyasını 30 kopyaya çıkarmaktır. Bir load balancer, gelen istekleri bu 30 instance arasında dağıtır. Şimdi kritik soru: kullanıcının ilk isteği instance #7'ye gitti, ikinci isteği instance #22'ye gitti. İkinci istek düzgün işlenebilir mi?

Eğer instance #7, kullanıcının oturum bilgisini (session) kendi belleğinde tuttuysa, instance #22 bu kullanıcıyı tanımaz — kullanıcı aniden logout olmuş gibi davranır. Bu, meşhur **sticky session** probleminin kaynağıdır. Sticky session ile bu sorunu load balancer seviyesinde yamamaya çalışabilirsiniz (aynı kullanıcıyı hep aynı instance'a yönlendirmek), ama bu bir tuzaktır: o instance ölürse kullanıcı state'ini kaybeder ve ölçeklenme esnekliğinizi baltalarsınız çünkü yükü serbestçe dağıtamazsınız.

Durumsuzluğun getirdiği özgürlük şudur: **instance'lar birbirinin yerine geçebilir hâle gelir.** Herhangi bir instance herhangi bir isteği işleyebildiği için, load balancer istekleri özgürce dağıtabilir, ölen instance'lar sorunsuz değiştirilebilir ve yeni instance'lar hiçbir "ısınma" gerektirmeden sürüye katılabilir.

### Somut Örnek: Oturum Yönetimi

Anti-pattern — session bellekte:

```javascript
// Sunucunun belleğinde oturum tutmak — ANTI-PATTERN
const sessions = {};  // process belleğinde bir obje

app.post('/login', (req, res) => {
  const sessionId = createSession();
  sessions[sessionId] = { userId: req.body.userId };  // BELLEKTE
  res.cookie('sid', sessionId);
});
```

Bu process yeniden başladığında `sessions` objesi sıfırlanır — tüm kullanıcılar logout olur. İkinci bir instance eklediğinizde o instance bu objeyi göremez.

Doğru yaklaşım — session harici bir store'da:

```javascript
// Oturumu Redis gibi paylaşımlı bir backing service'te tut
app.post('/login', async (req, res) => {
  const sessionId = createSession();
  await redis.set(`session:${sessionId}`, JSON.stringify({ userId: req.body.userId }));
  res.cookie('sid', sessionId);
});
```

Artık hangi instance isteği alırsa alsın, Redis'ten aynı oturumu okuyabilir. Process ölse de session kaybolmaz.

### Yaygın Hatalar

- **Dosya yükleme.** Kullanıcı yüklediği dosyayı lokal diske kaydetmek klasik bir hatadır. Bir sonraki istek başka instance'a giderse dosya orada olmaz; instance ölünce dosya kaybolur. Doğrusu: object storage (S3, GCS gibi) kullanmak.
- **Bellekte biriktirilen cache'e "gerçek kaynak" gibi güvenmek.** In-memory cache performans için iyidir, ama tek doğru kaynak (source of truth) o olamaz. Cache boşsa, uygulama veriyi backing service'ten yeniden üretebilmelidir.
- **Uzun süren işleri process belleğinde takip etmek.** Bir background job'un ilerlemesini bellekte tutmak, process ölünce işi görünmez kılar. İş kuyruğu (message queue) ve kalıcı state kullanılmalıdır.

## Faktör XI: Loglar — Log'u Bir Event Stream Olarak Ele Al

### İlke ve Çalışma Mantığı

Bu faktörün getirdiği zihniyet dönüşümü çok önemlidir: **uygulama, kendi loglarının nereye yazılacağıyla veya nasıl saklanacağıyla asla ilgilenmemelidir.** Uygulamanın tek işi, log satırlarını (event'leri) `stdout`'a (standart çıktı akışı) yazmaktır. O kadar. Dosya açmak, log döndürme (log rotation) ayarlamak, log dosyasının yolunu belirlemek — bunların hiçbiri uygulamanın işi değildir.

Neden? Çünkü log, doğası gereği zaman-sıralı bir **event stream** (olay akışı)'dır; bir depolama biçimi değil. Uygulama bu akışı üretir; akışın nereye gideceği ise çalışma ortamının (execution environment) sorumluluğudur.

### Kök Neden: Stateless ve Disposable Uygulamalarda Log Neden Dosyaya Yazılamaz?

Bu faktör aslında stateless ve disposable ilkelerinin doğrudan bir sonucudur. Düşünün: uygulamanız her an ölebilen, çoğaltılabilen, geçici (ephemeral) container'larda çalışıyor. Bir instance loglarını kendi lokal diskindeki `/var/log/app.log` dosyasına yazsa ne olur?

Birincisi, o instance öldüğünde (ki disposable ilkesi gereği sık sık ölecek) log dosyası da onunla birlikte yok olur. İkincisi, 30 instance'ınız varsa, logunuz 30 ayrı makinedeki 30 ayrı dosyaya dağılmış olur — bir hatayı incelemek için hangi makineye bakacağınızı bilemezsiniz. Üçüncüsü, container'ların lokal diski genellikle geçici ve kısıtlıdır; oraya log yazmak diski doldurabilir.

Çözüm, sorumluluğu tersine çevirmektir. Uygulama sadece `stdout`'a yazar. Bu akışı, çalışma ortamı yakalar. Modern bir sistemde bu akış şöyle bir yol izler: container runtime `stdout`'u yakalar, bir log toplayıcı (Fluentd, Fluent Bit, Vector gibi) bu akışları tüm instance'lardan toplar ve merkezî bir log yönetim sistemine (Elasticsearch/Kibana, Loki, Splunk, CloudWatch gibi) gönderir. Orada tüm instance'ların logları tek bir yerde birleşir; arama, filtreleme, uyarı (alerting) ve saklama (retention) politikaları uygulanır.

Bu ayrımın gücü şudur: uygulama kodu tamamen aynı kalır, ama development'ta logları terminalde görürsünüz, production'da ise devasa bir log altyapısına akar. Uygulama bu farktan haberdar bile değildir.

### Somut Örnek

Anti-pattern — uygulama kendi log dosyasını yönetiyor:

```python
# ANTI-PATTERN: uygulama log dosyası yolu ve rotation ile ilgileniyor
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler('/var/log/myapp/app.log', maxBytes=10_000_000, backupCount=5)
logging.getLogger().addHandler(handler)
```

Doğru yaklaşım — sadece `stdout`'a yaz:

```python
import logging
import sys

# Sadece stdout'a yaz; nereye gideceğine ortam karar versin
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.info("Ödeme işlendi: siparis=1234 tutar=250.00")
```

Modern bir eklenti: logları **yapılandırılmış (structured)** formatta, yani JSON olarak yazmak. Bu, düz metin yerine `{"level":"info","event":"payment","order":1234,"amount":250.00}` biçiminde yazmak demektir. Bu 12-Factor'ın orijinal metninde vurgulanmasa da bugünün log toplama sistemlerinin makine tarafından ayrıştırılabilir (parseable) veriyle çok daha iyi çalışması sayesinde neredeyse standart hâline gelmiştir.

## Faktör IX: Disposability — Hızlı Başla, Zarifçe Kapan

### İlke ve Çalışma Mantığı

Disposability (atılabilirlik), süreçlerin **atılabilir** olması gerektiğini söyler: bir saniye içinde başlayıp durabilmelidirler. Bu ilkenin iki teknik ayağı vardır: **hızlı başlangıç (fast startup)** ve **zarif kapanış (graceful shutdown)**.

Hızlı başlangıç önemlidir çünkü bulutta instance'lar sürekli oluşturulur. Trafik ani biçimde artarsa (autoscaling) yeni instance'ların saniyeler içinde yük almaya hazır olması gerekir. Başlangıcı 5 dakika süren bir uygulama, ani yük altında işe yaramaz; siz daha ısınırken kullanıcı çoktan gitmiştir.

Zarif kapanış ise daha inceliklidir. Bir process kapatma sinyali (Unix'te `SIGTERM`) aldığında, işini yarıda bırakıp aniden ölmemelidir. Bunun yerine: yeni istek/iş kabul etmeyi durdurmalı, elindeki mevcut isteği/işi bitirmeli ve ancak ondan sonra temiz biçimde çıkmalıdır.

### Kök Neden: Neden Graceful Shutdown Veri Kaybını Önler?

Kubernetes gibi bir orchestrator'ın bir instance'ı neden öldürdüğünü düşünelim: yeni bir sürüm dağıtılıyor (deployment), autoscaling yükü azaltıyor veya makine bakıma alınıyor. Orchestrator instance'a önce `SIGTERM` gönderir, sonra bir süre (grace period) bekler, hâlâ ölmediyse `SIGKILL` ile zorla öldürür.

Şimdi kritik senaryo: bir worker process, kuyruktan bir işi çekmiş, tam ortasında `SIGTERM` geldi. Eğer process aniden ölürse, o iş yarıda kalır. Zarif kapanış olmadan bu, veri tutarsızlığına veya kaybolan işlere yol açabilir. Doğru davranış: iş kuyruğu tabanlı sistemlerde, işlenen işi kuyruğa geri koymak (return to queue) veya bitirene kadar kısa süre beklemek. HTTP servislerinde ise: yeni bağlantı kabul etmeyi bırak, açık isteklerin yanıtını gönder, sonra kapan.

Ayrıca disposability, **ani ölüme dayanıklılık** (robustness against sudden death) da gerektirir. Bir instance elektrik kesintisiyle veya `SIGKILL` ile aniden gidebilir; zarif kapanışa hiç fırsat bulamayabilir. Bu yüzden sistemin genel tasarımı, herhangi bir işin yarıda kalmasına da tolerans göstermelidir — örneğin işlerin idempotent (birden fazla kez çalıştırıldığında aynı sonucu veren) olması ve tamamlanana kadar kuyruktan silinmemesi.

### Somut Örnek: SIGTERM Yakalamak

```javascript
const server = app.listen(3000);

process.on('SIGTERM', () => {
  console.log('SIGTERM alındı, zarif kapanış başlıyor');
  // 1) Yeni bağlantı kabul etmeyi bırak, açık istekleri bitir
  server.close(() => {
    console.log('Açık HTTP istekleri tamamlandı');
    // 2) Veritabanı/Redis bağlantılarını temizce kapat
    db.close().then(() => process.exit(0));
  });
});
```

Buradaki `server.close()`, yeni bağlantı kabulünü durdurur ama mevcut istekleri koparmaz. İstemci, isteğinin yarıda kesildiğini görmez.

### Tuzaklar ve İlişkili Faktörler

- **Grace period'ı görmezden gelmek.** Orchestrator size örneğin 30 saniye tanır. Kapanış işiniz bundan uzun sürerse, `SIGKILL` gelir ve zarafet çöker. İşlerinizi bu pencereye sığdırın.
- **Signal'ı hiç yakalamamak.** Birçok uygulama `SIGTERM`'i yakalamaz, doğrudan ölür. Özellikle container'da PID 1 olarak çalışan bir process, signal'ları düzgün ele almazsa graceful shutdown hiç gerçekleşmez. (Bu yüzden çoğu container imajında bir init sistemi veya `--init` bayrağı kullanılır.)
- **Uzun başlangıç işleri.** Başlangıçta büyük cache'leri önden doldurmak (warm-up), migration çalıştırmak gibi işler startup'ı yavaşlatır. Bunları mümkünse başlangıçtan ayırın — migration'ı ayrı bir release adımı (Faktör V ile ilişkili) olarak çalıştırın.

## Bu Faktörler Bir Arada: Bulut-Doğal Sinerji

Şimdiye kadar faktörleri ayrı ayrı inceledik, ama gerçek güçleri birbirlerini nasıl tamamladıklarında yatar. Bunlar birbirinden bağımsız kurallar değil, aynı hedefe yönelen bir zincirdir:

**Stateless olduğunuz için** herhangi bir instance herhangi bir isteği işleyebilir. **Bu yüzden** instance'lar birbirinin yerine geçebilir; **bu yüzden** disposable (atılabilir) olabilirler — birini öldürüp yerine yenisini koymak sorun yaratmaz. **Disposable oldukları için** loglarını lokal diske yazamazlar (o disk onlarla ölür), **bu yüzden** logu bir stream olarak `stdout`'a bırakırlar. **Ve tüm bunların çalışması için** config'in ortamda olması gerekir; **çünkü** aynı image'ı hiçbir değişiklik yapmadan onlarca ortama ve yüzlerce instance'a dağıtabilmelisiniz.

Bu zincirin toplamı **bulut-doğal (cloud-native)** dediğimiz şeydir: altyapının geçici, otomatik yönetilen ve elastik olduğu varsayımı üzerine kurulu uygulamalar. Kubernetes, ECS, Cloud Run gibi platformlar tam olarak bu varsayımları bekler. Bir uygulama bu faktörlere uyduğunda, orchestrator onu özgürce çoğaltabilir, taşıyabilir, öldürebilir ve yeniden yaratabilir — uygulama bundan hiç zarar görmez. Uymadığındaysa, orchestrator'ın her hareketi bir kesintiye veya veri kaybına dönüşür.

### 12-Factor'ın Sınırları ve Modern Eleştiriler

Dürüst bir değerlendirme için, 12-Factor'ın 2011'de yazıldığını ve bazı sınırlarının olduğunu belirtmek gerekir. Metodoloji ağırlıklı olarak **stateless web uygulamaları ve API'ler** için tasarlanmıştır. Doğası gereği stateful olan sistemler için (veritabanları, message broker'lar, kalıcı state tutan streaming işleyicileri) her faktör olduğu gibi uygulanamaz. Örneğin bir veritabanı, tanımı gereği disposable değildir; state'i o tutar.

Ayrıca metodoloji, dağıtık sistemlerin bazı modern gerçeklerini (service discovery, dağıtık izleme/distributed tracing, service mesh, sıfır kesintili dağıtım stratejilerinin incelikleri) doğrudan ele almaz — bunlar 12-Factor sonrası olgunlaşmış konulardır. Bu yüzden 12-Factor'ı bir bitiş çizgisi değil, **sağlam bir başlangıç temeli** olarak görmek gerekir. Faktörleri dogmatik biçimde değil, ardındaki "neden"i anlayarak uygulayın: amaç "12 kutucuğu işaretlemek" değil, uygulamayı gerçekten taşınabilir, ölçeklenebilir ve dayanıklı kılmaktır.

## En İyi Pratikler: Özet Kontrol Listesi

- **Config'i koddan tamamen ayırın.** Testiniz şu olsun: kod tabanını gizli bilgi sızmadan açık kaynak yapabilir misiniz? Ortam adına göre gruplanmış config dosyaları yerine, granüler ve ortamdan bağımsız environment variable'lar kullanın. Hassas secret'lar için özel secret yönetim sistemlerine geçin.
- **Uygulamayı katı biçimde stateless yapın.** Kalıcı olması gereken her şeyi (session, yüklenen dosyalar, job state) harici backing service'lere taşıyın. Bellek ve lokal disk yalnızca geçici, kaybı önemsiz veriler için kullanılabilir. Sticky session'a bel bağlamayın.
- **Logu `stdout`'a bir event stream olarak yazın.** Log dosyası yolu, rotation, saklama — bunları uygulamaya değil, çalışma ortamına bırakın. Mümkünse structured (JSON) log kullanın ki merkezî log sistemi verinizi kolay ayrıştırsın.
- **Hızlı başlayın, zarifçe kapanın.** Başlangıç süresini saniyeler mertebesinde tutun. `SIGTERM`'i yakalayın: yeni istek almayı durdurun, mevcut işi bitirin, kaynakları temiz kapatın. İşleri idempotent ve kuyruk-tabanlı tasarlayarak ani ölüme de tolerans gösterin.
- **Bulut-doğal düşünün.** Instance'larınızın her an ölebilecek, çoğaltılabilecek sürü hayvanları olduğunu varsayın. "Bu makine biricik" varsayımına dayanan her tasarım kararı, ölçeklendiğinizde bir arıza kaynağına dönüşür.

Bu beş faktör birlikte, uygulamanızı altyapının kaprislerinden bağımsız kılan bir sözleşmedir. Ne kadar sadık kalırsanız, bulut platformları o kadar çok işi sizin yerinize otomatik yapar — ve siz gecenin bir yarısı SSH ile sunucuya bağlanıp elle bir şey düzeltmek zorunda kalmazsınız. 12-Factor'ın nihai vaadi budur: operasyonel derdi altyapıya devretmek, siz yalnızca uygulamanın kendisiyle ilgilenmek.
