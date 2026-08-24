# Sanal Bellek ve Paging

## Giriş: Sanal Bellek Neyi Çözer?

Sanal bellek (virtual memory), modern işletim sistemlerinin en temel soyutlamalarından biridir ve genellikle "gözden ırak, gönülden ırak" bir mekanizmadır: doğru çalıştığında hiç fark etmezsiniz. İşin özü şudur: çalışan her process (süreç), sanki makinedeki tüm belleğe tek başına ve kesintisiz sahipmiş gibi bir adres uzayına (address space) yazar ve okur. Oysa gerçekte fiziksel RAM sınırlıdır, birçok process onu paylaşır ve çoğu zaman toplam talep edilen bellek fiziksel RAM'den büyüktür. Sanal bellek bu yanılsamayı üretir.

Bu yanılsamanın çözdüğü üç temel problem vardır. Birincisi **soyutlama**: programcı fiziksel adreslerin nerede oturduğunu düşünmez, her program 0 adresinden başlayan kendi düz adres uzayında yaşar. İkincisi **izolasyon**: bir process başka bir process'in belleğine — hatta çekirdeğin belleğine — kazara ya da kasıtlı olarak dokunamaz. Üçüncüsü **fazladan kapasite**: RAM'e sığmayan sayfalar diske taşınabildiği için sistem, fiziksel bellekten daha büyük çalışma kümelerini idare edebilir.

Bu makalede kavramı temelinden inşa edeceğiz: adres uzayı, sayfa (page) ve çerçeve (frame), MMU ve sayfa tablosu (page table), page fault mekaniği, swap, ve tüm bunların üzerinden geçen performans tuzakları ile en iyi pratikler.

## Adres Uzayı: Sanal ile Fizikselin Ayrılması

### Tanım

Bir process'in **sanal adres uzayı**, o process'in kullanabileceği tüm sanal adreslerin kümesidir. 64-bit bir sistemde teorik olarak 2^64 adres vardır, ancak pratikte donanım bu adres genişliğinin tamamını çözmez; yaygın x86-64 uygulamalarında adresin alt 48 biti (bazı yeni işlemcilerde 57 bit) anlamlıdır. Bu, tek bir process için bile devasa — terabaytlarca — bir sanal alan demektir. Fiziksel adres uzayı ise makineye takılı gerçek RAM ile sınırlıdır; 16 GB RAM'iniz varsa fiziksel adresler yaklaşık 34 bitlik bir aralığa sığar.

Kritik nokta şudur: **sanal adres ile fiziksel adres birbirinden bağımsızdır.** İki farklı process aynı sanal adresi (örneğin `0x400000`) kullanabilir; bu adresler bambaşka fiziksel konumlara eşlenir (map edilir). İşte izolasyon buradan doğar.

### Adres Uzayının Yapısı

Tipik bir process adres uzayı, aşağıdan yukarıya doğru kabaca şu bölgelere ayrılır:

- **Text (kod) segmenti**: makine talimatları. Genellikle salt-okunur ve execute izinli.
- **Data / BSS**: başlatılmış ve başlatılmamış global değişkenler.
- **Heap**: `malloc`/`new` ile dinamik büyüyen alan; yukarı doğru genişler.
- **Memory-mapped bölgeler**: paylaşımlı kütüphaneler (shared libraries) ve `mmap` ile eşlenmiş dosyalar.
- **Stack**: fonksiyon çağrı çerçeveleri; genellikle aşağı doğru büyür.

Heap ve stack'in zıt yönlerde büyümesi tesadüf değildir: ortadaki büyük boş sanal alan, ikisinin de birbirine çarpmadan genişleyebilmesi için tampon sağlar. Bu boşluğun büyük kısmı hiçbir zaman fiziksel belleğe dokunmaz; sadece "ayrılmış ama henüz gerçeklenmemiş" haldedir. Bu, sanal belleğin en önemli tembelliklerinden (lazy allocation) biridir ve birazdan page fault'ta buna döneceğiz.

