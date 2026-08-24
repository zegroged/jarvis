# Anti-Forensics ve Log/Artifact Manipülasyonu

## Giriş ve Kapsam

Bir saldırgan sisteme sızıp yetki yükselttikten (privilege escalation) sonra genellikle iki hedefe odaklanır: kalıcılık (persistence) ve **izlerini gizleme**. Anti-forensics, bir olay müdahale ekibinin (incident response) veya adli bilişim uzmanının (forensic analyst) olayı yeniden inşa etmesini zorlaştıran, yavaşlatan ya da imkânsızlaştıran tüm teknik ve taktiklerin genel adıdır.

Bu makale saldırgan tarafının **iz silme ve delil manipülasyonu** mantığını, savunma (defense) ve tespit (detection) perspektifinden inceler. Amaç, operasyonel bir saldırı reçetesi vermek değil; mekanizmayı anlayarak **hangi artifact'in neden önemli olduğunu**, saldırganın onu neden hedef aldığını ve savunmacının bunu nasıl yakalayabileceğini kavramaktır. Odak Windows ekosistemidir, çünkü kurumsal ortamlarda en yaygın hedef budur; ancak prensipler platformdan bağımsızdır.

Anti-forensics'in temel felsefesi şudur: **Bir eylemin gerçekleştiğini kanıtlayan her veri bir "artifact"tir.** Saldırgan ya bu artifact'i yok etmeye, ya değiştirmeye (tampering), ya da baştan hiç üretilmemesini sağlamaya çalışır. Savunmacının işi ise bu üç senaryonun her birini yakalayacak katmanlı ve **kurcalanmaya dirençli (tamper-resistant)** bir kayıt altyapısı kurmaktır.

## Adli İz (Artifact) Kavramı ve Anti-Forensics Kategorileri

Adli bilişimde delil, çoğunlukla işletim sisteminin normal işleyişi sırasında **istemeden** ürettiği yan ürünlerden gelir. Kullanıcı bir program çalıştırdığında Windows bunu birkaç bağımsız yerde kayıt altına alır: dosya sistemi zaman damgaları, Prefetch dosyaları, Amcache/Shimcache, Event Log kayıtları, registry MRU listeleri. Bu **çokluluk (redundancy)** savunmacının en büyük avantajıdır: saldırgan bir izi silse bile diğerleri kalabilir.

Anti-forensics teknikleri kabaca dört kategoriye ayrılır:

- **Yok etme (destruction):** Log dosyalarını, journal kayıtlarını, shadow copy'leri silme.
- **Gizleme/değiştirme (tampering):** Zaman damgalarını değiştirme (timestomping), kayıt içeriğini bozma.
- **Üretimi engelleme (prevention):** Logging'i kapatma, denetimi (auditing) devre dışı bırakma, "living off the land" ile normal görünme.
- **Şaşırtma (obfuscation):** Sahte iz bırakma, atıf (attribution) zorlaştırma, şifreleme.

Aşağıda en kritik somut tekniklere geçiyoruz.

## Timestomping (Zaman Damgası Manipülasyonu)

### Tanım ve Kök Neden

NTFS dosya sisteminde her dosya için **MACB** olarak bilinen dört zaman damgası tutulur: **M**odified (değiştirilme), **A**ccessed (erişilme), **C**hanged (MFT kaydının değişmesi), **B**orn/Created (oluşturulma). Timestomping, bir saldırganın kötü amaçlı dosyasının zaman damgalarını, aynı dizindeki eski ve masum sistem dosyalarınınkiyle eşleştirerek dosyayı "eski ve meşru" gibi göstermesidir.

Kök neden şudur: Analistler zaman çizelgesi (timeline) analizinde dosyaları oluşturulma/değişme zamanına göre sıralar. Bir DLL'in "geçen hafta" oluşturulduğunu görmek, incelemeyi oraya yönlendirir. Saldırgan bu zamanı yıllar öncesine çekerse dosya, gürültünün içinde kaybolur.

### Çalışma Mantığı ve Kritik Ayrıntı

