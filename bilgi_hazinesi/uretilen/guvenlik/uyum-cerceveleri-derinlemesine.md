# Uyum Çerçeveleri Derinlemesine: ISO 27001, NIST CSF 2.0/800-53, PCI DSS 4.0, SOC 2, KVKK/GDPR, DORA, NIS2

## Giriş: Neden Bu Konu Ayrı Bir Uzmanlık Alanıdır

Güvenlik mühendisliği literatüründe genellikle "risk değerlendirmesi" ve "threat modeling" tek bir madde olarak geçiştirilir; oysa bu ikisi ile "uyum (compliance)" arasında kritik bir fark vardır. Risk değerlendirmesi ve STRIDE gibi threat modeling teknikleri **sizin** organizasyonunuz için "ne kötü olabilir" sorusuna cevap arar; serbest formattadır, sonucu sizsiniz belirlersiniz. Uyum çerçeveleri ise **dışarıdan dayatılan, madde madde yazılmış, kanıtlanabilir ve denetlenebilir** gereksinim setleridir. Bir sistemin "güvenli" olması ile "uyumlu (compliant)" olması aynı şey değildir — biri teknik bir durum, diğeri hukuki/sözleşmesel bir durumdur ve ikisi çoğu zaman örtüşür ama asla birebir aynı değildir.

Bu makalenin amacı, bir güvenlik mühendisinin veya GRC (Governance, Risk, Compliance) uzmanının günlük işinde karşılaştığı yedi büyük çerçeveyi; kontrol maddesi seviyesinde, denetim kanıtı toplama mantığıyla ve teknik-uyum eşleştirmesi perspektifiyle ele almaktır. Kök neden şudur: bir organizasyon "güvenlik iyi uygulamaları"nı takip etse bile, bunu **kanıtla** ("evidence") gösteremiyorsa denetimden geçemez, sözleşme imzalayamaz veya para cezası yer. Dolayısıyla teknik kontrol ile denetim kanıtı arasındaki köprüyü kurmak, saf teknik savunmadan farklı, ayrı bir disiplindir.

---

## 1. ISO/IEC 27001:2022 ve Ek-A Kontrolleri

### Çalışma Mantığı

ISO 27001 bir **Bilgi Güvenliği Yönetim Sistemi (BGYS / ISMS)** standardıdır — yani teknik bir kontrol listesinden önce bir **yönetim süreci** tanımlar: Plan-Do-Check-Act (PDCA) döngüsü üzerine kurulu, sürekli iyileştirme mantığı taşıyan bir sistem. Ana gövde (madde 4-10) yönetimin taahhüdünü, kapsam belirlemeyi, risk değerlendirme metodolojisini ve iç denetimi zorunlu kılar. **Ek-A (Annex A)** ise 2022 revizyonuyla 93 kontrole indirgenmiş, 4 tema altında toplanmış (Organizational, People, Physical, Technological) bir kontrol kataloğudur.

Kök neden mantığı şudur: ISO 27001 size "şu firewall kuralını yaz" demez; "varlıklarınızı envanterleyin, risklerini değerlendirin, bu risklere karşı **Statement of Applicability (SoA)** içinde hangi Ek-A kontrolünü neden uyguladığınızı veya uygulamadığınızı gerekçelendirin" der. Bu, standardın esnekliğinin hem gücü hem de denetimdeki en çok tartışılan noktasıdır: aynı kontrol, iki farklı şirkette çok farklı teknik uygulamalarla karşılanabilir.

### Kanıt Toplama ve Gap Analizi

Denetçi (iç veya dış) her kontrol için üç şeyi sorar: **Politika var mı (yazılı kural), uygulama var mı (teknik/idari gerçekleşme), kanıt var mı (log, ekran görüntüsü, onay kaydı)**. Örnek: A.8.16 "İzleme Faaliyetleri" kontrolü için sadece bir SIEM (Security Information and Event Management) kurulu olması yetmez; alarm kurallarının gözden geçirildiğine, false-positive oranının izlendiğine ve olay müdahale sürecine bağlandığına dair kanıt istenir.

