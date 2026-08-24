# Ağ Zaman Senkronizasyonu ve Saldırıları (NTP/PTP)

## Giriş ve Neden Kritik

Ağa bağlı sistemlerin ortak, tutarlı bir zaman algısına sahip olması modern altyapının görünmez ama taşıyıcı bir sütunudur. Log korelasyonu, dağıtık işlem sıralaması, sertifika geçerlilik kontrolü, kimlik doğrulama protokolleri (Kerberos, TOTP), finansal işlem damgalama ve endüstriyel kontrol sistemlerinin faz senkronizasyonu — hepsi doğru zamana bağımlıdır. Zaman "yalnızca bir sayı" değildir; birçok güvenlik kararının sessiz girdisidir.

Bu nedenle zaman senkronizasyon protokolleri (**NTP** — Network Time Protocol ve **PTP** — Precision Time Protocol) hem operasyonel açıdan kritik hem de saldırı yüzeyi açısından sinsi bir hedeftir. Bir saldırgan zamanı manipüle edebilirse, doğrudan bir sistemi çökertmeden başka güvenlik mekanizmalarını dolaylı olarak devre dışı bırakabilir: süresi dolmuş bir sertifikayı geçerli gösterebilir, bir Kerberos bileti penceresini kaydırabilir, log zaman damgalarını bozarak adli analizi zehirleyebilir. Ayrıca NTP'nin bazı sürümleri klasik **amplifikasyon DDoS** silahına dönüşmüştür.

Bu makale protokollerin çalışma mantığını, saldırı sınıflarını ve — asıl amacımız — bunları nasıl tespit ve savunma altına alacağımızı ele alır.

## NTP'nin Çalışma Mantığı

### Temel Model

NTP, hiyerarşik bir **stratum** modeli kullanır. Stratum 0, referans saatlerdir (atomik saat, GPS alıcısı). Stratum 1 sunucular bu referanslara doğrudan bağlıdır. Stratum 2 sunucular Stratum 1'den zaman alır ve bu böyle devam eder — her katman bir üsttekinden senkronize olur. Stratum sayısı arttıkça referanstan uzaklık ve dolayısıyla belirsizlik artar.

NTP tipik olarak **UDP port 123** üzerinde çalışır. Bağlantısız (connectionless) olması hem hafifliğinin hem de saldırıya açıklığının kaynağıdır: UDP'de kaynak IP kolayca sahtelenebilir (spoofing), üç yönlü el sıkışma (handshake) yoktur.

### Saat Ofset Hesabı

NTP'nin kalbinde, sunucu ve istemci arasındaki **saat ofsetini** ve **gidiş-dönüş gecikmesini** (round-trip delay) hesaplayan zarif bir dört zaman damgası mekanizması vardır. İstemci bir istek gönderir ve dört zaman noktası kaydedilir:

- **T1**: İstemcinin isteği gönderdiği an (istemci saati)
- **T2**: Sunucunun isteği aldığı an (sunucu saati)
- **T3**: Sunucunun yanıtı gönderdiği an (sunucu saati)
- **T4**: İstemcinin yanıtı aldığı an (istemci saati)

Ofset yaklaşık olarak `((T2 - T1) + (T3 - T4)) / 2`, gecikme ise `(T4 - T1) - (T3 - T2)` formülüyle bulunur. Bu simetri varsayımı kritiktir: hesap, gidiş ve dönüş yollarının **eşit gecikmeye** sahip olduğunu varsayar. İşte birçok saldırının kök nedeni tam olarak bu varsayımı kırmaktır — yolun bir yönünü asimetrik biçimde geciktiren bir saldırgan, hiçbir paketi değiştirmeden ofset hesabını çarpıtabilir.

## PTP'nin Çalışma Mantığı ve NTP'den Farkı

**PTP (IEEE 1588)**, NTP'ye göre çok daha yüksek hassasiyet hedefler — mikrosaniye, hatta donanım destekli ortamlarda nanosaniye seviyesi. Telekom, finansal ticaret (MiFID II gibi düzenlemeler damgalama hassasiyeti şart koşar), elektrik şebekesi ve endüstriyel otomasyonda tercih edilir.

PTP'nin ayırt edici mekanizmaları:

- **Grandmaster clock**: PTP alanındaki en iyi referans saat. **BMCA (Best Master Clock Algorithm)** ile alandaki cihazlar hangi saatin master olacağını dinamik olarak seçer.
- **Donanım zaman damgalama**: Paketin ağ arayüzünden çıktığı/girdiği fiziksel an, yazılım katmanındaki kuyruk gecikmelerinden bağımsız olarak kaydedilir. Bu, işletim sistemi jitter'ını devre dışı bırakarak hassasiyeti dramatik artırır.
- **Transparent clock / Boundary clock**: Ağdaki switch'ler paketin içlerinde geçirdiği bekleme süresini (residence time) ölçüp düzeltmeye katkı verir, böylece switch gecikmesi hataya dönüşmez.