Windows'ta zaman damgaları iki ayrı yerde saklanır: MFT kaydının **$STANDARD_INFORMATION** ($SI) attribute'unda ve **$FILE_NAME** ($FN) attribute'unda. Çoğu timestomping aracı yalnızca **$SI** zaman damgalarını değiştirir; çünkü Windows Gezgini ve çoğu API bunları gösterir. Ancak **$FN** zaman damgaları normal user-mode araçlarla kolayca değiştirilemez ve genellikle dosya oluşturma/rename anındaki gerçek değerleri korur.

Bu asimetri savunmanın en güçlü kozudur: **$SI ile $FN zaman damgaları arasındaki tutarsızlık, timestomping'in klasik parmak izidir.** Ayrıca elle atanan zaman damgaları genellikle "yuvarlak" görünür (saniye/nanosaniye alt bölümleri sıfırdır), oysa doğal dosya işlemlerinde bu alanlar yüksek çözünürlükte doludur.

### Tespit ve Savunma

- **$SI vs $FN karşılaştırması:** MFT'yi ayrıştıran araçlarla (analytics/forensic parser) iki attribute'un zaman damgalarını yan yana koyun. Uyuşmazlık, özellikle $SI'nin $FN'den *önce* olması, güçlü bir sinyaldir.
- **Nanosaniye çözünürlüğü:** Alt-saniye kısmı tam sıfır olan created/modified değerlerini şüpheli olarak işaretleyin.
- **USN Journal korelasyonu:** Aşağıda ele alınan USN journal, dosyanın ne zaman gerçekten yazıldığını bağımsız olarak kaydeder; $SI ile çelişirse manipülasyon vardır.
- **Merkezi EDR/telemetri:** File-creation olaylarını uç noktadan (endpoint) anlık toplayan bir sistem, dosyanın gerçek geliş zamanını diskteki zaman damgasından bağımsız olarak saklar.

## Windows Event Log Temizleme ve Manipülasyonu

### Tanım ve Kök Neden

Windows Event Log (`.evtx` dosyaları, tipik olarak `%SystemRoot%\System32\winevt\Logs` altında) oturum açmalar, süreç oluşturma, servis kurulumu ve sayısız güvenlik olayını kaydeder. Saldırgan için bu, en doğrudan suçlayıcı delil kaynağıdır: Security log'undaki başarılı oturum açma (Logon), yeni servis kurulumu ya da hesap oluşturma kayıtları, saldırının anlatısını doğrudan verir.

Bu yüzden saldırganlar üç yol izler: (1) tüm log'u temizleme (clear), (2) belirli olay kayıtlarını seçerek çıkarma, (3) log servisini durdurma/askıya alma.

### Çalışma Mantığı

**Tüm log temizleme** en kaba yöntemdir ve genellikle `wevtutil` gibi yerel bir araç ya da API çağrısıyla yapılır. Kritik nokta: **Windows, log'un temizlendiği eylemi bizzat kaydeder.** Security log'unda **Event ID 1102** (audit log temizlendi), System log'unda **Event ID 104** (log temizlendi) üretilir. Yani "tüm delili sildim" hamlesi, kendisi bir delil bırakır. İyi saldırganlar bunu bildiği için tüm-temizleme yerine daha sofistike yollar tercih eder.

**Servisi askıya alma:** Bazı ileri teknikler, Event Log servisini (`EventLog`) sonlandırmadan, log yazan thread'leri askıya alarak (thread suspension) belirli bir zaman aralığında hiç kayıt üretilmemesini sağlar. Bu, "temizlik" olayı bile üretmediği için daha sinsidir; ama servisin anormal davranışı ve loglardaki **açıklanamayan sessizlik penceresi (gap)** iz bırakır.

**Seçici kayıt silme:** `.evtx` dosyasının ikili yapısını manipüle edip tek tek kayıtları çıkarmak teorik olarak mümkündür, ancak dosyanın iç sağlama (checksum) ve kayıt sayacı yapılarını tutarlı tutmak zordur; tutarsızlık analiz araçlarınca yakalanabilir.

### Tespit ve Savunma

