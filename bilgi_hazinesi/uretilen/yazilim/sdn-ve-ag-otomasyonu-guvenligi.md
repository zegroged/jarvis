# SDN ve Ağ Otomasyonu Güvenliği (OpenFlow, Ağ Telemetri Protokolleri: NetFlow/sFlow/gNMI)

## Giriş ve Bağlam

Geleneksel ağlarda her switch/router hem *nereye paket göndereceğine karar veren* mantığı (control plane) hem de *paketi fiilen ileten* donanımı (data plane) kendi içinde barındırır. **SDN (Software-Defined Networking)** bu iki düzlemi ayırır: karar verme mantığı, ağın dışındaki merkezî bir yazılıma — **SDN controller**'a — taşınır; switch'ler ise controller'ın kendilerine yüklediği akış kurallarını (flow rules) uygulayan "aptal" iletim elemanlarına dönüşür.

Bu ayrım muazzam esneklik getirir: bir tek noktadan tüm ağın davranışını programlayabilirsiniz. Ancak aynı ayrım, güvenlik açısından yeni ve geniş bir saldırı yüzeyi açar. Kontrol düzlemi artık ağdaki tek bir yazılımda merkezîleşmiştir; o yazılım düşerse veya ele geçirilirse tüm ağ tehlikeye girer. Buna paralel olarak, modern ağların gözlemlenebilirliği (observability) için kullanılan **NetFlow, sFlow, gNMI/gRPC telemetry** gibi protokoller, ağ hakkında son derece hassas bilgi taşır ve çoğu zaman güvenlik kontrolü açısından ihmal edilir.

Bu makale, SDN kontrol düzlemi mimarisini, OpenFlow'un çalışma mantığını, telemetri protokollerinin farklarını, bunlara yönelik tehdit modellerini ve **tespit/savunma** yaklaşımlarını uzman seviyesinde açıklar.

---

## Bölüm 1: SDN Mimarisi ve OpenFlow

### 1.1 Üç Düzlemli Model

SDN mimarisi kavramsal olarak üç katmana ayrılır:

- **Data plane (veri düzlemi):** Paketleri fiilen ileten switch'ler. OpenFlow switch'lerinde bu, bir dizi *flow table*'dan oluşur.
- **Control plane (kontrol düzlemi):** Merkezî controller (ör. ONOS, OpenDaylight, Ryu, Faucet). Ağın topolojisini öğrenir, yol hesaplar, switch'lere kural yazar.
- **Management/application plane:** Controller'ın kuzey arayüzü (northbound API, genelde REST/gRPC) üzerinden çalışan uygulamalar; trafik mühendisliği, firewall, load balancing gibi işlevleri programlar.

İki kritik arayüz vardır:
- **Southbound interface:** Controller ile switch arasındaki protokol. En yaygını **OpenFlow**'dur (ayrıca NETCONF, OVSDB, P4Runtime, gNMI de kullanılır).
- **Northbound interface:** Controller ile uygulamalar arasındaki API.

### 1.2 OpenFlow'un Çalışma Mantığı

OpenFlow, controller ile switch arasında TCP tabanlı (varsayılan olarak TLS ile korunması *önerilen*) bir kanal kurar. Switch'teki her **flow entry** kabaca şu bileşenlerden oluşur:

- **Match fields:** Hangi paketlere uyacağı (ör. kaynak/hedef MAC, IP, port, VLAN, ingress port).
- **Priority:** Birden fazla kural eşleştiğinde hangisinin kazanacağı.
- **Instructions/Actions:** Eşleşen pakete ne yapılacağı (forward to port, drop, modify header, send to controller vb.).
- **Counters, timeouts:** İstatistik ve kuralın ne kadar yaşayacağı.

Kritik mekanizma **`PACKET_IN`** olayıdır: switch, hiçbir flow entry ile eşleşmeyen bir paket gördüğünde (table-miss), paketi (ya da başlığını) controller'a gönderir ve "bununla ne yapayım?" diye sorar. Controller karar verir, gerekirse switch'e yeni bir flow kuralı yükler (**`FLOW_MOD`**) ve paketi geri gönderir (**`PACKET_OUT`**). Bu "reactive" model, SDN'in en zarif ama aynı zamanda en kırılgan yanıdır.