## Sayfa ve Çerçeve: Neden Sabit Boyutlu Bloklar?

### Tanım

Sanal adres uzayı, sabit boyutlu bloklara — **sayfalara (page)** — bölünür. Fiziksel bellek de aynı boyutta bloklara — **çerçevelere (frame)** — bölünür. Yaygın sayfa boyutu 4 KB'dir; ayrıca **huge page** olarak 2 MB ve 1 GB gibi büyük boyutlar da desteklenir. Eşleme (mapping) sayfa granülaritesinde yapılır: bir sanal sayfa, herhangi bir fiziksel çerçeveye oturtulabilir.

### Kök Neden: Neden Sayfalama, Segmentasyon Değil?

Belleği neden eşit boyutlu bloklara bölüyoruz? Alternatif, değişken boyutlu bölgeler (segmentasyon) atamaktır, ama bu **external fragmentation** yaratır: bellekte toplamda yeterli boş yer olduğu halde, boşluklar dağınık ve küçük olduğu için büyük bir talebi karşılayamazsınız. Sabit boyutlu sayfalar bu problemi kökten çözer — her boş çerçeve her sayfa için kullanılabilir olduğundan yerleştirme sorunu ortadan kalkar. Bedeli **internal fragmentation**'dır: bir process 4 KB + 1 bayt istediğinde iki tam sayfa (8 KB) tahsis edilir ve son sayfanın büyük kısmı boşa gider. Pratikte bu israf, external fragmentation'ın getirdiği baş ağrısından çok daha yönetilebilirdir.

### Adres Çevirisinin Mekaniği

Bir sanal adres iki parçaya ayrılır: **sayfa numarası** (üst bitler) ve **sayfa içi offset** (alt bitler). 4 KB sayfada offset 12 bittir (çünkü 2^12 = 4096). Çeviri şöyle işler: sayfa numarası, sayfa tablosunda (page table) ilgili fiziksel çerçeve numarasına çevrilir; offset ise değişmeden aktarılır. Yani offset'in çeviriye ihtiyacı yoktur — sadece sayfa numarası eşlenir. Bu, çevirinin neden bu kadar hızlı olabildiğinin ve neden sabit sayfa boyutunun hesabı basitleştirdiğinin özüdür.

## MMU ve Sayfa Tablosu: Çeviri Nerede ve Nasıl Yapılır?

### MMU'nun Rolü

**MMU (Memory Management Unit)**, CPU içinde yer alan bir donanım birimidir. Her bellek erişiminde — her talimat getirmede, her yükleme/saklamada — MMU sanal adresi fiziksel adrese çevirir. Bu çevirinin donanımda yapılması zorunludur, çünkü her komut için gerçekleşir; yazılımda yapılsaydı sistem kabul edilemez ölçüde yavaşlardı. İşletim sistemi ise politikayı belirler (hangi sayfa nereye eşlenecek, izinler ne olacak); MMU sadece bu politikayı hızla uygular.

### Sayfa Tablosu ve Çok Seviyeli Yapı

Çeviri bilgisi **sayfa tablosunda** tutulur. Naif bir tasarımda her olası sayfa için bir giriş (page table entry, PTE) olurdu; ancak 48-bit adres uzayı ve 4 KB sayfa ile bu, düz bir tabloda astronomik sayıda giriş demektir ve process başına bu kadar bellek ayrılması imkânsızdır. Çözüm **çok seviyeli sayfa tablosu**dur (multi-level page table): x86-64'te tipik olarak dört seviye kullanılır. Adres, her seviyede tablonun bir sonraki seviyesine indeks olan bit gruplarına bölünür. Bu ağaç yapısının güzelliği, **sadece gerçekten kullanılan dallar bellekte var olur**; adres uzayının büyük boş bölgeleri için hiçbir alt tablo tahsis edilmez. Böylece seyrek (sparse) adres uzayları ucuza temsil edilir.

