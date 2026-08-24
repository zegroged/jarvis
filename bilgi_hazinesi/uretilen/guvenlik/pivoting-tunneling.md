# Pivoting ve Tunneling: Ağ Derinliğinde İlerlemenin Mantığı

## Giriş ve Tanım

Bir hedef ağa ilk erişim sağlandığında, saldırgan neredeyse hiçbir zaman aradığı asıl varlığın (Domain Controller, veritabanı sunucusu, yedekleme sistemi) durduğu makineye doğrudan düşmez. İlk ele geçirilen makine genellikle bir DMZ web sunucusu, bir kullanıcı laptop'u ya da internete açık bir servistir. Asıl değerli sistemler ise iç ağ segmentlerinde, saldırganın kendi konumundan doğrudan `routing` (yönlendirme) ile ulaşamayacağı yerlerde yaşar.

**Pivoting**, ele geçirilmiş bir makineyi bir sıçrama taşı (İngilizcede "pivot" ya da "foothold") olarak kullanıp, o makinenin erişebildiği ama saldırganın doğrudan erişemediği ağlara ulaşma tekniğidir. **Tunneling** ise bu erişimi sağlamak için bir protokol trafiğini başka bir protokolün içine kapsülleyerek (encapsulation) taşıma yöntemidir. İki kavram iç içedir: pivoting "nereye" ulaşmak istediğinizi, tunneling ise "hangi boru üzerinden" ulaşacağınızı tanımlar.

Bu makale, konuya hem saldırı (offensive) hem de savunma (defensive) tarafından bakar. Amaç, komut ezberletmek değil; neden bu tekniklerin işe yaradığını, ağ katmanında tam olarak ne olduğunu ve bir savunmacının bu trafiği neden ve nasıl fark edebileceğini akıl yürüterek göstermektir.

## Kök Neden: Neden Pivoting'e İhtiyaç Duyulur?

Pivoting'in var olma nedeni tek bir kavrama dayanır: **ağ segmentasyonu ve routing sınırları**.

Modern kurumsal ağlar düz (flat) değildir; VLAN'lar, farklı subnet'ler ve firewall kuralları ile bölünmüştür. İnternetteki bir saldırgan yalnızca `10.0.1.0/24` DMZ ağındaki bir web sunucusuna erişebilirken, `10.0.50.0/24` iç sunucu ağına giden trafik firewall tarafından bloklanır. Ancak DMZ web sunucusunun kendisi, iş gereği veritabanına erişmek için `10.0.50.0/24`'e giden bir yola sahiptir. İşte pivoting'in kök nedeni budur: **ele geçirilen makine, saldırganın sahip olmadığı bir ağ görünürlüğüne ve routing iznine sahiptir.**

Saldırgan kendi makinesinden `10.0.50.10`'a bir paket gönderemez çünkü:

1. Kendi routing tablosunda o subnet'e giden bir yol yoktur (ve olsa bile araya firewall girer).
2. `10.0.50.0/24` özel (RFC 1918) bir adres alanıdır ve internet üzerinden yönlendirilemez.

Pivot makinesi ise o ağın parçasıdır. Dolayısıyla saldırgan, kendi trafiğini pivot üzerinden "akıtabilirse", pivot'un routing yeteneğini ödünç almış olur. Tunneling tam olarak bu akıtma işini yapar.

Buradaki ikinci kök neden **görünürlük ve tespit kaçırmadır**. Saldırgan, iç ağa yeni bir bağlantı açmak yerine, zaten var olan ve izin verilen bir kanalın (örneğin giden bir HTTPS ya da SSH bağlantısının) içine trafiğini gizler. Firewall'lar genellikle "içeriden dışarıya" giden 443 trafiğine izin verdiği için, bu yön saldırgan için doğal bir kaçış yoludur.

## SSH Port Forwarding: En Temel ve En Sağlam Tünel

