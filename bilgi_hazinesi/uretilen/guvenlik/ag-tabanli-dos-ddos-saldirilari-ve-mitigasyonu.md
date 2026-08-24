# Ağ Tabanlı DoS/DDoS Saldırıları ve Mitigasyonu

## Tanım ve Kavramsal Çerçeve

**DoS (Denial of Service / Hizmet Reddi)** saldırısı, bir sistemi, servisi veya ağı meşru kullanıcılarına hizmet veremez hâle getirmeyi amaçlayan saldırı sınıfıdır. **DDoS (Distributed Denial of Service / Dağıtık Hizmet Reddi)** ise aynı amacı, çok sayıda dağıtık kaynaktan (genellikle bir **botnet**) eş zamanlı trafik üreterek gerçekleştirir. Tek kaynaklı DoS'un kolayca engellenebilen zayıflığını (tek bir IP'yi kara listeye almak yeterli olur) aşmak için saldırganlar dağıtık modele geçmiştir.

Kritik kavramsal ayrım şudur: DoS/DDoS bir **kaynak tüketme** saldırısıdır, bir **veri sızıntısı** ya da **kod çalıştırma** saldırısı değildir. Amaç gizliliği ihlal etmek değil, **erişilebilirliği** (availability, CIA üçgeninin "A" ayağı) ortadan kaldırmaktır. Bu nedenle savunma da erişilebilirliği koruma etrafında kurgulanır: kapasite, filtreleme ve trafik yönlendirme.

Saldırıları hedefledikleri katmana ve sömürdükleri kaynağa göre kabaca üçe ayırmak faydalıdır:

- **Hacimsel (volumetric) saldırılar:** Amaç, hedefin veya erişim yolundaki bağlantının **bant genişliğini** doldurmaktır. Ölçü birimi genellikle **bps (bit/saniye)** ya da **Gbps/Tbps**'dir. UDP flood, ICMP flood ve amplifikasyon saldırıları bu sınıftadır.
- **Protokol saldırıları:** Amaç, hedef sistem veya ara katman cihazlarındaki (firewall, load balancer, güvenlik duvarı state tablosu) **durum tablolarını (state)** ve bağlantı kaynaklarını tüketmektir. Ölçü birimi genellikle **pps (paket/saniye)** ya da **cps (bağlantı/saniye)**'dir. SYN flood bunun klasik örneğidir.
- **Uygulama katmanı (Layer 7) saldırıları:** Amaç, görünüşte meşru isteklerle (örneğin pahalı bir HTTP GET/POST, arama sorgusu, oturum açma) sunucunun işlem gücünü, veritabanını veya thread havuzunu tüketmektir. Düşük trafikle büyük hasar verebilir, bu yüzden tespiti en zor sınıftır.

Bu makale ağ tabanlı (L3/L4) saldırılara ve onların savunma mimarisine odaklanır; uygulama katmanına da yeri geldikçe değinir.

---

## SYN Flood: Protokol Durumunu Sömürmek

### Kök Neden ve Çalışma Mantığı

SYN flood, TCP'nin **üç yönlü el sıkışma (three-way handshake)** tasarımındaki asimetriyi sömürür. Normal bir TCP bağlantısı şöyle kurulur:

1. İstemci sunucuya **SYN** paketi gönderir.
2. Sunucu **SYN-ACK** ile yanıt verir ve bu **yarı açık (half-open)** bağlantıyı bir kuyrukta (backlog queue) tutar; istemcinin son ACK'ini bekler.
3. İstemci **ACK** gönderir, bağlantı tamamlanır (ESTABLISHED).