Her PTE, çerçeve numarasının yanı sıra kontrol bitleri taşır: geçerlilik (present/valid), yazma izni, kullanıcı/çekirdek izni, erişildi (accessed) ve değiştirildi (dirty) bitleri. Bu bitler hem korumayı hem de birazdan göreceğimiz sayfa değiştirme politikalarını mümkün kılar.

### TLB: Çevirinin Önbelleği

Çok seviyeli tablo, tek bir çeviri için birden fazla bellek erişimi (her seviye için bir okuma) gerektirir. Her gerçek erişimden önce dört ek bellek okuması yapmak felaket olurdu. Bu yüzden MMU, **TLB (Translation Lookaside Buffer)** adında küçük ve çok hızlı bir önbellek tutar. TLB, son kullanılan sanal-sayfa → fiziksel-çerçeve eşlemelerini saklar. Erişim örüntüleri lokal olduğundan (bir program aynı sayfalara tekrar tekrar dokunur), TLB isabet oranı pratikte çok yüksektir ve çevirilerin ezici çoğunluğu tek bir hızlı adımda çözülür.

TLB'nin bir maliyeti vardır: process değiştiğinde (context switch) eski eşlemeler artık geçersizdir. Klasik çözüm TLB'yi boşaltmaktır (flush), ama bu her switch sonrası bir ısınma cezası getirir. Modern işlemciler bunu **ASID / PCID** (adres uzayı tanımlayıcıları) ile hafifletir: TLB girişleri process kimliğiyle etiketlenir, böylece flush gereksiz kalır ve farklı process'lerin girişleri TLB'de bir arada yaşayabilir.

## Page Fault: Eksik Sayfa Kesintisi

### Tanım ve Çalışma Mantığı

