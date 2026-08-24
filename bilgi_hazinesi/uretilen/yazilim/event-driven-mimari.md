# Event-Driven Mimari ve CQRS

## Giriş: Neden Bu Konu Önemli?

Klasik katmanlı mimarilerde bir işlem (örneğin "sipariş oluştur") tek bir senkron çağrı zinciri içinde tamamlanır: controller servisi çağırır, servis veritabanına yazar, cevap döner. Bu model küçük sistemlerde mükemmel çalışır. Fakat sistem büyüdükçe, farklı ekiplerin sahip olduğu servisler birbirine bağlandıkça ve "bir şey olduğunda birden fazla yerde tepki verilmesi" gerektikçe bu senkron zincir kırılganlaşır. Bir servisin yavaşlaması tüm zinciri yavaşlatır; bir bağımlılığın eklenmesi kaynak servisin kodunu değiştirmeyi gerektirir.

Event-Driven Architecture (EDA), yani olay güdümlü mimari, bu problemi "gerçekleşen bir olayı ilan etme" fikri üzerine kurarak çözmeye çalışır. Servisler birbirini doğrudan çağırmak yerine, sistemde bir şey olduğunda (`SiparisOlusturuldu`, `OdemeAlindi`) bunu bir olay olarak yayınlar; ilgilenen diğer servisler bu olayı dinleyip kendi işlerini yapar. Bu makale EDA'yı, onunla sık birlikte anılan CQRS ve Event Sourcing desenlerini, dağıtık işlemleri yöneten Saga desenini ve tüm bunların gerçek avantaj/dezavantajlarını derinlemesine ele alıyor.

## Event-Driven Mimarinin Temelleri

### Tanım ve Temel Kavramlar

Event-Driven Architecture, bileşenlerin **event** (olay) üretimi, algılanması ve tüketimi üzerinden iletişim kurduğu bir mimari tarzdır. Buradaki en kritik kavram şudur: bir **event, geçmişte olmuş ve değiştirilemez bir gerçeğin** ifadesidir. `SiparisOlusturuldu` bir olaydır; `SiparisOlustur` ise bir komuttur (command). Bu ayrım göründüğünden çok daha önemlidir:

- **Command** (komut): Gelecekte bir şeyin yapılmasını *isteyen* niyettir. Reddedilebilir. Tek bir alıcısı vardır. Emir kipindedir.
- **Event** (olay): Geçmişte bir şeyin olduğunu *bildiren* gerçektir. Reddedilemez, çünkü zaten olmuştur. Sıfır, bir veya birden çok alıcısı olabilir. Geçmiş zamandadır.

### Kök Neden: Neden Gevşek Bağlılık (Loose Coupling) İşe Yarar?

EDA'nın çalışma mantığının kalbinde **producer** (üretici) ile **consumer** (tüketici) arasındaki bağın koparılması yatar. Senkron bir çağrıda, sipariş servisi ödeme servisinin adresini, arayüzünü ve müsaitliğini bilmek zorundadır. Ödeme servisine bir de "sadakat puanı" servisi eklemek istediğinizde, sipariş servisinin kodunu açıp yeni bir çağrı eklemeniz gerekir. Bu, **temporal coupling** (zamansal bağlılık — iki servisin aynı anda ayakta olma zorunluluğu) ve **structural coupling** (yapısal bağlılık — birbirinin arayüzünü bilme zorunluluğu) demektir.

EDA'da sipariş servisi sadece `SiparisOlusturuldu` olayını yayınlar ve "kim ilgileniyorsa ilgilensin" der. Kimin dinlediğini bilmez, bilmek de istemez. Yeni bir tüketici eklemek, üreticinin kodunu hiç değiştirmeden, sadece yeni bir dinleyici yazmakla mümkün olur. İşte "genişletilebilirlik" (extensibility) buradan doğar. Kök neden budur: **bilgi eksikliği bir özelliktir, kusur değil.** Üreticinin tüketicileri bilmemesi, sistemin bir parçasını değiştirirken diğerini bozma riskini ortadan kaldırır.

### İki Temel İletişim Modeli