SSH, tünelleme dünyasının temel taşıdır çünkü şifreli, güvenilir ve neredeyse her Unix/Linux sistemde hazır bulunan bir protokoldür. SSH üç temel forwarding modu sunar ve bu üçünün farkını anlamak, tüm tunneling mantığının anahtarıdır.

### Local Port Forwarding (Yerel Yönlendirme)

Local forwarding'de saldırgan, **kendi makinesinde** bir port açar ve o porta gelen her şeyi SSH tüneli üzerinden pivot'a, oradan da hedefe iletir. Mantığı şudur: "Benim `localhost:8080` portuma bağlanan biri, aslında pivot'un görebildiği `10.0.50.10:80`'e bağlanmış olsun."

Kavramsal olarak yön şöyledir: *istemci (saldırgan) → SSH sunucusu (pivot) → nihai hedef*. Bu, saldırganın erişemediği bir iç servise (örneğin bir intranet web paneli) ulaşmak için kullanılır. Komut yapısında saldırgan yerel bir port, bir hedef IP:port ve pivot'un SSH bağlantısını belirtir; SSH istemcisi yerel portu dinler ve gelen bağlantıları tünelin diğer ucundan hedefe açar.

### Remote Port Forwarding (Uzak/Ters Yönlendirme)

Remote forwarding, yönü tersine çevirir ve reverse shell mantığına çok yakındır. Burada **SSH sunucusu tarafında** bir port açılır. Bu, en çok "pivot makinesi giden bağlantı kurabiliyor ama dışarıdan içeriye bağlantı kabul edemiyor" durumunda kullanılır.

Senaryo şudur: Ele geçirilen pivot bir firewall arkasındadır ve dışarıdan ona SSH ile bağlanamazsınız, ama o dışarıya (sizin sunucunuza) bağlanabilir. Pivot, sizin kontrolünüzdeki bir VPS'e SSH ile bağlanır ve remote forwarding ile "VPS'in bir portuna gelen bağlantıları bana geri gönder" der. Böylece firewall'ın "içeriden dışarıya izin verilir" kuralını kullanarak, dışarıdan içeriye erişim üretirsiniz. Bu, NAT ve firewall'ları aşmanın klasik yoludur.

### Dynamic Port Forwarding (SOCKS Proxy)

Local forwarding'in bir zayıflığı vardır: her hedef IP:port için ayrı bir tünel açmak gerekir. On farklı iç sunucuya erişmek istiyorsanız, on ayrı forwarding kuralı gerekir; bu hem hantal hem de keşif (reconnaissance) aşamasında imkansızdır çünkü hangi portların açık olduğunu henüz bilmezsiniz.

**Dynamic forwarding** bu sorunu çözer. SSH istemcisi yerel bir portta bir **SOCKS proxy** başlatır. Artık saldırgan hangi iç IP:port'a gitmek isterse, isteğini bu SOCKS proxy'ye söyler, SSH tüneli onu pivot üzerinden dinamik olarak hedefe iletir. Tek bir tünel, tüm iç ağa kapı açar.

## SOCKS Proxy: Neden Bu Kadar Merkezi?

SOCKS'un pivoting'de bu kadar merkezi olmasının kök nedeni, **uygulama katmanında protokolden bağımsız çalışmasıdır**. Bir HTTP proxy yalnızca HTTP anlar; SOCKS ise TCP (ve SOCKS5 ile UDP) düzeyinde çalışır, içeriğe karışmaz. Bu sayede bir SOCKS proxy üzerinden nmap taraması, RDP bağlantısı, SMB erişimi, veritabanı sorgusu — TCP kullanan her şey geçebilir.

SOCKS4 ve SOCKS5 arasındaki pratik fark önemlidir. SOCKS4 sadece IPv4 ve TCP destekler, DNS çözümlemesini istemci tarafında yapar. SOCKS5 ise kimlik doğrulama, IPv6, UDP ve — kritik olarak — **uzak DNS çözümlemesi** destekler. Bu son nokta pivoting'de hayatidir: eğer DNS çözümlemesini kendi makinenizde yaparsanız, iç ağın alan adlarını (örneğin `dc01.corp.local`) çözemezsiniz çünkü o DNS sunucusuna erişiminiz yoktur. SOCKS5 ile DNS çözümlemesini pivot tarafına ittiğinizde, iç DNS sunucusu isimleri sizin yerinize çözer.