**Page fault**, bir process bir sanal adrese eriştiğinde ve o adrese karşılık gelen sayfa şu an fiziksel bellekte hazır değilken (PTE'de present biti kapalıyken) MMU'nun tetiklediği bir donanım kesmesidir (exception). Kesme işletim sisteminin page fault handler'ına dallanır; çekirdek durumu çözer ve — çözülebiliyorsa — hatalı komutu yeniden çalıştırır. Kullanıcı programı çoğu zaman bunun olduğunu hiç fark etmez; sadece o erişim biraz daha uzun sürer.

Page fault'ların hepsi "hata" değildir; aslında çoğu tamamen normal işleyişin parçasıdır. Türlerini ayırmak kritiktir:

- **Minor (soft) fault**: sayfa aslında RAM'de mevcuttur ama bu process'in sayfa tablosunda henüz kurulu değildir. Örneğin bir paylaşımlı kütüphane zaten başka process için bellekteyken bu process ilk kez erişir; çekirdek sadece PTE'yi kurar. Disk erişimi yoktur, çok ucuzdur.
- **Major (hard) fault**: sayfanın içeriği diskte — ya swap alanında ya da eşlenmiş bir dosyada — durur ve RAM'e getirilmesi gerekir. Bu bir disk I/O'su içerir; SSD'de bile RAM'e göre kat kat yavaştır, dönen diskte felakettir.
- **Invalid fault**: process gerçekten hiç eşlenmemiş ya da izni olmayan bir adrese dokunur. Bu gerçek bir hatadır; sonucu genellikle Linux'ta SIGSEGV (segmentation fault) sinyali, yani programın çökmesidir.

### Kök Neden: Tembellik Bir Özelliktir

Page fault mekanizması, sanal belleğin tembel davranmasını mümkün kılan motordur ve bu tembellik kasıtlı bir tasarım tercihidir. Birkaç güçlü örneği:

**Demand paging (talep üzerine sayfalama):** Bir program başlatıldığında çalıştırılabilir dosyanın tamamı RAM'e yüklenmez. Sadece PTE'ler "diskte, henüz getirilmedi" olarak işaretlenir. Program çalışırken hangi sayfaya dokunursa o sayfa major fault ile getirilir. Böylece bir programın hiç çalıştırılmayan kod yolları belleğe hiç girmez; başlatma hem hızlı hem tasarrufludur.

**Lazy allocation:** `malloc` büyük bir blok döndürdüğünde çekirdek genellikle sadece adres aralığını ayırır, fiziksel çerçeve vermez. İlk yazma anında minor fault tetiklenir ve o an sıfırlanmış bir çerçeve bağlanır. Programın istediği ama hiç dokunmadığı bellek asla fiziksel RAM tüketmez. "malloc başarılı oldu ama gerçek RAM yok" durumu buradan doğar ve overcommit ile birleşince ilerideki tuzaklara zemin hazırlar.

**Copy-on-write (COW):** `fork` ile bir process kopyalandığında bellek fiziksel olarak kopyalanmaz. Ebeveyn ve çocuk aynı fiziksel çerçeveleri paylaşır, ancak tüm bu sayfalar salt-okunur işaretlenir. Taraflardan biri yazmaya kalkışınca yazma-koruması fault'u oluşur; çekirdek o an sadece o sayfayı kopyalar ve yazana özel kılar. Böylece hiç değiştirilmeyen sayfalar sonsuza dek paylaşılabilir. Bu, `fork` sonrası hemen `exec` çağıran kabuk gibi kalıpları neredeyse bedava yapar.

## Swap: RAM Bittiğinde Ne Olur?

### Tanım

**Swap**, fiziksel RAM'e sığmayan sayfaların geçici olarak diske (özel bir swap partisyonu ya da swap dosyası) taşınması işlemidir. Amaç, aktif çalışma kümesi RAM'i aşınca sistemin çökmek yerine yavaşça devam edebilmesidir. Sayfa diske yazılıp RAM'den çıkarıldığında (page-out) çerçevesi boşalır ve başka bir sayfa için kullanılabilir; o sayfaya yeniden erişilince major fault ile geri getirilir (page-in).

### Çalışma Mantığı ve Değiştirme Politikası

RAM dolduğunda çekirdek, çıkarmak (evict) için bir "kurban" sayfa seçmek zorundadır. İdeal politika, "gelecekte en uzun süre dokunulmayacak sayfayı çıkar" olurdu — ama gelecek bilinemez. Bu yüzden gerçek sistemler geçmişi geleceğin habercisi kabul eden yaklaşımlara başvurur; **LRU (Least Recently Used)** yaklaşımının pratik varyantları hakimdir. Gerçek LRU her erişimde güncelleme gerektirdiğinden pahalıdır; bunun yerine PTE'deki **accessed biti** periyodik taranarak "yakın zamanda kullanıldı mı" bilgisi ucuza toplanır (clock / second-chance algoritmaları). 

Burada **dirty bit** devreye girer: eğer çıkarılacak sayfa değiştirilmemişse (temiz) ve zaten diskte bir kaynağı varsa (örneğin dosyadan eşlenmiş kod), diske yazmaya gerek yoktur — çerçeve doğrudan geri alınabilir, geri gerektiğinde kaynağından yeniden okunur. Sayfa değiştirilmişse (dirty) önce diske yazılmalıdır. Bu ayrım, temiz sayfaların çıkarılmasını neden ucuz, kirli sayfalarınkini pahalı yaptığını açıklar.

### Thrashing: En Tehlikeli Durum

Swap'in kötüye gittiği hal **thrashing**tir. Aktif çalışma kümesi (working set) fiziksel RAM'den büyük olduğunda sistem sürekli sayfa çıkarıp geri getirir; her page-in başka bir sayfayı hemen tekrar gereken bir çerçeveden atar. Sonuç, CPU'nun çoğu zamanı disk I/O beklerken geçirmesi ve gerçek iş yapımının çökmesidir. Belirtisi tanıdıktır: disk sürekli çalışır, sistem yanıt vermez hale gelir ama CPU kullanımı düşüktür çünkü herkes disk bekliyordur. Thrashing, "swap açık olduğu için yavaşlıyoruz" değil, "çalışma kümemiz RAM'e sığmıyor" demektir; çözüm swap'i kapatmak değil, ya RAM eklemek ya bellek talebini azaltmaktır.

## Doğru Kullanım, Yaygın Hatalar ve Tuzaklar

### Overcommit ve OOM Killer

Linux varsayılan olarak belleği **overcommit** eder: process'lere fiziksel olarak var olandan daha fazla sanal bellek sözü verir, çünkü çoğu process istediği belleğin tamamına asla dokunmaz (lazy allocation'ı hatırlayın). Bu genellikle iyi çalışır, ama tehlikelidir: process'ler verilen sözü fiilen tahsile başlarsa ve gerçek RAM + swap tükenirse, çekirdek bir çıkış yolu olarak **OOM (Out Of Memory) killer**'ı devreye sokar ve bir process'i öldürür. Buradaki klasik hata, `malloc`'un başarılı dönmesini "bu bellek benimdir, garantidir" sanmaktır. Gerçekte garanti, o sayfaya ilk dokunduğunuz anda verilir — ve o an RAM yoksa bir process ölür. Uzun ömürlü sunucularda kritik process'lerin OOM davranışını bilinçli ayarlamak (skorunu düşürmek) önemli bir pratiktir.

