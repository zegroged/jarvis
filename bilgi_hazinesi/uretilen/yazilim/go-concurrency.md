# Go Eşzamanlılık ve İdiyomlar

Go'nun eşzamanlılık (concurrency) modeli, dilin en ayırt edici özelliğidir. Diğer birçok dilde eşzamanlılık, sonradan eklenen bir kütüphane katmanıyken, Go'da dilin çekirdeğine gömülüdür: `go` anahtar kelimesi, `chan` tipi ve `select` deyimi doğrudan gramerin parçasıdır. Bu makale goroutine'lerin nasıl çalıştığını, channel'ların hafıza modeli açısından ne anlama geldiğini, `select` ve `context` idiyomlarını ve race detector'ün doğruluğu nasıl koruduğunu kök nedenlerine inerek anlatır.

Önce bir kavramsal ayrım: **eşzamanlılık (concurrency)** ile **paralellik (parallelism)** aynı şey değildir. Eşzamanlılık, birbirinden bağımsız ilerleyebilen işlerin yapısını tanımlar; paralellik ise bu işlerin aynı anda fiziksel çekirdeklerde koşmasıdır. Rob Pike'ın meşhur ifadesiyle "concurrency is not parallelism". Go, eşzamanlı bir program yazmanızı kolaylaştıran araçları verir; bu programın paralel koşup koşmayacağı ise runtime'ın elindeki çekirdek sayısına ve zamanlayıcıya (scheduler) bağlıdır.

## Goroutine: Hafif İş Parçacığı

### Tanım

Goroutine, Go runtime'ı tarafından yönetilen hafif bir yürütme birimidir. Bir fonksiyonun önüne `go` yazarak yeni bir goroutine başlatırsınız:

```go
go islemYap(veri)
```

Bu satır, `islemYap` fonksiyonunu ayrı bir yürütme akışında başlatır ve çağıran kod hemen bir sonraki satıra geçer. Dönüş değeri beklenmez, bir "thread handle" verilmez; goroutine artık runtime'ın sorumluluğundadır.

### Kök neden: Neden goroutine, işletim sistemi thread'i değil?

İşletim sistemi thread'leri pahalıdır. Her OS thread'i tipik olarak megabaytlar ölçeğinde bir sabit stack alanı ayırır ve thread'ler arası geçiş (context switch) çekirdek moduna girmeyi gerektirir; bu da yüzlerce nanosaniyeden mikrosaniyelere kadar maliyet çıkarabilir. Bu yüzden geleneksel dillerde on binlerce thread açmak pratik değildir.

Goroutine bu maliyeti iki mekanizmayla düşürür. Birincisi, goroutine başlangıçta çok küçük bir stack ile başlar (tarihsel olarak birkaç kilobayt mertebesinde) ve ihtiyaç oldukça büyüyüp küçülen bir "growable stack" kullanır. Böylece yüz binlerce goroutine açmak mümkün hale gelir. İkincisi, goroutine'ler OS thread'lerine birebir eşlenmez; bunun yerine Go'nun **M:N zamanlayıcısı** devreye girer.

### Çalışma mantığı: G-M-P modeli ve zamanlayıcı

Go runtime'ının zamanlayıcısı üç temel soyutlama üzerine kuruludur:

- **G (goroutine):** Yürütülecek iş birimi, kendi stack'i ve durumu.
- **M (machine):** Gerçek bir OS thread'i. Kod ancak bir M üzerinde koşar.
- **P (processor):** Bir yürütme bağlamı; çalıştırılabilir goroutine'lerin yerel kuyruğunu tutan mantıksal işlemci. `P` sayısı `GOMAXPROCS` ile belirlenir ve genellikle mevcut mantıksal çekirdek sayısına eşittir.

Bir M'nin kod koşabilmesi için bir P'ye sahip olması gerekir. Zamanlayıcı, çalıştırılabilir G'leri P'lerin kuyruklarından alıp M'ler üzerinde koşturur. Bir P'nin kuyruğu boşaldığında **work stealing** yapılır: başka bir P'nin kuyruğundan yarısını çalar. Bu, yükü çekirdekler arasında dengede tutar.