- **Log forwarding / merkezi SIEM:** En güçlü savunma budur. Windows Event Forwarding (WEF) ya da bir ajan aracılığıyla log'lar **üretildikleri anda** merkezi, salt-yazılır (append-only) bir depoya gönderilirse, saldırgan uç noktadaki `.evtx` dosyasını silse bile merkezî kopya kalır. Anti-forensics'e karşı altın kural: **deliller olayın gerçekleştiği makinede tutulmamalı.**
- **1102 / 104 üzerine yüksek öncelikli alarm:** Log temizleme olayları neredeyse hiçbir zaman meşru değildir; bunlar için anında uyarı kurun.
- **Gap analizi:** Sürekli üretmesi beklenen bir sunucuda log'ların aniden durup sonra devam etmesi (zaman boşluğu) şüphelidir. Heartbeat/gözlem sürekliliği metrikleri bu boşlukları yakalar.
- **Servis durumu izleme:** `EventLog` servisinin durması ya da anormal davranışı bağımsız bir telemetriyle izlenmelidir.

## Prefetch, Amcache ve Shimcache Temizleme

### Tanım ve Kök Neden

Windows, çalıştırılan programları hızlandırmak ve uyumluluk için birçok yerde "yürütme kanıtı" (execution evidence) tutar:

- **Prefetch** (`%SystemRoot%\Prefetch\*.pf`): Bir programın çalıştırıldığını, kaç kez ve en son ne zaman çalıştırıldığını, hangi dosyalara eriştiğini gösterir. Adli açıdan "bu makinede şu exe çalıştı" için birinci sınıf delildir.
- **Amcache** (`Amcache.hve` registry hive'ı): Çalıştırılan/kurulmuş uygulamaların yolunu, SHA-1 hash'ini ve zaman bilgisini tutar.
- **Shimcache / AppCompatCache** (registry): Uygulama uyumluluk alt sistemi tarafından tutulan, çalıştırma/varlık kanıtı içeren bir başka kaynak.

Saldırgan, kötü amaçlı yürütülebilir dosyasının bu izlerini silerek "hiç çalışmamış" görüntüsü yaratmak ister.

### Çalışma Mantığı

Prefetch dosyalarını silmek dosya sistemi düzeyinde basittir, ancak yine burada **çokluluk savunması** devreye girer: Prefetch silinse bile Amcache veya Shimcache'te iz kalabilir; ya da tam tersi. Ayrıca Prefetch dosyasının silinmesi/eksikliği başlı başına anormaldir. Amcache ve Shimcache registry içinde olduğundan, bunları temiz bir şekilde manipüle etmek daha zordur ve genellikle registry yazma izleriyle çelişir.

Önemli dürüstlük notu: Bu artifact'lerin varlığı ve içeriği Windows sürümüne, yapılandırmaya (örneğin Prefetch'in SSD'lerde ya da sunucu SKU'larında varsayılan kapalı olabilmesi) göre değişir. Bu yüzden "her makinede kesinlikle şu iz olur" varsayımı yerine, **var olan izler arasında çapraz doğrulama** yaklaşımı esastır.

### Tespit ve Savunma

- **Çapraz artifact korelasyonu:** Bir yürütme kanıtı kaynağında olup diğerinde olmayan bir uygulama, seçici silmenin işaretidir. Prefetch'te olmayıp Amcache'te olan (ya da tersi) bir binary'yi araştırın.
- **Süreç oluşturma logları (Event ID 4688 / Sysmon Event ID 1):** Diskteki artifact'lerden bağımsız olarak, gerçek zamanlı süreç oluşturma telemetrisi tutulursa, saldırgan disk üzerindeki izleri silse bile yürütme merkezi logda kalır. Bu yüzden **komut satırı denetimini (command-line auditing) ve Sysmon'u** etkinleştirmek anti-forensics'e karşı temel bir kontrol katmanıdır.
- **Baseline karşılaştırması:** Prefetch dizininin beklenmedik biçimde boşalması ya da tek tek dosyaların eksilmesi, dizin baseline'ı ile karşılaştırılarak yakalanabilir.

## Volume Shadow Copy (VSS) Silme

### Tanım ve Kök Neden

Volume Shadow Copy Service (VSS), sistemin belirli anlardaki tutarlı kopyalarını (shadow copy / snapshot) oluşturur. Adli açıdan bu **paha biçilmez**dir: shadow copy'ler, saldırganın *sonradan sildiği* dosyaların ya da manipüle ettiği kayıtların eski hallerini içerebilir. Yani saldırgan bir dosyayı diskte değiştirse bile, eski shadow copy hâlâ orijinali barındırabilir.