**Gap analizi** metodolojik olarak şöyle işler: mevcut durum (as-is) ile Ek-A'nın 93 kontrolü karşılaştırılır, her biri için olgunluk seviyesi (yok / kısmen / tam) puanlanır, öncelik risk×maliyet matrisiyle sıralanır ve bir **remediation roadmap** çıkarılır. Bu belge genellikle sertifikasyon öncesi "gap assessment" adıyla ayrı bir teslim edilebilir olarak üretilir.

### Yaygın Hatalar

- **SoA'yı kopyala-yapıştır şablon olarak doldurmak**: Denetçiler SoA'daki gerekçelerin şirkete özgü olup olmadığını (varlık envanterine, risk kayıtlarına referans verip vermediğini) kontrol eder.
- **Kontrolü "var" işaretleyip kanıt sunamamak**: En sık reddedilme (non-conformity) nedeni budur.
- **İç denetimi (madde 9.2) formaliteye indirgemek**: İç denetim bulgularının düzeltici faaliyet (corrective action) sürecine bağlanmaması.

### Tespit / Savunma Açısı

Mühendislik ekibi için pratik çıkarım: her teknik kontrolü (erişim yönetimi, şifreleme, log tutma) hayata geçirirken **otomatik kanıt üretimi**ni tasarımın bir parçası yapın — örneğin IAM (Identity and Access Management) değişiklik onaylarının otomatik olarak bir kayıt sistemine (ticket + onay + zaman damgası) düşmesi, denetim hazırlığını manuel evrak toplamaktan çıkarıp sürekli hazır (continuous audit readiness) hâle getirir.

---

## 2. NIST CSF 2.0 ve NIST 800-53

### CSF 2.0: Fonksiyon Bazlı Dil

NIST Cybersecurity Framework 2.0, 2024'te güncellenerek altıncı bir fonksiyon eklendi: **Govern (Yönet)** — önceki beşi Identify, Protect, Detect, Respond, Recover idi. Govern'ün eklenmesinin kök nedeni şuydu: CSF 1.1 uygulayan organizasyonlarda teknik kontroller vardı ama üst yönetim hesap verebilirliği, tedarik zinciri risk yönetimi ve strateji-risk hizalaması eksikti. CSF artık ISO 27001'e daha yakın bir "yönetişim önce" mantığına kaymıştır.

CSF'nin kendisi bir kontrol listesi değil, bir **ortak dil ve olgunluk haritalama aracıdır** — "Tiers" (Partial, Risk Informed, Repeatable, Adaptive) ile organizasyonun risk yönetim olgunluğunu, "Profiles" ile mevcut durum/hedef durum farkını tanımlar. Bu nedenle CSF genellikle 800-53 gibi daha ayrıntılı bir kontrol kataloğuyla **eşleştirilerek (mapped)** kullanılır.

### NIST 800-53: Kontrol Kataloğu ve Baseline Mantığı

800-53, ABD federal sistemleri için yazılmış ama dünya çapında referans alınan, 20 kontrol ailesi (AC-Access Control, AU-Audit, IR-Incident Response, SC-System and Communications Protection vb.) altında yüzlerce kontrolden oluşan bir katalogdur. Kök çalışma mantığı **risk bazlı katmanlama**dır: FIPS 199 ile sistem Low/Moderate/High etki seviyesine sınıflandırılır, sonra 800-53B'deki baseline'lardan hangi kontrol setinin uygulanacağı belirlenir, ardından **tailoring** (organizasyona özgü ayarlama — kontrol ekleme/çıkarma/telafi edici kontrol tanımlama) yapılır.

