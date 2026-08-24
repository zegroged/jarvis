# Bulut Güvenlik Duruş Yönetimi ve CNAPP (CSPM/CWPP/CIEM Bütünleşik Yaklaşım)

## Giriş: Neden Ayrı Bir Konu?

"Bulut yanlış yapılandırma" konusu genellikle tekil örnekler üzerinden anlatılır: herkese açık bırakılmış bir S3 bucket, internete açılmış bir veritabanı portu, aşırı geniş bir IAM rolü. Ancak bu örnekler buzdağının görünen kısmıdır. Modern bir bulut ortamı; binlerce hesap, on binlerce kaynak, sürekli değişen kimlik yetkileri ve dakikada bir dağıtılan (deploy) container'lardan oluşur. Bu ölçekte güvenliği tek tek denetimlerle sağlamak imkânsızdır.

**Cloud Security Posture Management (CSPM)**, **Cloud Workload Protection Platform (CWPP)** ve **Cloud Infrastructure Entitlement Management (CIEM)** bu ölçek sorununa verilen üç ayrı cevaptır. **CNAPP (Cloud-Native Application Protection Platform)** ise bu üçünü (ve daha fazlasını) tek bir bütünleşik platformda birleştiren yaklaşımdır. Bu makale, bu araçların ne olduğunu değil, **nasıl çalıştığını**, **sürekli uyum/skorlama mantığını** ve **savunma ile tespit** açısından ne anlama geldiğini anlatır.

## Temel Tanımlar

### CSPM — Bulut Güvenlik Duruş Yönetimi
CSPM, bulut **kontrol düzlemini (control plane)** sürekli tarayarak yanlış yapılandırmaları, uyumsuzlukları ve politika ihlallerini tespit eden araç sınıfıdır. Odak noktası **yapılandırma (configuration)** durumudur: bir kaynak nasıl kurulmuş, hangi ayarlar açık, hangi güvenlik kontrolü eksik.

Örnek sorular CSPM'in cevapladığı sorulardır: "Hangi storage kovaları şifresiz?", "Hangi güvenlik gruplarında 0.0.0.0/0 üzerinden SSH açık?", "Loglama (audit logging) kapalı olan hesaplar hangileri?"

### CWPP — Bulut İş Yükü Koruma Platformu
CWPP, bulutta **çalışan iş yüklerini (workload)** korur: sanal makineler (VM), container'lar, serverless fonksiyonlar. Odak noktası **çalışma zamanı (runtime)** ve iş yükünün içeriğidir. Zafiyet taraması (vulnerability scanning), zararlı yazılım tespiti, dosya bütünlüğü izleme ve çalışma zamanı davranış analizi bu kategoriye girer.