Bu yüzden hem ransomware hem de gelişmiş saldırganlar için shadow copy'leri silmek öncelikli bir hedeftir: hem kurbanın geri dönüş (recovery) yeteneğini yok eder, hem de adli delil kaynağını ortadan kaldırır.

### Çalışma Mantığı

Shadow copy'ler `vssadmin`, WMI (`Win32_ShadowCopy`) veya `wmic` gibi yönetim arayüzleriyle silinebilir. Bu işlemler yönetici (administrator) yetkisi gerektirir; dolayısıyla shadow copy silinmesi, genellikle saldırganın zaten yetki yükselttiğinin de göstergesidir.

Kritik nokta: Bu silme eylemleri iz bırakır. VSS servisi ve ilgili alt sistem, shadow copy'lerin oluşturulup silinmesini kendi olaylarında kaydeder; ayrıca silme komutunu çalıştıran süreç, süreç oluşturma loglarında görünür. `vssadmin delete shadows` tarzı komutlar, tehdit avcılığında (threat hunting) klasik "yüksek güvenilirlikli" göstergelerdir çünkü meşru kullanımı nadirdir.

### Tespit ve Savunma

- **Komut satırı deseni izleme:** Shadow copy silmeye yönelik komutların çalıştırılması (süreç oluşturma + komut satırı denetimi ile) neredeyse her zaman kötü niyetlidir; anında yüksek öncelikli alarm konusu olmalıdır.
- **API/WMI düzeyi görünürlük:** Saldırganlar `vssadmin` yerine doğrudan COM/WMI arayüzünü kullanarak komut satırı tespitinden kaçabilir. Bu yüzden sadece komut adına değil, **VSS silme davranışına** (ilgili API çağrıları, servis olayları) bakan tespit daha dayanıklıdır.
- **Off-host / immutable yedek:** Shadow copy tek başına bir yedekleme stratejisi değildir; asıl savunma, saldırganın erişemeyeceği, değiştirilemez (immutable) ve makineden bağımsız yedeklerdir. Anti-forensics ancak deliller saldırganın kontrol alanının dışındaysa etkisiz kalır.

## USN Journal ve NTFS Meta Veri İzleri

### Tanım ve Çalışma Mantığı

**USN Journal** (Update Sequence Number Journal, `$Extend\$UsnJrnl`), NTFS'in bir birimdeki her dosya değişikliğini (oluşturma, silme, yeniden adlandırma, veri değişimi) sıralı olarak kaydettiği bir değişiklik günlüğüdür. Adli açıdan çok değerlidir çünkü **silinmiş dosyaların isimlerini ve üzerlerinde yapılan işlemleri**, dosyanın kendisi çoktan gitmiş olsa bile geçmişe dönük olarak gösterebilir.

Bu, timestomping ve dosya silme anti-forensics'ini yakalamak için mükemmel bir bağımsız kaynaktır: Saldırgan bir dosyayı oluşturup çalıştırıp silse ve zaman damgalarını değiştirse bile, USN journal bu işlemler dizisini zaman sırasıyla tutabilir. $SI zaman damgasıyla USN journal kaydının çelişmesi manipülasyonu ele verir.

Saldırganlar bu yüzden USN journal'ı silmeyi ya da devre dışı bırakmayı hedefleyebilir (`fsutil usn deletejournal` benzeri işlemler yönetici yetkisi ister). Ancak journal'ın silinmesi de anormal bir yönetimsel eylemdir ve süreç loglarında görünür.

### Tespit ve Savunma

- **USN journal'ı bir delil kaynağı olarak topla:** Adli imaj alırken ($MFT, $LogFile, $UsnJrnl birlikte), bu üçlü çapraz doğrulama için kullanılır.
- **Journal silme/devre dışı bırakma tespiti:** İlgili komut/işlemin çalıştırılması yüksek güvenilirlikli bir göstergedir.
- **$LogFile korelasyonu:** NTFS'in kendi işlem günlüğü ($LogFile) da kısa vadeli meta veri değişikliklerini içerir ve USN ile birlikte tutarlılık kontrolü sağlar.