### 1.3 Kök Neden: Merkezîleşmenin İkili Doğası

SDN'in gücü de zaafı da aynı yerden gelir: **kontrol düzleminin merkezîleşmesi**. Geleneksel dağıtık ağda bir switch'i ele geçirmek yereldir; SDN'de controller'ı ele geçirmek tüm ağı ele geçirmektir. Ayrıca `PACKET_IN`/`FLOW_MOD` döngüsü, switch ile controller arasında sürekli bir bağımlılık yaratır. Bu döngü, birazdan göreceğimiz en tipik saldırının hedefidir.

---

## Bölüm 2: Kontrol Düzlemi Saldırıları ve Savunma

### 2.1 Control Plane Saturation (PACKET_IN Flood)

**Mekanizma:** Saldırgan, veri düzleminde sürekli olarak *hiçbir mevcut kuralla eşleşmeyecek* paketler üretir — tipik olarak her paket için farklı, sahte (spoofed) başlıklar kullanır. Her yeni akış bir table-miss'e, dolayısıyla bir `PACKET_IN` mesajına yol açar. Sonuç:

1. Switch ile controller arasındaki **southbound kanal** doygunluğa ulaşır.
2. Controller'ın işlemci ve bellek kaynakları tükenir.
3. Switch'in `PACKET_IN` üretmek için kullandığı sınırlı buffer'ı taşar.
4. Flow table'lar sahte kurallarla dolar (TCAM tükenmesi).

Bu, klasik bir DoS'tur ama SDN'e özgüdür: saldırı bant genişliğini değil, *kontrol düzleminin karar verme kapasitesini* hedefler. Nispeten düşük trafikle bile controller'ı çökertebilir; çünkü darboğaz veri düzlemi kapasitesi değil, controller'ın akış-başına işlem yükü ve southbound kanaldır.

**Tespit:**
- `PACKET_IN` mesaj oranını switch ve controller bazında ölçün. Ani, süreklilik gösteren yükselişler ve *çok sayıda kısa ömürlü, tek paketlik akış* güçlü bir işarettir.
- Flow table doluluk oranını (özellikle TCAM kullanımı) izleyin.
- Akış giriş oranı ile gerçekleşen "tamamlanmış" akış oranı arasındaki uçurumu izleyin: normal trafikte akışlar birden çok paket taşırken saldırıda çoğu akış tek pakettir.

**Savunma:**
- **Rate limiting:** Switch başına `PACKET_IN` oranını sınırlayın; birçok controller ve OVS bunu destekler. Bir sınıra ulaşınca fazlasını controller'a taşımadan drop edin.
- **Proactive flow installation:** Mümkün olduğunca reactive değil, önceden (proactive) kural yükleyin; table-miss oranını düşürür.
- **Table-miss davranışını sıkılaştırma:** Bilinmeyen trafiği controller'a göndermek yerine, güvenli varsayılan olarak drop edin veya sınırlı bir "learning" tablosuna yönlendirin.
- Bu sınıf saldırıyı hafifletmek için akademik/endüstriyel öneriler (ör. ilk paketleri agregeleyip filtreleyen ara katmanlar) vardır; ilke şudur: *table-miss'i controller'a taşımadan önce yerelde eleme yap*.

### 2.2 Topology Poisoning (Sahte Bağlantı Enjeksiyonu)

**Mekanizma:** Controller'lar ağ topolojisini genellikle **LLDP** (Link Layer Discovery Protocol) paketlerini switch'ler arasında dolaştırarak öğrenir: controller bir switch'e LLDP paketi enjekte eder (`PACKET_OUT`), komşu switch onu alınca controller'a geri bildirir (`PACKET_IN`) ve controller "bu iki port arasında bir link var" sonucuna varır. Bu mekanizma güvenli değildir:

- **LLDP injection/relay:** Saldırgan sahte LLDP paketleri üreterek ya da meşru LLDP'yi kopyalayıp uzak bir noktaya tünelleyerek (relay), var olmayan bir bağlantı varmış gibi controller'ı kandırabilir. Controller bu "sahte link" üzerinden trafik yönlendirmeye başlar; bu, man-in-the-middle veya kara delik (blackhole) yaratabilir.
- **Host Location Hijacking:** Controller, hostların hangi porta bağlı olduğunu paketlerden öğrenir. Saldırgan bir kurbanın MAC/IP'sini spoofladığında, controller hostun "taşındığını" düşünüp trafiği saldırgana yönlendirebilir.

**Tespit ve savunma:**
- **LLDP bütünlüğü:** LLDP paketlerine controller tarafından doğrulanabilir bir imza/nonce ekleyin (bazı controller'larda TopoGuard benzeri korumalar bu fikri uygular). Böylece kopyalanmış/enjekte edilmiş LLDP tespit edilir.
- **Port tipi doğrulama:** Host'ların bağlı olduğu portlardan LLDP gelmemelidir; switch-to-switch link'lerinden host trafiği beklenmemelidir. Tutarsızlık alarm üretmelidir.
- **Host migration doğrulama:** Bir hostun konum değişikliği iddiası geldiğinde, eski konumun gerçekten "gittiğine" dair kanıt (ör. port down) arayın; anında kabul etmeyin.

### 2.3 Southbound Kanalın Güvenliği (TLS)

**Kök sorun:** OpenFlow, TLS'i *destekler* ama tarihsel olarak birçok kurulumda düz TCP (6653/eski 6633 portu) ile çalıştırılmıştır. TLS'siz southbound kanalda:

- Saldırgan, controller ile switch arasına girip `FLOW_MOD` mesajları enjekte ederek keyfî kural yazabilir.
- Trafiği izleyerek tüm ağ politikasını öğrenebilir.
- Sahte bir controller'ı switch'e tanıtabilir (rogue controller).

**Savunma:**
- Southbound için **karşılıklı TLS (mutual TLS)** zorunlu kılın: hem controller hem switch birbirini sertifikayla doğrulasın. Tek taraflı doğrulama yetmez; sahte switch de bir tehdittir.
- Kontrol düzlemi trafiğini ayrı, izole bir yönetim ağında (out-of-band management network) taşıyın. Kontrol trafiği veri trafiğiyle aynı düzlemde akmamalıdır.
- Sertifika yaşam döngüsünü (rotation, revocation) yönetin; uzun ömürlü, paylaşılan sertifikalardan kaçının.

### 2.4 Northbound API ve Controller Sertleştirme

Controller'ın kuzey arayüzü genellikle bir REST/gRPC API'dir ve tüm ağı programlama gücüne sahiptir. Bu, uygulama katmanı güvenliğinin klasik kurallarının burada hayatî olduğu anlamına gelir:

- **Kimlik doğrulama ve yetkilendirme:** Her northbound çağrısı güçlü kimlik doğrulamadan geçmeli; farklı uygulamalara en az ayrıcalık (least privilege) ilkesiyle sınırlı yetkiler verilmelidir. Bir "load balancer" uygulamasının firewall kurallarını silebilmesi tehlikelidir.
- **Uygulama izolasyonu:** Kötü niyetli veya hatalı bir SDN uygulaması, controller üzerinden çelişkili kurallar yükleyerek ağı bozabilir. Kural çakışması tespiti (flow rule conflict detection) ve uygulama bazlı izolasyon önemlidir.
- **Controller yazılım güvenliği:** Controller sonuçta bir yazılımdır — bağımlılık güvenliği, kimlik doğrulama zafiyetleri, varsayılan kimlik bilgileri (default credentials) hepsi geçerli tehditlerdir. Yönetim arayüzlerini asla internete açık ve varsayılan parolayla bırakmayın.

---

## Bölüm 3: Ağ Telemetri Protokolleri

Modern ağ gözlemlenebilirliği, ağın "ne yaptığını" görmek için farklı protokoller kullanır. Bunların çalışma modelleri ve güvenlik nitelikleri belirgin biçimde farklıdır.

### 3.1 NetFlow (ve IPFIX)

**Ne yapar:** NetFlow (Cisco kökenli; standartlaşmış hâli **IPFIX**), router/switch üzerinden geçen trafiği *akışlar* (flows) hâlinde özetler. Bir akış, aynı 5'li anahtarı (kaynak IP, hedef IP, kaynak port, hedef port, protokol) paylaşan paketler kümesidir. Cihaz, her akış için paket/bayt sayısı, başlangıç/bitiş zamanı gibi meta verileri biriktirir ve periyodik olarak bir **collector**'a UDP ile gönderir.

**Kritik nokta:** NetFlow paket *içeriğini* (payload) değil, *meta veriyi* taşır. Yani "kim kiminle, ne kadar, hangi portta konuştu" bilgisini verir — güvenlik izleme için son derece değerli, çünkü şifreli trafiği bile görünür kılar (içeriği değil ama iletişim desenini).

**Çalışma mantığı ve tuzaklar:**
- **Sampling:** Yüksek hızlı bağlantılarda her paketi işlemek pahalıdır; bu yüzden çoğu kurulum örnekleme yapar (ör. her N paketten birini). Örneklenmiş NetFlow, *hacim tahmini* için iyidir ama *az sayıda paketten oluşan* saldırıları (ör. tek paketlik port taraması) kaçırabilir. Güvenlik amaçlı analiz için örnekleme oranını bilmek şarttır.
- **UDP transport:** NetFlow tipik olarak UDP ile taşınır — güvenilmez ve doğrulanmamıştır. Bu iki soruna yol açar: (1) yoğunlukta kayıp; (2) **spoofing**. Saldırgan, collector'a sahte NetFlow kayıtları enjekte ederek görünürlüğü kirletebilir veya alarmları bastırabilir.

**Savunma:**
- NetFlow trafiğini ayrı bir yönetim ağında taşıyın ve collector'a yalnızca bilinen exporter IP'lerinden veri kabul edin (kaynak doğrulama).
- Örnekleme oranını dokümante edin ve güvenlik analizinde hesaba katın.
- Kayıtları başka kaynaklarla (firewall log, DNS, sFlow) çapraz doğrulayın; tek kaynağa güvenmeyin.

### 3.2 sFlow

**Ne yapar:** sFlow (sampled flow) farklı bir felsefe izler. NetFlow cihazda akış tablosu tutup özet üretirken, sFlow **paket örnekleme** yapar: her N paketten birinin *başlığından bir kesit* (ilk birkaç yüz bayt) doğrudan collector'a gönderilir. Ayrıca arayüz sayaçlarını periyodik örnekler.

**NetFlow ile fark:**
- sFlow *ham paket örnekleri* gönderir; collector analizi kendi yapar. NetFlow *cihazda özetlenmiş akışlar* gönderir.
- sFlow tasarımı gereği donanımda çok hafiftir (stateless örnekleme), bu yüzden çok yüksek hızlarda ölçeklenir; genellikle switch ASIC'lerinde yaygın desteklenir.
- sFlow ilk baytları taşıdığı için başlık düzeyinde daha zengin görünürlük verir; ama örnekleme nedeniyle yine istatistikseldir, her paketi görmez.

**Güvenlik nitelikleri:** sFlow da tipik olarak UDP ile taşınır ve NetFlow ile aynı spoofing/kayıp risklerini paylaşır. Örnekleme oranı, saldırı tespiti hassasiyetini doğrudan belirler: düşük örnekleme (ör. 1/2000) düşük hacimli saldırıları büyük olasılıkla kaçırır.

**Doğru kullanım:** sFlow'u geniş, yüksek hızlı ağlarda *hacimsel* anomali tespiti (DDoS, ani trafik patlamaları) için kullanın; adli inceleme veya tam görünürlük gerektiren durumlarda örneklemenin sınırını kabul edin.

### 3.3 gNMI ve gRPC Tabanlı Streaming Telemetry

**Ne yapar:** **gNMI (gRPC Network Management Interface)**, modern ağ yönetimi ve telemetrinin yeni nesil protokolüdür. NetFlow/sFlow *trafiği* özetlerken, gNMI *cihazın kendi durumunu* (state) modeller: arayüz sayaçları, CPU, kuyruk derinlikleri, BGP oturum durumu, sıcaklık gibi operasyonel veriyi **YANG** veri modelleriyle yapılandırılmış biçimde sunar.

**Çalışma mantığı — "streaming telemetry":** Geleneksel SNMP polling'de yönetim sistemi cihazı düzenli aralıklarla *sorar* ("CPU kaç?"). Bu, hem gecikmeli hem verimsizdir. gNMI **push/subscribe** modelini destekler: yönetim sistemi bir kez abone olur, cihaz veriyi değiştiğinde veya belirlenen aralıkla *kendisi iter*. Sonuç: çok daha yüksek çözünürlüklü, düşük gecikmeli görünürlük.

gNMI dört temel işlem sunar (kavramsal olarak): `Get` (anlık durum), `Set` (yapılandırma değiştir), `Subscribe` (streaming telemetri), `Capabilities` (desteklenen modeller). Kritik nokta: **gNMI hem telemetri hem yapılandırma protokolüdür**. `Set` işlemi cihazı yeniden yapılandırabilir — yani gNMI bir okuma kanalı değil, tam kontrol kanalıdır.

**Güvenlik nitelikleri — burada iyi haber var:** gNMI **gRPC üzerine kuruludur** ve gRPC de **HTTP/2 + TLS** üzerine. Yani gNMI, NetFlow/sFlow'un aksine tasarımı gereği **şifreli ve kimlik doğrulamalı** taşımaya sahiptir. Bu, telemetri protokolleri arasında güvenlik açısından önemli bir sıçramadır.

**Tuzaklar ve savunma:**
- **`Set` yetkisinin ayrılması:** Telemetri (okuma) için verilen gNMI kimlik bilgileri, `Set` (yazma) yetkisini içermemelidir. Bir izleme sistemi ele geçirilirse, salt-okunur olması cihazı yeniden yapılandırmasını engeller. En az ayrıcalık ilkesini gNMI seviyesinde uygulayın.
- **TLS'i gerçekten doğrulayın:** gRPC TLS destekler ama yanlış yapılandırmada sertifika doğrulaması devre dışı bırakılabilir (insecure/`skip-verify`). Bu, şifrelemeyi görünüşte korurken MITM'e açık bırakır. Sunucu (ve tercihen istemci) sertifikası doğrulanmalıdır.
- **YANG modeli hassasiyeti:** gNMI, cihazın iç durumu hakkında zengin bilgi verir; bu telemetri akışına erişen bir saldırgan ağ topolojisi, güvenlik cihazı durumları ve zafiyet ipuçları elde edebilir. Telemetri kanalını da hassas veri olarak sınıflandırın.

### 3.4 Üç Protokolü Karşılaştırma

| Boyut | NetFlow/IPFIX | sFlow | gNMI |
|---|---|---|---|
| Ne taşır | Cihazda özetlenmiş akış meta verisi | Ham paket örnekleri + sayaçlar | Yapılandırılmış cihaz durumu (YANG) |
| Model | Akış tabanlı, çoğunlukla örneklemeli | Paket örneklemeli | Durum tabanlı, subscribe/push |
| Taşıma | UDP (genelde şifresiz) | UDP (genelde şifresiz) | gRPC/HTTP2 + TLS |
| Güvenlik | Zayıf: spoofing/kayıp riski | Zayıf: spoofing/kayıp riski | Güçlü: TLS + auth (doğru yapılandırılırsa) |
| Yön | Salt okuma (telemetri) | Salt okuma (telemetri) | Okuma **ve yazma** (`Set`) |
| En iyi kullanım | İletişim deseni analizi | Yüksek hızda hacimsel anomali | Yüksek çözünürlüklü durum izleme |

---

## Bölüm 4: Yaygın Hatalar ve Kontrol Listesi

**En sık yapılan hatalar:**

1. **Southbound'u TLS'siz çalıştırmak.** OpenFlow'u düz TCP ile bırakmak, tüm kontrol düzlemini enjeksiyona açar. Her zaman mutual TLS ve out-of-band yönetim ağı.
2. **Reactive flow'a aşırı bağımlılık.** Her table-miss'i controller'a taşımak, `PACKET_IN` flood'una davetiye çıkarır. Proactive kurallar ve rate limiting şart.
3. **Telemetri protokollerini "sadece izleme, zararsız" saymak.** NetFlow/sFlow verisi ağın tüm iletişim haritasıdır; sızması istihbarat sızmasıdır. gNMI ise `Set` ile *cihazı değiştirebilir*. Telemetri kanalları da erişim kontrolü ve segmentasyon gerektirir.
4. **Collector'da kaynak doğrulaması yapmamak.** UDP tabanlı NetFlow/sFlow, sahte kayıtlarla zehirlenebilir. Yalnızca bilinen exporter'lardan veri kabul edin, izole ağda taşıyın.
5. **gNMI'de TLS doğrulamasını kapatmak.** "Çalışsın diye" `skip-verify` kullanmak, şifrelemenin güvenlik değerini sıfırlar. MITM yeniden mümkün olur.
6. **Örnekleme oranını göz ardı etmek.** Örneklemeli telemetriye dayanan bir tespit sistemi, düşük hacimli ama kritik saldırıları (yavaş tarama, tek paketlik keşif) sessizce kaçırabilir. Örnekleme oranını bilmeden yapılan güvenlik analizi yanıltıcıdır.
7. **Controller'ı tek arıza noktası bırakmak.** Merkezîleşme hem saldırı hem arıza için tek noktadır. Controller kümesi (cluster), yüksek erişilebilirlik ve state senkronizasyonu planlanmalıdır; aksi hâlde bir DoS tüm ağı düşürür.

**Savunma kontrol listesi:**
- [ ] Southbound (OpenFlow/gNMI) mutual TLS ile korunuyor mu?
- [ ] Kontrol ve telemetri trafiği out-of-band yönetim ağında mı?
- [ ] `PACKET_IN` rate limiting ve TCAM doluluk izleme aktif mi?
- [ ] LLDP topoloji öğrenme, enjeksiyon/relay'e karşı sertleştirildi mi?
- [ ] Northbound API en az ayrıcalık ve güçlü kimlik doğrulama ile mi çalışıyor?
- [ ] NetFlow/sFlow collector'ları yalnızca bilinen exporter'ları kabul ediyor mu?
- [ ] gNMI telemetri kimlik bilgileri salt-okunur mu (`Set` ayrı)?
- [ ] gNMI'de sertifika doğrulaması gerçekten açık mı?
- [ ] Örnekleme oranları biliniyor ve tespit hassasiyetine dahil ediliyor mu?

---

## Sonuç

SDN ve ağ otomasyonunun temel gerilimi tek cümlede özetlenebilir: **merkezîleşme, programlanabilirlik kazandırır ama saldırı ve arıza yüzeyini tek bir noktaya toplar.** OpenFlow'un `PACKET_IN`/`FLOW_MOD` döngüsü ve LLDP tabanlı topoloji öğrenmesi, doğru sertleştirilmezse kontrol düzlemini doğrudan istismara açar. Telemetri tarafında ise nesiller arası bir güvenlik farkı vardır: NetFlow ve sFlow, güçlü görünürlük sunsa da UDP üzerinde şifresiz ve doğrulanmamış çalışır; gNMI ise gRPC/TLS temelinde tasarımı gereği güvenli — ama aynı zamanda `Set` ile yazma yetkisi taşıdığı için yanlış yetkilendirildiğinde daha tehlikelidir.

Doğru yaklaşım her katmanda aynıdır: kontrol ve telemetri kanallarını *hassas* kabul et, şifrele ve kimlik doğrula, out-of-band taşı, en az ayrıcalık uygula, kaynakları doğrula ve örnekleme sınırlarını bilerek izle. Bu ilkeler, hem kontrol düzlemi saldırılarını hem de gözlemlenebilirlik verisinin sızmasını birlikte azaltır.