Pratikte araçların SOCKS üzerinden konuşması için `proxychains` ya da benzeri bir wrapper kullanılır. Burada yaygın ama kritik bir nokta: **proxychains'in kendisi ham ICMP taşıyamaz.** SOCKS bir TCP proxy'sidir; ICMP echo (ping) TCP değildir. Bu yüzden proxychains üzerinden nmap kullanırken host discovery'nin devre dışı bırakılması ve tam TCP connect taraması yapılması gerekir, aksi halde araç ping'e güvenip hedefleri "kapalı" sanabilir. Bu, ezberden değil, protokolün doğasından kaynaklanan bir kısıttır.

## chisel: HTTP Üzerinden Tünel

SSH her zaman elverişli olmayabilir: hedef Windows olabilir, SSH istemcisi/sunucusu bulunmayabilir, ya da giden trafikte yalnızca HTTP/HTTPS'e izin veriliyor olabilir. **chisel** tam bu boşluğu doldurur. Go ile yazılmış, tek binary halinde çalışan, TCP/UDP trafiğini HTTP üzerinden tünelleyen ve isteğe bağlı olarak SSH ile şifreleyen bir araçtır.

chisel'in çalışma mantığı bir sunucu-istemci modeline dayanır. Bir uçta chisel `server` modunda dinler, diğer uçta `client` modunda ona bağlanır. Kritik olan, kimin sunucu kimin istemci olduğunun ağ topolojisine göre seçilmesidir:

- **Reverse (ters) senaryo**, saldırgan tarafında en yaygın olanıdır. Saldırgan kendi VPS'inde chisel server çalıştırır. Pivot makinesi chisel client olarak dışarıya, saldırgana doğru bağlanır. Sonra bir reverse SOCKS proxy kurularak, saldırganın kendi makinesinde iç ağa açılan bir SOCKS portu belirir. Bu, remote SSH forwarding'in mantığının aynısıdır ama HTTP taşıması üzerinden.

chisel'in değerli olmasının kök nedeni, trafiğini standart bir web bağlantısı gibi göstermesidir. Firewall bir HTTP/WebSocket bağlantısı görür; içindeki tünellenmiş SOCKS trafiğini paket başlıklarından ayırt etmesi zordur. Ayrıca tek binary olması, dosya transferi kısıtlı ortamlarda taşınmasını kolaylaştırır.

## ligolo-ng: Modern Yaklaşım ve TUN Arayüzü

chisel ve proxychains ile çalışmanın kronik bir sıkıntısı vardır: her aracı proxychains ile sarmalamak, ham paket gönderen araçlarla (bazı tarama modları, belirli exploit'ler) uyumsuzluk ve yavaşlık. **ligolo-ng** bu paradigmayı değiştirir.

ligolo-ng'nin ana fikri, pivot'a bir SOCKS portu açmak yerine, **saldırganın makinesinde bir sanal ağ arayüzü (TUN interface) oluşturmaktır.** Saldırgan, iç ağın subnet'ini (örneğin `10.0.50.0/24`) kendi routing tablosuna bu sanal arayüz üzerinden ekler. Artık o subnet'e giden her paket, işletim sisteminin normal ağ yığını (network stack) tarafından otomatik olarak tünele yönlendirilir.

Bunun kök avantajı şudur: **proxychains'e gerek kalmaz.** Herhangi bir araç — nmap, tarayıcı, Metasploit, herhangi bir yerel istemci — hiçbir değişiklik olmadan, sanki iç ağa doğrudan bağlıymış gibi çalışır çünkü işletim sistemi seviyesinde routing yapılmaktadır. Bu, hem hız hem de uyumluluk açısından büyük fark yaratır. ICMP dahil (ligolo bir agent tarafı yapılandırmasıyla ping'i de taşıyabilir) trafik türleri çok daha doğal biçimde geçer.

