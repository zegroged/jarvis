# Dokümantasyon Mühendisliği: ADR, API Referans Üretimi, Docs-as-Code, Runbook Standartları

## Giriş: Dokümantasyon Neden Bir Mühendislik Disiplinidir

Yazılım dünyasında dokümantasyon genellikle "iş bittikten sonra yazılan, kimsenin okumadığı, hızla eskiyen metin" olarak görülür. Bu algı, dokümantasyonun bir **yan ürün** değil, bir **mühendislik artefaktı** olduğu gerçeğini gözden kaçırır. Kod nasıl derlenip test ediliyorsa, dokümantasyon da üretilmeli, doğrulanmalı ve sürüm kontrolüne tabi tutulmalıdır. Bu makalenin konusu, dokümantasyonu "yazı işi" olmaktan çıkarıp mühendislik disiplinine dönüştüren dört temel pratik: Architecture Decision Records (ADR), otomatik API referans üretimi, docs-as-code akışı ve runbook standartları.

Kök neden şudur: yazılım sistemleri zamanla büyür, insanlar takımlardan ayrılır, kararlar unutulur ve "neden böyle yaptık" sorusunun cevabı sadece birkaç kişinin kafasında kalır. Bu, **bilgi silosu** (knowledge silo) ve **bus factor** (bir kişinin ayrılmasıyla bilginin kaybolma riski) problemlerine yol açar. Dokümantasyon mühendisliği, bilgiyi insan hafızasından çıkarıp sistematik, aranabilir, sürüm kontrollü bir forma taşıyarak bu riski azaltır.

## Architecture Decision Records (ADR)

### Tanım ve Çalışma Mantığı

ADR, bir mimari kararın **ne olduğunu, neden alındığını, hangi alternatiflerin değerlendirildiğini ve hangi sonuçları doğurduğunu** kaydeden kısa, yapılandırılmış bir belgedir. Michael Nygard'ın popülerleştirdiği format, genellikle şu bölümlerden oluşur:

- **Title**: Kararın kısa başlığı (örnek: "ADR-014: Mesaj kuyruğu olarak Kafka seçildi")
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Context**: Kararın alınmasını gerektiren durum, kısıtlar, iş gereksinimleri
- **Decision**: Ne karar verildi
- **Consequences**: Kararın olumlu ve olumsuz sonuçları, ödünleşimler (trade-off)

Kök neden mantığı şudur: kod, **ne yaptığını** gösterir ama **neden o şekilde yapıldığını** göstermez. Bir yıl sonra gelen mühendis, "neden ORM kullanmadık da raw SQL yazdık" sorusuna kod içinde cevap bulamaz. ADR olmadan bu bilgi ya kaybolur ya da sözlü aktarımla (tribal knowledge) bozularak dolaşır. ADR'ler, kararı alındığı anın bağlamıyla birlikte dondurur (freeze). Bu, kararların sonradan sorgulanmasını da kolaylaştırır: "O zamanki kısıtlar hâlâ geçerli mi?" sorusu, context bölümü sayesinde cevaplanabilir hale gelir.

### Doğru Kullanım

ADR'ler **immutable** (değiştirilemez) olarak ele alınmalıdır. Bir karar değiştiğinde eski ADR düzenlenmez; yeni bir ADR yazılır ve eskisi "Superseded by ADR-XXX" olarak işaretlenir. Bunun nedeni, kararların **tarihsel bir iz** (audit trail) oluşturmasıdır — kim, ne zaman, hangi bağlamda ne düşünmüş, bu bilgi kaybolmamalıdır. Eski ADR'yi silmek veya üzerine yazmak, tarihsel bağlamı yok eder.

ADR'ler kod deposunun içinde (`docs/adr/` veya `docs/decisions/`) tutulmalı, numaralandırılmalı ve pull request süreciyle gözden geçirilmelidir. Bu, ADR'yi kodla aynı yaşam döngüsüne sokar: kod review'da olduğu gibi, karar da takım tarafından tartışılıp onaylanır.

