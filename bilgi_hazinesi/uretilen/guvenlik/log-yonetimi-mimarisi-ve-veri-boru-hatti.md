# Log Yönetimi Mimarisi ve Veri Boru Hattı

## Giriş: Neden Log Pipeline Bir Güvenlik Meselesidir?

Mavi Takım (Blue Team) uzmanlarının günlük hayatı çoğunlukla SIEM ekranlarında, tespit kuralları (detection rules) yazarken geçer. Ancak bu tespitlerin tamamı, altta sessizce çalışan bir **log yönetim mimarisine** dayanır. Eğer log toplama katmanı sağlıklı değilse, en zekice yazılmış korelasyon kuralı bile boşa çıkar: Ya log hiç gelmez, ya geç gelir, ya alanları (fields) yanlış parse edilmiştir, ya da bir saldırgan onu çoktan silmiştir.

Bu makale, bir olayın kaynağında üretilmesinden başlayıp, toplayıcı (collector) katmanından geçip, normalize edilip zenginleştirilerek (enrichment) depolanmasına kadar olan **veri boru hattını (data pipeline)** kavramsal ve mimari düzeyde ele alır. Amaç saldırı yapmak değil; loglama altyapısını **savunma dayanağı** hâline getirmek, log bütünlüğünü korumak ve maliyet ile görünürlük arasındaki dengeyi doğru kurmaktır.

---

## 1. Log Boru Hattının Anatomisi

### Tanım

Log pipeline; ham telemetriyi (raw telemetry) üreten kaynaktan (source), analiz edilebilir ve aranabilir bir depoya (store) taşıyan aşamalı işlem zinciridir. Klasik olarak beş katmandan söz ederiz:

```
Kaynak → Toplama (Collection) → Taşıma/Tampon (Transport/Buffer) → İşleme (Parse/Normalize/Enrich) → Depolama (Storage) → Sorgulama/Tespit
```

### Katmanların Çalışma Mantığı

**1. Kaynak (Source).** Log üreten her şey: işletim sistemi (Windows Event Log, Linux `journald`/`syslog`, `auditd`), uygulama logları, ağ cihazları, firewall, EDR ajanları, bulut denetim izleri (CloudTrail, Azure Activity Log, GCP Audit Logs), Kubernetes container `stdout`/`stderr`. Buradaki kritik kararlar: **hangi log seviyesinde** üretileceği ve **hangi olayların** üretileceğidir. Windows'ta örneğin Sysmon devreye alınmadan salt varsayılan Event Log ile birçok saldırı tekniği görünmez kalır.

**2. Toplama (Collection).** Log'u kaynaktan alan ajan (agent) veya toplayıcı. İki temel model vardır:
- **Push modeli:** Ajan log'u aktif olarak toplayıcıya gönderir (Fluent Bit, Vector, Winlogbeat, syslog forwarder).
- **Pull modeli:** Merkezî bir sistem kaynaktan log'u çeker (API polling, örneğin bulut denetim loglarının periyodik indirilmesi).

**3. Taşıma ve Tamponlama (Transport / Buffering).** Log kaybını önlemek için genelde araya bir mesaj kuyruğu (message queue) veya tampon konur: Kafka, Redis, ya da ajanın kendi disk tamponu. Bu katman "backpressure" (geri basınç) yönetiminin kalbidir: Depolama yavaşladığında log'lar kuyrukta birikir, hafızaya sığmazsa diske taşar (disk buffering). Bu olmadan trafik yükseldiğinde log **sessizce düşer**.

**4. İşleme (Processing).** Parse, normalizasyon ve zenginleştirmenin yapıldığı katman. Aşağıda ayrıntılı ele alınacaktır.

**5. Depolama (Storage).** Elasticsearch/OpenSearch, ClickHouse, Splunk indeksleri, Loki, veya bir data lake (S3 + Parquet). Depolama katmanının seçimi, hem sorgu performansını hem de maliyeti doğrudan belirler.

---

## 2. Normalizasyon ve Zenginleştirme

### Normalizasyon Neden Gerekli?

Farklı kaynaklar aynı kavramı farklı isimlerle ve formatlarla loglar. Bir firewall "src_ip", bir web sunucusu "client_addr", bir bulut logu "sourceIPAddress" diyebilir. Analistin bir IP adresini tek sorguyla tüm kaynaklarda araması için bu alanların **ortak bir şemaya** çekilmesi gerekir.