Her kontrolün alt bileşenleri vardır: temel kontrol + **control enhancements** (örneğin AC-2 "Account Management" temel kontrolü + AC-2(1) "otomatik hesap yönetimi" geliştirmesi). Bu, teknik ekipler için önemlidir çünkü "AC-2 uygulandı" demek yetersizdir; hangi enhancement'ların uygulandığı denetim kanıtının netliğini belirler.

### RMF (Risk Management Framework) ile İlişki

800-53 kontrolleri, 800-37'deki RMF'nin altı adımıyla (Categorize, Select, Implement, Assess, Authorize, Monitor) hayata geçirilir. **Assess** adımında 800-53A kullanılan değerlendirme prosedürleridir — her kontrol için "Examine, Interview, Test" yöntemleriyle kanıt toplanır. Bu üçlü, ISO 27001 denetiminden farklı olarak çok daha **prosedürel ve test-ağırlıklıdır**: örneğin bir erişim kontrolü için sadece dokümana bakmak (examine) yetmez, sistemde canlı test (test) ve sorumlu personelle görüşme (interview) yapılır.

### Yaygın Hatalar ve Savunma

- Baseline'ı olduğu gibi uygulayıp tailoring'i atlamak — bu, gereksiz kontrol yükü veya kritik boşluklara yol açar.
- POA&M (Plan of Action & Milestones) sürecini, yani "henüz karşılanmayan kontrol için telafi planı" belgelemeyi ihmal etmek — denetimde bu, "kontrol yok" ile "kontrol yönetiliyor ama henüz tamamlanmadı" arasındaki farkı gösteren kritik belgedir.
- Sürekli izleme (Continuous Monitoring, RMF adım 6) yerine "point-in-time" değerlendirmeyle yetinmek; oysa modern beklenti otomatik kontrol durumu izlemedir (örneğin SCAP/OSCAL ile makine-okunur kontrol durumu raporlama).

---

## 3. PCI DSS 4.0

### Amaç ve Kök Neden

PCI DSS (Payment Card Industry Data Security Standard), kart verisi (PAN — Primary Account Number) işleyen, ileten veya saklayan her kuruluşu bağlar. Kök mantığı: kart verisi çalınmasının maliyetini kart şemalarından (Visa/Mastercard) tacirlere ve işlemcilere aktarmak, dolayısıyla teknik kontrolleri sözleşmesel yükümlülük haline getirmektir. v4.0 (2022, zorunlu geçiş 2024-2025), önceki "check-box" eleştirisine cevaben **Customized Approach** seçeneğini getirdi: kuruluş, standart kontrolü birebir uygulamak yerine, aynı güvenlik hedefine ulaştığını kanıtlayan alternatif bir kontrol tasarlayıp bunu risk analizi ve test kanıtıyla belgeleyebilir.

### Kapsam Belirleme (Scoping) — En Kritik Adım

PCI DSS'in en teknik ve en çok hata yapılan kısmı **kapsam belirlemedir**. Kapsam, kart verisiyle doğrudan etkileşen sistemler (CDE — Cardholder Data Environment) artı bunlarla **bağlantılı veya bunları etkileyebilen** sistemleri kapsar (connected-to / security-impacting sistemler — örneğin CDE'ye erişimi olan bir yönetim istasyonu, kapsam dışı olsa bile CDE'yi etkileyebiliyorsa kapsama girer).

