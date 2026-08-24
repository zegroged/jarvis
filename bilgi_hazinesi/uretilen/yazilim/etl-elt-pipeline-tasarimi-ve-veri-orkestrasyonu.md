# ETL/ELT Pipeline Tasarımı ve Veri Orkestrasyonu (Airflow/dbt Tarzı)

## Giriş: Bu Konu Neden "Yazılım Mühendisliği" Konusudur

Veri mühendisliği çoğu zaman "sadece SQL yazmak" gibi algılanır, ama gerçekte dağıtık sistemler mühendisliğinin özel bir dalıdır. Bir ETL/ELT pipeline'ı; ağ hatalarına, kısmi başarısızlıklara, saat dilimi tuzaklarına, şema değişikliklerine ve eşzamanlılık sorunlarına dayanıklı olmak zorundadır — tıpkı bir dağıtık sistem gibi. Üstüne, orkestrasyon katmanı (Airflow, dbt, Dagster, Prefect vb.) genellikle **rastgele kod çalıştırma** yeteneğine sahiptir; bu da onu hem güçlü hem de güvenlik açısından kritik bir bileşen yapar. Bu makale, pipeline'ları doğru tasarlamayı (idempotency, backfill, DAG mimarisi, veri kalitesi) ve orkestrasyon katmanını güvenli işletmeyi (kod enjeksiyonu, RCE riskleri, tespit ve savunma) bir bütün olarak ele alır.

## ETL ve ELT: Kavramsal Fark ve Kök Neden

**ETL (Extract-Transform-Load)**: Veri kaynaktan çekilir, ayrı bir işleme katmanında (genellikle uygulama sunucusu veya özel bir ETL motoru) dönüştürülür, sonra hedef sisteme (veri ambarı) yazılır. Dönüşüm hedef sistemin dışında olur.

**ELT (Extract-Load-Transform)**: Veri ham haliyle önce hedefe (genellikle bulut veri ambarı: BigQuery, Snowflake, Redshift) yüklenir, dönüşüm hedef sistemin hesaplama gücü kullanılarak SQL ile orada yapılır.