Bu noktada **Elastic Common Schema (ECS)** veya **Open Cybersecurity Schema Framework (OCSF)** gibi standartlar devreye girer. Örneğin ECS'te kaynak IP daima `source.ip`, hedef IP daima `destination.ip` olur. Normalizasyon; ham metni yapılandırılmış alanlara (structured fields) çevirir ve bu alanları standart isimlere haritalar (field mapping).

### Zenginleştirme (Enrichment)

Ham log çoğu zaman tespit için yetersiz bağlam taşır. Zenginleştirme, log'a **dış bilgi** ekler:

- **GeoIP:** IP adresinden coğrafi konum ve ASN türetme.
- **Threat Intelligence:** IP/hash/domain'in bir IoC (Indicator of Compromise) listesinde olup olmadığının işaretlenmesi.
- **Asset context:** Bir IP'nin hangi kritik sunucuya ait olduğu, sahibi, iş birimi.
- **Kimlik zenginleştirme:** Kullanıcı adının departman, rol, yönetici bilgisiyle eşlenmesi.
- **DNS reverse lookup, kullanıcı-cihaz ilişkilendirme.**

Zenginleştirme tespit kalitesini kökten değiştirir: "10.0.4.7'den 3 başarısız giriş" sıradan görünürken, "Domain Admin hesabıyla, normalde İstanbul'dan bağlanan kullanıcının hesabıyla, Rusya'daki bir VPS'ten giriş" alarm seviyesindedir.

### Kritik Uyarı: Zenginleştirme Zamanlaması

Zenginleştirme **ingest sırasında (write-time)** mi yoksa **sorgu sırasında (query-time)** mı yapılmalı? İkisinin de tuzağı var:
- Write-time zenginleştirme hızlı sorgu sağlar ama TI verisi sonradan güncellenirse geçmiş loglar eski bağlamla kalır.
- Query-time zenginleştirme her zaman güncel veriyle çalışır ama sorguları yavaşlatır ve dış servise bağımlılık yaratır.

Pratikte kritik, değişmeyen bağlam (asset sahipliği gibi) write-time; sık değişen TI query-time veya periyodik yeniden zenginleştirme ile ele alınır.

---

## 3. Pipeline Araçları: Fluentd, Logstash, Vector

Bu üç araç, işleme katmanının en yaygın temsilcileridir. Kavramsal olarak hepsi **girdi (input) → filtre/dönüşüm (filter/transform) → çıktı (output)** modelini izler ama karakterleri farklıdır.

### Logstash

Elastic ekosisteminin klasik işleme motoru. JVM üzerinde çalışır, `input → filter → output` yapılandırması kullanır. `grok` deseni (pattern) ile serbest metni parse etmede çok güçlüdür. Zengin filtre ekosistemi (mutate, geoip, date, dissect) vardır. Dezavantajı: JVM nedeniyle **görece ağır** olması; yüksek hacimde bellek ve CPU tüketimi. Genelde ajan olarak değil, merkezî bir işleme katmanı olarak konumlandırılır (kaynaklarda hafif Beats ajanları kullanılır).

### Fluentd / Fluent Bit

CNCF projeleri. **Fluentd** eklenti-zengin (plugin-rich) Ruby tabanlı bir toplayıcıdır; **Fluent Bit** ise C ile yazılmış, çok hafif, container ve kenar (edge) ortamları için optimize edilmiş küçük kardeşidir. Kubernetes günlükleme dünyasında fiili standart hâline gelmiştir. Fluent Bit ajan olarak node'larda çalışıp Fluentd veya doğrudan depoya iletir. Etiket-tabanlı (tag-based) yönlendirme mantığı vardır.

### Vector

Rust ile yazılmış, görece yeni ve performans odaklı bir araçtır. `sources → transforms → sinks` modeli kullanır ve dönüşümler için **VRL (Vector Remap Language)** adlı kendi dilini sunar. Yüksek verim (throughput), düşük bellek ayak izi ve güçlü disk tamponlaması öne çıkan özellikleridir. Tek bir ikili (binary) hâlinde hem ajan hem toplayıcı (aggregator) rolünü oynayabilir.

### Seçim Mantığı

| Kriter | Logstash | Fluent Bit | Vector |
|---|---|---|---|
| Kaynak ayak izi | Ağır (JVM) | Çok hafif (C) | Hafif (Rust) |
| Parse gücü | Çok yüksek (grok) | Orta | Yüksek (VRL) |
| Ekosistem | Elastic merkezli | CNCF/K8s | Vendor-agnostik |
| Tipik rol | Merkezî işleme | Edge/ajan | Her ikisi |