**Ne zaman ADR yazılır?** Her küçük teknik seçim için değil — geri dönüşü maliyetli (expensive to reverse), birden fazla ekibi etkileyen veya uzun vadeli sonuçları olan kararlar için. Değişken adı seçimi ADR gerektirmez; veritabanı motoru seçimi gerektirir. Bu eşiği doğru belirlemek önemlidir: her şey için ADR yazmak "ADR yorgunluğu" yaratır ve pratiğin terk edilmesine yol açar; hiçbir şey için yazmamak ise orijinal problemi geri getirir.

### Yaygın Hatalar ve Tuzaklar

- **Geç yazmak**: Karar alındıktan aylar sonra ADR yazmaya çalışmak, bağlamın (o anki kısıtların, alternatiflerin) unutulmuş olması nedeniyle kaliteyi düşürür. ADR, karar alma sürecinin **bir parçası** olmalı, sonradan eklenen bir formalite olmamalıdır.
- **Sadece kararı yazıp gerekçeyi atlamak**: "Kafka kullanacağız" yazıp neden RabbitMQ veya SQS'in elenmediğini belirtmemek, ADR'nin asıl değerini (gelecekteki sorgulanabilirlik) yok eder.
- **Consequences bölümünü boş bırakmak**: Her kararın olumsuz tarafları da vardır (operasyonel karmaşıklık, öğrenme eğrisi, vendor lock-in). Bunları yazmamak, kararı gerçekte olduğundan daha "temiz" gösterir ve gelecekte "bunu biliyor muyduk?" tartışmalarına yol açar.
- **ADR'yi güncel tutmamak**: Bir mimari kökten değiştiğinde eski ADR'lerin "Superseded" olarak işaretlenmemesi, yeni gelen birinin güncelliğini yitirmiş bir kararı gerçekmiş gibi okumasına neden olur.

## Otomatik API Referans Üretimi (OpenAPI/Swagger ve Kod-Kaynaklı Dokümantasyon)

### Tanım ve Çalışma Mantığı

API referans dokümantasyonu, bir servisin uç noktalarını (endpoint), istek/yanıt şemalarını, hata kodlarını ve kimlik doğrulama gereksinimlerini tanımlar. Buradaki temel mühendislik prensibi **tek gerçek kaynak** (single source of truth) ilkesidir: dokümantasyon elle, koddan bağımsız olarak yazılırsa, kod değiştikçe dokümantasyon eskir — buna **doc drift** (dokümantasyon kayması) denir.

Kök neden analizi: iki ayrı artefakt (kod ve onu anlatan ayrı metin) senkron tutulmaya çalışıldığında, insan disiplinine bağımlı bir süreç ortaya çıkar ve insan disiplini ölçeklenmez. Çözüm, dokümantasyonu **kodun kendisinden türetmektir** (generate from source), böylece kod değiştiğinde dokümantasyon otomatik olarak (ya da build sürecinin bir adımı olarak) güncellenir.

Bunun iki ana yolu vardır:

1. **Şema-öncelikli (schema-first / contract-first) yaklaşım**: OpenAPI (eski adıyla Swagger) şeması elle veya araçlarla yazılır, hem sunucu kodu hem istemci kodu (client SDK) hem de dokümantasyon bu şemadan üretilir. Şema, API'nin "gerçek kaynağı" olur.
2. **Kod-öncelikli (code-first) yaklaşım**: API kodu, tip bilgisi ve annotation/decorator'larla (örnek: FastAPI'de Python type hint'leri, ASP.NET'te attribute'lar) işaretlenir; bir araç bu kodu tarayıp OpenAPI şemasını ve/veya HTML dokümantasyonu otomatik üretir.

Her iki yaklaşımın da ortak noktası: dokümantasyon, elle senkronize edilen ayrı bir dosya değil, **derleme/build zincirinin bir çıktısıdır**. Şema doğrulaması genellikle CI'da otomatik çalıştırılır (linting, breaking-change tespiti) — böylece uyumsuz bir değişiklik merge edilmeden önce yakalanır.

### Doğru Kullanım ve En İyi Pratikler