PTP genellikle yerel ağ (LAN) içinde, kontrollü bir alanda çalışır. Bu onu internet ölçekli amplifikasyon saldırılarından korur ama **iç tehdide** ve BMCA manipülasyonuna açık bırakır: alana sahte bir "daha iyi grandmaster" tanıtan bir saldırgan, tüm alanın zamanını ele geçirebilir (rogue master saldırısı).

## Saldırı Sınıfları

### 1. NTP Amplifikasyon DDoS

Bu, en yaygın ve tarihsel olarak en yıkıcı NTP kötüye kullanımıdır. Kök neden, bazı eski NTP sunucularında bulunan **monitoring/yönetim komutlarıdır** (klasik örnek `monlist`, sonraki mimarilerde `ntpdc`/`mode 7` sorguları). Bu komut, sunucuya son bağlanan çok sayıda istemcinin listesini döndürür.

Mekanizma şudur:

1. Saldırgan, kaynak IP'yi kurbanın adresi olacak şekilde **sahteler** (UDP olduğu için mümkün).
2. Çok küçük bir sorgu paketi (birkaç yüz bayt) açık, savunmasız bir NTP sunucusuna gönderilir.
3. Sunucu, çok büyük bir yanıtı **kurbana** gönderir.

Buradaki **amplifikasyon faktörü** oldukça yüksektir — küçük istek, kat kat büyük yanıt üretir. Saldırgan birçok savunmasız sunucuyu aynı anda kullanarak kurbanın bağlantısını doldurur. 2013-2014 döneminde bu teknik rekor kıran hacimlerde DDoS saldırılarına yol açtı.

**Kök neden özeti**: bağlantısız UDP + kaynak doğrulaması yokluğu + istek/yanıt boyut asimetrisi.

### 2. NTP Spoofing ve Man-in-the-Middle Zaman Kayması

Saldırgan istemci ile meşru NTP sunucusu arasına girip (on-path) veya UDP'nin kimlik doğrulamasızlığından faydalanıp (off-path, sahte yanıt yarıştırma) **kasıtlı yanlış zaman** enjekte edebilir. Klasikleşmiş NTP güvenlik araştırmaları (Malhotra ve ark.) birkaç önemli vektör göstermiştir:

- **Kademeli sürükleme (time shifting)**: Küçük ofsetlerle zamanı yavaşça kaydırmak. `ntpd` büyük ani sıçramaları reddedebilir (panic threshold), ama küçük artışlarla saati aylar-yıllar boyu geriye/ileriye sürüklemek mümkün olabilir. Yavaşlık, tespiti zorlaştırır.
- **Kickoff / yeniden başlatma anını hedefleme**: İstemci yeni başladığında büyük ofsetleri kabul etme eğilimindedir; saldırgan bu pencereyi kollar.
- **Asimetrik gecikme enjeksiyonu**: Yukarıda anlattığımız simetri varsayımını kırmak. Paketi değiştirmeden, sadece bir yönü geciktirerek ofset hesabını yanlışlatmak. Kimlik doğrulama bunu tek başına engellemez, çünkü paket içeriği bozulmamıştır.

### 3. Zaman Kaymasının Güvenlik Sonuçları

Zamanı manipüle etmek başlı başına amaç değildir; asıl tehlike **bağımlı güvenlik mekanizmalarını** çökertmesidir:

- **TLS/X.509 sertifika geçerliliği**: Sertifikalar `notBefore`/`notAfter` zaman aralığına bağlıdır. İstemcinin saatini ileri sürüklerseniz süresi dolmuş (veya iptal edilmiş, çünkü CRL/OCSP geçerlilik zamanı da kayar) bir sertifika hâlâ geçerli görünebilir. Geriye sürüklerseniz henüz geçerli olmayan sertifikalar sorun çıkarabilir veya saldırgan eski, çalınmış bir sertifikayı yeniden kullanabilir.
- **Kerberos**: Kerberos, replay saldırılarına karşı sıkı bir **saat toleransı** (varsayılan tipik olarak 5 dakika) kullanır. İstemci saati bu pencereyi aşarsa kimlik doğrulama başarısız olur (hizmet reddi) — ya da ters yönde, saldırgan zamanı manipüle ederek eski bir bilet/authenticator'ı geçerli pencereye taşıyabilir ve replay penceresini kötüye kullanabilir.
- **TOTP / iki faktörlü kodlar**: Zaman tabanlı tek kullanımlık şifreler zaman dilimine bağlıdır; kaymış saat kodları geçersizleştirir veya eski kodları geçerli kılabilir.
- **DNSSEC**: İmza geçerlilik pencereleri zamana bağlıdır; büyük zaman kayması doğrulamayı bozar.
- **Log ve adli analiz**: Zaman damgaları bozulursa olay korelasyonu ve kanıt zinciri güvenilmez hâle gelir. Saldırgan izlerini zamansal olarak "kaydırarak" gizleyebilir.
- **Önbellek/token yaşam süresi**: Session token'ları, JWT `exp` alanları, önbellek TTL'leri zamanla değerlendirilir; manipülasyon süresi dolmuş oturumları canlandırabilir.