Kritik nokta şudur: Bir goroutine bloklayıcı bir sistem çağrısına girdiğinde (örneğin disk I/O), o M çekirdek tarafında bloke olur. Runtime bunu fark edip P'yi o M'den ayırır ve başka bir M'ye bağlar ki diğer goroutine'ler koşmaya devam etsin. Ağ I/O'sunda ise daha zarif bir mekanizma vardır: goroutine, **netpoller** üzerinden park edilir, altındaki M serbest kalır ve veri hazır olduğunda goroutine yeniden çalıştırılabilir hale gelir. Bu sayede "her bağlantıya bir goroutine" modeli, on binlerce eşzamanlı bağlantıda dahi az sayıda OS thread'iyle ölçeklenir.

Zamanlayıcının bir başka önemli özelliği **preemption**'dır. Eski Go sürümlerinde zamanlama büyük ölçüde işbirlikçiydi (cooperative): bir goroutine ancak fonksiyon çağrısı, channel işlemi gibi belirli noktalarda kontrolü bırakırdı. Bu, hiç çağrı içermeyen sıkı bir döngünün (tight loop) tek bir P'yi süresiz işgal etmesine yol açabiliyordu. Modern Go sürümleri **asenkron preemption** getirdi: runtime, uzun süre koşan bir goroutine'i sinyal tabanlı bir mekanizmayla kesip zamanlayıcıya kontrolü geri alabilir. Bu yüzden artık "boş `for {}` döngüsü tüm programı dondurur" varsayımı genel olarak geçerli değildir; yine de bu davranışa güvenerek kod yazmak iyi bir fikir değildir.

### Yaygın tuzak: goroutine sızıntısı (leak)

Goroutine'ler garbage collector tarafından toplanmaz. Bir goroutine ancak fonksiyonu döndüğünde sona erer. Eğer bir goroutine sonsuza dek bir channel'dan okumayı beklerse ve o channel'a hiç yazılmazsa, o goroutine sonsuza kadar yaşar ve stack'i ile birlikte hafızada kalır. Bu **goroutine leak**'tir ve uzun süre koşan servislerde sinsi bir hafıza sızıntısı kaynağıdır.

```go
func sizintiliUret() <-chan int {
    ch := make(chan int)
    go func() {
        for i := 0; ; i++ {
            ch <- i // tüketici okumayı bırakırsa burada sonsuza dek bloke olur
        }
    }()
    return ch
}
```

Tüketici birkaç değer alıp döngüden çıkarsa, üretici goroutine `ch <- i` satırında ilelebet asılı kalır. Çözüm neredeyse her zaman bir iptal sinyali vermektir; bunun idiyomatik yolu `context` veya bir `done` channel'ıdır.

## Channel: İletişimle Paylaşım

### Tanım ve felsefe

Channel, goroutine'ler arasında tipli değer aktaran bir eşzamanlılık ilkelidir. Go'nun eşzamanlılık felsefesini özetleyen slogan şudur: **"Don't communicate by sharing memory; share memory by communicating."** Yani ortak bir değişkeni kilitle koruyup üzerine yazışmak yerine, verinin sahipliğini bir channel üzerinden bir goroutine'den diğerine devredin. Böylece aynı anda yalnızca tek bir goroutine veriye dokunur ve race'in kaynağı ortadan kalkar.

```go
ch := make(chan int)      // buffersiz (unbuffered) channel
buf := make(chan int, 8)  // 8 kapasiteli buffer'lı (buffered) channel
```

### Kök neden: Senkronizasyon nasıl ortaya çıkar

Buffersiz bir channel'da gönderme (`ch <- v`) ve alma (`<-ch`) **randevu (rendezvous)** noktasıdır. Gönderen, bir alan hazır olana kadar bloke olur; alan, bir gönderen hazır olana kadar bloke olur. Bu, sadece veri aktarımı değil aynı zamanda bir **senkronizasyon** olayıdır: gönderme tamamlandığında, gönderenin o noktaya kadar yaptığı tüm hafıza yazmaları, alan goroutine tarafından görülebilir hale gelir.