- **Şemayı CI'da doğrulamak**: OpenAPI şemasının geçerli olup olmadığı, gerçek API davranışıyla eşleşip eşleşmediği (contract testing) otomatik testlerle kontrol edilmelidir. Aksi halde şema da "yalan söyleyen dokümantasyon" haline gelebilir.
- **Breaking change tespiti**: Şema diff araçları, bir alanın kaldırılması veya tipinin değişmesi gibi geriye dönük uyumsuz değişiklikleri PR aşamasında tespit edip uyarabilir. Bu, API tüketicilerinin (consumer) habersiz kırılmalarla karşılaşmasını önler.
- **Örnekleri (examples) gerçek veriyle senkron tutmak**: Şemadaki örnek istek/yanıtların gerçek davranışı yansıtması için, mümkünse bu örnekler entegrasyon testlerinden otomatik üretilmeli veya en azından test paketiyle doğrulanmalıdır.
- **Versiyonlama stratejisini dokümante etmek**: API sürüm geçişleri (v1 → v2), deprecation zaman çizelgesi ve geriye dönük uyumluluk politikası, ayrı bir belgeyle açıkça belirtilmelidir.

### Yaygın Hatalar

- **Şemayı elle güncel tutmaya çalışmak**: Kod-first yaklaşım yerine, koddan bağımsız elle yazılmış bir OpenAPI dosyası tutmak, zamanla gerçek API davranışından sapar. Bu, otomatik üretimin çözmeye çalıştığı tam problemi geri getirir.
- **Sadece "happy path"i dokümante etmek**: Hata durumları, rate-limit yanıtları, sayfalama (pagination) davranışı gibi "mutlu yol dışı" senaryolar genellikle atlanır; oysa API tüketicisinin en çok ihtiyaç duyduğu bilgi çoğunlukla budur.
- **İç detayları dışa sızdırmak**: Otomatik üretim, bazen iç veri modelini (internal DTO) doğrudan dışa yansıtabilir; bu hem güvenlik hem API tasarım sağlığı açısından risklidir. Dış API sözleşmesi, iç uygulamadan kasıtlı olarak ayrıştırılmalıdır (API şemasını içeriden değil, kasıtlı tasarlanmış bir sözleşme katmanından türetmek gerekir).

## Docs-as-Code

### Tanım ve Çalışma Mantığı

Docs-as-code, dokümantasyonun kod ile **aynı araçlarla, aynı süreçlerle** yönetilmesi felsefesidir:

- Düz metin formatında yazılır (Markdown, reStructuredText, AsciiDoc) — ikili (binary) formatlar (Word, wiki'nin kendi kapalı formatı) değil.
- Sürüm kontrolünde (Git) tutulur, kodla aynı depoda veya yakın bağlı bir depoda yaşar.
- Pull request / code review süreciyle değişir — dokümantasyon değişikliği de gözden geçirilir.
- CI/CD ile otomatik olarak derlenir (statik site üretici: MkDocs, Docusaurus, Sphinx vb.) ve yayınlanır.
- Linting ve otomatik testlerden geçer (kırık link kontrolü, stil rehberi uyumu, kod örneklerinin gerçekten çalışıp çalışmadığının test edilmesi).

Kök neden mantığı: dokümantasyon ayrı bir sistemde (örnek: kapalı bir wiki, paylaşılan bir Word dosyası) tutulduğunda, kod değişikliğiyle dokümantasyon değişikliği **farklı zaman dilimlerinde, farklı kişiler tarafından, farklı onay süreçleriyle** gerçekleşir. Bu ayrışma, doc drift'in temel nedenidir. Docs-as-code, dokümantasyonu kodun "yanına" koyarak aynı commit'te, aynı PR'da, aynı review disiplini altında değişmesini sağlar — yani **aynı değişiklik biriminin (unit of change) parçası** haline getirir.

Ayrıca, dokümantasyonun kod gibi **diff'lenebilir** olması, "kim ne zaman neyi neden değiştirdi" sorusuna Git tarihi üzerinden cevap verilebilmesini sağlar. Bu, wiki'lerin genellikle sağlayamadığı bir izlenebilirlik katmanıdır.

### En İyi Pratikler

- **Dokümantasyon değişikliğini kod değişikliğiyle aynı PR'a koymak**: Bir API değişikliği yapan PR, ilgili dokümantasyon güncellemesini de içermelidir. Bu, "dokümantasyonu sonra güncelleriz" tuzağını yapısal olarak engeller.
- **Otomatik link/stil kontrolü**: Kırık iç bağlantılar, tutarsız terminoloji, yazım kuralları CI'da otomatik kontrol edilebilir; bu insan gözden geçirmesinin yükünü azaltır.
- **Kod örneklerini test etmek**: Dokümantasyondaki kod parçacıklarının (code snippet) gerçekten derlendiğini/çalıştığını doğrulayan testler (doctest benzeri mekanizmalar) yazmak, "dokümantasyondaki örnek artık çalışmıyor" problemini önler.
- **Sahiplik (ownership) tanımlamak**: Her dokümantasyon bölümünün bir sahibi (CODEOWNERS benzeri mekanizma) olmalı, böylece ilgili kod değiştiğinde doğru kişi otomatik olarak review'a dahil edilir.

### Yaygın Hatalar

- **"Dokümantasyon sprintini" ayrı bir faaliyet olarak planlamak**: Dokümantasyonu, geliştirme işinin bir parçası değil de dönemsel olarak "toparlanması gereken borç" gibi görmek, docs-as-code'un temel felsefesiyle çelişir. Doğru yaklaşım, dokümantasyon güncellemesini "definition of done"ın bir parçası yapmaktır.
- **Statik site üretici seçimini aşırı karmaşıklaştırmak**: Araç seçimi önemlidir ama asıl değer sürece disiplinden gelir; en gelişmiş araç bile PR disiplini olmadan doc drift'i önleyemez.
- **Wiki ile docs-as-code'u karıştırmak**: Bazı takımlar hem bir wiki hem bir docs-as-code sistemi tutar; bu, "hangisi güncel" belirsizliği yaratır. Tek bir gerçek kaynak (source of truth) ilkesi burada da geçerlidir — wiki'ye ya tamamen geçiş yapılmalı ya da wiki sadece geçici/informal notlar için kullanılmalı.

## Runbook Standartları

### Tanım ve Çalışma Mantığı

Runbook, belirli bir operasyonel durumla (olay müdahalesi, rutin bakım, deployment, geri alma/rollback) karşılaşıldığında **adım adım ne yapılacağını** tanımlayan işlemsel bir belgedir. Amaç, kritik bir anda (özellikle stresli bir olay sırasında, örneğin gece yarısı çağrılan nöbetçi mühendis için) karar vermeyi insan hafızasından çıkarıp önceden test edilmiş, tekrarlanabilir bir prosedüre indirgemektir.

Kök neden mantığı: olay anında insan bilişi stres altında bozulur (tunnel vision, panik, yanlış varsayım). Runbook, "şu an ne düşünmem gerekiyor" sorusunu ortadan kaldırıp "şu an ne yapmam gerekiyor" sorusuna somut bir cevap verir. Ayrıca, runbook'un varlığı, bilginin tek bir kişinin (genellikle sistemi kuran mühendisin) kafasında hapsolmasını önler — o kişi izinli, işten ayrılmış veya ulaşılamaz olsa bile nöbetçi başka biri prosedürü takip edebilir.

### İyi Bir Runbook'un Anatomisi

- **Tetikleyici (trigger)**: Bu runbook ne zaman kullanılır? Hangi alarm/metrik/belirti bu prosedürü başlatır?
- **Ön koşullar ve yetkiler**: Hangi erişim, hangi araç gerekli?
- **Adım adım işlemler**: Belirsizlik bırakmayan, kopyala-yapıştır edilebilir komutlar (gerçek ortamda test edilmiş olmalı — teorik olarak doğru görünen ama denenmemiş komutlar tehlikelidir).
- **Doğrulama adımları**: Her adımdan sonra "başarılı oldu mu" nasıl anlaşılır?
- **Geri alma (rollback) planı**: Bir şey ters giderse nasıl eski duruma dönülür?
- **Eskalasyon yolu**: Runbook yetersiz kalırsa kime, nasıl ulaşılır?
- **Son güncelleme tarihi ve test kaydı**: Runbook'un ne zaman son çalıştırıldığı/doğrulandığı.

### Doğru Kullanım ve En İyi Pratikler

- **Runbook'ları düzenli olarak "tatbikat" (game day / fire drill) ile test etmek**: Kullanılmayan bir runbook, gerçek bir olayda çalışmayan komutlar, değişmiş dosya yolları veya artık geçersiz varsayımlar içerebilir. Periyodik tatbikat, runbook'un hâlâ doğru olduğunu doğrular — bu, testsiz kodun güvenilmez olmasıyla aynı mantık.
- **Otomasyona geçişin bir ara adımı olarak görmek**: Olgun bir runbook, zamanla bir script veya otomasyona (runbook automation / self-healing) dönüşmelidir. Runbook, "bunu otomatikleştirmeye değer mi" sorusunun cevabını da ortaya çıkarır — sık tekrarlanan, hataya açık, iyi tanımlanmış bir runbook otomasyon adayıdır.
- **Olay sonrası (postmortem/incident review) ile geri beslemek**: Bir olay sırasında runbook'un eksik kaldığı veya yanlış yönlendirdiği noktalar, olay sonrası incelemede tespit edilip runbook'a geri işlenmelidir. Bu, runbook'u statik bir belge değil, yaşayan bir artefakt haline getirir.
- **Erişilebilirlik**: Runbook, olay anında erişilebilir olmalıdır — eğer runbook'un kendisi, olaya neden olan sistemin (örnek: dahili wiki, aynı veritabanına bağımlı bir araç) üzerinde barınıyorsa, tam da ihtiyaç duyulduğu anda erişilemez hale gelebilir. Bu döngüsel bağımlılık, kritik runbook'ların bağımsız/yedekli bir kanaldan erişilebilir olmasını gerektirir.

### Yaygın Hatalar ve Tuzaklar

- **"Nasıl olsa aklımdaydı" varsayımıyla yazmamak**: Sistemi kuran kişi için bariz olan adımlar, ilk kez müdahale eden nöbetçi için bariz değildir. Runbook, "hiçbir bağlam bilgisi olmayan yetkin bir mühendis" varsayımıyla yazılmalıdır.
- **Eskimiş runbook'u güncel sanmak**: Sistem değiştikçe (yeni bir servis, değişen bir port, kaldırılan bir komut) runbook güncellenmezse, kriz anında yanlış talimat vermek gerçek bir riski büyütür — hiç runbook olmamasından daha kötü olabilir çünkü yanlış güven verir.
- **Sadece "ne yapılacağını" yazıp "neden" ve "risk" bilgisini atlamak**: Bir komutun potansiyel yan etkisi (örnek: "bu servisi yeniden başlatmak açık bağlantıları keser") belirtilmezse, nöbetçi mühendis riski göze alıp almayacağını değerlendiremez.
- **Aşırı otomasyon ile şeffaflığı kaybetmek**: Runbook'u tek bir "her şeyi düzelt" script'ine indirgemek, bir şey ters gittiğinde neyin, neden yapıldığını anlamayı zorlaştırabilir. Otomasyon, adımların şeffaf/loglanan/geri alınabilir olmasını korumalıdır.

## Bu Dört Pratiğin Ortak Paydası

ADR, otomatik API dokümantasyonu, docs-as-code ve runbook standartları, yüzeyde farklı belge türleri gibi görünse de aynı temel mühendislik ilkesinden beslenir: **bilgiyi, güvenilmez ve ölçeklenmeyen insan hafızasından/disiplininden çıkarıp, sistematik, doğrulanabilir, sürüm kontrollü bir sürece taşımak.**

- ADR, **kararların** neden alındığını kalıcı hale getirir.
- Otomatik API üretimi, **arayüzün** kodla senkron kalmasını garanti altına alır.
- Docs-as-code, **tüm dokümantasyonun** kodla aynı yaşam döngüsüne (review, versiyon, CI) girmesini sağlar.
- Runbook'lar, **operasyonel bilgiyi** kriz anında güvenilir şekilde erişilebilir kılar.

Ortak tespit ve savunma perspektifinden bakıldığında, bir organizasyonun dokümantasyon olgunluğunu değerlendirmenin pratik yolu şudur: "Bu bilgi, onu yazan kişi yarın işe gelmese hâlâ doğru ve erişilebilir olur muydu?" Cevap hayırsa, o bilgi hâlâ bir kişinin kafasında yaşıyor demektir — ve bu, dokümantasyon mühendisliğinin çözmeye çalıştığı temel kırılganlıktır. Bu dört pratik, bireysel hafızaya bağımlılığı azaltıp bilgiyi sistemin, sürecin ve deponun bir parçası haline getirerek organizasyonel dayanıklılığı (resilience) artırır.
