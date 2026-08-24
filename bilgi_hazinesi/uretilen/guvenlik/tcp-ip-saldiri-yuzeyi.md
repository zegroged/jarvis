# TCP/IP Saldırı Yüzeyi: Katman Katman Saldırılar, Spoofing ve SYN Flood

## Giriş ve Kapsam

TCP/IP protokol ailesi, bugün internetin üzerinde çalıştığı temel iletişim modelidir. Ancak bu protokoller 1970'lerin sonu ve 1980'lerin başında, birbirine güvenen akademik ve askerî ağlar için tasarlandı. O dönemde tehdit modeli "ağdaki taraflar kötü niyetli olabilir" varsayımını içermiyordu. Sonuç olarak IPv4, ICMP, ARP ve klasik TCP; kimlik doğrulama, bütünlük (integrity) ve gizlilik (confidentiality) özelliklerinden yoksun doğdu. Bugün gördüğümüz saldırı yüzeyinin büyük kısmı, bu tasarım kararlarının doğrudan sonucudur.

Bu makalede TCP/IP yığınını (stack) katman katman ele alıp her katmanın kendine özgü saldırı yüzeyini inceleyeceğiz. Özellikle iki temel konuya derinlemesine ineceğiz: **spoofing** (kaynak kimliğini sahtecilik) ve **SYN flood** (bir kaynak tüketme / resource exhaustion saldırısı). Amacım kuru bir liste vermek değil; her saldırının **neden** mümkün olduğunu, protokolün hangi tasarım özelliğinin buna izin verdiğini ve savunmanın **nasıl** çalıştığını akıl yürüterek göstermek.

## TCP/IP Katman Modeli ve Saldırı Yüzeyinin Dağılımı

Klasik TCP/IP modeli dört katmandan oluşur: **Link (bağlantı) katmanı**, **Internet (ağ) katmanı**, **Transport (taşıma) katmanı** ve **Application (uygulama) katmanı**. Her katman kendi altındaki katmana "güvenir" ve bu güven zinciri, saldırganların en sevdiği kaldıraçtır. Bir alt katmanı ele geçiren saldırgan, üstteki tüm katmanların güvenlik varsayımlarını çökertebilir.

Saldırı yüzeyini katmanlara göre düşünmek önemlidir çünkü her katmanın kimlik doğrulama zayıflığı farklı bir ölçekte sömürülür: Link katmanı yerel ağ (LAN) ile sınırlıyken, Internet katmanı saldırıları teorik olarak internet ölçeğinde yapılabilir.

## Link Katmanı Saldırıları

### ARP Spoofing / ARP Poisoning

**Tanım.** ARP (Address Resolution Protocol), aynı yerel ağdaki bir IP adresini bir MAC adresine eşler. Bir cihaz "192.168.1.1 kimin?" diye yayın (broadcast) yaptığında, ilgili cihaz "benim, MAC adresim şu" diye yanıt verir.

**Kök neden.** ARP'ın hiçbir kimlik doğrulaması yoktur. Protokol, istenmemiş (gratuitous) ARP yanıtlarını da kabul eder; yani bir cihaz kimse sormadan "ben 192.168.1.1'im ve MAC'im budur" diyebilir. Kurban cihaz bu yanıtı ARP tablosuna yazar. Neden böyle? Çünkü ARP, tüm LAN katılımcılarının dürüst olduğu varsayımıyla tasarlandı; doğrulama yükü performans ve basitlik adına dışlandı.

**Sömürü mantığı.** Saldırgan, ağ geçidinin (gateway) IP'sini kendi MAC'ine, kurbanın IP'sini de yine kendi MAC'ine bağlayan sahte ARP yanıtları gönderir. Böylece kurban ile ağ geçidi arasındaki trafik saldırganın makinesinden geçmeye başlar. Bu klasik bir **Man-in-the-Middle (MitM)** konumudur. Saldırgan trafiği pasif olarak dinleyebilir, değiştirebilir veya düşürebilir (denial). ARP poisoning genellikle SSL stripping, DNS manipülasyonu veya oturum (session) ele geçirme saldırılarının başlangıç adımıdır.