Bu "görünürlük" garantisi, Go'nun **hafıza modeli (memory model)**'nden gelir. Hafıza modeli, "happens-before" ilişkisiyle tanımlanır: bir olay diğerinden önce gerçekleşiyorsa (happens-before), ilkinin hafıza etkileri ikinci tarafından gözlemlenir. Channel işlemleri bu ilişkiyi kuran temel araçlardan biridir. Kabaca: buffersiz bir channel'a gönderme, o gönderiye karşılık gelen almanın tamamlanmasından önce gerçekleşir; buffer'lı bir channel'da ise bir gönderi, buffer'ın dolmasına bağlı olarak ilgili almadan önce gerçekleşir. Bu kurallar, kilit kullanmadan doğru senkronize kod yazmayı mümkün kılar. Kesin ve yetkili tanımlar için Go'nun resmî hafıza modeli belgesine başvurmak gerekir; buradaki anlatım kavramsaldır.

Buffer'lı channel'da gönderme, buffer dolu olmadıkça bloke olmaz; alma, buffer boş olmadıkça bloke olmaz. Buffer, üretici ile tüketici arasındaki hız dalgalanmalarını yumuşatan bir tampon görevi görür. Ama buffer, bir "kuyruk sihiri" değildir: buffer dolduğunda üretici yine bloke olur. Buffer boyutunu keyfî büyütmek, gerçek bir backpressure (geri baskı) probleminin belirtisini gizlemekten başka işe yaramaz.

### close, range ve alma idiyomları

Bir channel `close(ch)` ile kapatılır. Kapatma, "artık gönderi gelmeyecek" sinyalidir. Kapalı bir channel'dan alma hemen döner: buffer'da kalan değerler tüketildikten sonra, tipin sıfır değerini ve `ok == false` bilgisini verir.

```go
v, ok := <-ch
if !ok {
    // channel kapalı ve boşaldı
}
```

`for range` bir channel üzerinde döndüğünde, channel kapatılıp boşalana dek değerleri okur ve ondan sonra döngüden temiz biçimde çıkar. Bu, üretici/tüketici zincirlerinin idiyomatik yazım biçimidir:

```go
for v := range ch {
    isle(v)
}
```

### Kritik kurallar ve tuzaklar

Channel kullanımının en sık ihlal edilen kuralları şunlardır:

**Kapalı channel'a gönderme panic üretir.** `send on closed channel` panic'i, kim tarafından ne zaman kapatılacağı netleştirilmediğinde ortaya çıkar. İdiyomatik kural: **channel'ı yalnızca gönderen kapatır**, alan asla kapatmaz. Çünkü kapatmak, "başka gönderi gelmeyecek" demektir ve bunu yalnızca gönderen bilebilir.

**Birden çok gönderen varken kim kapatacak?** Tek bir gönderen kapatmayı sahiplenemez. Bu durumda ya bir `sync.WaitGroup` ile tüm göndericilerin bittiği beklenip ayrı bir koordinatör goroutine kapatır, ya da kapatma yerine ayrı bir `done` / `context` iptal kanalı kullanılır.

**`nil` channel sonsuza kadar bloke eder.** Sıfır değerinde (nil) bir channel'a gönderme veya ondan alma asla tamamlanmaz. Bu bir hata gibi görünse de aslında `select` içinde bir dalı "kapatmak" için bilinçli olarak kullanılan güçlü bir idiyomdur (aşağıda değinilecek).

**Buffersiz channel'a aynı goroutine içinde önce gönderip sonra almak deadlock'tur.** Randevu için karşı taraf gerekir; tek goroutine kendi kendine randevu veremez.

## select: Birden Fazla Channel'ı Yönetmek

### Tanım ve çalışma mantığı

`select`, birden çok channel işleminden hangisi hazırsa onu yürüten bir kontrol yapısıdır. Sözdizimsel olarak `switch`'e benzer ama koşullar boolean değil channel işlemleridir:

```go
select {
case v := <-girisA:
    isle(v)
case cikisB <- sonuc:
    // gönderim yapıldı
case <-time.After(2 * time.Second):
    // zaman aşımı
default:
    // hiçbir case hazır değilse (bloke olmadan)
}
```

`select`'in semantiği şudur: hazır olan (bloke olmadan tamamlanabilecek) case'lerden **rastgele biri** seçilir. Birden fazla case aynı anda hazırsa seçim rastgeledir; bu, bilinçli bir tasarım kararıdır ve belirli bir channel'ın sürekli önceliklenip diğerlerinin **açlığa (starvation)** düşmesini engeller. Hiçbir case hazır değilse ve bir `default` varsa, `default` çalışır ve `select` bloke olmaz. `default` yoksa, `select` en az bir case hazır olana dek bloke olur.