Doğrusu; tek bir "en iyi" yoktur. Kenar node'larda hafif Fluent Bit veya Vector, merkezde ağır dönüşümler için Logstash veya Vector aggregator sık görülen kombinasyondur.

---

## 4. Retention ve Maliyet Dengesi: Hot / Warm / Cold / Frozen

### Sorun

Log'lar sınırsız büyür. Her şeyi hızlı-arama yapan pahalı SSD depoda sonsuza dek tutmak ekonomik olarak imkânsızdır. Öte yandan olay müdahalesinde (incident response) ve adli analizde (forensics) eski loglar hayati olabilir. Denge, **erişim hızı ile depolama maliyeti** arasında kurulur.

### Katmanlı Depolama (Tiered Storage)

- **Hot:** En taze veri (örneğin son günler/haftalar). Hızlı SSD, en pahalı, en hızlı sorgulanabilir. Aktif tespit ve günlük çalışma buradan yürür.
- **Warm:** Orta yaşlı veri. Daha yavaş disk, daha az kaynak, hâlâ aranabilir ama sorgu daha yavaş.
- **Cold:** Eski veri. Sıkıştırılmış, düşük maliyetli depoda; sorgulanabilir ama yavaş.
- **Frozen / Archive:** Nadir erişilen, genelde nesne depolamada (S3 gibi) tutulan, gerektiğinde geri yüklenen veri. En ucuz, en yavaş.

Elastic'in ILM (Index Lifecycle Management) veya Splunk'ın bucket yaşam döngüsü bu geçişleri otomatikleştirir.

### Retention Kararının Bileşenleri

Ne kadar süre saklanacağı üç kuvvetin çekişmesidir:
1. **Uyumluluk (compliance):** Bazı regülasyonlar (PCI DSS, KVKK/GDPR bağlamı, sektörel gereklilikler) belirli log türlerini asgari bir süre saklamayı zorunlu kılar. Detayları kurumun tabi olduğu çerçeveye göre değişir; kesin süreleri kendi uyumluluk ekibinizle doğrulayın.
2. **Tespit ihtiyacı:** APT'ler (Advanced Persistent Threat) aylarca sessiz kalabilir; "dwell time" (saldırganın fark edilmeden geçirdiği süre) ortalamaları göz önüne alındığında, sadece birkaç haftalık log tutmak geç keşfedilen ihlalleri kör noktada bırakır.
3. **Maliyet:** Hacim × saklama süresi × depolama birim maliyeti.

### Maliyet Optimizasyonu Yaklaşımları

- **Ingest-time filtering:** Gürültülü, düşük değerli logları (örneğin sağlık kontrolü/heartbeat kayıtları) daha depoya girmeden düşürmek veya örneklemek (sampling).
- **Değere göre yönlendirme:** Yüksek değerli güvenlik loglarını hot'ta, düşük değerlileri doğrudan ucuz arşive.
- **Sıkıştırma ve sütunlu format:** Cold/archive katmanında Parquet gibi sütunlu (columnar) formatlar hem yer hem sorgu maliyetini düşürür.
- **Aggregation/roll-up:** Ham logu arşive atarken, özet metrikleri hot'ta tutmak.

**Yaygın hata:** Maliyeti kısmak için güvenlik açısından kritik logları (authentication, process creation, PowerShell logları) örneklemek. Bunlar örneklenmemeli; örnekleme yalnızca gerçekten yüksek hacimli ve düşük tekil-değerli veri için düşünülmelidir.

---

## 5. Log Bütünlüğü ve Değiştirilemezlik (Integrity & Immutability)

### Neden Bu Kadar Kritik?

Saldırganın klasik hamlelerinden biri **iz temizlemedir (anti-forensics)**. MITRE ATT&CK'te bu, *Indicator Removal* (T1070) altında toplanır: log silme, log servisini durdurma, event log temizleme. Eğer log'lar saldırganın eriştiği makinede kalırsa, ihlali gizlemek için onları silebilir veya değiştirebilir. Bu yüzden savunmanın altın kuralı: **Log'u üretildiği yerden hızla, güvenli ve değiştirilemez bir merkeze taşımak.**

### Değiştirilemezlik Mekanizmaları

**1. Merkezîleştirme (Central forwarding).** İlk ve en temel savunma. Log yerel diskte kalmadan uzak toplayıcıya iletilir; saldırgan yerel kopyayı silse bile merkezî kopya durur. İdeali, iletim ajanının log'u tampona alıp güvenilir teslim (reliable delivery) garantisi vermesidir.