CWPP'nin cevapladığı sorular: "Bu container image'ında hangi bilinen zafiyetler (CVE'ler) var?", "Bir VM üzerinde beklenmedik bir process mi çalışıyor?", "Container içinden ana makineye (host) escape denemesi var mı?"

### CIEM — Bulut Altyapısı Yetki Yönetimi
CIEM, buluttaki **kimlik ve yetkilere (entitlements)** odaklanır. Bulutta "kim, neye, hangi koşulda erişebilir?" sorusunun cevabı çoğu zaman insan aklının kavrayamayacağı kadar karmaşıktır çünkü yetkiler; kullanıcılar, roller, gruplar, servis hesapları, kaynak-tabanlı politikalar ve geçişli (transitive) izinler üzerinden dolaylı olarak birikir. CIEM bu karmaşayı çözerek **efektif izinleri (effective permissions)** hesaplar ve aşırı yetkiyi (over-permissioning) tespit eder.

CIEM'in cevapladığı sorular: "Bu servis hesabı gerçekte neye erişebiliyor?", "90 gündür kullanılmayan ama admin yetkisi olan kimlikler hangileri?", "Hangi kimlikler yetki yükseltmesi (privilege escalation) yapabilecek bir izin zincirine sahip?"

### CNAPP — Bütünleşik Platform
CNAPP, yukarıdaki üç yeteneği artı IaC (Infrastructure as Code) taraması, container güvenliği ve bazı durumlarda ağ güvenliğini tek bir platformda toplayan konsolidasyon yaklaşımıdır. Kilit fikir şudur: bu yetenekler ayrı ayrı çalıştığında **bağlam (context)** kaybolur; birleştiğinde ise bir bulgu diğerini zenginleştirir.

## Kök Neden: Neden Bütünleşmeye İhtiyaç Var?

Ayrı araçların temel problemi **bağlamsız uyarı yığını (alert fatigue)** üretmesidir. Bir örnekle açıklayalım.

Diyelim ki üç ayrı araç şu üç bulguyu üretiyor:
- **CSPM**: "Bir sanal makine internete açık (public IP + 0.0.0.0/0 giriş kuralı)."
- **CWPP**: "Aynı VM üzerindeki bir pakette kritik bir uzaktan kod çalıştırma zafiyeti var."
- **CIEM**: "Bu VM'e atanmış servis hesabı, tüm veritabanlarına okuma yetkisine sahip."

Ayrı ayrı bakıldığında bunların her biri "orta öncelikli" bir uyarı gibi görünür ve binlerce uyarı arasında kaybolur. Ancak **birleştirildiğinde** ortaya çıkan tablo felakettir: internete açık + istismar edilebilir + yetkili bir kaynak, yani **doğrudan sömürülebilir bir saldırı yolu (attack path)**. Bir saldırgan bu zinciri kullanarak makineyi ele geçirir, servis hesabının kimliğini üstlenir (assume) ve tüm veritabanlarını okur.

İşte CNAPP'in getirdiği asıl değer **attack path analysis** yani bulguları tekil risk skorları olarak değil, birbirine bağlı **bir grafik (graph)** olarak değerlendirmesidir. Grafiğin düğümleri kaynaklar/kimlikler, kenarları ise "erişebilir", "üstlenebilir", "istismar edilebilir" gibi ilişkilerdir. Bu grafik üzerinde "internetten değerli veriye giden en kısa yol" hesaplanır ve önceliklendirme buna göre yapılır.

## Çalışma Mantığı: Sürekli Uyum ve Skorlama

CNAPP/CSPM araçlarının kalbinde **sürekli değerlendirme döngüsü (continuous assessment loop)** vardır. Bu döngü kavramsal olarak dört adımdan oluşur.

### 1. Envanter Toplama (Discovery / Inventory)
Araç, bulut sağlayıcısının API'leri üzerinden (genellikle salt-okunur bir rol ile) tüm kaynakları listeler: hesaplar, VM'ler, storage, veritabanları, IAM politikaları, ağ yapılandırmaları. Bu iki modelle yapılır:
- **Agentless (ajansız)**: Sadece API'lerden yapılandırma okunur. Hızlı ve hafif; ancak çalışma zamanı görünürlüğü sınırlıdır.
- **Agent-based (ajanlı)**: İş yükü üzerine bir ajan kurulur; çalışma zamanı davranışını, process'leri, ağ bağlantılarını görür. Derin görünürlük sağlar; ancak dağıtım ve bakım yükü getirir.

Modern platformlar genellikle hibrittir: yapılandırma için agentless tarama, kritik iş yükleri için agent (veya snapshot tabanlı tarama) kullanır.

### 2. Politika/Kural Değerlendirmesi (Policy Evaluation)
Toplanan durum, bir **kural motoru (policy engine)** tarafından bir dizi politikaya karşı değerlendirilir. Politikalar genellikle bildirimsel (declarative) bir dille yazılır. Örneğin kavramsal olarak: "Her storage kovası için, `public_access == true` ise bu bir ihlaldir." Birçok platform, politikaları **Open Policy Agent (OPA) / Rego** gibi standartlarla veya kendi kural formatlarıyla ifade eder.

Bu politikalar iki kaynaktan gelir:
- **Yerleşik uyum çerçeveleri (compliance frameworks)**: CIS Benchmarks, PCI-DSS, HIPAA, SOC 2, ISO 27001, GDPR gibi standartların bulut kontrollerine eşlenmiş (mapped) hâli.
- **Özel (custom) politikalar**: Kurumun kendi güvenlik gereksinimleri.

### 3. Skorlama ve Önceliklendirme (Scoring / Prioritization)
Her bulgu tekil bir "geçti/kaldı" değildir; bir **risk skoru** taşır. Skorlama genellikle şu boyutları birleştirir:
- **Şiddet (severity)**: Yanlış yapılandırmanın veya zafiyetin ciddiyeti.
- **Maruziyet (exposure)**: Kaynak internete açık mı, yoksa iç ağda izole mi?
- **Varlık hassasiyeti (asset sensitivity)**: Hassas veri (PII, kredi kartı, sağlık verisi) barındırıyor mu?
- **İstismar edilebilirlik (exploitability)**: Bilinen bir istismar (exploit) mevcut mu, aktif olarak sömürülüyor mu?
- **Bağlam / attack path**: Bu bulgu daha büyük bir saldırı zincirinin parçası mı?

Buradaki kritik nokta şudur: iyi bir CNAPP, **10.000 uyarıyı 20 saldırı yoluna** indirger. Skorlama, uyarı sayısını azaltmak değil, insan dikkatini gerçekten önemli olana yöneltmek içindir. Bir "duruş skoru (posture score)" da genellikle tüm ortamın uyum yüzdesi olarak yönetime raporlanır (ör. "CIS uyumu %78").

### 4. Düzeltme ve Geri Bildirim (Remediation / Feedback)
Bulgular; bir bilet sistemine (Jira, ServiceNow), bir SIEM/SOAR'a veya doğrudan otomatik düzeltme (auto-remediation) akışlarına aktarılır. Döngü kapanır ve yeniden başa döner. "Sürekli" kelimesinin anlamı budur: bulut durumu dakikalar içinde değişir, dolayısıyla değerlendirme de sürekli tekrarlanmalıdır.

## Kaymayı Sola Alma: Shift-Left ve IaC

Modern CNAPP yaklaşımının önemli bir bileşeni **shift-left** yani güvenliği geliştirme sürecinin başına çekmektir. Bir yanlış yapılandırma production'a ulaşmadan, **kod aşamasında** yakalanabilir.

Bu, **IaC taraması** ile yapılır. Terraform, CloudFormation, ARM template, Kubernetes manifest gibi altyapı tanımları, dağıtımdan önce (örneğin CI/CD pipeline'ında veya pull request sırasında) taranır. Örneğin bir Terraform dosyasında bir güvenlik grubunun 0.0.0.0/0'a açık SSH kuralı, kod merge edilmeden yakalanır ve engellenir.

Buradaki temel kavram, aynı politikanın **hem koda (build-time) hem de çalışan buluta (run-time) uygulanmasıdır**. Böylece "çalışan ortamda tespit ettiğim şeyi, gelecekte kod aşamasında da engelleyebilirim" bütünlüğü sağlanır. Buna bazen "code-to-cloud" görünürlüğü denir: production'daki bir bulgunun hangi kod deposundaki hangi satırdan kaynaklandığını izleyebilmek.

## CIEM'in Derinliği: Efektif İzin Hesabı

CIEM'in neden ayrı ve zor bir problem olduğunu anlamak önemli. Bulutta bir kimliğin gerçek yetkisini bulmak basit bir tablo okuma işi değildir. Şunların hepsi birleşir:
- Kimliğe doğrudan atanan politikalar.
- Kimliğin üyesi olduğu grupların politikaları.
- Kaynak-tabanlı politikalar (kaynağın kendisi "şu kimliğe izin ver" diyebilir).
- Üstlenilebilen (assumable) roller ve rol zincirleri.
- İzin sınırları (permission boundaries), servis kontrol politikaları (SCP) gibi kısıtlayıcı katmanlar.
- Koşullar (belirli IP'den, belirli zamanda, MFA ile vb.).

Bu katmanların **kesişimi ve birleşimi**, kimliğin **efektif izinlerini** oluşturur. CIEM motoru bu hesabı otomatik yapar ve sonra iki şeyi bulur: **kullanılmayan izinler** (verilmiş ama son X gündür hiç kullanılmamış) ve **tehlikeli izin kombinasyonları** (yetki yükseltmeye veya yanal harekete izin verenler).

Buradan **least privilege (en az yetki)** önerileri çıkar: CIEM, gerçek kullanım verisine bakarak "bu kimliğin şu 200 izninden yalnızca 12'sini kullandığını, gerisini kaldırabilirsin" der. Bu, elle yapılması neredeyse imkânsız bir analizdir.

## Tespit (Detection)

Savunmacı açısından bu araçlar hem birer **önleyici (preventive)** hem de **tespit edici (detective)** kontroldür. Tespit boyutunda dikkat edilmesi gerekenler:

- **Yapılandırma sapması (configuration drift)**: Onaylı bir temel çizgiden (baseline) sapmalar. Örneğin bir loglama ayarının aniden kapatılması güçlü bir tehlike işaretidir; saldırganlar iz bırakmamak için audit logging'i kapatmaya çalışır.
- **Runtime anomali tespiti (CWPP)**: Bir container'ın normalde çalıştırmadığı bir process'i başlatması, beklenmedik bir dışarı bağlantı (egress) açması, `/etc/shadow` gibi hassas dosyalara erişmesi.
- **Kimlik anomalileri (CIEM + CloudTrail/Audit logları)**: Uzun süredir uykuda olan bir kimliğin aniden aktifleşmesi, alışılmadık bir bölgeden (region) API çağrısı, kısa sürede çok sayıda `AssumeRole` denemesi.
- **Attack path değişimi**: Yeni bir kaynağın internete açılmasıyla, daha önce izole olan hassas bir varlığa yeni bir saldırı yolu açılması. İyi bir CNAPP bunu "yeni kritik saldırı yolu oluştu" diye uyarır.

Bu tespitlerin çoğu, bulutun kendi **denetim loglarına** (AWS CloudTrail, Azure Activity Log / Entra logları, GCP Cloud Audit Logs) dayanır. CNAPP, bu logları yapılandırma bağlamıyla birleştirdiği için ham log analizinden daha anlamlı sonuç verir.

## Savunma (Defense)

Kavramsal savunma önlemleri:

1. **Salt-okunur ve kapsamlı envanter**: CNAPP'e verilen erişim mümkün olduğunca salt-okunur olmalı; auto-remediation için verilen yazma yetkileri dar kapsamlı ve denetlenir olmalı. Aracın kendisi güçlü bir hedef olduğu için ona verilen yetki bir risk kaynağıdır.
2. **Guardrail'ler (önleyici bariyerler)**: SCP'ler, Azure Policy "deny" etkileri, organizasyon politikaları gibi **önleyici** kontrollerle tehlikeli işlemler daha gerçekleşmeden engellenir. Tespit her zaman geç kalabilir; önleme her zaman tercih edilir.
3. **Least privilege'ın operasyonelleştirilmesi**: CIEM önerilerini yalnızca raporlamak değil, aşamalı olarak uygulamak. Önce kullanılmayan izinleri "izle-uyar", sonra kaldır.
4. **Shift-left uygulama**: IaC taramasını CI/CD'de zorunlu (blocking) hâle getirmek; kritik ihlallerde merge'i engellemek.
5. **Attack path önceliklendirmesi**: Kaynakları tek tek yamamak yerine, "internetten kritik veriye giden yolu kır" mantığıyla darboğaz noktalarına (choke points) odaklanmak. Bir tek düğümü kapatmak, o yoldaki onlarca bulguyu etkisiz kılabilir.
6. **Bütünleşik iş akışı**: Bulguları SIEM/SOAR'a besleyerek, bulut duruşunu genel güvenlik operasyonlarının (SOC) bir parçası hâline getirmek.

## Somut Örnek Senaryo

Bir e-ticaret şirketinin bulut ortamını düşünelim. CNAPP şu zinciri tespit eder ve **tek bir kritik saldırı yolu** olarak sunar:

1. Bir geliştirme (dev) Kubernetes cluster'ındaki bir pod, internete açık bir ingress arkasında.
2. Bu pod'daki bir kütüphanede kritik bir uzaktan kod çalıştırma zafiyeti var (CWPP bulgusu).
3. Pod'un kullandığı servis hesabı, cluster içinde geniş yetkilere sahip (CIEM bulgusu).
4. Bu servis hesabı, bir bulut IAM rolüne bağlanmış (workload identity) ve o rol production veritabanı yedeklerinin bulunduğu storage'a erişebiliyor (CSPM + CIEM bağlamı).

Ayrı araçlar dört ayrı orta seviye uyarı üretir. CNAPP ise şunu der: "İnternetten production veri yedeklerine ulaşan istismar edilebilir bir yol var." Önceliklendirme netleşir, ekip önce ingress'i kapatır veya zafiyeti yamalar ve tek hamlede zinciri kırar.

## Yaygın Hatalar

- **Uyarı yığınında boğulmak**: Her bulguyu eşit görmek. Skorlama ve attack path olmadan CSPM bir "gürültü üreteci"ne dönüşür. Doğru yaklaşım: sömürülebilir yolları önceliklendirmek.
- **Sadece kontrol düzlemine bakmak**: CSPM yapılandırmayı görür ama iş yükünün içindeki zafiyeti göremez. CWPP olmadan resim eksiktir. Tersine, sadece CWPP de kimlik/yapılandırma bağlamını kaçırır.
- **CIEM'i ihmal etmek**: Yanlış yapılandırma tartışmaları genellikle ağ ve storage'a odaklanır; oysa aşırı yetkili kimlikler bulut ihlallerinin en yaygın yükseltme (escalation) yoludur. "Kimlik yeni çevre güvenliğidir (identity is the new perimeter)."
- **Agentless'i her şey sanmak**: Ajansız tarama hızlıdır ama çalışma zamanı davranışını (fileless saldırılar, canlı process anomalileri) tek başına yakalayamaz. Kritik iş yükleri için runtime görünürlüğü gerekir.
- **Shift-left'i shift-only sanmak**: IaC taraması harikadır ama çalışan ortam da taranmalıdır. Kod dışı yollarla (manuel değişiklik, drift) yapılan yanlış yapılandırmalar kod taramasından kaçar.
- **Uyum skorunu güvenlikle karıştırmak**: "%95 CIS uyumu" iyidir ama uyum bir taban çizgisidir, hedef değil. Uyumlu bir ortam da kritik bir attack path barındırabilir. Uyum ≠ güvenlik.
- **Aracın kendi yetkisini gözden kaçırmak**: CNAPP'e verilen geniş okuma (ve varsa yazma) yetkisi, saldırganlar için birinci sınıf bir hedeftir. Aracın kimliği de en az yetki ile yönetilmelidir.

## Özet

CSPM, CWPP ve CIEM aynı temel probleme farklı açılardan bakar: bulutu güvenli tutmak. CSPM **nasıl kurulmuş** (yapılandırma), CWPP **içinde ne çalışıyor** (iş yükü), CIEM **kim neye erişebiliyor** (kimlik) sorularını cevaplar. CNAPP bu üçünü, IaC taraması ve attack path analiziyle birleştirerek bağımsız uyarıları bağlamsal saldırı yollarına dönüştürür. Sürekli değerlendirme döngüsü (envanter → politika → skorlama → düzeltme) ile bulutun dinamik doğasına ayak uydurur. Savunmacı için asıl kazanım, sınırlı insan dikkatini binlerce uyarı arasında değil, gerçekten sömürülebilir birkaç yol üzerinde yoğunlaştırabilmektir.