**Savunma.** 
- **Dynamic ARP Inspection (DAI):** Yönetilebilir switch'lerde, DHCP snooping tablosuyla tutarsız ARP paketlerini düşürür.
- **Statik ARP girişleri:** Kritik cihazlar (ör. ağ geçidi) için elle sabit MAC-IP eşlemesi. Yönetim yükü nedeniyle ölçeklenmez ama yüksek değerli hedeflerde işe yarar.
- **Port security ve 802.1X:** Ağa katılan cihazların kimliğini doğrular.
- **Şifreleme:** En sağlam yaklaşım, ARP'ı güvenilir kabul etmemektir. Uçtan uca TLS, ARP poisoning ile araya giren saldırganın trafiği okumasını/değiştirmesini anlamsız kılar. Bu, "alt katmana güvenme, güvenliği üst katmanda sağla" prensibinin somut örneğidir.

### MAC Flooding ve VLAN Saldırıları

Switch'lerin CAM (Content Addressable Memory) tablosu sınırlı boyuttadır. Saldırgan binlerce sahte kaynak MAC adresiyle tabloyu doldurursa (MAC flooding), switch öğrenme yeteneğini kaybedip **fail-open** davranarak paketleri hub gibi tüm portlara yayınlamaya başlayabilir; bu da pasif dinlemeyi mümkün kılar. Savunma yine port security'dir (port başına öğrenilen MAC sayısını sınırlamak).

## Internet (Ağ) Katmanı Saldırıları

### IP Spoofing

**Tanım.** IP spoofing, bir IP paketinin kaynak adres alanına saldırganın gerçek adresi yerine başka bir adres yazmasıdır.

**Kök neden.** IP başlığındaki kaynak adres alanı, gönderen tarafından serbestçe doldurulur ve yol boyunca hiçbir zorunlu doğrulama yapılmaz. IP, "best effort" (en iyi çaba) bir teslimat protokolüdür; kaynak kimliğini doğrulamak onun görevi değildir. Bu, protokolün en temel güven açığıdır.

**Sömürü mantığı ve iki farklı senaryo.** Burada kritik bir ayrım vardır ve çoğu yanlış anlama buradan doğar:

1. **Tek yönlü (blind) saldırılar:** Saldırgan yanıtı görmeye ihtiyaç duymuyorsa spoofing çok etkilidir. En önemli örnek **reflection ve amplification** saldırılarıdır. Saldırgan, kaynak adresi kurbanın IP'si olacak şekilde sahte istekler gönderir (ör. DNS, NTP, memcached gibi UDP tabanlı servislere). Sunucu yanıtı kurbana yollar. Eğer yanıt istekten çok daha büyükse (amplification faktörü), kurban devasa bir trafik seliyle boğulur. Burada spoofing işe yarar çünkü **saldırgan yanıtı hiç görmek zorunda değildir.**

2. **TCP oturumu ele geçirme (blind spoofing):** Saldırgan sahte bir IP ile tam bir TCP oturumu kurmaya çalışıyorsa iş çok zorlaşır. Çünkü TCP three-way handshake sırasında sunucu, SYN-ACK yanıtını **spoof edilen gerçek adrese** yollar, saldırgana değil. Oturumu tamamlamak için saldırganın sunucunun ürettiği **Initial Sequence Number (ISN)**'i doğru tahmin etmesi gerekir. Eski sistemlerde ISN üretimi tahmin edilebilirdi ve bu saldırılar mümkündü. Modern yığınlar ISN'i kriptografik olarak randomize ettiği için kör TCP spoofing günümüzde pratikte çok zordur. Bu, neden hâlâ TCP'nin bağlantısız UDP'den daha spoofing-dirençli olduğunu açıklar.

**Savunma.**
- **Ingress/Egress filtering (BCP 38):** İnternet servis sağlayıcılarının, kendi ağlarından çıkan paketlerin kaynak adresinin gerçekten o ağa ait olduğunu doğrulaması gerekir. Eğer herkes bunu uygulasaydı, IP spoofing'in büyük kısmı kökten engellenirdi. Bunun evrensel olarak uygulanmaması, spoofing'in hâlâ yaşamasının temel sebebidir.
- **Unicast Reverse Path Forwarding (uRPF):** Router, gelen paketin kaynak adresine bakıp "bu adrese giden yol, paketin geldiği arayüz mü?" diye kontrol eder; değilse düşürür.
- **Uygulama katmanı kimlik doğrulaması:** IP adresine güvenerek yetki verme (IP-based trust) mimarisinden kaçınmak. rlogin/rsh gibi eski servisler tam da bu güven modeli yüzünden felakete yol açmıştı.

### ICMP Tabanlı Saldırılar