**2. WORM depolama (Write Once Read Many).** Bir kez yazılan verinin değiştirilemez, silinemez olduğu depolama. Bulut nesne depolamalarında bu genelde **object lock / immutability policy** olarak sunulur (örneğin S3 Object Lock). Belirlenen süre boyunca root yetkili biri bile veriyi silemez/değiştiremez (compliance modu). Bu, insider threat ve yetki ele geçirme senaryolarına karşı güçlü bir kontroldür.

**3. Hash zinciri (Hash chaining) ve dijital imza.** Bütünlük kanıtı için her log kaydının (veya blok/segmentin) kriptografik özeti (hash) alınır ve **bir sonraki kaydın özetine önceki özet dahil edilir** — tıpkı bir blokzincirdeki gibi zincirleme bağ kurulur:

```
H(n) = hash( kayit(n) || H(n-1) )
```

Bu sayede zincirin ortasındaki tek bir kayıt değiştirilse, sonraki tüm özetler tutmaz; oynama (tampering) tespit edilir. Bazı sistemler zincirin uç özetini periyodik olarak güvenilir bir zaman damgası (trusted timestamp) otoritesine mühürletir. Linux dünyasında `journald` **Forward Secure Sealing (FSS)** ile benzer bir bütünlük mührü sunar. Splunk gibi ürünler de data integrity control ile blok bazlı hash tutar.

**4. Erişim kontrolü ve görev ayrılığı (SoD).** Log'u üreten hesap ile log deposunu yönetebilen hesap **ayrı** olmalı. Sistem yöneticisinin kendi izlerini sildiği deponun sahibi olmaması gerekir; ideali güvenlik ekibinin ayrı bir güven alanında (trust boundary) tuttuğu depodur.

---

## 6. Saat Senkronizasyonu (Time Synchronization)

### Neden Görünürden Daha Önemli?

Adli analizin ve korelasyonun temeli **zaman**dır. Bir olayı yeniden kurmak (event reconstruction), farklı sistemlerden gelen olayları doğru sıraya dizmekle mümkündür. Eğer web sunucusunun saati firewall'dan 4 dakika sapmışsa, aslında aynı saniyede olan iki olay ilişkisiz görünür veya sebep-sonuç sırası tersine döner. Bu, bir saldırı zincirini (kill chain) çözemez hâle getirir.

### Çalışma Mantığı

- **NTP (Network Time Protocol):** Sistem saatlerini güvenilir zaman kaynaklarına (stratum sunucular) senkronize eder. Tüm log üreten sistemler ortak, güvenilir bir NTP hiyerarşisine bağlı olmalıdır.
- **Chrony / systemd-timesyncd:** Modern Linux'ta yaygın NTP istemcileri.
- **PTP (Precision Time Protocol):** Mikrosaniye hassasiyeti gereken ortamlar (finans işlem sistemleri gibi) için.

### En İyi Uygulamalar

- **UTC kullanın.** Tüm loglar mümkünse UTC'de tutulmalı; yerel saat dilimi ve yaz saati (DST) geçişleri korelasyonu bozan klasik hatalardır. Görüntüleme katmanında yerel saate çevirmek yeterlidir.
- **İki zaman damgasını da saklayın:** Olayın **kaynakta üretildiği zaman (event time)** ile **pipeline'a alındığı zaman (ingest time)**. İkisi arasındaki fark hem gecikmeyi (latency) hem de saat sapmasını (clock skew) ortaya çıkarır.
- **NTP'nin kendisini izleyin.** Saatin senkron kalması bir güvenlik kontrolüdür; NTP servisi durursa veya saat sapması eşiği aşarsa alarm üretilmelidir. Saldırganın saati kasıtlı kaydırması (timestomping ile birlikte) bir anti-forensics tekniğidir.

---

## 7. Tespit ve Savunma: Pipeline'ın Kendisini İzlemek

Log pipeline sadece tespit **aracı** değildir; kendisi de bir **saldırı yüzeyi** ve bir **izlenmesi gereken varlıktır**. Görünürlükteki kör noktalar (visibility gaps) çoğu ihlalin sessiz kalma nedenidir.

### İzlenmesi Gerekenler (Detection)