Bu ayrımın kök nedeni **hesaplama maliyetinin nerede olduğu** ile ilgilidir. 2010'lar öncesi veri ambarları pahalı ve sınırlı kapasiteliydi; bu yüzden dönüşümü ayrı, ucuz sunuculara (Hadoop, özel ETL araçları) taşımak mantıklıydı. Bulut veri ambarlarının depolama ve hesaplamayı ayrıştırıp neredeyse sınırsız ölçeklenebilir hale getirmesiyle (örn. Snowflake'in mimarisi), "ham veriyi hemen yükle, dönüşümü orada, SQL ile, versiyonlanmış biçimde yap" yaklaşımı (dbt'nin popülerleştirdiği model) daha ucuz ve daha izlenebilir hale geldi. dbt (data build tool) tam olarak bu ELT felsefesinin yazılım mühendisliği pratiklerini (test, versiyon kontrolü, modülerlik, CI/CD) veri dönüşümüne getiren araçtır.

Pratik sonuç: ELT'de "şema önce tanımla" (schema-on-write) yerine "veriyi al, şemayı sorgu zamanında yorumla" (schema-on-read) esnekliği artar, ama ham katmanda kalite kontrolü yapılmazsa kirli veri ambarın en alt katmanına kadar sızar. Bu nedenle modern mimarilerde "medallion" (bronze/silver/gold) katmanlama yaygındır: bronze ham veri, silver temizlenmiş/normalize, gold iş mantığına göre agregatlanmış veridir.

## DAG Tasarımı: Kök Mantık

Orkestrasyon araçları (Airflow, Dagster, Prefect) işleri bir **DAG (Directed Acyclic Graph — yönlü çevrimsiz çizge)** olarak modeller. Neden çizge, neden döngüsüz?

- **Yönlülük**: Görev B, görev A'nın çıktısına bağımlıysa, bu bağımlılığı açıkça temsil etmek gerekir; aksi halde sıralama varsayımlara (örneğin dosya sistemi zamanlamasına) dayanır ve kırılgan olur.
- **Çevrimsizlik (acyclic)**: Bir döngü olsaydı ("A, B'ye bağımlı; B, A'ya bağımlı") görev hiç bitmezdi — DAG yapısı, zamanlayıcının bağımlılık çözümlemesini matematiksel olarak sonlandırılabilir kılar (topological sort ile).

DAG tasarımının pratikte karşılaştığı temel kararlar:

**Görev granülaritesi**: Çok büyük tek görev ("tüm pipeline tek Python scripti") hata ayıklamayı ve kısmi yeniden çalıştırmayı imkânsızlaştırır. Çok ince görev granülaritesi ise orkestrasyon ek yükünü (scheduler overhead, task queue gecikmesi) artırır. Doğru pratik: her görev, tek bir mantıksal sorumluluğa sahip olmalı ve bağımsız olarak yeniden denenebilir (retry edilebilir) olmalıdır.

**Statik DAG vs. dinamik DAG üretimi**: Airflow'da DAG dosyaları Python kodudur ve scheduler tarafından periyodik olarak yeniden çalıştırılıp (re-parse edilip) yorumlanır. Bu, hem esneklik (parametrik DAG üretimi) hem de risk kaynağıdır — aşağıda güvenlik bölümünde bunu detaylandırıyoruz.

**Fan-out/fan-in desenleri**: Bir görev birçok paralel alt göreve bölünüp (örn. her müşteri için ayrı çıkarma), sonra tek bir birleştirme görevinde toplanabilir. Bu, büyük veri kümelerini paralelleştirmenin doğal yoludur ama başarısızlık durumunda "kısmi tamamlanma" durumunu yönetmek gerekir (bkz. idempotency).

## Idempotency: Pipeline Güvenilirliğinin Temel Taşı

**Idempotency (幂等lik/eşgüçlülük)**: Bir işlemin bir kez çalıştırılmasıyla N kez çalıştırılmasının aynı nihai durumu üretmesi özelliğidir.

### Neden Kritik?

Dağıtık sistemlerde "tam olarak bir kez" (exactly-once) teslim garantisi, ağ hataları ve kısmi başarısızlıklar nedeniyle pratikte neredeyse imkânsızdır (bkz. dağıtık sistemler literatüründeki "iki general problemi"). Gerçekçi olan, "en az bir kez" (at-least-once) teslim + idempotent işleme birleşimidir. Bir Airflow görevi zaman aşımına uğrayıp yeniden denendiğinde (retry), ya da bir operator manuel olarak bir görevi tekrar tetiklediğinde, pipeline'ın bunu güvenle kaldırabilmesi gerekir.

### Idempotent Olmayan Tasarımların Yaygın Tuzakları

- `INSERT INTO table VALUES (...)` şeklinde saf ekleme: Görev iki kez çalışırsa veri **çiftlenir** (duplicate). Doğrusu: `MERGE`/`UPSERT` mantığı, ya da önce o zaman dilimine ait veriyi silip yeniden yazmak (`DELETE WHERE date = X` + `INSERT`).
- Artımlı sayaçlar veya "şu ana kadarki toplam" gibi durum tutan (stateful) mutasyonlar: Yeniden çalıştırma durumu bozar. Doğrusu: mutlak değerler hesapla, göreli artış değil.
- Yan etkili olmayan harici çağrılar (örn. bir e-posta gönderme görevi, bir ödeme tetikleme görevi) idempotency açısından özellikle tehlikelidir — retry, kullanıcıya iki kez e-posta gitmesine ya da (çok daha kötü) ödemenin iki kez tetiklenmesine yol açabilir. Bunun standart çözümü: **idempotency key** (istemcinin ürettiği benzersiz bir işlem kimliği; hedef sistem bu anahtarı daha önce işlediyse isteği yok sayar).

### Pratik Desen: Partition Overwrite

Veri ambarı pipeline'larında en yaygın idempotent desen, "zaman dilimine göre bölüntüle (partition), her çalıştırmada ilgili bölüntüyü komple üzerine yaz" mantığıdır. Örneğin günlük bir pipeline `WHERE partition_date = '{{ ds }}'` bölüntüsünü her çalıştığında tamamen siler ve yeniden yazar. Bu sayede aynı gün için pipeline 5 kez de çalışsa, 1 kez de çalışsa sonuç aynıdır.

## Backfill: Kavram ve Tuzaklar

**Backfill**, bir pipeline mantığı değiştiğinde veya yeni eklendiğinde, geçmiş tarihler için de veriyi yeniden/ilk kez işleme sürecidir.

### Kök Neden ve Tasarım Gerekliliği

Airflow'un `execution_date` (mantıksal çalışma tarihi) kavramı tam olarak backfill'i kolaylaştırmak için tasarlanmıştır: bir görev "bugün ne zaman çalıştığı" ile değil, "hangi mantıksal zaman dilimini işlediği" ile parametrize edilir. Bu ayrım (wall-clock time vs. logical/data time) kritiktir — görev 15 gün gecikmeli çalışsa bile, doğru veri aralığını işlemeye devam edebilir.

### Yaygın Backfill Hataları

- **Kaynak sisteme aşırı yük**: 2 yıllık veriyi tek seferde, tüm partition'ları paralel tetikleyerek backfill etmek, kaynak API'yi (rate limit) veya veritabanını (I/O) boğabilir. Doğru pratik: `max_active_runs` / eşzamanlılık sınırları koymak, kademeli (throttled) backfill yapmak.
- **Şema kayması (schema drift) göz ardı etme**: Geçmiş veri, bugünkü şemadan farklı bir yapıya sahip olabilir (kaynak sistem alan eklemiş/kaldırmışsa). Backfill mantığı bunu varsaymadan yazılırsa sessizce yanlış veri üretir.
- **Yan etkili görevlerin backfill edilmesi**: Bir bildirim/e-posta görevi yanlışlıkla backfill kapsamına girerse, kullanıcılara geçmişe dönük binlerce bildirim gitmesi gibi ciddi olaylar yaşanmıştır (endüstride sıkça anlatılan bir "olay" (incident) sınıfıdır). Bu yüzden yan etkili görevler DAG'da açıkça izole edilmeli ve backfill'den hariç tutulabilmelidir.
- **Idempotent olmayan pipeline'ı backfill etmek**: Yukarıdaki idempotency kuralı çiğnenmişse, backfill veri çiftlenmesine yol açar.

## Veri Kalitesi Kontrolleri (Data Quality / Validation)

### Neden Gerekli?

"Garbage in, garbage out" ilkesi veri pipeline'larında özellikle tehlikelidir çünkü hatalar genellikle **sessizce** yayılır: pipeline hata fırlatmaz, sadece yanlış sayı üretir ve bu sayı bir yönetici raporuna, bir ML modelinin eğitim setine ya da bir faturaya kadar sessizce ilerler. Bu nedenle "pipeline çalıştı = başarılı" varsayımı yanlıştır; başarı kriteri veri kalitesi kontrollerinden geçmektir.

### Kontrol Katmanları

1. **Şema doğrulama (schema validation)**: Beklenen kolonlar var mı, tipler uyuşuyor mu, NOT NULL kısıtları ihlal edilmiş mi. Kaynak sistemler sessizce şema değiştirebilir (yeni alan, tip değişikliği); pipeline bunu fark etmezse aşağı akışta (downstream) tip hatası veya yanlış agregasyon oluşur.
2. **Hacim/anomali kontrolleri (volume anomaly)**: "Bugünkü satır sayısı, geçen haftanın aynı gününe göre %50'den fazla mı düştü/arttı?" gibi istatistiksel eşik kontrolleri. Ani düşüşler genellikle üst akıştaki (upstream) bir kesintiyi işaret eder.
3. **İş kuralı doğrulamaları (business logic assertions)**: dbt'nin `tests` mekanizması bunun tipik örneğidir — `unique`, `not_null`, `relationships` (referans bütünlüğü), `accepted_values` gibi deklaratif testler her model çalıştırıldığında otomatik kontrol edilir.
4. **Freshness (tazelik) kontrolü**: Verinin ne kadar süredir güncellenmediği izlenir; bir kaynak beklenenden eski kalmışsa uyarı üretilir (dbt'de `source freshness`, Airflow'da SLA/sensor mekanizmaları).

### Tasarım İlkesi: "Fail Fast, Fail Loud" ile "Sessiz Bozulma" Arasındaki Denge

Kritik bir mühendislik kararı: veri kalite kontrolü başarısız olduğunda pipeline'ı **durdurmalı mı** (hard fail, aşağı akışa hiç veri gitmesin) yoksa **uyarı verip devam mı etmeli** (soft fail, veri eksik/şüpheli olarak işaretlensin)? Finansal raporlama gibi yüksek riskli alanlarda genellikle hard fail tercih edilir; keşifsel analitik gibi düşük riskli alanlarda soft fail + izleme yeterli olabilir. Bu kararı önceden, veri sözleşmesi (data contract) seviyesinde netleştirmemek, üretimde belirsiz davranışa yol açar.

## Orkestrasyon Güvenliği: Airflow ve Benzeri Araçlarda Kod Enjeksiyonu / RCE Riski

Bu bölüm, savunmacı/tespit amaçlıdır: mekanizmayı anlamak, riski azaltmak ve tespit etmek içindir; saldırı talimatı değildir.

### Kök Neden: DAG'lar Kod, Konfigürasyon Değildir

Airflow gibi araçlarda bir "DAG dosyası" aslında rastgele Python kodu çalıştırabilen bir programdır — scheduler bu dosyayı periyodik olarak import edip çalıştırır (`DagBag` mantığı ile). Bu, **tasarım gereği** güçlü bir esneklik sağlar (dinamik DAG üretimi, parametrik görevler) ama şu anlama gelir: **DAG dosyasını yazma yetkisine sahip olan herkes, scheduler'ın çalıştığı ortamda kod çalıştırma yetkisine sahiptir.** Bu, geleneksel "konfigürasyon dosyası" (YAML/JSON, veri olarak yorumlanan) modelinden temelde farklıdır ve genellikle yeterince ciddiye alınmaz.

Bunun somut sonuçları:

- **DAG deposu (repo/dosya sistemi) erişim kontrolü zayıfsa**: Kötü niyetli ya da hatalı bir DAG dosyası, scheduler'ın servis hesabı yetkileriyle (genellikle bulut kimlik bilgilerine, veritabanı bağlantılarına erişimi olan bir hesap) rastgele kod çalıştırabilir. Bu, klasik "supply chain" (tedarik zinciri) riskiyle örtüşür: DAG'a eklenen bir üçüncü parti kütüphane veya `pip install` adımı da aynı güvenle çalışır.
- **Templating/Jinja enjeksiyonu**: Airflow, görev parametrelerinde Jinja template'lerini (`{{ ds }}`, `{{ params.x }}` gibi) değerlendirir. Kullanıcı girdisinin (örn. bir web formu üzerinden `trigger_dag` ile geçirilen `conf` parametresi) doğrudan bir shell komutuna veya SQL sorgusuna, sanitize edilmeden enjekte edilmesi klasik bir **template/command injection** deseni oluşturur — mekanizma olarak SQL injection'a çok benzer: güvenilmeyen veri ile çalıştırılabilir kod arasındaki sınır kaybolur.
- **Yetki ayrımının (RBAC) eksikliği**: Airflow web arayüzünde "DAG tetikleme" yetkisi olan bir kullanıcı, eğer DAG `conf` parametresini denetimsiz biçimde bir `BashOperator` veya `PythonOperator` içinde kullanıyorsa, aslında dolaylı kod çalıştırma yetkisine sahip olur. Bu, "en az yetki" (principle of least privilege) ilkesinin ihlalinin somut bir örneğidir.
- **Deserialization riskleri**: Görevler arası veri aktarımında (XCom) veya bazı entegrasyonlarda güvensiz deserialization (örn. `pickle` kullanımı) rastgele nesne/kod çalıştırmaya yol açabilecek klasik bir güvenlik açığı sınıfıdır — genel prensip: güvenilmeyen kaynaktan gelen serileştirilmiş veriyi asla doğrudan `pickle.loads` gibi mekanizmalarla açmayın.

### Savunma ve Tespit Yaklaşımları

**Erişim kontrolü katmanlama**:
- DAG dosyalarının bulunduğu depoya (Git repo, dosya paylaşımı) yazma erişimini, kod incelemesi (code review/PR) zorunluluğuyla sınırlayın. "DAG dosyası = üretim koduna commit" muamelesi görmeli, gündelik bir konfigürasyon değişikliği gibi değil.
- Scheduler'ın çalıştığı servis hesabının yetkilerini minimuma indirin (least privilege): scheduler'ın erişebildiği bulut kaynakları, sırlar (secrets) ve veritabanları, sadece gerçekten ihtiyaç duyulanlarla sınırlı olmalı.
- Airflow'un kendi RBAC (Role-Based Access Control) mekanizmasını aktif kullanın; "kim DAG tetikleyebilir", "kim `conf` parametresi geçirebilir", "kim yeni DAG dosyası ekleyebilir" ayrı yetkiler olarak düşünülmeli.

**Girdi doğrulama ve şablon güvenliği**:
- Kullanıcıdan/harici sistemden gelen her `conf`/parametre değerinin, bir komut veya sorguya enjekte edilmeden önce whitelist (izin verilen değerler listesi) ile doğrulanması gerekir. Serbest metin alanlarının doğrudan `BashOperator` komutuna string birleştirmeyle (string concatenation) geçirilmesi kaçınılması gereken bir tasarımdır; parametreli çağrı (parametrized execution) tercih edilmelidir.
- Mümkün olduğunca `BashOperator` yerine, girdi/çıktıları açıkça tanımlı, izole edilebilir operatörler (örn. konteynerize edilmiş `KubernetesPodOperator`) kullanmak, "keyfi komut yürütme yüzeyini" daraltır.

**İzolasyon**:
- Görevleri, scheduler'ın kendisinden ayrı, izole çalışma ortamlarında (worker konteynerleri, sanal makineler, ayrı Kubernetes pod'ları) çalıştırmak, bir görevin kötüye kullanılması durumunda etkiyi sınırlar ("blast radius" azaltma). Scheduler sürecinin kendisi, mümkün olduğunca üretim sırlarına doğrudan erişimden izole edilmelidir.
- Bağımlılık yönetiminde (requirements.txt, pip install adımları) tedarik zinciri güvenliği: sürüm sabitleme (pinning), bilinen zafiyet taraması (dependency scanning), özel bir paket deposu (private package index) kullanımı.