### 4. PTP'ye Özgü Saldırılar

PTP genelde iç ağda olduğu için tehdit modeli farklıdır:

- **Rogue master / BMCA manipülasyonu**: Sahte bir grandmaster, kendini en iyi saat gibi tanıtarak alanın kontrolünü ele geçirir.
- **Delay attack**: PTP'nin gecikme ölçüm mesajlarını (delay request/response) seçici geciktirerek offset hesabını kaydırmak. Yine simetri varsayımının kırılması.
- **Announce spoofing**: BMCA'nın dayandığı Announce mesajlarının sahtelenmesi.

## Doğru Kullanım ve Savunma

### Amplifikasyona Karşı

- **Yönetim/monitoring komutlarını kapatın**: `monlist` gibi büyük yanıt üreten sorguları devre dışı bırakın. Modern `ntpd` sürümleri bunu varsayılan kapatmıştır, ama eski sürümleri güncelleyin veya konfigürasyonda `noquery`/`restrict` ile kısıtlayın. Alternatif olarak monitoring gerektirmeyen daha küçük bir daemon (`chrony`, `openntpd`) tercih edin.
- **BCP 38 / kaynak adres doğrulaması (ingress filtering)**: Sahtelenmiş kaynak IP'li paketlerin ağınızdan çıkmasını (ve girmesini) engelleyin. Amplifikasyon saldırısının temel önkoşulu spoofing'dir; onu kesmek saldırıyı kökeninden zayıflatır.
- **Rate limiting**: NTP yanıtlarına oran sınırı (`limited`, `kod` — Kiss-o'-Death) uygulayın.
- **Gereksiz açık NTP sunucusu bırakmayın**: İnternete açık bir NTP hizmeti sağlamıyorsanız port 123'ü dışarıya kapatın.

### Spoofing ve Zaman Kaymasına Karşı

- **Birden çok bağımsız zaman kaynağı kullanın**: Tek bir sunucuya güvenmek tek nokta manipülasyonuna açar. NTP'nin **istatistiksel filtreleme ve seçim algoritmaları** (falseticker eleme, marjinal saatlerin dışlanması) tam da bunun içindir — dört veya daha fazla bağımsız kaynak vererek bir manipüle edilmiş kaynağın çoğunluk tarafından "yalancı" (falseticker) olarak elenmesini sağlarsınız.
- **Kimliği doğrulanmış zaman**: NTP'nin **NTS (Network Time Security, RFC 8915)** uzantısı, TLS tabanlı anahtar kurulumu ile zaman paketlerinin kimliğini ve bütünlüğünü doğrular. Eski `autokey` mekanizmasının zayıflıkları vardı; mümkün olan yerde **NTS** tercih edin. Kimlik doğrulama, içerik değiştirme ve off-path spoofing'i büyük ölçüde engeller (ama saf asimetrik gecikme saldırısını tam çözmez).
- **Panic/step eşiklerini bilinçli ayarlayın**: `ntpd` büyük ani ofsetlerde durur (panic threshold, tipik varsayılan büyük sıçramalar için ~1000 saniye). Bu eşiği gevşetmek saldırıyı kolaylaştırır; sıkı tutun. `-g` gibi başlangıçta büyük düzeltmeye izin veren bayrakların ne zaman devreye girdiğini anlayın.
- **Maksimum kabul edilebilir sürüklenme sınırlaması**: `chrony` gibi araçlarda `maxchange`, `makestep` ile büyük veya beklenmedik değişiklikleri reddedebilir veya loglayabilirsiniz.

### PTP Savunması

- **PTP alanını izole edin**: PTP LAN'ını segmentleyin, yetkisiz cihazların Announce mesajı basmasını engelleyin (switch port güvenliği, VLAN ayrımı).
- **IEEE 1588 güvenlik uzantıları / MACsec**: Katman-2 kimlik doğrulama ile sahte master ve mesaj enjeksiyonunu zorlaştırın.
- **Grandmaster beyaz listesi**: Yalnızca bilinen, yetkili saatlerin master olabilmesini konfigüre edin.

### Tespit (Detection)

Savunmanın çoğu, zaman manipülasyonunu **görebilmekle** başlar:

- **Bağımsız bir referans saatle karşılaştırma**: Yerel bir GPS/atomik referans veya dışarıdan bağımsız kaynaklarla sistem saatini periyodik kıyaslayın. Beklenmedik sapma alarm üretmeli.
- **Ofset/jitter metriklerini izleyin**: `ntpq -p`, `chronyc tracking`/`sources` çıktısındaki offset, jitter, delay ve reach değerlerini metrik olarak toplayın (Prometheus vb.). Ani offset sıçraması, bir kaynağın falseticker işaretlenmesi veya beklenmedik stratum değişimi şüphelidir.
- **Kaynak tutarlılığı**: Yapılandırdığınız peer'ların gerçekten beklenen sunucular olup olmadığını, stratum ve referans ID'lerinin değişip değişmediğini izleyin.
- **Adli çapraz kontrol**: Log zaman damgalarını harici, güvenilir bir zaman kaynağıyla çapraz doğrulayın; tutarsızlık manipülasyon işareti olabilir.
- **DDoS tarafında**: Port 123'te ani giden yanıt hacmi artışı, tek boyutlu büyük yanıt paketleri, tanınmayan kaynaklardan gelen monitoring sorguları amplifikasyon kötüye kullanımının işaretidir.

## Yaygın Hatalar ve Tuzaklar

- **Tek NTP kaynağına güvenmek**: NTP'nin yalancı-eleme algoritması ancak yeterli (tipik olarak en az 3-4) bağımsız kaynakla çalışır. Tek kaynak = tek nokta manipülasyon.
- **Panic eşiğini keyfi gevşetmek**: "Saatim çok kaymıştı, senkron olmadı" diye `panic 0` ayarlamak, saldırgana istediği kadar sürükleme kapısı açar. Kök neden (donanım saati, virtualizasyon zaman kayması) araştırılmalıdır.
- **Kimlik doğrulamayı ihmal etmek**: Düz NTP internetten kimlik doğrulamasız zaman almak, off-path/on-path spoofing'e açıktır. Kritik sistemlerde NTS veya izole güvenilir kaynak şart.
- **Eski `ntpd` sürümlerini güncellememek**: `monlist` gibi tarihsel açıkların ve çeşitli CVE'lerin çoğu güncellenmiş sürümlerde kapatılmıştır. Sürümü güncel tutmak en ucuz savunmadır.
- **Sanallaştırma zaman kaymasını gözden kaçırmak**: VM'lerde host saati ve konuk saati arasında doğal sürüklenme olur; bunu bir "saldırı" ile karıştırmamak ama aynı zamanda bir saldırıyı "sadece VM sürüklenmesi" diye normalleştirmemek gerekir. Uygun sanal ortam zaman entegrasyonu (host senkronizasyonu) kullanın.
- **Kimlik doğrulamanın asimetrik gecikme saldırısını çözdüğünü sanmak**: NTS içerik bütünlüğünü korur ama saldırgan sadece bir yönü geciktirdiğinde paket geçerli kalır; savunma için çoklu yol/çoklu kaynak ve gecikme anomali izleme gerekir.
- **PTP'yi "iç ağda, güvenli" varsaymak**: İç tehdit ve yanlış yapılandırılmış cihazlar rogue master'a yol açabilir; segmentasyon ve kimlik doğrulama ihmal edilmemeli.

## Özet

Zaman senkronizasyonu, güvenlik zincirinin sessiz ama taşıyıcı bir halkasıdır. NTP ve PTP, doğru zaman dağıtmak için zarif ofset/gecikme hesaplarına dayanır; ancak bu hesapların **simetri varsayımı** ve UDP'nin **kimlik doğrulamasızlığı** iki temel kök zayıflıktır. Saldırılar iki ana eksende toplanır: NTP'yi bir **amplifikasyon silahına** çevirmek (DDoS) ve zamanı manipüle ederek **bağımlı güvenlik mekanizmalarını** (TLS, Kerberos, TOTP, DNSSEC, loglar) dolaylı olarak devre dışı bırakmak.

Savunma çok katmanlıdır: monitoring komutlarını kapatmak ve kaynak filtreleme ile amplifikasyonu kesmek; çoklu bağımsız kaynak, NTS kimlik doğrulaması ve sıkı panic eşikleriyle spoofing'i zorlaştırmak; PTP alanını izole edip grandmaster'ı beyaz listelemek; ve her şeyin üstünde, bağımsız bir referansla **sapmayı sürekli izleyerek** manipülasyonu görünür kılmaktır. Zamanı bir güvenlik varlığı olarak görmek, birçok görünmez saldırıyı önceden kapatır.