- **Log kaynağının susması (silent host / log source gap).** En kritik ve en çok ihmal edilen tespit. Normalde saatte binlerce olay gönderen bir sunucudan aniden log gelmemesi, ya makinenin çöktüğü ya da saldırganın loglamayı kestiği anlamına gelir. **Beklenen kaynaklar listesi (asset inventory)** ile fiilî gönderen kaynaklar sürekli karşılaştırılmalı; eksik olanlar alarm üretmelidir.
- **Log servisinin durdurulması/temizlenmesi.** Windows'ta Event Log servisinin durması, `wevtutil cl` ile log temizleme, Windows Event ID 1102 (audit log temizlendi) veya 104; Linux'ta `auditd`/`rsyslog` servisinin durması güçlü tespit sinyalleridir.
- **Pipeline sağlık metrikleri.** Kuyruk derinliği (queue depth), backpressure, düşen olay sayısı (dropped events), ingest gecikmesi. Bunların ani değişimi ya bir arıza ya da bir gizleme girişimidir.
- **Zaman anomalileri.** Ingest time ile event time arasında olağandışı büyük fark; gelecek tarihli veya çok eski tarihli olaylar.
- **Konfigürasyon değişikliği.** Audit politikasının kısılması, Sysmon konfigürasyonunun değiştirilmesi, log yönlendirme kurallarının silinmesi.

### Savunma (Defense) Prensipleri

- **Log'u kaynağından hızla uzaklaştır (get logs off-host fast).** Yerelde bekleme süresi ne kadar kısa olursa, saldırganın silme fırsatı o kadar azalır.
- **Değiştirilemez arşiv katmanı.** En azından güvenlik-kritik loglar için WORM/object-lock'lu bir kopya bulundur.
- **Pipeline'ı ayrı bir güven alanına koy.** Toplayıcı ve depo, izlenen sistemlerden farklı kimlik ve ağ sınırında olmalı; üretim admini bu alana erişememeli.
- **Uçtan uca şifreleme ve kimlik doğrulama.** Log iletimi TLS ile şifrelenmeli; ajanlar mutual authentication ile toplayıcıya bağlanmalı ki sahte log enjeksiyonu (log injection/spoofing) yapılamasın.
- **Kapasite planlaması ve backpressure.** Disk tamponu ve kuyruk boyutu, en yoğun trafik anında bile log kaybı olmayacak şekilde boyutlandırılmalı.

---

## 8. Yaygın Hatalar (Anti-Patterns)

1. **"Her şeyi logla, sonra düşünürüz."** Kontrolsüz hacim maliyeti patlatır ve gürültü, gerçek sinyali gömer. Log stratejisi tehdit modeliyle (threat model) hizalanmalıdır.
2. **Parse'ın sessiz başarısızlığı.** `grok`/parser deseni değişen bir log formatına uymayınca alanlar boş kalır ve tespit kuralı **sessizce çalışmaz**. Parse hata oranı (parse failure rate) izlenmelidir.
3. **Log kaynağı envanterinin olmaması.** Neyin log göndermesi gerektiğini bilmiyorsanız, susan kaynağı fark edemezsiniz. Görünürlük eksikliği ölçülemez.
4. **Retention'ı sadece maliyetle belirlemek.** Uyumluluk ve dwell time göz ardı edilirse, ihtiyaç anında log çoktan silinmiş olur.
5. **Pipeline'ı izlenen sistemle aynı güven alanında tutmak.** Sistemi ele geçiren saldırgan log deposunu da ele geçirir; bütünlük tamamen kaybolur.
6. **Saat senkronizasyonunu "ayarla ve unut" sanmak.** NTP sapması izlenmezse, korelasyon ve adli analiz sessizce güvenilmez hâle gelir.
7. **Zenginleştirmeyi tek kaynağa aşırı bağımlı kılmak.** Dış TI/GeoIP servisi düşünce pipeline tıkanır; bu bağımlılıklar tamponlanmalı ve zaman aşımı (timeout) ile korunmalıdır.

---

## Sonuç

Log yönetim mimarisi, Mavi Takım'ın gerçek anlamda **görme yeteneğidir**. Kaynaktan depoya uzanan boru hattının her katmanı bir tespit kabiliyeti ya da bir kör nokta yaratır. Normalizasyon ortak bir dil kurar, zenginleştirme bağlam ekler, katmanlı depolama görünürlüğü sürdürülebilir maliyetle sağlar. Ama bunların hepsinin üstünde iki sessiz temel yatar: **log bütünlüğü** (silinemeyen, oynanamayan kanıt) ve **saat senkronizasyonu** (olayları doğru sıraya dizen zemin). Bir tespit mühendisi kural yazmadan önce, o kuralı besleyen verinin eksiksiz, doğru zamanlı ve değiştirilemez geldiğinden emin olmalıdır. Çünkü göremediğiniz şeyi savunamazsınız; ve güvenmediğiniz log ile de savunamazsınız.
