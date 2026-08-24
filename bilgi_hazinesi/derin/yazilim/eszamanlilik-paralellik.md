# Eşzamanlılık ve Paralellik — Derin Dalış

Bu metin, eşzamanlılık ve paralellik kavramlarının tanımını tekrar etmez; onları kanlı canlı kod üzerinde çalıştırır. Amaç, "race condition'a dikkat edin" gibi soyut uyarıların ötesine geçip, hatanın *nasıl* doğduğunu, üretim kodunda hangi kılığa büründüğünü ve doğru çözümün somut şeklini göstermektir. Kavramsal çerçeve için özet makaleye başvurulabilir; burada elimiz klavyede.

---

## 1. Çözümlü yürüyüş: Banka hesabından para çekme

En sevdiğim örnek, para çekme işlemidir çünkü hata sezgiye tamamen aykırı bir yerden gelir ve testte neredeyse hiç görünmez. Aşağıdaki Go kodu, tek bir hesaba iki farklı goroutine'den aynı anda para çekme isteği gönderir. Kod ilk bakışta doğru görünür: çekmeden önce bakiyeyi kontrol ediyoruz, yani "yetersiz bakiye" durumunda çekmeyeceğiz.

### Zafiyetli kod

```go
package main

import (
	"fmt"
	"sync"
)

type Account struct {
	balance int
}

// ZAFİYETLİ: kontrol ve güncelleme arasında koruma yok
func (a *Account) Withdraw(amount int) bool {
	if a.balance >= amount { // 1. KONTROL
		// Tam bu noktada başka bir goroutine araya girebilir
		a.balance -= amount // 2. GÜNCELLEME
		return true
	}
	return false
}

func main() {
	acc := &Account{balance: 100}
	var wg sync.WaitGroup

	// İki goroutine aynı anda 100'er lira çekmeye çalışıyor
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if acc.Withdraw(100) {
				fmt.Println("Çekim başarılı: 100")
			}
		}()
	}

	wg.Wait()
	fmt.Printf("Son bakiye: %d\n", acc.balance)
}
```

Beklenti şudur: hesapta 100 lira var, iki istek 100'er lira çekmek istiyor. Yalnızca biri başarılı olmalı, bakiye 0'da kalmalı. Kodu bir kez çalıştırdığınızda çoğu zaman tam da bunu görürsünüz. Ama yarış dedektörüyle çalıştırın:

```
go run -race main.go
```

Şu çıktıyı görürsünüz (özetlenmiş):

```
Çekim başarılı: 100
Çekim başarılı: 100
Son bakiye: -100
==================
WARNING: DATA RACE
Read at 0x... by goroutine 8:
  main.(*Account).Withdraw()
Previous write at 0x... by goroutine 7:
  main.(*Account).Withdraw()
==================
```

**İki çekim de başarılı oldu ve bakiye -100'e düştü.** Hesapta olmayan parayı çektik.

### Sorun neden oluşuyor?

Hata, `if a.balance >= amount` kontrolü ile `a.balance -= amount` güncellemesi arasındaki boşlukta yatar. Bu ikisi *atomik* değildir; araları ayrılabilir. Olay sırası şöyle işler:

1. Goroutine A, `balance`'ı okur: 100. `100 >= 100` doğru, çekmeye karar verir.
2. Tam güncellemeden önce, zamanlayıcı A'yı durdurur ve B'yi çalıştırır.
3. Goroutine B, `balance`'ı okur: hâlâ 100. `100 >= 100` doğru, o da çekmeye karar verir.
4. B, bakiyeyi günceller: `100 - 100 = 0`.
5. A kaldığı yerden devam eder. Elinde hâlâ eski kararı vardır ve günceller: `0 - 100 = -100`.

Bu, klasik bir **check-then-act** (kontrol-sonra-uygula) yarışıdır. Kontrol ile eylem arasında dünya değişmiştir, ama A bunun farkında değildir. Kritik nokta: kontrolün doğru olması, eylem anında hâlâ doğru olacağı anlamına gelmez. Paylaşılan değiştirilebilir durumda, "az önce kontrol ettim" garanti değildir.

### Düzeltilmiş kod

Çözüm, kontrol ve eylemi tek bir bölünemez kritik bölgeye kapatmaktır. Bir mutex ile:

```go
package main

import (
	"fmt"
	"sync"
)

type Account struct {
	mu      sync.Mutex
	balance int
}

// DOĞRU: kontrol ve güncelleme tek kritik bölgede
func (a *Account) Withdraw(amount int) bool {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.balance >= amount {
		a.balance -= amount
		return true
	}
	return false
}

func main() {
	acc := &Account{balance: 100}
	var wg sync.WaitGroup

	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if acc.Withdraw(100) {
				fmt.Println("Çekim başarılı: 100")
			}
		}()
	}

	wg.Wait()
	fmt.Printf("Son bakiye: %d\n", acc.balance) // Her zaman 0
}
```

Artık `Lock()` çağrısı, kritik bölgeye aynı anda yalnızca bir goroutine'in girmesini garanti eder. A kilidi aldığında kontrol ve güncellemeyi tamamlar, sonra bırakır; B ancak o zaman girer ve `balance`'ı 0 görür, çekmeyi reddeder. Sonuç her zaman tutarlıdır ve yarış dedektörü artık susar.

Dikkat edilmesi gereken ince nokta: kilidi `Withdraw` metodunun içine, veriye *bitişik* koyduk. Çağıran tarafta değil. Çünkü koruma, veriyi kullanan her yolun kapsanmasını gerektirir; koruma sorumluluğunu çağırana bırakırsak, bir gün biri kilit almadan çağırır ve zafiyet geri döner. Kilit ile korunan veri aynı struct'ta bir arada durmalı ve o veriye erişen her metot kilidi almalıdır.

Bu örneğin bir de "peki bunu kilitsiz çözemez miydik?" sorusu vardır ve cevabı öğreticidir. Tek bir `int64` bakiye ve tek bir çekme işlemi olsaydı, `atomic.CompareAndSwap` ile lock-free bir çözüm kurulabilirdi: bakiyeyi oku, yeni değeri hesapla, CAS ile "bakiye hâlâ okuduğum değerse yeni değere geçir, değilse başarısız ol ve baştan dene" döngüsü kur. Ama gerçek bir hesapta işlem tek değişkenle bitmez — çekimi bir loglara yazmak, bir limit tablosunu kontrol etmek, bir bildirim tetiklemek gerekir. Bu bileşik invariant'lar ortaya çıkınca CAS döngüsü hızla yönetilemez hale gelir ve mutex tekrar en temiz araç olur. Lock-free'in doğru yeri, işlemin gerçekten tek atomik adıma indirgenebildiği dar durumlardır; bunu 3. bölümde ayrıntılandıracağız.

Son bir uyarı: `defer a.mu.Unlock()` kullanımı burada bilinçli bir tercihtir. Kritik bölge içinde erken `return` veya panic olsa bile `defer`, kilidin mutlaka bırakılmasını garanti eder. Elle `Unlock()` yazıp bir hata yolunda onu atlamak, kilidin sonsuza dek tutulu kalmasına ve tüm sistemin o kilit etrafında donmasına yol açar — üretimde gördüğüm en sinsi kilitlenme sebeplerinden biridir.

---

## 2. Gerçek sistem örneği: Sınırlı worker havuzu ve backpressure

Gerçek dünyada eşzamanlılık nadiren "iki goroutine bir sayaç" kadar temiz gelir. Tipik senaryo şudur: bir kuyruğa iş akıyor, bunları paralel işleyecek işçileriniz var, ama işçi sayısını ve bellek kullanımını kontrol altında tutmanız gerekiyor. Naif çözüm — her iş için yeni bir goroutine — üretimde sistemi çökertir çünkü ani bir yük dalgası milyonlarca goroutine açar, bellek şişer ve zamanlayıcı boğulur.

Aşağıda, üretimde güvenle kullanabileceğiniz bir **sınırlı worker havuzu** vardır. Bu desen üç sorunu birden çözer: paralelliği çekirdek sayısına göre sınırlar, kuyruğu bounded (sınırlı) tutarak backpressure sağlar, ve tüm işçilerin temiz kapanmasını garanti eder.