**Gözlemlenebilirlik ve tespit**:
- Scheduler ve worker loglarında beklenmeyen dış ağ bağlantıları, beklenmeyen alt süreç (subprocess) çağrıları veya olağandışı dosya sistemi erişimleri için izleme (monitoring) kurulmalı.
- DAG dosyalarındaki değişikliklerin denetim izi (audit log) tutulmalı: kim, ne zaman, hangi DAG'ı değiştirdi/tetikledi.
- Anormal derecede uzun süren, beklenmedik dış IP'lere bağlanan veya CPU/ağ profilinde ani sıçrama gösteren görevler, kod enjeksiyonu sonucu çalışan yabancı bir yükün (payload) belirtisi olabilir; bu tür davranışsal anomaliler için temel eşik/uyarı mekanizmaları faydalıdır.

## En İyi Pratikler Özeti

- Her görevi idempotent tasarlayın; "N kez çalışsa da sonuç aynı" testini mantalitenin merkezine koyun.
- Mantıksal zaman (`execution_date`/`ds`) ile gerçek çalışma zamanını (wall-clock) ayırın; backfill bunun üzerine kurulur.
- Veri kalite kontrollerini pipeline'ın "bir adımı" değil, "geçiş şartı" (gate) olarak modelleyin.
- Yan etkili görevleri (bildirim, ödeme tetikleme) DAG'da açıkça izole edin ve backfill/retry kapsamından bilinçli olarak çıkarın ya da idempotency key ile koruyun.
- DAG kodunu üretim yazılımı gibi ele alın: code review, test, CI/CD, en az yetki ilkesi.
- Kullanıcıdan/harici sistemden gelen her parametreyi, komut veya sorgu yürütme noktasına ulaşmadan önce doğrulayın; string birleştirme yerine parametrized execution kullanın.