### mmap ve Dosya Eşleme

`mmap` ile bir dosyayı doğrudan adres uzayına eşlemek güçlü bir tekniktir: dosya içeriğine bellek gibi erişirsiniz, çekirdek sayfaları talep üzerine getirir ve sayfa önbelleğini (page cache) paylaşır. Ancak tuzakları vardır. Eşlenmiş bir bölgeye erişirken dosya kısalırsa (truncate) ya da eşlemenin ötesine dokunursanız, beklenmedik bir sinyal (SIGBUS) alırsınız — bu bir dizin taşmasından farklı, sinsi bir hata biçimidir. Ayrıca büyük dosyaları rastgele erişimle eşlemek, dağınık major fault yağmuruna yol açarak sıralı okumadan yavaş olabilir; erişim örüntüsünü çekirdeğe bildirmek (madvise ile sıralı/rastgele ipucu vermek) bu durumda ölçülebilir fark yaratır.

### Performans Tuzakları

**TLB baskısı ve huge page.** Bellek-yoğun uygulamalar (büyük veritabanları, in-memory analitik) çok sayıda sayfaya dokunur ve TLB kapasitesi aşılınca çeviri maliyeti (sayfa tablosu yürüyüşü) belirginleşir. Huge page kullanmak, tek bir TLB girişinin çok daha büyük bir alanı kapsamasını sağlayarak bu maliyeti düşürür. Ancak huge page'ler daha kaba granülaritede çalışır; küçük ve seyrek erişimlerde iç fragmentasyonu ve bellek israfını artırabilir. **Transparent huge page (THP)** otomatik yardım etse de, bazı latency-hassas iş yüklerinde beklenmedik duraklamalara yol açtığı bilinir; bu tür sistemlerde bilinçli olarak kapatmak ya da yalnız açık talep edilen bölgelerde kullanmak tercih edilir.

**Erişim lokalitesi.** Sanal bellek performansı büyük ölçüde lokaliteye bağlıdır. Bir matrisi bellek düzenine ters yönde (kolon-kolon, satır-major bir dizide) dolaşmak, her erişimde farklı sayfaya atlayarak hem cache hem TLB isabetlerini yok eder. Aynı algoritma, erişimi bellek düzenine hizalayınca kat kat hızlanır. Bu, "aynı big-O ama çok farklı gerçek hız" olgusunun en yaygın kaynaklarından biridir.

### Güvenlik Boyutu