Olayların taşınma biçimi mimarinin karakterini belirler:

1. **Pub/Sub (Publish/Subscribe):** Üretici olayı bir topic'e yayınlar, tüm aboneler kendi kopyasını alır. Genellikle olay "yayınlandıktan sonra unutulur"; broker mesajı tüm abonelere dağıtınca görevini tamamlar. Klasik message broker'lar bu modeli kullanır.

2. **Event Streaming (Olay Akışı):** Olaylar kalıcı, sıralı, tekrar okunabilir bir **log** (kayıt defteri) üzerinde tutulur. Tüketiciler bu log üzerinde kendi konumlarını (offset) tutar ve istedikleri zaman geçmişe gidip olayları yeniden okuyabilir. Kafka türü sistemlerin ayırt edici özelliği budur: olay tüketildikten sonra silinmez, log'da bir süre (retention) boyunca kalır. Bu ayrım, birazdan göreceğimiz Event Sourcing için kritik bir zemin hazırlar.

## CQRS: Komut ve Sorgu Sorumluluklarının Ayrılması

### Tanım

CQRS (Command Query Responsibility Segregation), bir sistemin **veriyi değiştiren işlemleri (command)** ile **veriyi okuyan işlemleri (query)** farklı modeller, hatta farklı veri depoları üzerinden ele alma prensibidir. Klasik CRUD yaklaşımında tek bir model (örneğin `Siparis` entity'si) hem yazma hem okuma için kullanılır. CQRS bu tek modeli ikiye böler: bir **write model** (yazma modeli) ve bir veya daha fazla **read model** (okuma modeli).

### Kök Neden: Neden Okuma ve Yazma Farklı İhtiyaçlara Sahiptir?

Bu deseni anlamanın anahtarı, okuma ve yazma iş yüklerinin doğası gereği farklı olduğunu görmektir:

- **Yazma tarafı** iş kurallarıyla, tutarlılıkla ve doğrulamayla ilgilenir. "Bu siparişin toplamı negatif olamaz", "stok yetersizse sipariş reddedilir" gibi invariant'ları (değişmezleri) korumak zorundadır. Normalize edilmiş, tutarlı bir yapı ister.
- **Okuma tarafı** ise hız ve gösterim biçimiyle ilgilenir. Bir ekranda "müşterinin son 10 siparişi, ürün adları ve toplam tutarlarıyla" gösterilecekse, bu veriyi normalize tablolardan `JOIN`'lerle her seferinde toplamak pahalıdır. Okuma tarafı denormalize, önceden birleştirilmiş, gösterime hazır veri ister.

Tek bir model bu iki zıt ihtiyacı aynı anda karşılamaya çalıştığında ikisinde de vasat kalır. CQRS'in kök mantığı şudur: **bu iki tarafı ayırırsan, her birini kendi ihtiyacına göre bağımsız optimize edebilir ve bağımsız ölçekleyebilirsin.** Okuma tarafı genellikle yazmadan çok daha fazla trafik alır; ayırınca okuma replikalarını yazma tarafını hiç etkilemeden çoğaltabilirsiniz.

### Somut Örnek

Bir e-ticaret sisteminde:

- **Komut tarafı:** `SiparisOlusturKomutu` gelir. Write model stok kontrolü yapar, iş kurallarını uygular, normalize edilmiş `siparisler` ve `siparis_kalemleri` tablolarına yazar.
- Yazma sonrası bir `SiparisOlusturuldu` olayı yayınlanır.
- **Sorgu tarafı:** Bir projeksiyon (projection) bu olayı dinler ve okuma için optimize edilmiş bir `siparis_ozetleri` tablosunu (müşteri adı, ürün adları, toplam — hepsi tek satırda, denormalize) günceller.
- Kullanıcı "siparişlerim" sayfasını açtığında, sistem karmaşık `JOIN`'ler yapmadan doğrudan bu hazır tablodan tek sorguyla okur.

### Kritik Tuzak: CQRS Her Yerde Kullanılmaz

En sık yapılan hata CQRS'i basit bir CRUD uygulamasına uygulamaktır. Eğer okuma ve yazma modelleriniz neredeyse aynıysa, iki ayrı model tutmak sadece gereksiz kod, gereksiz senkronizasyon ve gereksiz karmaşıklık üretir. CQRS, okuma ve yazma ihtiyaçları **gerçekten** birbirinden ayrıştığında; okuma tarafı ağır ve farklı; iş mantığı karmaşık olduğunda değer üretir. Basit bir formu, olay yayınlamadan, sadece aynı veritabanında ayrı okuma/yazma sorgu yolları tutarak da uygulayabilirsiniz — CQRS ille de mesajlaşma altyapısı gerektirmez.

## Event Sourcing: Durumu Değil Değişimleri Saklamak

### Tanım

Event Sourcing, bir varlığın (aggregate) **mevcut durumunu** saklamak yerine, o duruma yol açan **tüm olayların sıralı listesini** saklama tekniğidir. Klasik yaklaşımda `hesap` tablosunda `bakiye = 150` yazar. Event Sourcing'de ise hesabın tarihçesini saklarsınız:

```
1. HesapAcildi(id=42, tarih=...)
2. ParaYatirildi(miktar=200)
3. ParaCekildi(miktar=50)
```

Mevcut bakiye (150) bir kolonda tutulmaz; bu olaylar baştan sona oynatılarak (**replay**) her seferinde yeniden hesaplanır. Kayıt defterinin kendisi tek doğruluk kaynağıdır (source of truth).

### Kök Neden: Neden Değişimi Saklamak Durumu Saklamaktan Daha Güçlü?

Klasik `UPDATE` işleminin sessiz ve yıkıcı bir yan etkisi vardır: **eski değeri geri dönülemez biçimde yok eder.** `bakiye = 150` yazdığınız an, bir önceki değerin ne olduğu, ne zaman ve neden değiştiği bilgisi kaybolur. İş dünyası ise sürekli "peki bu değer nasıl bu hale geldi?" diye sorar. Muhasebe, denetim, dolandırıcılık analizi, "geçen salı saat 14:00'te bakiye neydi?" gibi sorular klasik modelde ancak ayrı ayrı log'lar tutarak yaklaşık olarak cevaplanır.

Event Sourcing'in kök mantığı, muhasebenin yüzyıllardır yaptığı şeyle aynıdır: **defterdeki bir kaydı silmez, düzeltmeyi yeni bir kayıtla yaparsın.** Olaylar değiştirilemez (immutable) ve yalnızca eklenir (append-only). Bunun doğal sonuçları güçlüdür:

- **Tam denetim izi (audit trail) bedavaya gelir.** Ayrı bir loglama sistemine gerek yoktur; tarihçe zaten verinin kendisidir.
- **Zaman içinde geriye gitme (temporal query):** Herhangi bir geçmiş andaki durumu, olayları o ana kadar oynatarak birebir yeniden üretebilirsiniz.
- **Yeni okuma modelleri sonradan türetilebilir.** Bugün aklınıza gelmeyen bir raporu, altı ay sonra tüm geçmiş olayları yeni bir projeksiyondan geçirerek geriye dönük olarak üretebilirsiniz. Klasik modelde bu veri çoktan kaybolmuş olurdu.

### Event Sourcing ve CQRS'in Doğal Ortaklığı

Bu iki desen ayrı ayrı var olabilir ama birlikte çok güçlüdür. Olayların ham log'undan mevcut durumu her sorguda replay ederek okumak pahalıdır. Bu yüzden Event Sourcing neredeyse her zaman CQRS ile eşleşir: yazma tarafı olayları log'a ekler; projeksiyonlar bu olayları dinleyerek okuma tarafında sorgulanabilir, hazır durum tabloları (read model) oluşturur. Yazma "gerçeğin defteri", okuma ise "o defterden türetilmiş özet" olur.

### Kritik Kavram: Snapshot

Bir aggregate'in binlerce olayı biriktiğinde, her yüklemede hepsini baştan replay etmek yavaşlar. Çözüm **snapshot**'tır: belirli aralıklarla aggregate'in o anki durumunun bir fotoğrafı kaydedilir. Yükleme sırasında en son snapshot'tan başlanır ve sadece ondan sonraki olaylar oynatılır. Snapshot bir optimizasyondur, doğruluk kaynağı değildir — istenirse silinip olaylardan yeniden üretilebilir.

### Zorlu Tuzaklar ve Yaygın Hatalar

Event Sourcing güçlü ama ucuz değildir. En sık düşülen tuzaklar:

- **Olay şeması evrimi (schema evolution):** Olaylar değiştirilemez ve *sonsuza kadar* saklanır. Üç yıl önce yazdığınız `SiparisOlusturuldu` olayının yapısını bugün değiştiremezsiniz — o eski olaylar hâlâ log'da durur ve okunmaları gerekir. Alan eklemek, silmek, yeniden adlandırmak versiyonlama (event versioning) ve **upcasting** (eski olay biçimini yükleme anında yeni biçime dönüştürme) stratejileri gerektirir. Bunu baştan planlamamak, projeyi ilerleyen aylarda felç eder.
- **Kişisel veri ve silme hakkı:** Değiştirilemez, append-only bir log ile "beni unut" (GDPR türü silme) taleplerini birleştirmek gerçek bir gerilimdir. Yaygın çözüm, kişisel veriyi olayın içine gömmeyip şifreleyerek ayrı tutmak ve gerektiğinde şifreleme anahtarını yok ederek veriyi pratikte erişilemez kılmaktır (crypto-shredding). Bu detayı ihmal etmek ciddi yasal risk doğurur.
- **Olayları CRUD gibi düşünmek:** Olaylar iş anlamı taşımalıdır. `SiparisGuncellendi` gibi jenerik, "hangi alan değişti belli değil" tarzı olaylar bir anti-pattern'dir. `TeslimatAdresiDegistirildi` gibi niyeti belli, iş diliyle konuşan olaylar tercih edilir.
- **Nihai tutarlılık (eventual consistency):** Yazma tarafına olay eklendiği an ile okuma modelinin güncellendiği an arasında bir gecikme vardır. Kullanıcı bir siparişi oluşturup hemen listeye baktığında henüz göremeyebilir. Bunu arayüz ve iş akışında öngörmek zorunludur.

## Saga: Dağıtık İşlemleri Yönetmek

### Tanım ve Kök Neden

Mikroservis mimarisinde her servisin kendi veritabanı vardır. "Sipariş oluştur, ödemeyi çek, stoğu düş, kargo başlat" akışı beş farklı servisi ve beş farklı veritabanını ilgilendirir. Klasik yaklaşım bu işlemi tek bir ACID transaction içinde atomik yapmaktı. Fakat dağıtık sistemde birden fazla bağımsız veritabanını tek transaction'da kilitleyip iki-fazlı commit (2PC) yapmak hem ölçeklenmez hem de servisleri birbirine sıkıca bağlar; bir servis çökerse tüm işlem askıda kalır. Bu, mikroservislerin kazandırdığı bağımsızlığı yok eder.

**Saga deseni** bu probleme farklı bir cevap verir: tek büyük atomik işlem yerine, her biri kendi servisinde yerel (local) transaction olan **bir dizi adım** tanımlanır. Adımlar olaylarla birbirini tetikler. Eğer bir adım başarısız olursa, o ana kadar başarılı olan adımların etkisini geri almak için **compensating transaction** (telafi işlemi) çalıştırılır. Kritik nokta şudur: Saga rollback yapmaz; **geri alamaz, ancak tersine çeviren yeni bir işlem yapar.** Ödemeyi "geri almazsınız", "iade edersiniz". Stoğu "geri koymazsınız", "rezervasyonu serbest bırakırsınız".

### İki Koordinasyon Biçimi

**1. Choreography (Koreografi):** Merkezi bir yönetici yoktur. Her servis bir olayı dinler, işini yapar, kendi olayını yayınlar; bir sonraki servis onu dinler. Sanki dansçılar önceden anlaşmış gibi sırayla hareket eder.

- *Avantaj:* Basit akışlarda gevşek bağlı ve ekstra bileşen gerektirmez.
- *Dezavantaj:* Akış büyüdükçe "şu an sürecin neresindeyiz?" sorusuna cevap vermek zorlaşır; iş mantığı servislere dağılır ve hiçbir yerde bütün akış tek parça görünmez. Döngüsel bağımlılık riski doğar.

**2. Orchestration (Orkestrasyon):** Merkezi bir **orchestrator** (orkestra şefi) süreci yönetir. Şef her servise sırayla komut gönderir, cevabı bekler, bir sonraki adıma karar verir, hata olursa telafi adımlarını tetikler.

- *Avantaj:* Akış tek bir yerde görünür ve yönetilebilir; karmaşık süreçlerde takibi ve hata yönetimi çok daha kolaydır.
- *Dezavantaj:* Orchestrator bir merkezi bileşendir; iş mantığının fazlası oraya toplanıp servisleri "aptallaştırma" riski taşır. Yine de karmaşık, çok adımlı iş akışlarında genellikle tercih edilen yaklaşımdır.

### Somut Örnek: Sipariş Sagası (Orkestrasyon)

```
1. Orchestrator → ÖdemeServisi: ÖdemeÇek
   ← ÖdemeAlındı  ✓
2. Orchestrator → StokServisi: StokRezerveEt
   ← StokRezerveEdildi  ✓
3. Orchestrator → KargoServisi: KargoBaşlat
   ← KargoHatası  ✗

TELAFİ (ters sırada):
4. Orchestrator → StokServisi: RezervasyonuSerbestBırak
5. Orchestrator → ÖdemeServisi: ÖdemeİadeEt
6. Orchestrator: Sipariş iptal edildi olarak işaretle
```

### Saga'nın En Sinsi Tuzağı: Idempotency ve Semantik Kilitleme

Dağıtık ve mesaj tabanlı bir sistemde bir olay **birden fazla kez teslim edilebilir** (at-least-once delivery yaygın garantidir). Aynı `ÖdemeÇek` komutunun ağ tekrarı yüzünden iki kez gelmesi, müşteriden iki kez para çekmek demek olabilir. Bu yüzden Saga adımları **idempotent** olmak zorundadır — aynı işlem birden çok kez uygulansa da sonuç tek uygulanmış gibi olmalıdır. Bu genellikle her komuta benzersiz bir kimlik verip "bu kimliği daha önce işledim mi?" kontrolüyle sağlanır.

İkinci sinsi konu, telafi mantığının **iş açısından her zaman mümkün olmayabileceğidir.** Bir e-posta gönderildikten sonra onu "geri alamazsınız". Bu yüzden telafisi zor olan, geri dönülemez adımları (irreversible steps) mümkün olduğunca sürecin **sonuna** koymak iyi bir tasarım prensibidir; böylece o adıma geldiğinizde öncesindeki tüm adımlar başarılı olmuştur ve telafiye ihtiyaç kalma olasılığı düşer.

## Avantajlar ve Dezavantajlar: Dürüst Bir Değerlendirme

### Avantajlar

- **Gevşek bağlılık ve bağımsız evrim:** Servisler birbirini bilmeden gelişebilir; yeni tüketiciler mevcut kodu bozmadan eklenir.
- **Ölçeklenebilirlik ve dayanıklılık:** Bir tüketici yavaşlarsa veya çökerse, olaylar broker'da/log'da birikir ve tüketici geri geldiğinde kaldığı yerden devam eder. Ani yük artışları (spike) mesaj kuyruğu tarafından tamponlanır (buffering) — sistem çökmek yerine geride kalır.
- **Denetlenebilirlik (özellikle Event Sourcing ile):** Ne olduğu, ne zaman olduğu tam olarak kayıtlıdır.
- **Bağımsız okuma/yazma ölçeklendirme (CQRS ile):** İki taraf kendi ihtiyacına göre ayrı ölçeklenir.
- **Esneklik:** Aynı olaylar farklı amaçlar için (analitik, bildirim, arama indeksi) tekrar tekrar kullanılabilir.

### Dezavantajlar — Ve Neden Ciddiye Alınmalı

Bu desenlerin en dürüst özeti şudur: **karmaşıklığı yok etmezler, onu yer değiştirirler.** Senkron çağrılardaki bağımlılık karmaşıklığını alır, dağıtık sistem karmaşıklığına dönüştürürler.

- **Nihai tutarlılık (eventual consistency):** Belki de en büyük kavramsal maliyet budur. "Yazdım, hemen okuyabilirim" garantisi yok olur. Bu, kod değil, iş mantığı ve kullanıcı deneyimi problemidir ve baştan kabullenilmelidir.
- **Debug ve gözlemlenebilirlik zorluğu:** Bir isteğin nedeni-sonucu artık tek bir stack trace'te görünmez; olay olay birden fazla servise dağılır. Distributed tracing (dağıtık izleme) ve correlation ID kullanımı zorunlu hale gelir, opsiyonel değil.
- **Mesaj sıralaması ve tekrar (ordering & duplication):** Olayların sırası garanti edilmeyebilir ve tekrar edebilir. Idempotency ve sıralama stratejileri baştan tasarlanmalıdır.
- **Operasyonel yük:** Bir message broker veya event streaming platformu kurmak, izlemek, ölçeklemek ve arıza durumunda kurtarmak ciddi bir işletme (ops) yatırımıdır.
- **Bilişsel yük:** Ekibin bu modele göre düşünmesi gerekir. Senkron dünyaya alışkın bir ekip için öğrenme eğrisi diktir; yanlış anlaşılmış EDA, klasik monolitten çok daha kırılgan bir sistem üretir.

## En İyi Pratikler ve Sonuç

Bu desenleri sağlıklı uygulamak için birkaç ilke öne çıkar:

1. **Basit başla, kanıtla, sonra ekle.** EDA, CQRS, Event Sourcing ve Saga bir paket değildir. Çoğu sistem CQRS'siz de, Event Sourcing'siz de gayet iyi çalışır. Bu desenleri, çözdükleri problemi gerçekten yaşadığınızda ekleyin. "Modern olsun diye" eklemek en pahalı hatadır.

2. **Olayları iş dilinde tasarla.** Olaylar teknik değil, iş (domain) olaylarıdır. İyi bir olay adı, iş uzmanının anlayacağı bir cümledir. Event Storming gibi teknikler bu olayları keşfetmek için değerlidir.

3. **Idempotency'yi opsiyonel görme.** At-least-once teslimat neredeyse her yerde vardır; her tüketiciyi tekrarları güvenle karşılayacak şekilde yaz.

4. **Şema evrimini ilk günden planla.** Özellikle Event Sourcing'de olaylar sonsuza kadar yaşar. Versiyonlama ve upcasting stratejin olmadan başlama.

5. **Gözlemlenebilirliğe erkenden yatırım yap.** Correlation ID, distributed tracing ve merkezi loglama, dağıtık olay akışında ışık kaynağındır; sonradan eklemek çok daha zordur.

6. **Nihai tutarlılığı gizleme, tasarla.** Kullanıcıya "işleminiz alındı, işleniyor" demek, ona yalancı bir "tamamlandı" gösterip sonra geri almaktan iyidir.

**Özet:** Event-Driven Architecture, CQRS, Event Sourcing ve Saga, büyük ve karmaşık sistemlerde gerçek problemleri — sıkı bağlılığı, ölçeklenme darboğazlarını, denetim ihtiyacını ve dağıtık işlem tutarlılığını — çözen güçlü araçlardır. Ancak hepsi ortak bir bedelle gelir: karmaşıklığı kod içinden alıp sistemin mimarisine ve operasyonuna taşırlar. Bu takasın (trade-off) farkında olarak, doğru problemde ve doğru dozda uygulandıklarında olağanüstü değerlidirler; moda olduğu için körü körüne uygulandıklarında ise çözdüklerinden daha büyük problemler yaratırlar. Uzmanlık, bu desenleri bilmekte değil, ne zaman kullanmayacağını bilmektedir.