## Genel Savunma Mimarisi: Anti-Forensics'e Karşı İlkeler

Tek tek tekniklerin ötesinde, savunmacının benimsemesi gereken birkaç yapısal ilke vardır:

1. **Delili olay yerinden uzaklaştır.** Log forwarding, EDR telemetrisi ve merkezi SIEM ile veriler üretildikleri anda saldırganın erişemeyeceği bir yere kopyalanmalı. Yerel diskteki her artifact silinebilir; merkezî ve immutable kopya silinemez.
2. **Çokluluğa güven.** Hiçbir artifact tek başına gerçeğin tamamı değildir. $SI/$FN, Prefetch/Amcache/Shimcache, Event Log/Sysmon, USN/MFT gibi bağımsız kaynakların çapraz doğrulaması, tekil silmeleri etkisiz kılar.
3. **"Silme eylemi" de bir olaydır.** 1102, 104, shadow copy silme, journal silme gibi eylemler kendileri yüksek değerli sinyallerdir. İyi bir tespit stratejisi, delilin yokluğunu değil, **yok edilme eylemini** yakalar.
4. **Denetimi (auditing) doğru yapılandır.** Command-line auditing, Sysmon, süreç oluşturma ve nesne erişim denetimi açık olmalı. Anti-forensics'in en sinsi biçimi, hiç log üretilmemesini sağlamaktır; bunu ancak sağlam ve dirençli bir logging tabanı engeller.
5. **Zaman senkronizasyonu.** Tüm sistemler güvenilir bir zaman kaynağıyla (NTP) senkron olmalı ki farklı kaynaklardaki zaman damgaları korele edilebilsin; timestomping'i yakalamanın önkoşulu tutarlı bir zaman referansıdır.

## Yaygın Hatalar

- **Sadece diskteki artifact'e güvenmek.** Yerel `.evtx`, Prefetch ya da zaman damgalarına tam güvenmek, bunların manipüle edilebilir olduğunu göz ardı eder. Adli sonuç her zaman bağımsız kaynaklarla doğrulanmalıdır.
- **$FN zaman damgalarını atlamak.** Timestomping incelemesinde yalnızca Gezgin'in gösterdiği ($SI) değerlere bakmak, en yaygın tespit fırsatını kaçırmaktır.
- **Log temizlenince "iz yok" sanmak.** 1102/104 olayları, gap analizi ve merkezi kopyalar sayesinde temizleme genellikle kendini ele verir. Boş log, "olay yok" demek değil, "birileri temizledi" demek olabilir.
- **VSS'i yedek sanmak.** Shadow copy hem saldırganca silinebilir hem de gerçek felaket kurtarma için yetersizdir; asıl güvence off-host, immutable yedeklerdir.
- **Tespiti tek komut adına bağlamak.** `vssadmin` yerine WMI, `wevtutil` yerine API kullanımı gibi varyasyonlar, imza bazlı tespiti atlatır. Tespit, komut adına değil **davranışa** dayanmalıdır.
- **Zaman senkronizasyonunu ihmal etmek.** Saatleri uyumsuz sistemlerde çapraz zaman çizelgesi analizi çöker; bu da her türlü zaman tabanlı tespiti zayıflatır.

## Özet

Anti-forensics, saldırının kalıcılık zincirinin doğal ve genellikle son halkasıdır: yetki yükseltme sonrası saldırgan, timestomping ile zaman damgalarını, event log clear ile denetim kayıtlarını, Prefetch/Amcache temizleme ile yürütme kanıtlarını, shadow copy ve USN journal silme ile geri dönüş ve meta veri izlerini hedefler. Ancak her yok etme eyleminin kendisi de bir iz bırakır ve Windows'un artifact çokluluğu, savunmacıya bağımsız çapraz doğrulama imkânı verir. Anti-forensics'i etkisiz kılmanın anahtarı üç ilkededir: delili olay yerinden uzaklaştırmak (merkezi/immutable toplama), bağımsız kaynakları korele etmek ve yok etme eyleminin kendisini yüksek değerli bir alarm olarak izlemek.