Sanal bellek yalıtımı bir güvenlik sınırıdır ve bu sınırı zorlayan saldırılar vardır. **Rowhammer**, komşu bellek hücrelerine hızlı erişimle fiziksel olarak bit çevirerek yalıtımı bozmayı hedefler. **Meltdown/Spectre** sınıfı spekülatif yürütme açıkları, çevirinin ve önbelleğin yan kanallarını (side channel) kullanarak izinsiz bellek içeriğini sızdırmıştır; bunların savunması olan **KPTI (kernel page-table isolation)** çekirdek ve kullanıcı sayfa tablolarını ayırır ve gözle görülür bir performans bedeli getirmiştir. Buradaki ders şudur: sanal bellek yalıtımı yazılım düzeyinde temiz görünse de, altındaki fiziksel ve mikro-mimari gerçeklik sızıntı kanalları barındırabilir.

## En İyi Pratikler

Sanal belleği doğru kullanmanın özü, mekanizmayı görmezden gelmek değil, tembelliklerini ve maliyetlerini bilerek çalışmaktır.

- **Çalışma kümenizi RAM'e sığdırın.** En büyük performans kazancı thrashing'i tümden önlemektir. Ölçün: major fault oranı sürekli yüksekse ve sistem swap'te boğuluyorsa, algoritmik iyileştirme ya da RAM artışı, mikro-optimizasyondan çok daha değerlidir.

- **Minor ve major fault'u ayırt edin.** İzleme yaparken bu ikisini karıştırmayın. Yüksek minor fault normaldir (yeni bellek dokunuşu); yüksek major fault ise diske gidiyorsunuz demektir ve gerçek bir darboğaz sinyalidir.

- **Bellek erişimini lokal tutun.** Veri yapılarını erişim örüntüsüne göre düzenleyin, sıralı dolaşımı tercih edin. Bu hem cache hem TLB'ye yarar ve sanal bellek katmanının maliyetini en aza indirir.

- **Büyük ve yoğun iş yüklerinde huge page'i ölçerek kullanın.** Faydası TLB baskısı yüksek uygulamalarda gerçektir, ama otomatik THP'nin latency yan etkilerine karşı ölçüm yapmadan güvenmeyin.

- **`malloc` başarısını RAM garantisi sanmayın.** Overcommit ortamında gerçek tahsis ilk dokunuşta olur. Bellek kritik servislerde OOM davranışını bilinçli yapılandırın ve bellek limitlerini (cgroup gibi mekanizmalarla) açıkça belirleyin.

- **`mmap` kullanırken kaynağın ömrünü ve sınırlarını yönetin.** Eşlenmiş dosyanın altından çekilmesi (truncate) SIGBUS üretebilir; erişim örüntüsünü çekirdeğe bildirmek performansı iyileştirir.

- **Swap'i kategorik olarak kötü görmeyin.** Az miktarda swap, nadiren kullanılan soğuk sayfaları RAM'den çıkararak sıcak veriye ve sayfa önbelleğine yer açar ve sistemi daha sağlıklı kılar. Sorun swap'in varlığı değil, aktif çalışma kümesinin swap'e taşmasıdır.

## Kapanış

Sanal bellek, tek bir zarif fikrin — sanal adresi fiziksel adresten ayırmanın — üzerine kurulu koca bir mekanizmalar ailesidir: sayfa ve çerçeve granülaritesi external fragmentation'ı çözer, MMU ve TLB çeviriyi görünmez ve hızlı kılar, çok seviyeli sayfa tabloları seyrek adres uzaylarını ucuza temsil eder, page fault tembel tahsis ve copy-on-write gibi güçlü tekniklerin motorudur, swap ise fiziksel sınırın ötesine esneme payı verir. Bu katmanın en büyük başarısı, çoğu zaman fark edilmemesidir. Ama fark edilmesi gerektiği an — thrashing, OOM, TLB baskısı ya da yalıtım açıkları — geldiğinde, altındaki mekanizmayı anlamak, sorunu tahmine dayalı çözmekle kökten çözmek arasındaki farkı belirler.