Sorun şudur: Sunucu, 2. adımda kaynak ayırır (bağlantı durumu için bellek) ve **son adımı beklerken bu kaynağı tutar**. Saldırgan bir sürü SYN paketi gönderir ama **hiçbir zaman ACK ile yanıtlamaz** (ya da genellikle **spoofed / sahte kaynak IP'leri** kullanır, böylece SYN-ACK varolmayan/ilgisiz adreslere gider ve doğal olarak ACK hiç gelmez).

Sonuç: Sunucunun yarı açık bağlantı kuyruğu (SYN backlog) dolar. Kuyruk dolduğunda sunucu **yeni meşru SYN'leri reddetmeye başlar** ve servis fiilen durur. Dikkat: Bu saldırının etkili olması için devasa bant genişliği gerekmez; asıl darboğaz **durum tablosu kapasitesidir**, ham hacim değil. Bu yüzden SYN flood bir "protokol saldırısı"dır.

### Örnek Senaryo

Bir web sunucusunun SYN backlog kuyruğu, diyelim ki 1024 girdi tutabiliyor ve yarı açık bağlantı zaman aşımı (retransmit denemeleriyle birlikte) onlarca saniye sürüyor olsun. Saldırgan saniyede birkaç bin sahte kaynaklı SYN gönderirse, kuyruk anında dolar ve zaman aşımı süresince dolu kalır. Meşru bir kullanıcının SYN'i, kuyrukta yer bulamadığı için düşürülür; kullanıcı "bağlantı zaman aşımına uğradı" hatası alır.

### Tespit

- **Yarı açık bağlantı oranında ani artış:** `SYN_RECV` durumundaki bağlantı sayısının anormal yükselmesi (Linux'ta `ss` / `netstat` ile bu durumlar gözlemlenebilir).
- **SYN'e karşı ACK dengesizliği:** Gelen SYN sayısı ile tamamlanan handshake (ACK) sayısı arasında büyük uçurum. Sağlıklı trafikte bunlar birbirine yakın seyreder.
- **Kaynak IP dağılımı:** Çok sayıda benzersiz, coğrafi olarak dağınık veya sahte görünen (örneğin private/reserved aralıklardan gelen, ki bunlar hiç görülmemeli) kaynak IP.
- **NetFlow/IPFIX analizi:** Akış kayıtlarında çok sayıda kısa ömürlü, tek paketlik akışlar.

### Savunma

- **SYN cookies:** En temel ve etkili karşı önlemdir. Fikir şudur: Sunucu, SYN-ACK gönderirken bağlantı durumunu bellekte tutmak yerine, bağlantıya ait bilgiyi kriptografik olarak sequence number içine **kodlar (cookie)**. Böylece yarı açık bağlantı için bellek ayırmaz. Meşru istemci ACK ile döndüğünde, sunucu ACK içindeki sequence number'dan durumu **yeniden türetir** ve bağlantıyı ancak o zaman kurar. Kuyruk dolması sorunu ortadan kalkar. Çoğu modern işletim sistemi çekirdeğinde bir yapılandırma anahtarıyla açılabilir (Linux'ta `tcp_syncookies` kavramı). Bedeli: Bazı TCP seçeneklerinin (örneğin bazı durumlarda window scaling) taşınmasında sınırlamalar olabilir; bu yüzden genellikle "kuyruk dolduğunda devreye giren" bir emniyet supabı olarak çalışır.
- **Backlog kuyruğunu büyütmek ve zaman aşımını kısaltmak:** Palyatif; tek başına yetersizdir ama yardımcı olur.
- **Upstream/kenar filtreleme ve SYN proxy:** Bir güvenlik cihazı veya scrubbing servisi handshake'i **kendi üzerinde** tamamlar; yalnızca meşru şekilde tamamlanan bağlantıları arka uç sunucuya iletir. Sahte kaynaklı SYN'ler proxy'de ölür.
- **Anti-spoofing (BCP 38 / kaynak adres doğrulama):** İdeal olarak ISP'ler kendi ağlarından çıkan, kaynağı o ağa ait olmayan paketleri (spoofed) filtrelemelidir. Bu, spoofing tabanlı saldırıların kökünü kurutur ama tek bir kurumun kontrolünde değildir; internet çapında eksik uygulanması amplifikasyon saldırılarının da temel sebebidir.

---

## Amplifikasyon (Yansıtma) Saldırıları: Küçük Soru, Devasa Cevap

### Kök Neden ve Çalışma Mantığı

Amplifikasyon saldırıları, iki zafiyeti birleştirir:

1. **IP kaynak adresi sahteciliği (spoofing):** UDP bağlantısız (connectionless) olduğundan el sıkışma yoktur; bir paketin kaynak adresi kolayca yalan söyleyebilir. Saldırgan, gönderdiği isteğin kaynak IP'sine **kurbanın IP'sini** yazar.
2. **Amplifikasyon faktörü yüksek, açık (public) UDP servisleri:** Bazı protokollerde **küçük bir istek çok büyük bir yanıt** üretir. Saldırgan, internetteki açık (yanlış yapılandırılmış) sunuculara küçük bir istek gönderir; bu sunucu koca yanıtı **kurbanın adresine** gönderir.

Böylece saldırgan trafiği **yansıtır (reflection)** ve **büyütür (amplification)**. Saldırgan kendi bant genişliğinin çok üstünde bir trafiği kurbana yöneltebilir. Ayrıca gerçek saldırgan gizlenir; kurbanın gördüğü trafik masum yansıtıcı (reflector) sunuculardan gelir.

**Amplifikasyon faktörü**, "yanıt boyutu / istek boyutu" oranıdır. Bu oran protokole göre değişir ve bazı protokollerde onlarca hatta yüzlerce kata ulaşabilir. Klasik yansıtma vektörleri şunlardır (mekanizmayı anlamak için):

- **DNS amplifikasyonu:** Küçük bir DNS sorgusu (özellikle `ANY` tipi ya da DNSSEC nedeniyle büyümüş yanıtlar), açık **DNS resolver**'lardan büyük yanıtlar aldırır.
- **NTP amplifikasyonu:** Bazı NTP sunucularındaki `monlist` benzeri (son bağlanan istemcileri listeleyen) komutlar, tek istekle çok büyük yanıt döndürebildiği için tarihsel olarak yüksek amplifikasyon sağlamıştır.
- **SSDP, SNMP, Memcached, CLDAP** gibi diğer UDP tabanlı servisler de yanlış yapılandırıldığında yansıtıcı olarak kötüye kullanılmıştır. Memcached tabanlı olaylar, çok yüksek amplifikasyon faktörleriyle rekor düzeyde saldırı hacimlerine yol açmıştır.

> Not: Yukarıdaki amplifikasyon faktörü değerleri protokol ve yapılandırmaya göre çok değişkendir; tek bir "kesin" sayı ezberlemek yerine mekanizmayı — küçük istek, büyük yanıt, sahte kaynak — anlamak önemlidir.

### Örnek Senaryo

Saldırgan, kaynak IP'si kurbanın adresi olacak şekilde, açık bir DNS resolver'a küçük bir sorgu gönderir. Resolver, sorguya karşılık gelen büyük yanıtı **kurbana** gönderir. Bunu binlerce açık resolver'a, saniyede yüz binlerce sahte istekle çarparsanız, kurbanın erişim hattı çok büyük bir UDP yanıt seliyle boğulur. Kurban, gerçek saldırganı hiç görmez; yalnızca dünyanın dört bir yanındaki DNS sunucularından gelen "cevap" trafiğini görür.

### Tespit

- **Beklenmeyen yanıt trafiği:** İstemediğiniz halde gelen büyük hacimli UDP yanıtları (örneğin hiç DNS sorgusu yapmadığınız halde gelen DNS yanıt paketleri — kaynak port 53).
- **Tek protokol/port yoğunlaşması:** Trafiğin belirli bir kaynak porta (53, 123, 1900, 11211 vb.) kilitlenmesi.
- **Paket boyutu profili:** Anormal büyük, tekdüze UDP paketleri.
- **Kaynak IP çeşitliliği:** Çok sayıda meşru ama alakasız sunucu (yansıtıcılar).

### Savunma

- **Bant genişliği ötesinde filtreleme gerekir:** Hacimsel saldırılar hedefin erişim hattını **hattın kendisinden önce** doldurabildiği için, savunmanın büyük kısmı **upstream** (ISP/temizleme merkezi/CDN) tarafında yapılmalıdır. Kurumun kendi firewall'unda filtrelemek çoğu zaman geç kalmış olur — çünkü hat zaten dolmuştur.
- **Kullanılmayan UDP portlarını/protokolleri kenarda düşürmek:** Erişim listeleriyle (ACL) beklenmeyen UDP yanıt trafiğini bloklamak.
- **Yansıtıcı olmamak (kurumsal sorumluluk):** Kendi DNS/NTP/SNMP/Memcached sunucularınızı internete **açık resolver / açık servis** olarak bırakmayın. Yetkili DNS sunucunuz rekürsiyonu herkese açmasın; NTP sunucunuz `monlist` benzeri komutları devre dışı bıraksın; Memcached UDP'ye internetten erişilemesin. Bu, sizi hem saldırı aracı olmaktan hem de itibar kaybından korur.
- **BCP 38 (kaynak adres doğrulama):** Sahtecilik olmadan yansıtma saldırıları çalışamaz. ISP düzeyinde egress/ingress filtreleme bu saldırı sınıfının kökünü kurutur.
- **Response Rate Limiting (RRL):** Yetkili DNS sunucularında aynı yanıtı aynı ağa aşırı sıklıkta göndermeyi sınırlayan mekanizma, sunucunuzun yansıtıcı olarak istismarını azaltır.

---

## Savunma Mimarisi: Scrubbing, Rate-Limiting, Anycast ve BGP

Ağ tabanlı DDoS savunması tek bir cihaza değil, **katmanlı bir mimariye** dayanır. Temel bileşenler:

### Scrubbing (Temizleme) Merkezleri

**Scrubbing center**, saldırı trafiğini "temizleyen" özel bir tesistir. Mantık şudur: Saldırı anında hedefe giden trafik, hedefe ulaşmadan önce büyük kapasiteli bir temizleme merkezine **yönlendirilir**. Bu merkez, kötü niyetli paketleri (saldırı imzaları, davranış anomalileri, kara listeler) ayıklar; yalnızca **temiz trafiği** hedefe iletir (buna "clean pipe" denir).

Yönlendirme iki yolla yapılır:

- **BGP yönlendirmesi (on-demand):** Saldırı algılandığında, hedef IP bloğunun (prefix) yönlendirilmesi BGP anonsuyla scrubbing sağlayıcısına çekilir. Temizlenen trafik, hedefe genellikle **GRE tüneli** ya da özel bir bağlantıyla geri gönderilir. Bu model, saldırı yokken trafiğin dolambaçlı yol izlemesini önler (always-on değil, gerektiğinde devreye girer).
- **DNS yönlendirmesi:** Hedefin DNS kaydı, trafiği temizleme sağlayıcısının IP'lerine yönlendirecek şekilde değiştirilir (genellikle proxy/CDN tabanlı korumada).

### Rate-Limiting (Hız Sınırlama)

Belirli bir kaynaktan, belirli bir protokolden veya belirli bir istek tipinden gelen trafiği bir eşiğin üzerinde **kısıtlamak** ya da düşürmektir. Örnekler: saniyede belirli sayının üstündeki SYN'leri düşürmek, aynı IP'den gelen istekleri sınırlamak, belirli bir URL'ye gelen istek oranını dizginlemek.

**Kritik uyarı — meşru trafiği kesme riski:** Rate-limiting kör uygulanırsa **meşru kullanıcıları da cezalandırır**. Dağıtık bir saldırıda kötü trafik binlerce IP'ye yayıldığı için IP başına sınır koymak yeterince ayırt edici olmayabilir. Bu yüzden rate-limiting, davranışsal profil çıkarma ve challenge mekanizmalarıyla (örneğin şüpheli istemciye bir doğrulama adımı sunmak) birlikte kullanılır. Rate-limiting bir başlangıç savunmasıdır, tek başına yeterli bir çözüm değildir.

### Anycast: Saldırıyı Coğrafi Olarak Dağıtmak

**Anycast**, aynı IP adresinin **birden çok coğrafi konumdaki** (PoP — Point of Presence) sunucular tarafından, BGP üzerinden aynı anda anons edilmesidir. İnternetin yönlendirme mantığı gereği, her kullanıcının trafiği kendisine **topolojik olarak en yakın** PoP'a gider.

DDoS savunmasındaki dahiyane etkisi şudur: Saldırı trafiği tek bir noktaya yığılmak yerine, saldırgan botnet'in coğrafi dağılımına göre **birçok PoP arasında otomatik olarak bölünür**. 10 PoP'unuz varsa, teorik olarak her PoP saldırının yalnızca bir kısmını görür. Böylece:

- Toplam absorbe kapasite, tüm PoP'ların kapasitesinin toplamı kadar olur.
- Bir PoP çökse bile diğerleri hizmet vermeye devam eder (saldırının etkisi **coğrafi olarak izole edilir**).
- Saldırgan, hedefi tek bir fiziksel noktada boğamaz.

Anycast, büyük DNS altyapılarının ve CDN'lerin DDoS'a karşı dayanıklılığının temel taşıdır. Ancak dikkat: Anycast, oturum durumu (state) tutan protokollerde yönlendirme değişiklikleri sırasında bağlantı sürekliliği konusunda özen ister; genellikle DNS gibi durumsuz veya kısa ömürlü işlemler ve CDN kenarları için idealdir.

### BGP Tabanlı Acil Önlem: RTBH (Remotely Triggered Black Hole)

Aşırı durumlarda, saldırı altındaki tek bir IP'ye giden **tüm trafiği** (iyi + kötü) upstream'de düşürmek için BGP kullanılır. **RTBH (uzaktan tetiklenen kara delik)**, hedef IP'yi bir "null route"a (hiçbir yere gitmeyen rota) yönlendirir. Bunun acı gerçeği: Bu, **saldırının amacını kısmen gerçekleştirir** — o IP artık kimseye hizmet vermez. Ama mantık şudur: Tek bir kurban IP'yi feda ederek, o saldırının **paylaşılan altyapının** (ve diğer müşterilerin/servislerin) geri kalanını çökertmesini önlersiniz. RTBH, cerrahi bir çözüm değil, hasar kontrol aracıdır. Daha ince ayarlı bir varyantı olan **BGP FlowSpec**, sadece bir IP'yi tümüyle karartmak yerine belirli akış kriterlerine (port, protokol, paket boyutu) göre filtreleme kurallarını BGP üzerinden yayabilir — böylece meşru trafiğin bir kısmını kurtarmak mümkün olur.

---

## Katmanlı Savunma: Bir Bütün Olarak

Sağlam bir DDoS savunması bu bileşenleri sıralı katmanlar hâlinde birleştirir:

1. **Upstream / bulut ölçekli absorpsiyon:** Hacimsel saldırılar için CDN veya scrubbing sağlayıcısı ilk hattır. Kurumsal internet bağlantınızın kapasitesi asla bir Tbps'lik saldırıyı absorbe edemez; bu iş **hattınızdan önce** yapılmalıdır.
2. **Ağ kenarı (edge) filtreleme:** ACL'ler, anti-spoofing, kullanılmayan protokol/portların düşürülmesi, FlowSpec/RTBH ile acil müdahale.
3. **Protokol düzeyi sertleştirme:** SYN cookies, SYN proxy, backlog ayarları, RRL.
4. **Uygulama katmanı koruması:** WAF, davranışsal analiz, challenge mekanizmaları, oran sınırlama (L7 saldırıları için).
5. **Görünürlük ve tespit:** NetFlow/IPFIX, akış anomalisi tespiti, baseline (normal trafik profili) çıkarma ve eşik/anomali tabanlı alarm. **Tespit edemediğinizi savunamazsınız** — bu yüzden trafik görünürlüğü savunmanın önkoşuludur.
6. **Runbook ve hazırlık:** Saldırı anında kimin ne yapacağı, sağlayıcı iletişim kanalları, BGP yönlendirme prosedürleri önceden yazılı olmalı. Saldırı anı, mimari kurma zamanı değildir.

---

## Yaygın Hatalar ve Yanlış Anlamalar

- **"Firewall'um DDoS'u durdurur" yanılgısı:** Geleneksel stateful firewall, hacimsel saldırıda **ilk çöken bileşenlerden biridir**; çünkü her bağlantı için state tutar ve durum tablosu saldırıyla dolar. Firewall'un kendisi bir hedef hâline gelir. DDoS savunması, firewall'dan önce ve upstream'de başlamalıdır.
- **Kapasiteyi tek başına savunma sanmak:** "Daha çok bant genişliği alırım" yaklaşımı, hacimsel saldırıların ulaştığı ölçeklere karşı ekonomik olarak sürdürülemez. Absorpsiyon değil, dağıtım (anycast) ve filtreleme (scrubbing) gerekir.
- **Anti-spoofing'i (BCP 38) önemsememek:** Kendi ağınızdan sahte kaynaklı paket çıkmasına izin vermek, sizi tüm internetin amplifikasyon saldırılarına dolaylı ortak yapar. Egress filtreleme temel bir hijyen kuralıdır.
- **Açık servis bırakmak:** İnternete açık, rekürsif DNS resolver, `monlist` açık NTP, korumasız Memcached/SNMP bırakmak sizi hem yansıtıcı (başkalarına saldırı aracı) hem de itibar/kaynak kaybı riski altına sokar.
- **Rate-limiting'i kör uygulamak:** Aşırı agresif hız sınırlama, saldırı sırasında meşru kullanıcıları da dışarıda bırakır — yani saldırganın işini bir bölümüyle sizin adınıza tamamlar. Sınırlar, davranış analizi ve challenge ile ince ayarlanmalı.
- **L7 saldırılarını hacimle ölçmek:** Uygulama katmanı saldırıları düşük bps/pps ile gelebilir ama pahalı işlemlerle sunucuyu boğar. Sadece bant genişliği grafiğine bakan bir izleme, bu saldırıyı **hiç fark etmeyebilir**. İstek başına maliyet ve backend doygunluğu da izlenmelidir.
- **Saldırı anında plan yapmaya çalışmak:** Scrubbing sözleşmesi, BGP prosedürleri ve iletişim kanalları önceden hazır değilse, müdahale saatlerce gecikir. Hazırlık, saldırı öncesi yapılır.

---

## Özet

Ağ tabanlı DoS/DDoS saldırıları erişilebilirliği hedef alan kaynak tüketme saldırılarıdır ve üç ana sınıfta incelenir: hacimsel (bant genişliği), protokol (durum tablosu) ve uygulama katmanı. **SYN flood**, TCP el sıkışmasının yarı açık bağlantı kuyruğunu sömürür; başlıca savunması **SYN cookies** ve SYN proxy'dir. **Amplifikasyon saldırıları**, IP sahteciliği ile açık UDP servislerini birleştirerek küçük istekleri büyük, yansıtılmış saldırılara dönüştürür; başlıca savunma açık servis bırakmamak, upstream filtreleme ve BCP 38'dir. Modern savunma mimarisi **scrubbing merkezleri**, **rate-limiting**, **anycast** ve **BGP tabanlı yönlendirme (RTBH/FlowSpec)** katmanlarını birleştirir. Temel ilke değişmez: Savunma hedefin erişim hattından **önce**, upstream'de ve **dağıtık** olarak kurulmalı; görünürlük ve hazırlık ise savunmanın olmazsa olmaz önkoşuludur.