Mimarisi de sunucu-istemci ("proxy" ve "agent") modelidir. Saldırgan tarafında proxy çalışır ve TUN arayüzünü yönetir; pivot tarafında agent çalışır ve dışarıya proxy'ye bağlanır. Bu ters bağlantı modeli, chisel'de olduğu gibi firewall'ların giden-izinli doğasını kullanır.

## Ağ Derinliği: Çok Katmanlı (Nested) Pivoting

Gerçek dünyada tek bir pivot yeterli olmaz. Ele geçirilen ilk makine ikinci bir segmenti görür, o segmentteki bir makine üçüncü bir segmenti görür ve asıl hedef en derinde durur. Buna **ağ derinliği** ya da **zincirleme (chained/nested) pivoting** denir.

Burada temel prensip **tünellerin iç içe geçirilmesidir**. İlk pivot üzerinden ikinci ağa bir SOCKS proxy kurulur; sonra o ikinci ağdaki makine ele geçirilir ve onun üzerinden üçüncü ağa yeni bir tünel açılır. Her katman, bir öncekinin sağladığı erişim üzerine inşa edilir.

Bu noktada araçların derinlik yönetim farkı öne çıkar. proxychains ile çok katmanlı zincir kurmak, `proxychains.conf` içinde proxy'leri sırayla dizmek ve dikkatli bir konfigürasyon yönetmek anlamına gelir; her ek katman gecikmeyi (latency) artırır ve hata ayıklamayı zorlaştırır. ligolo-ng gibi araçlar ise çoklu agent ve çoklu TUN arayüzü kavramıyla bu derinliği daha yönetilebilir kılar: her iç ağ için ayrı bir sanal arayüz ve routing kuralı tanımlanabilir.

Derinlik arttıkça pratik gerçekler acımasızlaşır. Her katman şunları getirir:

- **Gecikme birikimi:** Her hop, gidiş-dönüş süresine (round-trip time) katkı yapar. Beş katmanlı bir tünelde interaktif bir shell bile fark edilir derecede yavaşlar; büyük dosya transferleri işkenceye döner.
- **Kırılganlık:** Zincirdeki herhangi bir pivot çökerse ya da bağlantısı koparsa, ondan sonraki tüm erişim kaybolur. Bu yüzden dayanıklı (persistent) tüneller ve otomatik yeniden bağlanma (auto-reconnect) mantığı önem kazanır.
- **Tespit yüzeyi:** Her pivot makinesinde bıraktığınız binary, açtığınız bağlantı ve ürettiğiniz trafik, savunmacıya yeni bir yakalanma fırsatı sunar.

## Sömürü/İstismar Mantığı: Saldırgan Neden Başarılı Olur?

Saldırganın pivoting'de başarılı olmasının altında yatan istismar mantığı birkaç yapısal zafiyete dayanır.

Birincisi, **giden trafiğe aşırı güvendir.** Çoğu kurum, "içeriden dışarıya" trafiği görece serbest bırakır; asıl sıkı denetimi dışarıdan içeriye uygular. Saldırgan bu asimetriyi kullanır: reverse tüneller kurar, çünkü pivot'un dışarıya bağlanma izni neredeyse her zaman vardır.

İkincisi, **şifreli trafiğin içeriğinin görünmezliğidir.** SSH, chisel'in TLS/WebSocket katmanı ya da ligolo'nun kendi şifrelemesi, tünelin içindeki gerçek trafiği (SMB, RDP, veritabanı sorguları) firewall ve IDS'ten gizler. Savunmacı yalnızca "443 portuna giden şifreli bir akış" görür.