### İdiyomlar

**Zaman aşımı (timeout).** `time.After` bir channel döndürür ve belirtilen süre sonra üzerine bir değer yazar. Bir işlemi zaman aşımıyla sınırlamak için ana işlemin channel'ı ile `time.After`'ı aynı `select`'e koyarsınız. Ancak dikkat: `time.After` her çağrıda yeni bir timer oluşturur ve bu timer süre dolana dek toplanmaz; sıkı bir döngü içinde `time.After` kullanmak yavaş bir kaynak sızıntısı yaratabilir. Yüksek frekanslı döngülerde `time.NewTimer` oluşturup yeniden kullanmak veya `context` tabanlı iptal tercih edilmelidir.

**Bloke olmayan işlem (non-blocking).** `default` dalı, bir channel'a bloke olmadan göndermeyi veya ondan okumayı sağlar. Örneğin bir metrik channel'ı doluysa metriği düşürmek (drop) meşru bir stratejidir:

```go
select {
case metrikCh <- olcum:
default:
    // channel dolu, bu ölçümü atla
}
```

**`nil` channel ile dalı devre dışı bırakmak.** Bir case'in channel'ını `nil`'e set ederseniz, o case asla seçilmez; çünkü nil channel hiçbir zaman hazır olmaz. Bu, bir kaynak tükendiğinde (örneğin bir giriş channel'ı kapandığında) o dalı dinamik olarak "kapatmanın" temiz yoludur. Böylece `select`'ten o kolu çıkarmak için kod dallanması yazmanız gerekmez.

## context: İptal ve Son Tarih Yaymak

### Tanım

`context` paketi, bir çağrı zinciri (call chain) boyunca **iptal (cancellation)**, **son tarih (deadline)** ve **istek kapsamlı değer** taşımanın standart yoludur. Bir sunucuda gelen her istek için bir `Context` oluşturulur ve bu context, o isteği işlerken çağrılan tüm alt fonksiyonlara ve başlatılan goroutine'lere ilk parametre olarak geçirilir. İstek iptal edilirse veya süresi dolarsa, context'ten türeyen tüm iş kolları bunu öğrenip erkenden durabilir.

### Kök neden: Neden ayrı bir context tipi?

Go'da bir goroutine'i dışarıdan zorla öldürmenin bir yolu yoktur; bu bilinçli bir tasarım tercihidir çünkü zorla sonlandırma, kilitlerin serbest bırakılmaması gibi tutarsız durumlar yaratır. O halde iptal, **işbirlikçi** olmak zorundadır: goroutine'in kendisi düzenli aralıklarla "durmam mı gerekiyor?" diye kontrol etmeli ve gerekiyorsa temizce çıkmalıdır. `context`, bu "durmam mı gerekiyor?" sorusunu standartlaştırır.

`Context` arayüzünün özü şu iki üyedir: `Done()` bir `<-chan struct{}` döndürür ve iptal gerçekleştiğinde bu channel kapatılır; `Err()` ise neden durulduğunu (`context.Canceled` mi yoksa `context.DeadlineExceeded` mi) söyler. `Done()`'ın bir channel olması kritiktir: bu sayede iptal, `select` ile diğer channel işlemlerinin yanında doğal biçimde beklenebilir.

### Kullanım

```go
func islemYap(ctx context.Context, girdi <-chan İş) error {
    for {
        select {
        case <-ctx.Done():
            return ctx.Err()  // iptal veya deadline
        case is := <-girdi:
            if err := calis(ctx, is); err != nil {
                return err
            }
        }
    }
}
```

Context'ler bir ağaç oluşturur. `context.Background()` kökten türer; `context.WithCancel`, `context.WithTimeout` ve `context.WithDeadline` yeni bir alt context ve onu iptal eden bir fonksiyon döndürür. Bir üst context iptal edildiğinde tüm alt context'ler de iptal olur. Bu yayılma, tek bir istek iptalinin tüm alt işleri (veritabanı sorgusu, dış API çağrısı, arka plan hesabı) aynı anda durdurmasını sağlar.

### Kurallar ve tuzaklar