ICMP, ağ hata ve tanı mesajları taşır. Saldırı yüzeyi birkaç boyutta ortaya çıkar:

- **ICMP redirect:** Sahte bir "daha iyi bir yol var" mesajıyla kurbanın yönlendirme (routing) tablosunu zehirlemek, trafiği saldırgan üzerinden geçirmek. Modern işletim sistemleri ICMP redirect'i varsayılan olarak yok saymaya veya sıkı kısıtlamaya yönelmiştir.
- **ICMP flood / Smurf saldırısı:** Klasik Smurf saldırısında, saldırgan kaynağı kurbanın IP'si olan ICMP echo request'leri bir ağın broadcast adresine gönderir; ağdaki tüm cihazlar kurbana yanıt yağdırır. Bu bir amplification örneğidir. Savunma, yönlendiricilerde yönlendirilmiş broadcast'i (directed broadcast) kapatmaktır; bugün bu neredeyse evrensel bir varsayılandır, bu yüzden klasik Smurf artık nadirdir.
- **Path MTU manipülasyonu:** Sahte "fragmentation needed" mesajlarıyla bağlantıyı bozmak.

### Fragmentation Saldırıları

IP paketleri yol boyunca parçalanabilir (fragmentation). Saldırganlar çakışan (overlapping) veya eksik fragment'ler göndererek IDS/IPS ve güvenlik duvarlarını atlatmayı (evasion) deneyebilir; farklı işletim sistemlerinin fragment'leri farklı birleştirmesi (reassembly ambiguity) bu evasion'ın kök nedenidir. Ayrıca eksik fragment'lerin bellekte tutulması bir kaynak tüketme vektörüdür.

## Transport Katmanı Saldırıları

### TCP Three-Way Handshake: Neden Saldırıya Açık?

TCP güvenilir, bağlantı odaklı bir protokoldür ve her bağlantı **three-way handshake** ile başlar:

1. İstemci **SYN** gönderir (bağlantı kurmak istiyorum, sıra numaram X).
2. Sunucu **SYN-ACK** yanıtlar (kabul, benim sıra numaram Y, senin X'ini aldım).
3. İstemci **ACK** yollar (Y'yi aldım, bağlantı kuruldu).

Kritik nokta: Sunucu, ikinci adımda SYN-ACK'i yolladıktan sonra bağlantıyı "yarı açık" (half-open) durumda tutar ve üçüncü adımdaki ACK'i beklerken **bellekte durum bilgisi (state) ayırır.** İşte SYN flood tam da bu davranışı sömürür.

### SYN Flood: Derinlemesine

**Tanım.** SYN flood, sunucunun yarı açık bağlantı tablosunu (backlog queue) doldurarak meşru istemcilerin bağlantı kuramamasına yol açan bir Denial of Service (DoS) saldırısıdır.

**Kök neden ve çalışma mantığı.** Sunucu bir SYN aldığında bir TCB (Transmission Control Block) benzeri yapı ayırır ve SYN-ACK yollar. Eğer üçüncü ACK hiç gelmezse, bu yarı açık kayıt bir zaman aşımı (timeout) süresince tabloda kalır. Bu tablonun boyutu sınırlıdır (backlog). Saldırgan sürekli SYN gönderip ACK'leri hiç tamamlamazsa, tablo dolar ve sunucu yeni SYN'leri reddetmeye başlar; meşru kullanıcılar dışarıda kalır.

**Spoofing ile birleşimi.** Saldırgan genellikle **sahte (spoofed) kaynak IP'ler** kullanır. Bunun iki amacı vardır. Birincisi, sunucunun yolladığı SYN-ACK var olmayan veya masum bir adrese gider, dolayısıyla asla ACK gelmez ve kayıt tam süre tabloda kalır. İkincisi, saldırganın kendi kimliği gizlenir ve savunmanın kaynağı IP bazında engellemesi zorlaşır. Buradan neden IP spoofing ile SYN flood'un birbirini tamamladığını görürüz: spoofing, saldırıyı hem daha etkili hem de daha izlenemez yapar.

Dikkat edilmesi gereken bir nokta: SYN flood klasik bir **bant genişliği** saldırısı değildir; küçük paketlerle bile sunucunun **bağlantı durumu belleğini** tükettiği için etkilidir. Yani düşük hacimli trafikle büyük hasar mümkündür. Bu onu hacimsel (volumetric) DDoS'tan kavramsal olarak ayırır.

**Savunma: SYN Cookies.** En zarif savunma **SYN cookie** tekniğidir. Fikir şudur: Sunucu, SYN aldığında bellekte durum ayırmak yerine, bağlantıya ait bilgiyi (istemci adresi, portlar, bir zaman damgası ve bir MSS ipucu dahil) kriptografik bir fonksiyonla kodlayarak SYN-ACK'in **sıra numarası (ISN)** alanına gömer. Böylece sunucu hiçbir durum tutmaz. Meşru istemci ACK ile döndüğünde, ACK içindeki alan (beklenen sıra numarası + 1) sunucunun cookie'yi doğrulamasını sağlar; doğrulanırsa bağlantı tam olarak o anda oluşturulur.

Neden bu işe yarar? Çünkü saldırgan spoofed IP kullandığında SYN-ACK'i hiç görmez, dolayısıyla geçerli bir cookie üretemez ve üçüncü ACK'i doğru cevaplayamaz. Meşru istemci ise SYN-ACK'i alır ve doğru cookie ile döner. Böylece sunucu, "yalnızca gerçekten üç yönlü el sıkışmayı tamamlayabilenler için" durum ayırır ve backlog tükenmez.

SYN cookie'nin bir bedeli vardır: Durum tutmadığı için bazı TCP seçenekleri (options) tam korunamaz ve MSS gibi değerler sınırlı bir kümeye sıkıştırılır. Bu yüzden birçok sistem SYN cookie'leri **yalnızca backlog dolmaya başladığında** devreye alır; normal koşulda klasik davranışı korur. Bu, "savunmayı sadece saldırı anında etkinleştir, normal işlevselliği bozma" mühendislik dengesinin güzel bir örneğidir.

**Diğer savunmalar.**
- **Backlog boyutunu artırmak ve timeout'u kısaltmak:** Palyatif çözümlerdir; kararlı bir saldırıya karşı tek başına yetmez ama saldırı maliyetini yükseltir.
- **Sınır cihazlarında SYN proxy:** Bir güvenlik duvarı/yük dengeleyici el sıkışmayı istemci adına tamamlar, ancak bağlantı gerçekten kurulunca sunucuya devreder. Böylece yarım açık yük sunucuya hiç ulaşmaz.
- **Rate limiting ve anomali tespiti:** Kaynak başına SYN oranını sınırlamak.
- **Yukarı akış DDoS temizleme (scrubbing):** Büyük ölçekli saldırılarda trafik, filtreleyen bir servise yönlendirilir.

### TCP RST Injection ve Oturum Ele Geçirme

Saldırgan trafiği görebiliyorsa (on-path) veya sıra numaralarını tahmin edebiliyorsa, sahte bir **RST** (reset) paketi enjekte ederek meşru bir bağlantıyı aniden koparabilir. Bu teknik hem sansür sistemleri hem de hedefli DoS için kullanılır. Kök neden yine aynıdır: TCP, doğru sıra numarasına sahip bir kontrol paketini kimlik doğrulamadan kabul eder.

Benzer şekilde, doğru sıra numarasıyla sahte veri paketleri enjekte edilerek **TCP session hijacking** yapılabilir. Modern ISN randomizasyonu off-path saldırıları çok zorlaştırmıştır, ama on-path (ARP poisoning ile araya girmiş) bir saldırgan için bu tehdit gerçektir. Buradaki savunma net: **bağlantı bütünlüğünü ve gizliliğini TCP'ye değil TLS'e emanet et.** TLS, enjekte edilen veriyi bütünlük doğrulamasında yakalar; RST enjeksiyonu ise bağlantıyı koparabilir ama içeriği ele geçiremez.

### UDP'nin Durumsuzluğu ve Amplification

UDP el sıkışma yapmaz, durum tutmaz ve dolayısıyla kaynak doğrulaması yoktur. Bu, onu spoofing tabanlı **amplification DDoS** için ideal kılar. Saldırgan küçük bir sorguyu kurbanın adresinden yollar, sunucu büyük bir yanıtı kurbana gönderir. Amplification faktörü yüksek olan servisler (yanlış yapılandırılmış açık DNS resolver'lar, NTP, ve tarihsel olarak çok yüksek faktörlü memcached gibi) en tehlikeli reflektörlerdir. Savunma zinciri: açık/yanlış yapılandırılmış servisleri kapatmak, kaynak spoofing'i BCP 38 ile engellemek ve kritik servisleri rate limiting ile korumak.

## Uygulama Katmanı ile İlişki

Alt katman zayıflıkları uygulama katmanına doğrudan yansır. DNS spoofing/cache poisoning, IP ve UDP'nin spoofing'e açıklığından güç alır: saldırgan, çözümleyicinin sorgusuna sahte bir yanıtı gerçek sunucudan önce ulaştırmaya çalışır. Doğru **transaction ID** ve **kaynak port randomizasyonu** bu tahmini zorlaştırır; kalıcı çözüm ise yanıtları kriptografik olarak imzalayan **DNSSEC**'tir. Buradaki ders tutarlıdır: alt katman doğrulama sağlamadığında, güvenlik üst katmanda kriptografiyle inşa edilmek zorundadır.

## Yaygın Hatalar

- **IP adresini kimlik olarak kabul etmek.** "Bu istek şirket IP'sinden geliyor, güvenilir" mantığı spoofing karşısında çöker. IP, kimlik değil yalnızca bir yönlendirme ipucudur.
- **SYN flood'u bant genişliği sorunu sanmak.** Backlog tükenmesi bir durum/bellek sorunudur; "hattı büyütmek" onu çözmez, SYN cookie / SYN proxy çözer.
- **Alt katman güvenliğine bel bağlamak.** "Aynı LAN'dayız, şifrelemeye gerek yok" varsayımı ARP poisoning ile yıkılır. İç ağ da düşman ağ kabul edilmelidir (zero trust).
- **SYN cookie'yi her koşulda açık bırakıp TCP options kaybını göz ardı etmek.** Doğru yaklaşım, eşik tabanlı devreye almadır.
- **BCP 38'i "başkasının sorunu" görmek.** Herkes kendi çıkış trafiğini filtrelemedikçe spoofing tabanlı DDoS'lar yaşamaya devam eder; bu kolektif bir sorumluluktur.
- **ICMP'yi tamamen kapatmak.** Aşırı tepki olarak tüm ICMP'yi engellemek, Path MTU Discovery gibi meşru mekanizmaları bozar ve garip bağlantı sorunlarına yol açar. Seçici filtreleme gerekir.

## En İyi Pratikler

1. **Katmanlı savunma (defense in depth).** Her katmanı tek başına yeterli görme; ARP koruması, uRPF, SYN cookie ve TLS'i birlikte kullan.
2. **Kriptografiyi taşıyıcıya emanet et, ağa değil.** Bütünlük ve gizliliği TLS/IPsec ile sağla; böylece alt katman ele geçirilse bile veri korunur.
3. **Kaynak adres doğrulamasını uygula (BCP 38 / uRPF).** Ağ kenarında spoofed paketleri kökten düşür.
4. **SYN flood'a karşı eşik tabanlı SYN cookie ve/veya SYN proxy.** Palyatif backlog ayarlarına değil, durumsuz doğrulamaya güven.
5. **Switch güvenliği: DAI, DHCP snooping, port security, 802.1X.** LAN'ı güvenilir bölge olarak görme.
6. **Açık reflektörleri kapat.** DNS resolver, NTP ve benzeri servisleri sadece meşru istemcilere hizmet verecek şekilde kısıtla; amplification vektörlerini yok et.
7. **Rate limiting ve anomali izleme.** Bağlantı kurulum oranlarını, yarım açık bağlantı sayısını ve olağandışı trafik desenlerini sürekli izle.
8. **DNSSEC ve modern protokoller.** Uygulama katmanında spoofing'e karşı imzalı yanıtları ve şifreli taşıma katmanlarını benimse.

## Sonuç

TCP/IP saldırı yüzeyinin tamamı tek bir kök nedene indirgenebilir: **protokoller, tarafların dürüst olduğu bir dünya için tasarlandı ve kaynak kimliğini doğrulamadı.** ARP spoofing, IP spoofing, SYN flood ve amplification saldırıları hep bu doğrulama boşluğunun farklı katmanlardaki yansımalarıdır. Bu yüzden savunmanın felsefesi de tek cümlede özetlenir: **hiçbir alt katmana güvenme, kimliği ve bütünlüğü kriptografiyle üst katmanda kur, kaynak doğrulamasını ağ kenarında zorla ve durum tüketen mekanizmaları durumsuz doğrulamayla koru.** Saldırıların "nasıl"ını anlamak, savunmanın "neden"ini kavramanın tek yoludur.