Üçüncüsü, **yatay hareket (lateral movement) ile pivoting'in birleşmesidir.** Saldırgan bir pivot üzerinden iç ağı tarar, çalınmış kimlik bilgileri (credentials) ile bir sonraki makineye atlar ve orayı yeni bir pivot yapar. Bu döngü, Domain Controller'a ya da hedef veriye ulaşana dek tekrar eder. Pivoting, yatay hareketin "ağ borusu"dur.

## Savunma: Bu Trafiği Nasıl Tespit ve Engelleriz?

Savunma tarafı, saldırganın dayandığı yapısal zafiyetleri tersine çevirmekle başlar.

**Ağ segmentasyonu ve mikro-segmentasyon:** Pivoting'in kök nedeni pivot'un geniş ağ görünürlüğüne sahip olmasıysa, çözüm bu görünürlüğü daraltmaktır. Bir DMZ web sunucusunun iç ağda yalnızca ihtiyaç duyduğu tek veritabanı portuna erişmesi, geri kalan her şeye erişememesi gerekir. En küçük ayrıcalık (least privilege) prensibi ağ katmanında da geçerlidir. Böyle bir ortamda pivot ele geçirilse bile, saldırganın sıçrayabileceği yer daralır.

**Giden trafik (egress) filtreleme:** Reverse tünellerin panzehiri, giden bağlantıların da denetlenmesidir. Sunucuların keyfi dış IP'lere ve portlara bağlanmasına izin verilmemelidir. Bir DMZ sunucusunun bilinmeyen bir VPS'in 443 portuna sürekli WebSocket bağlantısı açması, meşru bir davranış değildir ve egress kuralları bunu engelleyebilir. Beklenmedik giden bağlantılar, alarm üretmesi gereken güçlü bir sinyaldir.

**Anomali ve davranış tabanlı tespit:** Tünel trafiğinin içeriği şifreli olsa da davranışı ele verir. Uzun ömürlü, sürekli veri taşıyan tek bir TCP bağlantısı; bir web sunucusundan kaynaklanan alışılmadık SSH ya da beklenmedik protokol trafiği; iç ağda kısa sürede birçok host'a giden bağlantı denemeleri (tarama davranışı) — bunların hepsi izleme ile yakalanabilir. JA3/JA4 gibi TLS parmak izi (fingerprint) teknikleri, chisel gibi araçların kendine has TLS el sıkışma (handshake) desenlerini standart tarayıcılardan ayırt etmeye yardımcı olabilir.

**Endpoint tespiti (EDR):** Pivot makinesinin kendisinde çalışan bir EDR, chisel/ligolo gibi bilinmeyen bir binary'nin diske yazılmasını, alışılmadık bir process'in ağ dinlemesini ya da bir TUN/TAP arayüzü oluşturulmasını fark edebilir. Özellikle sunucularda yeni bir sanal ağ arayüzünün belirmesi, doğal olmayan ve dikkat çekmesi gereken bir olaydır.

**DNS izleme:** SOCKS5'in uzak DNS çözümlemesi savunmacı için bir ipucudur. İç DNS sunucusunda, tek bir makineden gelen olağandışı sayıda ve çeşitlilikte iç isim çözümleme isteği, keşif ve pivoting'in işareti olabilir.

## Yaygın Hatalar

Hem saldırı hem savunma tarafında tekrar eden hatalar vardır; bunları bilmek her iki tarafı da güçlendirir.

**proxychains ile ICMP beklemek:** En sık yapılan saldırgan hatası, SOCKS üzerinden ping ya da ICMP tabanlı host discovery çalıştırıp sonuçları doğru sanmaktır. SOCKS TCP taşır; ping'in çalışmaması bir arıza değil, protokolün doğasıdır. Tarama TCP connect moduna alınmalı ve ping keşfi kapatılmalıdır.

**DNS'i yerelde çözmek:** Uzak DNS çözümlemesi ayarlanmadığında iç alan adları çözülemez ve saldırgan "ağ bozuk" sanabilir. Sorun ağda değil, DNS çözümlemesinin yanlış tarafta yapılmasındadır.