**Segmentasyon testi** burada devreye giren somut teknik kontroldür: eğer ağ segmentasyonuyla kapsam daraltılmak isteniyorsa (kapsam dışı ağların CDE'ye erişemediğini iddia ediyorsanız), bunu **penetrasyon testiyle kanıtlamak zorunludur** (Requirement 11.4.5). Bu test, segmentasyon kontrollerinin (firewall/ACL kuralları, VLAN ayrımı) gerçekten etkili olduğunu; yani CDE dışındaki bir sistemden CDE'ye erişim denemesinin başarısız olduğunu göstermelidir. Segmentasyon testi eksikse veya zayıfsa, denetçi tüm ağı kapsam içi kabul eder — bu maliyet ve denetim yükünü katlar.

### Somut Kontrol Örnekleri ve Teknik-Uyum Eşleştirmesi

- **Requirement 3**: Saklanan kart verisinin korunması — PAN saklanıyorsa güçlü şifreleme (AES gibi) veya tokenization zorunlu; CVV/CVC gibi hassas kimlik doğrulama verisinin **yetkilendirme sonrası asla saklanmaması** mutlak kuraldır. Teknik karşılığı: log dosyalarında, hata ayıklama (debug) çıktılarında veya bellek dump'larında yanlışlıkla PAN/CVV sızıntısı olup olmadığının DLP (Data Loss Prevention) ve statik kod analiziyle taranması.
- **Requirement 6**: Güvenli yazılım geliştirme — SAST/DAST (Static/Dynamic Application Security Testing) entegrasyonu, değişiklik yönetimi süreçlerinin denetim izinin tutulması.
- **Requirement 8/v4.0 yeniliği**: Çok faktörlü kimlik doğrulama (MFA) artık CDE'ye her erişim için (sadece uzaktan erişim değil) zorunlu hale geldi — bu, önceki versiyona göre en somut sıkılaştırmadır.
- **Requirement 10/11**: Log toplama + günlük log incelemesi + düzenli açıklık taraması (ASV taramaları — Approved Scanning Vendor, üç ayda bir) + yıllık penetrasyon testi.

### Yaygın Hatalar

- Kapsam daraltmayı "biz zaten segmentliyiz" varsayımıyla yapıp testle doğrulamamak.
- Tokenization sağlayıcısını devreye alıp CDE'nin hâlâ tokenization öncesi ham PAN'a dokunduğu ara adımları (örneğin bir loglama middleware'i) kapsam dışı sanmak.
- v4.0'ın getirdiği "hedef bazlı özelleştirilmiş yaklaşım"ı gerekçelendirme yükünü hafife almak — bu yaklaşım daha fazla, standart yaklaşımdan daha ağır belgeleme gerektirir.

---

## 4. SOC 2 (System and Organization Controls 2)

### Yapısı: Trust Services Criteria

SOC 2, AICPA (Amerikan Sertifikalı Kamu Muhasebecileri Enstitüsü) tarafından tanımlanan, bir **denetim raporu türüdür** — ISO/PCI gibi "sertifika" değil, bağımsız bir denetçinin (CPA firması) görüşünü içeren bir rapordur. Beş **Trust Services Criteria (TSC)** kategorisi vardır: Security (zorunlu, "Common Criteria" olarak da bilinir), Availability, Processing Integrity, Confidentiality, Privacy. Security dışındakiler kuruluşun kapsamına göre seçimlik.

### Type I vs Type II — Kritik Fark

Bu ayrım sıkça karıştırılır ama denetim mantığı açısından temeldir: **Type I** raporu belirli bir **an**da (point-in-time) kontrollerin tasarımının uygunluğunu değerlendirir — "kontrol var mı, mantıklı tasarlanmış mı". **Type II** ise bir **dönem boyunca** (tipik olarak 6-12 ay) kontrollerin **fiilen çalıştığını** test eder — "operating effectiveness". Müşteriler/ortaklar genellikle Type II ister çünkü Type I sadece anlık fotoğraftır, sürekliliği kanıtlamaz.

### Kanıt Toplama Mantığı

Common Criteria, COSO çerçevesinin beş bileşenine (Control Environment, Risk Assessment, Control Activities, Information & Communication, Monitoring) dayanır ve bunun üstüne CC6 (Logical/Physical Access), CC7 (System Operations/Incident Response) gibi ek kriterler eklenir. Denetçi her kriter için **örnekleme (sampling)** yöntemiyle kanıt talep eder: örneğin "son 6 ayda işten ayrılan 25 çalışandan 10'unu seç, erişimlerinin 24 saat içinde kapatıldığını göster" gibi. Bu, sürekli, otomatikleştirilmiş kanıt toplama altyapısının (örneğin bir GRC platformunda IAM loglarının otomatik çekilmesi) neden değerli olduğunu açıklar — manuel kanıt toplama Type II denetimlerinde ölçeklenmez.

### Yaygın Hatalar

- Kontrolü sadece denetim dönemi başlarken kurup "sürekli çalıştığını" iddia etmek — Type II örneklemesi bunu yakalar (örneğin bir kontrol Ocak'ta yoktu, Mart'ta kuruldu, denetçi bunu istisna/exception olarak raporlar).
- Alt yüklenici (subservice organization) risklerini "carve-out" yöntemiyle dışlayıp, bu yüklenicinin kendi SOC 2 raporunu takip etmemek (complementary user entity controls'un göz ardı edilmesi).

---

## 5. KVKK ve GDPR — Teknik Gereksinimler

### Kök Mantık: Veri Koruma "By Design and By Default"

KVKK (6698 sayılı Kanun, Türkiye) ve GDPR (AB) birbirine büyük ölçüde paralel ama tam örtüşmeyen iki rejimdir. Her ikisinin de teknik köküne indiğinizde şu mantık yatar: kişisel veri işleme bir **hukuki dayanağa** (açık rıza, sözleşme, kanuni yükümlülük vb.) bağlanmalı ve bu işleme **hesap verebilir (accountable)** şekilde belgelenmelidir. "Privacy by Design/Default" (GDPR Md.25) ilkesi, güvenliği sonradan eklenen bir katman değil, sistem tasarımının başlangıç noktası yapar.

### Somut Teknik Gereksinim: Veri İşleme Envanteri (ROPA)

GDPR Md.30 ve KVKK'nın VERBİS (Veri Sorumluları Sicil Bilgi Sistemi) kaydı, aynı kök ihtiyacın iki farklı uygulamasıdır: **hangi kişisel verinin, hangi amaçla, kimden toplandığı, kimlerle paylaşıldığı, ne kadar saklandığı ve nasıl korunduğunun envanterini** tutmak. Teknik ekip için bunun karşılığı **veri akış haritalama (data flow mapping)** çalışmasıdır: her mikroservisin/veritabanının hangi kişisel veri alanlarını tuttuğunu, bu verinin nereden nereye aktığını (üçüncü taraf API'ler dahil) çıkaran otomatikleştirilmiş veya yarı-otomatik keşif (data discovery/classification) araçlarıyla desteklenen bir süreç.

Bu envanter olmadan ne DPIA (Data Protection Impact Assessment / KVKK'da benzer mahiyette risk analizleri) ne de bir veri ihlali bildirimi (72 saat kuralı — GDPR Md.33, KVKK'da 72 saat benzeri süre) doğru yapılabilir çünkü "hangi verinin etkilendiği" sorusuna hızlı cevap vermek, önceden çıkarılmış bir envanterle mümkündür.

### Teknik-Uyum Eşleştirmesi: Pseudonymization, Şifreleme, Silme Hakkı

- **Pseudonymization (GDPR Md.32)**: Doğrudan tanımlayıcıların (ad, TCKN/ulusal kimlik no) ayrı bir anahtar tablosuyla değiştirilmesi — şifrelemeden farklıdır, geri döndürülebilir ama anahtar ayrı tutulursa veri "kişisel veri" sayılma riskini azaltır. Teknik karşılığı: veritabanı tasarımında tokenization katmanı, anahtar yönetiminin (KMS) ayrı erişim kontrolüyle izole edilmesi.
- **Silme/unutulma hakkı (Right to Erasure)**: Teknik zorluk, verinin **tüm** kopyalarının (yedekler, log'lar, cache, üçüncü taraf işlemciler, veri ambarı) silinmesini garanti etmektir. Bu genellikle "soft delete" ile "hard delete" arasındaki farkın ve yedekleme rotasyon politikasının (backup retention) uyumla çelişebileceği noktadır — pratik çözüm çoğunlukla "yedekte kalan veri, geri yüklenirse tekrar silinecek şekilde işaretlenir" politikasıdır.
- **Veri işleyen (processor) sözleşmeleri**: GDPR Md.28 / KVKK'nın veri işleyen yükümlülükleri — bir bulut sağlayıcısı veya SaaS aracı kullanıyorsanız, DPA (Data Processing Agreement) imzalanmadan veri aktarımı hukuki dayanaktan yoksun kalır. Teknik ekip için çıkarım: yeni bir üçüncü taraf entegrasyonu **önce** hukuki/DPA onayından geçmeli, sonra veri akışı açılmalı.

### Yaygın Hatalar

- Envanteri (ROPA/VERBİS) bir kerelik proje olarak yapıp güncel tutmamak — yeni bir özellik kişisel veri alanı eklediğinde envanterin güncellenmemesi en sık rastlanan boşluktur.
- Pseudonymization'ı anonimleştirme (anonymization) ile karıştırmak — pseudonymized veri hâlâ GDPR/KVKK kapsamındadır, anonim veri değildir.
- Sınır ötesi veri aktarımı (KVKK Md.9, GDPR Ch.V — SCC/Standard Contractual Clauses) mekanizmasını atlayıp veriyi yurt dışı sunucuya taşımak.

---

## 6. DORA (Digital Operational Resilience Act)

DORA, AB'de finansal sektör (bankalar, sigorta, yatırım firmaları ve bunlara BT hizmeti veren üçüncü taraflar dahil) için Ocak 2025'te yürürlüğe giren, **operasyonel dayanıklılığı** merkeze alan bir düzenlemedir. Kök mantığı: geleneksel uyum çerçeveleri "önleme"ye odaklanırken, DORA "kesinti olacağını varsayıp hızlı toparlanma (resilience) kapasitesini" zorunlu kılar. Beş sütunu vardır: BT risk yönetimi, olay raporlama (ICT-related incident reporting — sıkı zaman çizelgeli), dijital operasyonel dayanıklılık testi (TLPT — Threat-Led Penetration Testing dahil), üçüncü taraf risk yönetimi (kritik BT sağlayıcılarının doğrudan düzenleyici gözetimi) ve bilgi paylaşımı.

Teknik ekip için en somut fark: **TLPT**, klasik pentest'ten daha ileri — kırmızı takım (red team) tarafından gerçek tehdit istihbaratına dayalı, canlı prodüksiyon sistemlerine karşı (kontrollü şekilde) yapılan, düzenleyici gözetiminde yürütülen bir tatbikattır. Ayrıca kritik üçüncü taraf BT sağlayıcıları (büyük bulut sağlayıcılar gibi) artık AB düzenleyicileri tarafından **doğrudan** denetlenebilir hale gelmiştir — bu, tedarik zinciri risk yönetimini "sözleşmesel" olmaktan çıkarıp "düzenleyici" bir konuya taşımıştır.

---

## 7. NIS2 (Network and Information Security Directive 2)

NIS2, AB'de "temel" ve "önemli" sektörlerdeki (enerji, ulaşım, sağlık, dijital altyapı, kamu yönetimi vb.) kuruluşlar için siber güvenlik risk yönetimini ve olay bildirimini düzenler; NIS1'e göre kapsamı genişletmiş ve yaptırımları (üst yönetim kişisel sorumluluğu dahil) sertleştirmiştir. Kök mantığı DORA'ya benzer ama sektör kapsamı finansal olmayan kritik altyapıya odaklanır. Teknik gereksinimler arasında **tedarik zinciri güvenliği**, olay müdahale ve iş sürekliliği planları, şifreleme ve zafiyet yönetimi politikaları, ve **erken uyarı bildirimi** (olay tespitinden itibaren 24 saat içinde ilk bildirim, 72 saat içinde detaylı rapor gibi sıkı zaman çizelgeleri) yer alır. Kritik fark: NIS2'de üst yönetim, siber risk yönetimi eğitimi almak ve önlemleri onaylamakla **kişisel olarak** yükümlü tutulur — bu, güvenliği IT departmanından çıkarıp yönetim kurulu gündemine taşıyan en somut değişikliktir.

---

## 8. Çerçeveler Arası Eşleştirme (Cross-Mapping) Mantığı

Büyük kuruluşlar genellikle birden fazla çerçeveye aynı anda tabidir (örneğin bir AB bankası: DORA + GDPR + ISO 27001 + SOC 2 müşteri talebiyle). Burada devreye giren pratik, **kontrol eşleştirme matrisi (control mapping)** kurmaktır: örneğin "MFA zorunluluğu" tek bir teknik kontrol olarak uygulanır ama bu kontrol; ISO 27001 A.8.5, NIST 800-53 IA-2, PCI DSS Req.8.4, SOC2 CC6.1 gibi birden fazla çerçevede karşılık bulur. İyi kurulmuş bir GRC programı, kontrolleri **çerçeveye göre değil, teknik gerçekliğe göre** bir kere uygular ve bunu bir eşleştirme tablosuyla her çerçevenin diliyle ifade eder (bu genellikle "Unified Control Framework" veya "Common Control Framework" olarak adlandırılır). Bu yaklaşımın kök nedeni basittir: aynı MFA kontrolünü yedi farklı denetim için yedi kere ayrı ayrı "uygulamak" yerine bir kere sağlam kurup, kanıtını tüm çerçevelere eşleştirmek mühendislik ve denetim maliyetini ciddi biçimde düşürür.

## 9. Gap Analizi ve Denetim Kanıtı Toplamanın Ortak Metodolojisi

Tüm çerçevelerde tekrar eden bir desen vardır: **(1) kapsam belirleme, (2) mevcut kontrol envanteri çıkarma, (3) gereksinimle mevcut durumu karşılaştırma (gap), (4) risk bazlı önceliklendirme, (5) düzeltici faaliyet planı, (6) kanıt toplama altyapısı kurma, (7) sürekli izleme.** Modern GRC pratiğinde bu döngü, manuel Excel tablolarından **sürekli kontrol izleme (Continuous Control Monitoring)** platformlarına kaymaktadır: API'ler üzerinden bulut yapılandırmasını (IAM politikaları, şifreleme durumu, log saklama süreleri) otomatik çekip, her kontrolü hangi çerçeve maddesine eşlediğini gösteren, kanıtı zaman damgalı şekilde saklayan sistemler. Bir güvenlik mühendisi için pratik çıkarım: yeni bir sistem tasarlarken "bu kontrolün denetim kanıtı otomatik olarak nasıl üretilecek" sorusunu mimari kararın bir parçası yapmak, sonradan manuel kanıt toplama krizini önler.

## Sonuç

Uyum çerçeveleri, teknik güvenlik kontrollerinin üzerine oturan bir **hesap verebilirlik ve kanıt katmanıdır**. ISO 27001 ve SOC 2 daha genel yönetim sistemi/güven kriterleri sunarken, PCI DSS çok somut teknik gereksinimler (segmentasyon testi gibi) dayatır; KVKK/GDPR veri merkezli hukuki-teknik hibrit bir rejim kurar; DORA ve NIS2 ise operasyonel dayanıklılığı ve üst yönetim hesap verebilirliğini öne çıkaran en yeni nesil düzenlemelerdir. Bir savunma mühendisinin bakış açısından ortak ders şudur: kontrolü uygulamak yeterli değildir — kontrolün **sürekli çalıştığını, kanıtlanabilir şekilde** göstermek, modern güvenlik/uyum mühendisliğinin asıl işidir.