```go
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type Job struct {
	ID int
}

type Result struct {
	JobID int
	Value int
}

// worker: jobs kanalından iş alır, sonucu results kanalına yazar
func worker(ctx context.Context, id int, jobs <-chan Job, results chan<- Result, wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		select {
		case job, ok := <-jobs:
			if !ok {
				return // kanal kapandı, iş bitti
			}
			// Gerçek işi simüle et
			time.Sleep(10 * time.Millisecond)
			select {
			case results <- Result{JobID: job.ID, Value: job.ID * job.ID}:
			case <-ctx.Done():
				return // iptal edildi
			}
		case <-ctx.Done():
			return // iptal edildi
		}
	}
}

func main() {
	const numWorkers = 4
	const queueSize = 16

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	jobs := make(chan Job, queueSize)       // BOUNDED kuyruk: backpressure sağlar
	results := make(chan Result, queueSize)

	var wg sync.WaitGroup
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go worker(ctx, i, jobs, results, &wg)
	}

	// Üretici: işleri kuyruğa gönderir. Kuyruk doluysa BLOKLANIR (backpressure).
	go func() {
		for i := 1; i <= 50; i++ {
			select {
			case jobs <- Job{ID: i}:
			case <-ctx.Done():
				break
			}
		}
		close(jobs) // tüm işler gönderildi, kanalı kapat
	}()

	// Tüm işçiler bitince results kanalını kapat
	go func() {
		wg.Wait()
		close(results)
	}()

	// Sonuçları topla
	total := 0
	count := 0
	for r := range results {
		total += r.Value
		count++
	}
	fmt.Printf("%d iş tamamlandı, toplam: %d\n", count, total)
}
```

Bu kodda dikkat edilmesi gereken mimari kararlar şunlardır:

**Bounded kanal = backpressure.** `jobs` kanalını `queueSize` kapasiteyle oluşturduk. Üretici, kuyruk dolduğunda `jobs <- Job{...}` satırında *bloklanır*. Bu bir bug değil, bir özelliktir: işçiler yetişemezse üretici otomatik olarak yavaşlar. Unbounded olsaydı (`make(chan Job)` yerine sınırsız bir slice'a biriktirseydik), üretici tüketiciyi geçtiğinde bellek sonsuza kadar şişerdi. Bu, gerçek sistemlerde OOM (out of memory) çökmelerinin baş sebebidir.

**`close(jobs)` sinyali.** İşçiler sonsuz bir döngüde `<-jobs` okur. Üretici bitince kanalı kapatır; kapalı kanaldan okuma `ok=false` döndürür ve işçiler döngüden çıkar. Bu, "artık iş gelmeyecek" sinyalini yaymanın idiomatic yoludur. Kritik kural: kanalı **her zaman üretici kapatır, asla tüketici**. Tüketici kapatırsa, üretici kapalı kanala yazmaya çalışıp panic eder.

**İki aşamalı kapanış.** `wg.Wait()` ayrı bir goroutine'de çağrılır ve tüm işçiler bitince `results`'ı kapatır. Ana goroutine `for r := range results` ile okur; kanal kapanınca döngü doğal olarak biter. `wg.Wait()`'i doğrudan ana goroutine'de çağırsaydık deadlock olurdu: işçiler `results`'a yazmaya çalışırken bloklanır, ana goroutine `wg.Wait()`'te bloklanır, kimse `results`'ı okumaz.

**Context ile iptal.** Her `select` bloğunda `<-ctx.Done()` dalı var. Timeout dolduğunda veya `cancel()` çağrıldığında, tüm işçiler ve üretici temizce durur. Bu, yapılandırılmış eşzamanlılığın Go'daki karşılığıdır: hiçbir goroutine "başıboş" kalmaz.

Python tarafında aynı desenin `asyncio` karşılığı `Semaphore` ile kurulur; eşzamanlılık derecesini sınırlamak için:

```python
import asyncio

async def worker(sem: asyncio.Semaphore, job_id: int) -> int:
    async with sem:  # aynı anda en fazla N iş çalışır
        await asyncio.sleep(0.01)  # I/O simülasyonu
        return job_id * job_id

async def main():
    sem = asyncio.Semaphore(4)  # eşzamanlılık sınırı
    tasks = [worker(sem, i) for i in range(1, 51)]
    results = await asyncio.gather(*tasks)
    print(f"{len(results)} iş, toplam: {sum(results)}")

asyncio.run(main())
```

Burada `Semaphore(4)`, aynı anda en fazla 4 coroutine'in `async with` bloğuna girmesine izin verir. 50 task birden oluşturulsa da, gerçek eşzamanlılık 4 ile sınırlıdır. Bu, örneğin bir dış API'ye saniyede en fazla N istek atmanız gerektiğinde kritiktir — semafor olmadan `gather` 50 isteği aynı anda fırlatır ve API sizi rate-limit'ler veya banlar.

Python'da bu deseni kurarken sık atlanan bir ayrıntı, `asyncio.gather`'ın hata davranışıdır. Varsayılan olarak `gather`, task'lardan biri exception fırlatırsa hemen o exception'ı yeniden fırlatır ama *diğer task'ları iptal etmez* — onlar arka planda çalışmaya devam eder ve sonuçları kaybolur. Eğer "biri patlarsa hepsini durdur" davranışı istiyorsanız, Python 3.11+ ile gelen `asyncio.TaskGroup` doğru araçtır; o, bir task hata verdiğinde kardeş task'ları otomatik iptal eder ve tümünün temiz kapandığını garanti eder. Bu, tam olarak yapılandırılmış eşzamanlılığın (structured concurrency) dile gömülmüş halidir:

```python
async def main():
    sem = asyncio.Semaphore(4)
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(worker(sem, i)) for i in range(1, 51)]
    # Buraya ulaşıldığında TÜM task'lar kesin bitmiştir veya
    # biri hata verdiyse tümü iptal edilip exception yükseltilmiştir
    results = [t.result() for t in tasks]
    print(f"{len(results)} iş, toplam: {sum(results)}")
```

`async with asyncio.TaskGroup()` bloğu bitene kadar kontrol geri dönmez; blok, içindeki her task'ın yaşam süresini kendi kapsamına bağlar. Bu sayede "başlattım ama beklemeyi unuttum" sınıfı hatalar yapısal olarak imkânsız hale gelir. Ateşle-ve-unut task'ların yol açtığı sessiz hata yutmaları, bu desende kökten yok olur.

---

## 3. Karşılaştırma / karar: Mutex mi, kanal mı, atomik mi?

Aynı problemi — paylaşılan bir sayacı güvenle artırmak — üç farklı araçla çözebilirsiniz. Hangisi ne zaman? Bu, eşzamanlı kod yazarken en sık verdiğiniz karardır ve yanlışı ciddi performans veya karmaşıklık maliyeti getirir.

### Seçenek A: Mutex

```go
type Counter struct {
	mu sync.Mutex
	n  int
}
func (c *Counter) Inc() {
	c.mu.Lock()
	c.n++
	c.mu.Unlock()
}
```

**Ne zaman:** Korunan işlem birden fazla adım içeriyorsa (bir map'e yaz + bir slice'a ekle + bir koşul kontrol et gibi bileşik invariant'lar), mutex tek doğru araçtır. Okunması ve akıl yürütmesi en kolayı budur.

**Takas:** Kilit çekişmesi (contention) yüksekse — çok sayıda goroutine aynı kilidi kapışıyorsa — kilit bir darboğaz olur ve paralelliği öldürür. Ayrıca deadlock riski taşır: birden fazla kilit alıyorsanız sıralama disiplini şarttır.

### Seçenek B: Atomik

```go
import "sync/atomic"

type Counter struct {
	n atomic.Int64
}
func (c *Counter) Inc() {
	c.n.Add(1)
}
```

**Ne zaman:** İşlem *tek* bir değişken üzerinde tek bir atomik operasyonla (increment, compare-and-swap, load, store) ifade edilebiliyorsa. Atomikler donanımın CAS (compare-and-swap) komutlarına derlenir, kilit almazlar, bu yüzden yüksek çekişmede mutex'ten belirgin şekilde hızlıdırlar.

**Takas:** Yalnızca tek değişkenlik, basit işlemlerde çalışır. "Önce X'i artır sonra Y'yi güncelle" gibi bileşik invariant'ları atomiklerle *doğru* kurmak son derece zordur ve genellikle yanlış yapılır. Ayrıca lock-free algoritmalar (ABA problemi, memory ordering incelikleri) uzman işidir; ölçülmüş bir darboğaz olmadan buraya atlamak erken optimizasyondur.

### Seçenek C: Kanal / mesaj geçişi

```go
type Counter struct {
	inc chan struct{}
	get chan chan int
}
func (c *Counter) run() {
	n := 0 // durum tek bir goroutine'e kapatıldı, kilit yok
	for {
		select {
		case <-c.inc:
			n++
		case reply := <-c.get:
			reply <- n
		}
	}
}
```

**Ne zaman:** Durum doğal olarak tek bir sahibe aitse, veya sistemi dağıtık/aktör tabanlı kurmak istiyorsanız. Kilit tamamen ortadan kalkar çünkü durum paylaşılmaz — yalnızca `run` goroutine'i `n`'e dokunur.

**Takas:** Basit bir sayaç için bu aşırı mühendisliktir; mesaj gönderme ve alma, atomik `Add`'den kat kat pahalıdır. Kanallar, durumun karmaşık ve sahipliğin net olduğu senaryolarda parlar, mikro işlemlerde değil. Go topluluğunun kendi tavsiyesi nettir: "Sayaç gibi basit durum için mutex kullanın; kanalları veri akışını koordine etmek için saklayın."

### Karar özeti

| Kriter | Mutex | Atomik | Kanal |
|---|---|---|---|
| Bileşik invariant | En iyi | Zayıf | İyi |
| Tek değişken, yüksek çekişme | Orta | En iyi | Zayıf |
| Okunabilirlik | İyi | İyi | Duruma göre |
| Dağıtık/aktör'e uzanma | Hayır | Hayır | En iyi |
| Deadlock riski | Var | Yok | Var (kanal deadlock'u) |

Pratik kural: **Şüpheye düşünce mutex ile başla.** Ölç. Eğer profil kilit çekişmesini gerçek bir darboğaz gösterirse ve işlem tek değişkenlikse, atomike geç. Durum sahipliği doğal olarak tek bir bileşene aitse ve koordinasyon karmaşıksa, kanala geç. Ters yönde — kanalla başlayıp her yeri mesajla süslemek — çoğu ekibin düştüğü ve gereksiz karmaşıklık üreten tuzaktır.

Bir ölçek daha yukarı çıkıldığında, yani tek makinenin sınırlarını aştığınızda, bu takaslar yeniden şekil değiştirir. `RWMutex` (okuma-yazma kilidi) bu noktada devreye girer: eğer veriniz *çok okunan, az yazılan* bir yapıysa (örneğin bir yapılandırma tablosu, bir cache), `RWMutex` birden fazla okuyucunun aynı anda kilidi paylaşmasına izin verir ve yalnızca yazarken dışlama uygular. Bu, okuma ağırlıklı yüklerde belirgin hız kazandırır. Ama tuzağı vardır: yazma nadir bile olsa, sürekli okuyucu akışı yazarı sonsuza dek bekletebilir (writer starvation), ve `RWMutex`'in kendisi düz `Mutex`'ten daha ağır bir yapıdır — çekişme düşükse basit `Mutex` çoğu zaman daha hızlıdır. Yani "okuma çok, o halde `RWMutex`" refleksi de ölçülmeden verilmemelidir.

Dağıtık dünyada ise bu üç seçenek kavramsal karşılıklarını korur ama araçları değişir: mutex yerine dağıtık kilit (ör. bir kilit servisi üzerinden), atomik yerine veritabanının atomik `UPDATE ... WHERE version = ?` (optimistic locking) deseni, kanal yerine gerçek bir mesaj kuyruğu (message broker) gelir. Aynı zihinsel modeller — kritik bölge, tek atomik adım, mesajla haberleşme — ölçekten bağımsız geçerlidir; yalnızca uygulama katmanı büyür.

---

## 4. Hata-modu kataloğu

Aşağıdakiler, eşzamanlı kod yazan geliştiricilerin tekrar tekrar düştüğü tuzaklardır. Her biri gerçek üretim hatalarının kaynağıdır.

1. **Check-then-act yarışı.** `if key not in map: map[key] = value` gibi kontrol ve eylemin ayrı olduğu her yer bir yarıştır. İki thread aynı anda kontrolü geçer, ikisi de yazar. Kontrol ve eylem tek atomik bölgede olmalı (bkz. Bölüm 1).

2. **Kilidi kopyalamak.** Go'da `sync.Mutex` içeren bir struct'ı değerle (by value) kopyalamak, kilidin de kopyalanmasına yol açar; artık iki ayrı kilit vardır ve koruma çöker. `go vet` bunu yakalar ama sessizce kaçırılabilir. Mutex içeren tipler her zaman pointer ile geçirilmelidir.

3. **`RWMutex`'te yükseltme (upgrade) denemek.** Okuma kilidi tutarken yazma kilidi almaya çalışmak, aynı thread kendini beklediği için deadlock üretir. Kilit yükseltme çoğu implementasyonda desteklenmez; okuma kilidini bırakıp yazma kilidini yeniden almak gerekir (ve bu arada durum değişmiş olabilir, yeniden kontrol şart).

4. **Event loop'u bloklamak.** Async kodda senkron bir çağrı yapmak — `time.sleep()` yerine `asyncio.sleep()` unutmak, bloklu bir DB sürücüsü kullanmak, ağır bir CPU hesabını `await` etmeden yapmak — tüm event loop'u dondurur ve binlerce bağlantıyı aynı anda felç eder. CPU-yoğun işler `run_in_executor` veya ayrı process'e taşınmalıdır.

5. **Ateşle-ve-unut (fire-and-forget) task.** `asyncio.create_task(coro())` çağırıp dönen task'ı bir yerde tutmamak. Task garbage collector tarafından toplanabilir ve sessizce iptal olur; ya da içinde bir exception fırlar ve kimse yakalamadığı için kaybolur. Task'lar bir referansta tutulmalı ve beklenmeli (yapılandırılmış eşzamanlılık).

6. **`WaitGroup.Add`'i goroutine'in *içinde* çağırmak.** `go func() { wg.Add(1); ... }()` yazmak bir yarıştır: `wg.Wait()` bazı goroutine'ler daha `Add` demeden önce çalışabilir ve sıfır sayaç görüp erken döner. `Add` her zaman `go` deyiminden *önce*, çağıran goroutine'de yapılmalıdır.

7. **Deadlock — tutarsız kilit sıralaması.** Bir yol X'ten sonra Y'yi, başka bir yol Y'den sonra X'i kilitliyorsa, döngüsel bekleme oluşur ve sistem donar. Tüm kod tabanında tek bir global kilit sıralaması tanımlanmalı ve istisnasız uyulmalıdır.

8. **`volatile` / atomik-değil görünürlüğü atomiklikle karıştırmak.** Bir değişkeni "volatile" veya benzeri yapmak yalnızca görünürlüğü garanti eder — güncellemenin diğer thread'e görüneceğini. Ama `x++` hâlâ oku-artır-yaz olarak üç adımdır ve hâlâ yarışa açıktır. Görünürlük ve atomiklik ayrı problemlerdir.

9. **Kilit altında dış çağrı yapmak.** Bir kilidi tutarken ağ isteği atmak, başka bir kilit beklemek veya callback çağırmak, hem kilidi çok uzun tutar (paralelliği öldürür) hem de callback'in başka bir kilit alması durumunda deadlock davetiyesidir. Kilit altında yalnızca hızlı, yerel, deterministik iş yapılmalı.

10. **Unbounded kuyruk ile üretici-tüketici.** Tüketici üreticiye yetişemediğinde sınırsız kuyruk bellekte sonsuza kadar büyür ve sistem OOM ile çöker. Kuyruklar bounded olmalı ve dolduğunda üreticiyi yavaşlatmalı (backpressure).

11. **Kapalı kanala yazmak / iki kez kapatmak.** Go'da kapalı bir kanala yazmak veya onu ikinci kez kapatmak panic üretir. Kural: kanalı yalnızca üretici, yalnızca bir kez kapatır. Birden fazla üretici varsa kapatma koordinasyonu (ör. ayrı bir `WaitGroup` + tek kapatıcı goroutine) gerekir.

12. **Döngü değişkenini goroutine'de yakalama (closure capture).** Go 1.22 öncesinde `for i := range xs { go func() { use(i) }() }` yazmak, tüm goroutine'lerin *aynı* `i`'yi paylaşmasına ve genellikle son değeri görmesine yol açardı. Değişken döngü gövdesinde yeniden bağlanmalı (`i := i`) veya parametre olarak geçirilmelidir. Go 1.22 semantiği düzeltti, ama eski kod tabanlarında ve başka dillerde bu tuzak hâlâ canlıdır.

---

## Kapanış notu

Bu dört bölümün ortak dersi tektir: eşzamanlılık hataları, kodu okurken *doğru görünür*. Banka örneğindeki `if balance >= amount` mantıklıydı; check-then-act yarışı gözle görünmezdi. Bu yüzden en güçlü savunma testten önce tasarımdır — kontrol ve eylemi atomik tutmak, durumu tek sahibe kapatmak, kuyruğu bounded yapmak, kilit sıralamasını kurala bağlamak. Testle yakalanan bir eşzamanlılık hatası şanslıdır; çoğu, üretimde yük altında, yeniden üretilemez biçimde patlar. Usta mühendis, hatayı yakalamaya değil, doğduğu yeri tasarımla kapatmaya çalışır.