- **`cancel` fonksiyonunu her zaman çağırın.** `WithCancel`/`WithTimeout`/`WithDeadline`, dönen `cancel`'i çağırmazsanız kaynak sızdırır. İdiyomatik yazım hemen ardından `defer cancel()`'dir. Bu, işlem erken bitse bile ilişkili zamanlayıcının ve iç yapıların serbest kalmasını garanti eder.
- **Context'i ilk parametre yapın ve isim olarak `ctx` verin.** Yerleşik konvansiyon budur; okunabilirlik ve statik analiz araçları buna güvenir.
- **Context'i struct alanında saklamayın.** Context istek kapsamlıdır ve fonksiyon boyunca akmalıdır; bir struct içine gömmek yaşam döngüsünü belirsizleştirir.
- **`context.Value`'yu yalnızca istek kapsamlı, taşıyıcı verinin (request ID, trace bilgisi gibi) yayılması için kullanın.** İsteğe bağlı fonksiyon parametrelerini context içine tıkıştırmak bir anti-pattern'dir; tip güvenliğini kaybeder ve bağımlılıkları gizler.
- **İptali kontrol etmezseniz context'in hiçbir faydası olmaz.** `ctx.Done()`'ı beklemeyen veya `ctx`'i alt çağrılara geçirmeyen kod, iptal edilebilir görünse de değildir.

## Race Detector: Doğruluğu Korumak

### Tanım

**Data race**, iki veya daha fazla goroutine'in aynı hafıza konumuna, en az biri yazma olacak şekilde ve aralarında bir senkronizasyon (happens-before) ilişkisi olmadan eşzamanlı eriştiği durumdur. Data race, Go'da **tanımsız davranıştır (undefined behavior)**: sonuç bozuk veriden, çökmeye, hatta imkânsız görünen program durumlarına kadar değişebilir ve genellikle sporadik, tekrar üretilmesi zor hatalar olarak görünür.

Go, bu hataları yakalamak için yerleşik bir **race detector** ile gelir. `-race` bayrağıyla derlenen veya test edilen bir program, çalışma zamanında hafıza erişimlerini izler ve senkronizasyonsuz eşzamanlı erişimleri tespit ettiğinde ayrıntılı bir rapor basar.

```
go test -race ./...
go run -race main.go
go build -race
```

### Çalışma mantığı: Neden dinamik, statik değil?

Race detector **dinamik** bir araçtır; yani programı gerçekten koşturarak çalışır, kaynak kodu statik olarak analiz ederek değil. Kök neden şudur: bir data race'in var olup olmadığı, hangi goroutine'lerin gerçekte hangi sırayla hangi adreslere eriştiğine bağlıdır ve bu, çalışma zamanındaki zamanlamaya, girdilere ve `GOMAXPROCS` gibi ayarlara göre değişir. Genel durumda statik olarak kesin karar vermek çok zordur.

Detector, altında bir **happens-before** takibi yapar (kavramsal olarak "vector clock" benzeri bir muhasebe). Her hafıza erişiminde, o erişimin hangi senkronizasyon olaylarından sonra geldiğini kaydeder. İki erişim arasında yazma varsa ve bunları sıralayan bir happens-before ilişkisi kurulamıyorsa, bir race raporlanır. Bu yaklaşımın en önemli özelliği şudur: **race detector yanlış pozitif (false positive) üretmez** kabul edilir; bildirdiği bir race, o koşuda gerçekten gözlemlenmiş gerçek bir race'tir. Onaylanabilir bir race raporu asla göz ardı edilmemelidir.

Bunun bedeli vardır. `-race` ile derlenen program belirgin biçimde yavaşlar (tipik olarak birkaç kat) ve daha çok hafıza kullanır. Bu yüzden race detector genellikle production'da değil, test ve CI aşamasında çalıştırılır.

### Kritik sınırlama: Kapsama bağımlılığı

Race detector'ün en yanıltıcı yönü şudur: **yalnızca o koşuda gerçekten tetiklenen kod yollarındaki race'leri görebilir.** Eğer bir race'e yol açan zamanlama o koşuda hiç oluşmadıysa, detector onu göremez. Dolayısıyla "`-race` ile testler temiz geçti" demek, "kodda hiç race yok" anlamına gelmez; yalnızca "test edilen senaryolarda ve o çalıştırmadaki zamanlamada race gözlenmedi" demektir.