**MTU ve parçalanma (fragmentation) sorunları:** TUN tabanlı çözümlerde (ligolo gibi) sanal arayüzün MTU değeri, tünelin kapsülleme ek yükünü hesaba katmazsa, büyük paketler sessizce düşebilir ya da bağlantılar takılabilir. Küçük paketler çalışırken büyük transferlerin bozulması genellikle MTU işaretidir.

**Kalıcılık ve temizlik ihmali:** Saldırgan tarafında bırakılan binary'ler, açık portlar ve process'ler temizlenmezse tespit ve adli inceleme (forensics) için birer delil olur. Savunmacı tarafında ise, bir tünel tespit edilip kapatıldığında yalnızca o katmanın kesilmesi, alttaki foothold'un ve diğer pivot'ların ayakta kalmasına yol açabilir; olay müdahalesinde zincirin tamamı düşünülmelidir.

**Yalnızca perimeter'a güvenmek:** En büyük savunma hatası, "firewall içeri girişi engelliyor, iç ağ güvende" varsayımıdır. Pivoting'in tüm varlık nedeni, bir kez içeri girildiğinde iç ağın düz ve savunmasız olmasıdır. İç ağı da düşman bölge (assume breach) kabul etmeyen bir mimari, pivoting'e davetiye çıkarır.

## En İyi Pratikler

**Savunma tarafı için:**

- İç ağı mikro-segmente edin; her sistemin yalnızca iş için gerekli olan minimum bağlantıya erişmesini sağlayın. Pivot'un görünürlüğünü daraltmak, pivoting'i kökünden zayıflatır.
- Egress filtrelemeyi ciddiye alın; sunuculardan çıkan trafiği en az giren trafik kadar denetleyin. Reverse tünellerin çoğu, sıkı egress kuralları karşısında kurulamaz.
- Uzun ömürlü, yüksek hacimli tek bağlantıları ve sunuculardan kaynaklanan alışılmadık giden bağlantıları izleyen davranış tabanlı tespit kurun.
- EDR'i sunucularda da çalıştırın; yeni sanal ağ arayüzleri, bilinmeyen binary'ler ve dinleme yapan process'ler için alarm üretin.
- "Assume breach" zihniyetini benimseyin: perimeter'ın delineceğini varsayarak iç ağı da savunun.

**Kırmızı takım / test tarafı için (yetkili ve yasal kapsamda):**

- Ortama en az iz bırakan aracı seçin; her katmanda gereksiz binary ve açık port bırakmayın.
- Tünel derinliğini gecikme ve kırılganlık maliyetiyle tartın; her zaman en derine inmek yerine, hedefe ulaşan en kısa güvenilir yolu tercih edin.
- DNS ve ICMP davranışını protokol düzeyinde anlayın; araçları körlemesine değil, ne taşıyıp ne taşıyamayacaklarını bilerek kullanın.
- Test bittiğinde tüm tünelleri, binary'leri ve yapılandırma değişikliklerini titizlikle temizleyin; bu hem etik bir zorunluluk hem de savunmacıya verilen değerli bir geri bildirimdir.

## Kapanış

Pivoting ve tunneling, özünde tek bir gerçeğin sonucudur: ağlar bölünmüştür ama bu bölünme, ele geçirilmiş bir düğümün ödünç verilen görünürlüğüyle aşılabilir. Saldırgan, giden trafiğe duyulan güveni ve şifreli kanalların görünmezliğini kullanarak segmentleri birbirine bağlar; savunmacı ise aynı yapısal gerçekleri — segmentasyon, egress denetimi, davranış analizi, endpoint görünürlüğü — tersine çevirerek bu köprüleri yıkar. Bu tekniklerin araçları (SSH, chisel, ligolo) değişip gelişecektir; ama altta yatan mantık — routing sınırlarını ödünç alınmış erişimle aşmak — değişmez. Bu mantığı kavrayan, hangi araç çıkarsa çıksın ne olduğunu anlar.
