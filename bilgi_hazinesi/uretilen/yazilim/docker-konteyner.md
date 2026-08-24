# Docker ve Konteynerleştirme: İmaj, Katman, Çok Aşamalı Build ve En Az Yetki

## Giriş ve Temel Tanım

Konteynerleştirme (containerization), bir uygulamayı ve onun çalışması için gereken tüm bağımlılıkları (kütüphaneler, çalışma zamanı, sistem araçları, konfigürasyon) tek bir taşınabilir birim içinde paketleme tekniğidir. Docker, bu tekniği yaygınlaştıran ve endüstri standardı hâline getiren araç setidir. Temel vaadi meşhur "benim makinemde çalışıyordu" (it works on my machine) problemini ortadan kaldırmaktır: geliştirici laptop'unda çalışan uygulama, aynı imajla test ortamında, staging'de ve production'da da bit bit aynı davranır.

Konteyneri sanal makineden (virtual machine) ayıran kritik nokta şudur: sanal makine, donanımı emüle eden bir hypervisor üzerinde tam bir misafir işletim sistemi (guest OS) çalıştırır. Konteyner ise host makinenin kernel'ini paylaşır; kendi kernel'ini taşımaz. Bu yüzden konteyner megabaytlar seviyesinde olabilirken, sanal makine gigabaytlarla ölçülür ve konteyner saniyeler değil milisaniyeler içinde başlar. Konteyner aslında "hafif bir sanal makine" değildir; izole edilmiş bir Linux process'idir.

## Kök Neden: Konteyner Aslında Nasıl Çalışır?

Konteynerin sihir gibi görünmesinin altında Linux kernel'inin üç temel mekanizması yatar. Bunları anlamak, sonradan karşılaşacağınız garip davranışların kökünü görmenizi sağlar.

### Namespaces (İzolasyon)