Pratik sonuç: race detector'ü, gerçekçi eşzamanlılık içeren, iyi kapsama sağlayan testlerle birlikte kullanmak gerekir. Zayıf test kapsamı, race detector'ün etkinliğini doğrudan sınırlar.

### Örnek: Klasik sayaç race'i

```go
var sayac int
var wg sync.WaitGroup
for i := 0; i < 1000; i++ {
    wg.Add(1)
    go func() {
        defer wg.Done()
        sayac++ // RACE: senkronizasyonsuz eşzamanlı okuma-değiştirme-yazma
    }()
}
wg.Wait()
```

`sayac++` aslında üç işlemdir: oku, artır, yaz. Birden çok goroutine bunu senkronizasyonsuz yaptığında güncellemeler kaybolur ve sonuç 1000 olmayabilir. Doğru çözümler: `sayac`'ı bir mutex ile korumak, `sync/atomic` (örneğin `atomic.AddInt64`) kullanmak, ya da sayımı tek bir goroutine'e devredip artışları bir channel üzerinden göndermek. Hangisinin seçileceği, erişim deseni ve okunabilirlik ihtiyacına bağlıdır.

## En İyi Pratikler ve Toparlama

Aşağıdaki ilkeler, üretim kalitesinde eşzamanlı Go kodunun bel kemiğini oluşturur:

**Bir goroutine başlatırken onun nasıl sona ereceğini planlayın.** Her `go` deyimi için "bu goroutine hangi koşulda döner?" sorusuna net bir cevabınız olmalı. Cevap genellikle bir `context` iptali, bir giriş channel'ının kapanması veya bir işin bitmesidir. Cevabı olmayan goroutine, gelecekteki bir leak'tir.

**Sahiplik ve kapatma sorumluluğunu netleştirin.** Her channel'ın tek bir "sahibi" olsun; kapatmayı bu sahip yapsın. Birden çok gönderen varsa kapatmayı hiç kullanmayıp `context`/`done` idiyomuna geçin.

**Backpressure'ı bilinçli tasarlayın.** Buffer boyutunu bir performans yaması olarak değil, üretici-tüketici hız uyumsuzluğunu yönetmenin açık bir kararı olarak belirleyin. Sınırsız büyüyebilen kuyruklar, hafızayı tüketen gizli bir tehlikedir.

**Kilitle paylaşım ile channel arasında bilinçli seçim yapın.** Slogan channel'ı över ama her problem channel'a uygun değildir. Basit, kısa süreli, paylaşılan bir sayaç veya map için `sync.Mutex` ya da `sync/atomic` çoğu zaman daha basit ve daha hızlıdır. Channel, veri **akışı** ve sahiplik **devri** olduğunda parlar; salt karşılıklı dışlama (mutual exclusion) için mutex daha doğrudandır. "Channel her yerde" dogması, gereksiz karmaşıklık üretir.

**`select`'te her zaman bir çıkış yolu bulundurun.** Uzun süre koşan `select` döngülerinde `ctx.Done()` dalını neredeyse her zaman ekleyin; aksi halde döngü, iptal gelmişken bile içeride asılı kalabilir.

**CI'da `-race` ile test edin.** Race detector'ü CI hattınızın standart bir parçası yapın ve eşzamanlılık içeren kod yollarını gerçekten çalıştıran testler yazın. Bildirilen her race'i bir doğruluk hatası olarak ele alın, "nadiren oluyor" diye geçiştirmeyin.

**Senkronizasyonu happens-before üzerinden düşünün.** "Bu yazma, o okumadan önce mutlaka gerçekleşiyor mu?" sorusunu channel işlemleri, mutex kilitleri veya `WaitGroup` gibi belirli senkronizasyon araçlarıyla kurulmuş bir ilişkiye dayandırın. "Sıralama muhtemelen böyle olur" varsayımı, data race'in ta kendisidir.

Son bir çerçeve: Go'nun eşzamanlılık araçları güçlüdür ama sihirli değildir. Goroutine ucuz olsa da bedavа değildir; channel senkronizasyon sağlasa da yanlış kullanıldığında deadlock ve leak üretir; race detector güçlü olsa da yalnızca gördüğü kadarını yakalar. Bu araçları etkin kılan şey, altlarındaki modeli (zamanlayıcı, hafıza modeli, işbirlikçi iptal) anlayarak ve idiyomlara sadık kalarak kullanmaktır.