## Yaygın Hatalar

- "Pipeline hatasız çalıştı" ile "veri doğru" ifadelerini eşitlemek — veri kalite kontrolü olmadan bu varsayım çürüktür.
- Backfill'i normal çalıştırmayla aynı eşzamanlılıkta, kaynak sistemin kapasitesini hesaba katmadan tetiklemek.
- DAG dosyasına yazma erişimini, uygulama koduna yazma erişiminden daha gevşek bir güvenlik rejimiyle yönetmek.
- Kullanıcı/harici girdiyi doğrudan `BashOperator` veya benzeri komut çalıştıran operatörlere sanitize etmeden geçirmek.
- Şema kaymasını (schema drift) sessizce yutan, tip hatası fırlatmayan "esnek" ayrıştırma mantıkları kurmak.

## Sonuç

ETL/ELT pipeline tasarımı, hem bir mühendislik disiplinidir (idempotency, backfill, DAG mimarisi, veri kalitesi) hem de bir güvenlik yüzeyidir (orkestrasyon katmanının rastgele kod çalıştırma gücü). Bu iki boyutu ayrı düşünmek yanlıştır: iyi tasarlanmış, idempotent, test edilmiş bir pipeline aynı zamanda daha güvenli bir pipeline'dır, çünkü öngörülebilirlik hem güvenilirliğin hem güvenliğin ortak temelidir.