Bir process'in "gördüğü" dünyayı sınırlayan mekanizma namespace'lerdir. Kernel farklı türde namespace sunar: PID namespace (process numaraları), NET namespace (ağ arayüzleri), MNT namespace (dosya sistemi bağlama noktaları), UTS namespace (hostname), IPC namespace (process'ler arası iletişim) ve user namespace (kullanıcı/grup ID eşlemesi). Bir konteyner başlatıldığında, içindeki process kendi PID namespace'inde PID 1 olarak görünür; host'taki gerçek PID'i tamamen farklıdır. Konteyner içinden `ps` çalıştırdığınızda host'taki yüzlerce process'i görmemenizin sebebi budur: process'in gördüğü process listesi kendi namespace'iyle sınırlıdır.

### Control Groups (Kaynak Sınırlama)

Namespace izolasyonu "ne görünür" sorusunu çözer; cgroups ise "ne kadar kaynak kullanılabilir" sorusunu çözer. CPU, bellek (memory), disk I/O ve ağ bant genişliği gibi kaynaklar cgroups üzerinden sınırlandırılır. Bir konteynere `--memory=512m` verdiğinizde, cgroup bu process grubunun bellek kullanımını sınırlar; limiti aşarsa OOM killer devreye girer. Bu yüzden bir konteynerin belleği tükettiğinde tüm host'u değil çoğunlukla sadece kendini çökertmesi mümkün olur.

### Union Filesystem (Katmanlı Dosya Sistemi)

Konteynerin dosya sistemi, üst üste bindirilmiş salt-okunur (read-only) katmanlardan ve en üstte yazılabilir (writable) ince bir katmandan oluşur. Bu, overlayfs gibi bir union filesystem sayesinde mümkün olur. Bu mimari, aşağıda ele alacağımız imaj ve katman kavramlarının doğrudan temelidir.

Buradaki asıl kavrayış şudur: Docker, yeni bir teknoloji icat etmedi. namespaces, cgroups ve union filesystem yıllardır Linux kernel'inde vardı. Docker'ın yaptığı, bu düşük seviyeli mekanizmaları bir araya getirip herkesin kullanabileceği tutarlı bir arayüz ve imaj formatı sunmak oldu. Bu tarihsel gerçek, konteynerin neden hâlâ temelde bir Linux teknolojisi olduğunu ve Windows ile macOS'te neden arka planda bir Linux sanal makinesi üzerinden çalıştığını açıklar.

## İmaj ve Katman: İşin Kalbi

### İmaj Nedir?

Bir imaj (image), konteynerin dondurulmuş, salt-okunur şablonudur. Konteyner ise bu imajın çalışan bir örneğidir (instance). İmaj ile konteyner arasındaki ilişki, sınıf (class) ile nesne (object) arasındaki ilişkiye benzer: tek bir imajdan onlarca konteyner örneği başlatabilirsiniz. İmaj diskte durur, konteyner çalışır.

### Katman Nedir ve Neden Vardır?

Bir imaj tek bir dev dosya değildir; katmanların (layers) yığınıdır. Dockerfile'daki her komut (`FROM`, `RUN`, `COPY`, `ADD`) yeni bir katman üretir. Her katman, bir önceki duruma göre yalnızca değişikliği (delta) içerir: eklenen dosyalar, değiştirilen dosyalar, silinen dosyalar.

Bu tasarımın kök nedeni verimliliktir ve iki büyük fayda sağlar:

Birincisi, **katman paylaşımıdır (layer sharing)**. Aynı temel imajı (örneğin `python:3.12-slim`) kullanan on farklı uygulamanız varsa, o temel katmanlar diskte yalnızca bir kez saklanır. On uygulama, aynı salt-okunur katmanları paylaşır; her biri yalnızca kendi üst katmanlarını ayrı tutar. Bu, hem disk alanından hem de ağ bant genişliğinden büyük tasarruf sağlar; çünkü zaten sahip olduğunuz katmanlar tekrar indirilmez.

İkincisi, **build cache'idir**. Docker bir imajı yeniden build ederken, değişmemiş katmanları önbellekten (cache) yeniden kullanır. Docker katmanları sırayla işler ve bir katman değiştiğinde o katmandan sonraki bütün katmanların cache'i geçersiz olur (cache invalidation). Bu davranış, Dockerfile satır sırasının neden bu kadar önemli olduğunu doğrudan belirler.

### Katman Sırasının Somut Etkisi: Yanlış ve Doğru

Şu yaygın hatayı ele alalım. Bir Node.js uygulaması için:

```dockerfile
# KÖTÜ: kaynak kodunu bağımlılıklardan ÖNCE kopyalamak
FROM node:20-slim
WORKDIR /app
COPY . .
RUN npm install
CMD ["node", "server.js"]
```

Buradaki sorun şudur: `COPY . .` tüm proje dosyalarını (kaynak kod dahil) kopyalar. Kaynak kodunuzda tek bir satır değiştirdiğinizde bu katmanın cache'i geçersiz olur, dolayısıyla ondan sonra gelen `RUN npm install` da her seferinde yeniden çalışır. Kod değiştirmediğiniz hâlde tüm bağımlılıklar tekrar tekrar indirilir; build dakikalarca sürer.

Doğrusu, nadiren değişen şeyi önce, sık değişen şeyi sonra kopyalamaktır:

```dockerfile
# İYİ: önce bağımlılık manifestleri, sonra kaynak kod
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
CMD ["node", "server.js"]
```

Burada `package.json` değişmediği sürece `npm ci` katmanı cache'ten gelir. Yalnızca kaynak kodunuzu değiştirdiğinizde son `COPY . .` katmanı yeniden işlenir; bağımlılık kurulumu atlanır. Bu tek değişiklik, günlük build sürenizi dakikalardan saniyelere indirebilir. Kavrayış nettir: Dockerfile'ı değişim sıklığına göre, en kararlıdan en oynak olana doğru sıralayın.

### Katmanların Bir Diğer Tuzağı: Silme İşe Yaramaz

Yeni başlayanların en sık düştüğü hatalardan biri, bir katmanda oluşturulan büyük dosyaların sonraki bir katmanda silinmesiyle imajın küçüleceğini sanmaktır:

```dockerfile
# YANLIŞ: dosya siliniyor ama imaj küçülmüyor
RUN wget https://ornek.com/kocaman.tar.gz
RUN tar -xzf kocaman.tar.gz && make install
RUN rm kocaman.tar.gz
```

Katmanlar toplamsaldır (additive) ve değişmezdir (immutable). Alt bir katmanda eklenen bir dosya, üst bir katmanda "silindiğinde" gerçekte diskten kaybolmaz; union filesystem onu yalnızca bir "whiteout" işaretiyle görünmez kılar. Dosyanın byte'ları alt katmanda hâlâ durur ve imajın toplam boyutuna dahildir. Doğru yaklaşım, indirme, kullanma ve silme işlemlerini tek bir `RUN` içinde `&&` ile zincirlemektir; böylece o dosya hiçbir kalıcı katmana yazılmadan aynı katman içinde temizlenir:

```dockerfile
RUN wget https://ornek.com/kocaman.tar.gz \
    && tar -xzf kocaman.tar.gz \
    && make install \
    && rm kocaman.tar.gz
```

## Çok Aşamalı Build (Multi-Stage Build)

### Çözdüğü Problem

Derlenen (compiled) dillerde veya build adımı gerektiren uygulamalarda temel bir gerilim vardır: build için gereken araçlar (compiler, build sistemi, geliştirme kütüphaneleri, test bağımlılıkları) çalışma zamanı için gerekli değildir. Bir Go uygulaması düşünün; derlemek için Go toolchain'inin tamamına ihtiyacınız var (yüzlerce megabayt), ama sonuçta ortaya çıkan tek bir statik binary'yi çalıştırmak için hiçbirine ihtiyacınız yok.

Çok aşamalı build'den önce insanlar ya devasa imajlarla yaşıyor ya da karmaşık iki-Dockerfile hileleri kullanıyordu. Multi-stage build bu problemi zarif biçimde çözer.

### Nasıl Çalışır?

Tek bir Dockerfile içinde birden fazla `FROM` ifadesi kullanırsınız. Her `FROM` yeni bir aşama (stage) başlatır. Kritik nokta şudur: son aşamanın ürettiği katmanlar nihai imajı oluşturur; önceki aşamalar yalnızca ara üretim tesisi olarak kullanılır ve nihai imaja dahil edilmez. Aşamalar arasında yalnızca ihtiyaç duyduğunuz artefaktları `COPY --from=<aşama>` ile taşırsınız.

Bir Go örneği bunu net gösterir:

```dockerfile
# 1. AŞAMA: build ortamı (ağır)
FROM golang:1.22 AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /uygulama ./cmd/server

# 2. AŞAMA: çalışma ortamı (minimal)
FROM gcr.io/distroless/static-debian12
COPY --from=builder /uygulama /uygulama
USER 65534:65534
ENTRYPOINT ["/uygulama"]
```

Burada olan biten şudur: `builder` aşaması tüm Go toolchain'ini içerir ve binary'yi üretir. Nihai imaj ise neredeyse boş bir taban (distroless) üzerine yalnızca tek bir binary kopyalar. Sonuç, yüzlerce megabaytlık build ortamı yerine belki 10-20 megabaytlık bir üretim imajıdır. Toolchain, kaynak kod, ara dosyalar; hiçbiri nihai imaja sızmaz.

### İki Kat Fayda: Boyut ve Güvenlik

Multi-stage build'in değeri yalnızca boyut değildir, aynı zamanda saldırı yüzeyidir (attack surface). Nihai imajınızda compiler yoksa, shell yoksa, paket yöneticisi (package manager) yoksa, bir saldırgan konteynere sızsa bile elinde çok az araç kalır. İçinde `bash`, `curl`, `apt` bulunan bir imaj, saldırgana zengin bir alet çantası sunar; distroless bir imaj ise onu neredeyse kör bırakır. Az kod, az açık demektir; taşımadığınız yazılımın güvenlik açığı da olmaz.

Ek olarak, belirli bir ara aşamayı hedefleyerek de build yapabilirsiniz. Bu, test veya debug amaçlı ayrı aşamalar tanımlayıp yalnızca gerektiğinde onları build etmenizi sağlar; nihai üretim imajı bunlardan etkilenmez.

## En Az Yetki (Least Privilege) İlkesi

En az yetki ilkesi güvenlik dünyasının temel taşıdır: bir bileşene, görevini yerine getirmek için gereken minimum yetkiden fazlasını verme. Konteyner dünyasında bu ilke birkaç somut cephede karşımıza çıkar ve çoğu ihlal edilmeye çok müsaittir.

### Root Olarak Çalışmama

Bir Dockerfile'da `USER` talimatı belirtmezseniz, konteyner içindeki process varsayılan olarak root (UID 0) olarak çalışır. Bu, insanların hafife aldığı ciddi bir risktir. Konteyner içindeki root, tam anlamıyla host root'u değildir; namespace'ler ve yetenek (capability) kısıtlamaları araya girer. Ama yine de tehlikelidir çünkü:

Birincisi, konteynerden kaçış (container escape) sağlayan bir kernel açığı veya yanlış konfigürasyon durumunda, konteyner içindeki root, host üzerinde root'a dönüşebilir. İkincisi, çoğu gerçek dünya saldırısı kernel açığına bile ihtiyaç duymaz: yanlışlıkla host dizininin konteynere bağlanması (bind mount) gibi bir konfigürasyon hatası, konteyner root'una host dosyalarını değiştirme yetkisi verebilir. Uygulamanız bir web sunucusundan ibaretse, o process'in root olması için hiçbir meşru sebep yoktur.

Doğru yaklaşım, imajda root olmayan bir kullanıcı tanımlamak ve ona geçmektir:

```dockerfile
FROM python:3.12-slim
RUN groupadd --system uygulama && useradd --system --gid uygulama uygulama
WORKDIR /app
COPY --chown=uygulama:uygulama . .
RUN pip install --no-cache-dir -r requirements.txt
USER uygulama
CMD ["python", "server.py"]
```

Buradaki incelik şudur: root gerektiren işlemleri (paket kurulumu gibi) `USER` talimatından önce yapmalısınız, çünkü kullanıcıyı değiştirdikten sonraki komutlar artık o sınırlı kullanıcının yetkisiyle çalışır. Ayrıca dosyaların sahipliğini (`--chown`) doğru ayarlamazsanız, uygulama kendi dosyalarına yazamayıp izin (permission denied) hatası alabilir.

### Yetenekleri (Capabilities) Kısma

Linux, geleneksel "ya root ya değil" ikiliğini yetenekler (capabilities) ile parçalara böler. Örneğin `CAP_NET_BIND_SERVICE` 1024'ün altındaki portları dinleme yetkisidir, `CAP_SYS_ADMIN` ise neredeyse her şeyi yapabilen tehlikeli bir yetenektir. Docker, konteynerlere varsayılan olarak makul bir alt küme verir. En az yetki ilkesi burada şunu söyler: konteynere ihtiyacı olmayan tüm yetenekleri düşürün ve yalnızca gerekenleri geri ekleyin. Pratikte bu, tüm yetenekleri düşürüp (drop all) yalnızca uygulamanızın ihtiyaç duyduğu bir-iki tanesini eklemek şeklinde uygulanır. Böylece bir process ele geçirilse bile elindeki kernel yetkileri asgaride kalır.

### Salt Okunur Dosya Sistemi ve Diğer Sertleştirmeler

Uygulamanız çalışırken kök dosya sistemine yazmak zorunda değilse, konteyneri salt-okunur (read-only) çalıştırmak güçlü bir savunmadır. Bir saldırgan konteynere kötü amaçlı bir script yazamaz, mevcut binary'leri değiştiremez. Yazması gereken geçici alanları (örneğin `/tmp`) ayrı, sınırlı yazılabilir hacimler (volume) olarak verirsiniz. Benzer şekilde, yeni ayrıcalık kazanmayı engelleyen bir bayrak (no-new-privileges), `setuid` binary'leri aracılığıyla yetki yükseltmeyi (privilege escalation) engeller. Bu katmanlı savunmaların (defense in depth) her biri tek başına yeterli değildir; birlikte, bir saldırganın hareket alanını sistematik olarak daraltırlar.

## Yaygın Hatalar

Şimdiye kadar dağınık şekilde değindiğimiz tuzakları, en sık görülenleri toparlayarak bir arada verelim.

**Sırların (secrets) imaja gömülmesi.** Bir API anahtarını veya parolayı `ENV` ile ya da bir `COPY` ile imaja koymak ciddi bir hatadır. Katmanlar değişmez olduğu için, sonraki bir katmanda o değişkeni silseniz veya dosyayı kaldırsanız bile sır alt katmanın geçmişinde kalır; imaj geçmişini inceleyen herkes onu bulabilir. Sırlar çalışma zamanında (environment variable, secret yönetim aracı veya build-time secret mekanizmaları) enjekte edilmeli, asla imaj katmanına yazılmamalıdır.

**`latest` etiketine güvenmek.** `FROM node:latest` yazmak, bugün bir sürümü, altı ay sonra bambaşka bir sürümü çekebilir. Bu, tekrarlanabilirliği (reproducibility) yok eder ve "dün çalışan build bugün neden bozuldu" gizemlerine yol açar. Belirli bir sürüm etiketi, hatta mümkünse içeriğin değişmezliğini garanti eden bir digest (içerik hash'i) sabitleyin.

**Gereksiz büyük taban imajları.** `ubuntu` veya tam `node` imajıyla başlamak, yüzlerce megabaytlık gereksiz araç getirir. Çoğu durumda `-slim` varyantları, Alpine tabanlı imajlar veya distroless imajlar çok daha küçük ve güvenlidir. (Not: Alpine, `glibc` yerine `musl libc` kullanır; bazı uygulamalarda beklenmedik uyumluluk farklarına yol açabilir, bu yüzden körlemesine tercih edilmemelidir.)

**`.dockerignore` kullanmamak.** `COPY . .` yaparken `.dockerignore` dosyası yoksa, `.git` klasörü, `node_modules`, yerel `.env` dosyaları, log'lar ve build artefaktları da build bağlamına (context) ve potansiyel olarak imaja girer. Bu hem imajı şişirir hem de yerel sırların sızması gibi güvenlik riskleri doğurur. `.gitignore` gibi bir `.dockerignore` her ciddi projede olmalıdır.

**Konteyneri kalıcı veri deposu sanmak.** Konteynerin yazılabilir katmanı geçicidir (ephemeral); konteyner silindiğinde o veri de gider. Veritabanı dosyaları, yüklenen kullanıcı içerikleri gibi kalıcı olması gereken her şey, adlandırılmış hacimler (named volumes) veya bind mount'lar aracılığıyla konteyner yaşam döngüsünün dışında tutulmalıdır. Bu ilke, konteynerlerin "sığır değil, evcil hayvan" (cattle not pets) felsefesiyle, yani istendiğinde atılıp yeniden yaratılabilir olmasıyla doğrudan ilgilidir.

**Tek konteynerde çok fazla process.** Bir konteynerde hem web sunucusu hem veritabanı hem de cron çalıştırmaya kalkmak, konteynerin izolasyon ve ölçeklenebilirlik faydalarını yok eder. İlke olarak her konteyner tek bir sorumluluğa odaklanmalıdır; farklı bileşenler ayrı konteynerlerde çalışıp orkestrasyon katmanı (Docker Compose, Kubernetes) tarafından bir araya getirilmelidir.

## En İyi Pratikler (Toparlama)

Buraya kadar anlattıklarımızı, uygulanabilir bir kontrol listesine dönüştürelim. Her maddenin arkasında yukarıda açıkladığımız bir "neden" vardır.

**Katmanları değişim sıklığına göre sıralayın.** Bağımlılık manifestlerini kaynak koddan önce kopyalayın ki build cache'i mümkün olduğunca uzun sağlam kalsın.

**Multi-stage build'i varsayılan yapın.** Build araçlarını üretim imajından ayırın. Nihai imaja yalnızca çalıştırmak için kesinlikle gerekli artefaktları taşıyın. Bu hem boyutu hem saldırı yüzeyini birlikte küçültür.

**Root olmayan bir kullanıcı ile çalışın.** Açık bir `USER` talimatı ekleyin. root gerektiren adımları önce yapın, sonra kullanıcıyı düşürün. Dosya sahipliklerini doğru ayarlayın.

**Taban imajı küçük ve sabit tutun.** `slim`, Alpine veya distroless varyantlarını tercih edin; sürümleri belirli etiket veya digest ile sabitleyin; `latest`'e güvenmeyin.

**Katman içinde temizlik yapın.** Paket yöneticisi cache'lerini, indirilen arşivleri ve ara dosyaları oluşturuldukları `RUN` içinde, aynı katmanda temizleyin. Ayrı bir `RUN rm` katmanı boyutu düşürmez.

**`.dockerignore` yazın.** Build bağlamına girmemesi gereken her şeyi (versiyon kontrol klasörleri, bağımlılık dizinleri, yerel sırlar, log'lar) dışarıda bırakın.

**Sırları imaja koymayın.** Sırları çalışma zamanında veya güvenli build-time mekanizmalarıyla enjekte edin; asla `ENV` veya `COPY` yoluyla katmana yazmayın.

**Çalışma zamanı sertleştirmesi uygulayın.** Mümkünse salt-okunur kök dosya sistemi, gereksiz yeteneklerin düşürülmesi ve yetki yükseltmesini engelleyen bayraklarla katmanlı savunma kurun.

**Kalıcı veriyi hacimlere taşıyın.** Konteynerin geçici olduğunu kabul edin; kaybolmaması gereken her şeyi named volume veya bind mount ile dışarıda tutun.

**Her konteynere tek sorumluluk verin.** Bileşenleri ayırın; birleştirmeyi orkestrasyon katmanına bırakın.

## Sonuç

Docker'ın gerçek gücü, üç düşük seviyeli Linux mekanizmasını (namespaces, cgroups, union filesystem) herkesin kullanabileceği tutarlı bir modele dönüştürmesinde yatar. İmaj ve katman kavramı, bu union filesystem tasarımının doğrudan sonucudur ve build performansından imaj boyutuna kadar birçok pratik davranışı belirler. Katman sırasını neden dikkatli seçtiğinizi, silinen dosyaların neden boyutu düşürmediğini, multi-stage build'in neden hem küçük hem güvenli imajlar ürettiğini ve en az yetki ilkesinin her cephede neden önemli olduğunu bir kez kavradığınızda, Dockerfile yazmak ezberlenmiş kalıplar dizisi olmaktan çıkıp bilinçli mühendislik kararlarına dönüşür. İyi bir konteyner imajı; küçük, tekrarlanabilir, en az yetkiyle çalışan ve yalnızca işini yapmak için gereken şeyi içeren imajdır. Geri kalan her şey gereksiz ağırlık ve gereksiz risktir.
