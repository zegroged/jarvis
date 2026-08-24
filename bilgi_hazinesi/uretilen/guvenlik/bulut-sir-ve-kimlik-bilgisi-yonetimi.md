# Bulut Sır ve Kimlik Bilgisi Yönetimi (Cloud Secrets Management)

## Giriş ve Tanım

Modern sistemlerin neredeyse tamamı, çalışabilmek için **sırlara** (secrets) muhtaçtır: veritabanı parolaları, API anahtarları, TLS özel anahtarları, üçüncü taraf token'ları, imzalama anahtarları. Bir uygulamanın kaynak kodu açık kaynak olabilir; ama o uygulamanın canlı ortamda hangi sırlarla konuştuğu asla açık olmamalıdır. **Cloud secrets management**, bu sırların bulut sağlayıcı ortamında güvenli biçimde saklanması, dağıtılması, döndürülmesi (rotation) ve denetlenmesi disiplinidir.

Genel "anahtar/sır yönetimi" ilkeleri (en az yetki, döndürme, şifreli saklama) her yerde geçerlidir. Fakat bulutta iş, sağlayıcıya özgü servislerle ve önemli bir mimari kayma ile birleşir: **statik uzun ömürlü kimlik bilgilerini tamamen ortadan kaldırma** eğilimi. Bu makale üç ekseni derinlemesine ele alır:

1. Sağlayıcıya özgü servisler: **AWS KMS/Secrets Manager**, **Azure Key Vault**, **GCP Cloud KMS/Secret Manager**.
2. **OIDC federasyonu** ile statik anahtarsız (keyless) kimlik doğrulama, özellikle CI/CD'den buluta.
3. **Secret sprawl** (sır dağınıklığı) tespiti ve savunması.

---

## Bölüm 1 — Envelope Encryption ve KMS'in Çalışma Mantığı

### KMS ne yapar, ne yapmaz

Bir yaygın yanılgı, KMS'in (Key Management Service) verinizi doğrudan şifreleyip depoladığı yönündedir. Genellikle böyle çalışmaz. KMS'in asıl işi bir **kök anahtarı** (root/master key) korumak ve **envelope encryption** (zarf şifreleme) modelini mümkün kılmaktır.

**Envelope encryption** mantığı şudur:

- Veriyi şifrelemek için rastgele üretilen bir **data encryption key (DEK)** kullanılır. DEK simetriktir ve hızlıdır (tipik olarak AES-GCM).
- DEK'in kendisi, KMS'te duran ve **hiçbir zaman KMS'i terk etmeyen** bir **key encryption key (KEK)** / master key ile şifrelenir.
- Diskte veya veritabanında saklanan şey: şifreli veri + şifreli DEK.
- Veriyi çözmek isteyen taraf, şifreli DEK'i KMS'e gönderir; KMS onu KEK ile çözer ve düz DEK'i geri verir (bu çağrı denetlenir). Uygulama düz DEK ile veriyi çözer, sonra DEK'i bellekten atar.

Bu tasarımın **kök nedeni** şudur: Kök anahtar asla ağ üzerinde dolaşmaz, HSM (Hardware Security Module) sınırları içinde kalır; buna karşılık gigabaytlarca veriyi KMS'e gönderip şifreletmek gerekmez. Böylece hem performans hem de anahtar izolasyonu sağlanır. Ayrıca kök anahtarı döndürdüğünüzde tüm veriyi yeniden şifrelemeniz gerekmez — sadece yeni DEK'ler yeni KEK sürümüyle sarılır.

### Sağlayıcı karşılıkları

- **AWS:** KMS (CMK / KMS key), sıklıkla S3, EBS, RDS, DynamoDB şifrelemesinin altında çalışır. Sır **metnini** saklamak için ayrıca **Secrets Manager** (otomatik rotation destekli) veya **SSM Parameter Store** (SecureString) kullanılır.
- **Azure:** **Key Vault**, hem anahtar (key), hem sır (secret), hem sertifika saklar. HSM destekli katman (Managed HSM) ayrıca sunulur.
- **GCP:** **Cloud KMS** anahtarları yönetir; **Secret Manager** sır metnini sürümlü biçimde saklar.

Not: Ürün adları ve tam özellik setleri sağlayıcı tarafından zaman içinde değişebilir; buradaki amaç kavramsal karşılıkları vermektir. Belirli bir API sürümü veya bayrağı için resmî dokümana bakılmalıdır.

---

## Bölüm 2 — Kritik Kavram: BYOK, Anahtar Politikaları ve Denetim

Bir sırrı KMS/Vault'a koymak tek başına güvenlik sağlamaz. Asıl güvenlik iki mekanizmadan gelir:

**Anahtar erişim politikası (key policy / IAM).** Bir sırra kimin erişebileceği, o sırrı saklayan servisin değil, ona bağlanan kimlik politikasının işidir. En sık yapılan hata, bir KMS anahtarını veya Key Vault'u "herkese açık okuma" ya da geniş wildcard'lı bir role bağlamaktır. Doğru yaklaşım: **her uygulama/servis için ayrı bir kimlik**, ve o kimliğe **yalnızca ihtiyaç duyduğu sırların** okuma yetkisi.

**Denetim (audit) ve gözlemlenebilirlik.** KMS/Vault'un en değerli güvenlik özelliği, her `Decrypt` / `GetSecretValue` / `GetSecret` çağrısının loglanmasıdır. Bu, statik bir `.env` dosyasında asla var olamayacak bir yetenektir: "Bu API anahtarını en son kim, ne zaman, hangi IP'den okudu?" sorusuna cevap verebilirsiniz. Tespit stratejisinin çekirdeği burasıdır.

**BYOK / HYOK.** "Bring Your Own Key" ile kendi ürettiğiniz anahtar materyalini içe aktarabilirsiniz; bazı senaryolarda düzenleyici gereklilikler bunu ister. Fakat BYOK, anahtarın güvenliğini otomatik artırmaz — çoğu zaman anahtar üretimini bulut HSM'ine bırakmak daha güvenlidir, çünkü içe aktarma sürecinin kendisi bir sızıntı yüzeyidir.

---

## Bölüm 3 — Statik Anahtarların Ölümü: OIDC Federasyonu

### Sorun: Uzun ömürlü kimlik bilgileri

Yıllarca yaygın uygulama şuydu: CI/CD sistemine (ör. GitHub Actions) bir `AWS_ACCESS_KEY_ID` ve `AWS_SECRET_ACCESS_KEY` çifti secret olarak konur, pipeline buluta bununla bağlanırdı. Bu modelin temel kusurları:

- **Uzun ömürlü.** Anahtar sızarsa, siz iptal edene kadar geçerli kalır — belki aylarca.
- **Taşınabilir.** Sızan bir statik anahtar dünyanın her yerinden kullanılabilir; hangi pipeline'ın ürettiğini bağlamı yoktur.
- **Depolanır.** CI secret store'unda, log'larda, ekran görüntülerinde, geliştirici makinelerinde çoğalır (bu tam da secret sprawl'dır).

### Çözüm: OIDC ile kısa ömürlü, federatif kimlik

**OIDC federasyonu**, statik anahtarı tamamen ortadan kaldırır. Çalışma mantığı, güven zinciri kavramına dayanır:

1. **Kimlik sağlayıcı (IdP / OP).** GitHub Actions gibi bir CI sistemi, her iş çalışmasında imzalı bir **OIDC ID token** (JWT) üretir. Bu token, işin bağlamını taşıyan **claim**'ler içerir: hangi repo (`repo`), hangi branch/ref (`ref`), hangi environment, hangi workflow, `sub` (subject), `aud` (audience) vb.

2. **Güven ilişkisi (trust).** Bulut tarafında (ör. AWS IAM) bir **OIDC identity provider** tanımlanır ve GitHub'ın imzalama anahtarlarına (JWKS uç noktası aracılığıyla, `iss` = issuer üzerinden) güvenilir. Bulut, token imzasını IdP'nin açık anahtarıyla **doğrulayabilir**; sahte token üretilemez çünkü özel imzalama anahtarı yalnızca IdP'dedir.

3. **Rol ve koşullar.** Bulutta bir **role** (AWS'de IAM Role, Azure'da federated credential, GCP'de Workload Identity Federation) oluşturulur. Bu rolün **trust policy**'si, kabul edilecek token'ın claim'lerini **kısıtlar**: yalnızca `repo:org/proje` ve `ref:refs/heads/main` gibi. Yani sadece belirli bir reponun belirli bir branch'inin işi bu rolü üstlenebilir.

4. **Token takası (AssumeRoleWithWebIdentity).** Pipeline, OIDC token'ı buluta sunar; bulut onu doğrular ve claim koşulları tutuyorsa **kısa ömürlü** geçici kimlik bilgisi (örn. birkaç dakika–saat geçerli STS credential) verir. İş biter, credential ölür.

**Kök kazanım:** Artık depolanan hiçbir uzun ömürlü sır yoktur. Sızacak statik anahtar yoktur. Erişim; repo, branch ve iş bağlamıyla **cryptographic olarak** sınırlandırılmıştır.

### Sağlayıcı karşılıkları

- **AWS:** IAM OIDC identity provider + `sts:AssumeRoleWithWebIdentity`.
- **Azure:** Microsoft Entra ID uygulamasında **federated identity credential** (workload identity federation).
- **GCP:** **Workload Identity Federation** + workload identity pool/provider.

### OIDC'nin en tehlikeli hatası: gevşek subject koşulu

OIDC'yi doğru kurmak, trust policy'deki claim eşleşmesinin **doğru** olmasına bağlıdır. En kritik yanlış yapılandırma, `sub` koşulunu **wildcard** ile açık bırakmaktır. Örneğin bir trust policy `sub` alanında `repo:org/*` gibi çok geniş bir eşleşmeye ya da yalnızca `iss` (issuer) doğrulamasına dayanıyorsa: **o bulut sağlayıcıdaki (ör. github.com) herhangi bir repo**, hatta saldırganın kendi kişisel reposundan üretilmiş bir token ile o rolü üstlenebilir. Bu, hesabınıza dışarıdan giriş kapısı açar.

Bunun ilk savunması **audience (`aud`) doğrulaması** ve **tam `sub` eşleşmesidir**: rol yalnızca `repo:ORG/REPO:ref:refs/heads/main` gibi tam ve organizasyonunuza ait bir subject için token kabul etmelidir. Ayrıca fork'lardan gelen pull request'lerin token üretemeyeceğinden veya üretilse bile bu role eşleşmeyeceğinden emin olunmalıdır.

---

## Bölüm 4 — Secret Sprawl: Tanım ve Kök Neden

**Secret sprawl** (sır dağınıklığı), sırların merkezî ve denetlenebilir bir kasadan sızıp sistemin her yerine kopyalanmasıdır. Bir sır ne kadar çok yerde bulunuyorsa, o kadar çok saldırı yüzeyi ve o kadar zor bir döndürme (rotation) süreci demektir.

Tipik sprawl konumları:

- **Git repoları.** Kaynak kodda hardcode edilmiş anahtarlar. En sinsi olanı: silinmiş olsalar bile **git history**'de kalırlar. Bir anahtarı commit edip sonraki commit'te silmek onu güvene almaz — geçmişte hâlâ okunabilir.
- **Konteyner katmanları (container layers).** Bir `Dockerfile`'da `ENV SECRET=...` ya da build sırasında kopyalanan bir dosya, image'ın bir **layer**'ına gömülür. Sonraki katmanda dosyayı silseniz bile, önceki katman image geçmişinde durur ve `docker history` / katman çıkarımı ile okunabilir. Registry'ye push edilen her image bu sırrı taşır.
- **Environment değişkenleri.** `.env` dosyaları, CI değişkenleri, proses ortamı. Environment değişkenleri; alt proseslere miras kalır, crash dump'larda, hata raporlama servislerinde ve bazen `/proc` üzerinden görünür olur.
- **Log'lar ve gözlemlenebilirlik.** Bir token'ın yanlışlıkla loglanması, onu tüm log toplama/SIEM zincirine yayar.
- **CI/CD artifact'leri, IaC state dosyaları** (ör. Terraform state düz metin sır tutabilir), konfigürasyon yönetimi depoları, wiki/ticket sistemleri.

**Kök neden** çoğu zaman kolaylıktır: Sırrı doğru yere koymak (kasadan çekmek, kimlik federasyonu kurmak) kısa vadede zahmetlidir; kopyalayıp yapıştırmak kolaydır. Sprawl, bu kolaylık borcunun faizidir.

---

## Bölüm 5 — Tespit (Detection)

### 5.1 Sır tarama (secret scanning)

Sprawl'a karşı ilk savunma, **sırları otomatik tespit eden tarayıcılardır**. Bu araçlar iki yöntem kullanır:

- **Desen tabanlı (regex/pattern).** Sağlayıcıya özgü anahtar formatları belirgin ön eklere sahiptir (birçok bulut anahtarı ve token'ı tanınabilir prefix'lerle başlar). Bu prefix'ler ve uzunluk/karakter setleri regex ile taranır.
- **Entropi tabanlı.** Rastgele üretilmiş yüksek entropili dizeler (parolalar, gizli anahtarlar) istatistiksel olarak sıradan metinden ayrışır. Yüksek Shannon entropisi, olası bir sır işaretidir (yanlış pozitifleri çoktur, bu yüzden desenle birleştirilir).

Bu taramaların **git geçmişinin tamamını** kapsaması şarttır; sadece son commit'i taramak yetersizdir. Konteyner tarafında ise araçlar **image katmanlarını açıp** her katmanda sır arar. Kavramsal olarak açık kaynak araçlar (ör. git geçmişi/entropi tabanlı tarayıcılar) ve sağlayıcıların yerleşik "push protection / secret scanning" özellikleri bu işi yapar. Belirli bir aracın tam bayrak setini uydurmak yerine kavramı bilin: **taranan yüzey = tüm geçmiş + tüm katmanlar + tüm konfigürasyon**.

### 5.2 Sağlayıcı tarafında doğrulanmış sızıntı (provider verification)

Bazı sağlayıcılar, tarayıcı bir aday anahtar bulduğunda onu (yıkıcı olmayan bir çağrıyla) **canlı olup olmadığını** doğrulayabilir. "Doğrulanmış aktif sızıntı" bulgusu, ham desen eşleşmesinden çok daha yüksek önceliklidir ve derhal döndürme gerektirir.

### 5.3 Anomali tespiti — KMS/Vault denetim loglarından

Sır kasasını kullanmanın en büyük tespit avantajı buradadır. İzlenecek sinyaller:

- **Beklenmedik prensip (principal).** Bir sırrı normalde yalnızca `service-A` okurken, birden bir kullanıcı kimliği veya farklı bir rol `GetSecretValue` çağırıyorsa.
- **Coğrafi / IP anomalisi.** `Decrypt` çağrılarının alışılmadık bir bölgeden veya ağdan gelmesi.
- **Hacim anomalisi.** Kısa sürede çok sayıda farklı sırrın okunması — bir saldırganın "sır toplama" (secret harvesting) davranışı buna benzer.
- **`AccessDenied` fırtınası.** Bir kimliğin, yetkisi olmayan sırları ardı ardına yoklaması (enumeration) girişimi.
- **KMS anahtar politikası / Vault erişim politikası değişiklikleri.** Politikanın genişletilmesi (ör. yeni bir principal eklenmesi) izlenmeli ve alarm üretmelidir.

Bu logların (AWS CloudTrail, Azure Monitor/Activity Log, GCP Cloud Audit Logs) bir **SIEM**'e akıtılması ve yukarıdaki desenlere karşı kural yazılması, savunmanın kalbidir.

---

## Bölüm 6 — Savunma (Defense)

**1. Statik sırları mümkün olduğunca yok edin.** İdeal savunma, korunacak sırrın hiç var olmamasıdır. CI/CD → bulut için **OIDC federasyonu**; bulut içi servis → servis için **managed identity / instance role** (AWS IAM instance role, Azure Managed Identity, GCP service account attachment) kullanın. Bunlar kısa ömürlü, otomatik döndürülen kimlik bilgileri sağlar.

**2. Kalan sırları merkezî kasaya alın.** Kaçınılmaz statik sırlar (ör. üçüncü taraf API anahtarı) yalnızca KMS destekli Secrets Manager / Key Vault / Secret Manager'da dursun; uygulamalar çalışma zamanında oradan çeksin, dosyaya yazılmasın.

**3. En az yetki ve sır başına izolasyon.** Her kimlik yalnızca gereken sırlara, yalnızca gereken işlemle (read vs. read+write) erişsin. Wildcard'lı KMS/Vault politikalarından kaçının.

**4. Döndürme (rotation) ve kısa ömür.** Sırları düzenli döndürün; mümkünse otomatik rotation kullanın. Kısa ömürlü kimlik bilgileri, sızıntının etki süresini radikal biçimde kısaltır.

**5. Önleyici bariyerler (shift-left).** Pre-commit hook'ları ve CI adımı ile sır taraması yapın; **push protection** ile sır içeren commit'lerin repoya girmesini en baştan engelleyin. Tespit, önlemeden ucuz değildir — sızmış sır her hâlükârda döndürülmelidir.

**6. OIDC trust policy'lerini sıkı yazın.** `aud` doğrulaması + tam `sub` eşleşmesi + branch/environment kısıtı. Wildcard subject asla kullanmayın.

**7. Sızmışsa iptal edin, temizlemeyin.** Bir sır git geçmişine veya bir image katmanına girdiyse, onu geçmişten silmek (rewrite/rebase) **birincil çözüm değildir** — çünkü çoktan çoğalmış olabilir. Birincil çözüm daima **döndürme/iptal**tir: eski sırrı geçersiz kılın. Geçmiş temizliği ikincil, tamamlayıcı adımdır.

---

## Bölüm 7 — Yaygın Hatalar (Anti-patterns)

- **"Silince güvende sandım."** Anahtarı bir sonraki commit'te veya bir sonraki Docker katmanında silmek onu güvene almaz; geçmiş/katman hâlâ okunabilir. Tek doğru refleks: iptal + döndürme.
- **Base64'ü şifreleme sanmak.** Kubernetes `Secret` nesneleri varsayılan olarak yalnızca base64 **kodlanmıştır**, şifreli değildir. etcd şifrelemesi ayrıca yapılandırılmalıdır.
- **KMS/Vault'a koyup politikayı açık bırakmak.** Sırrı kasaya taşımak, erişim politikası gevşekse güvenlik sağlamaz. Kasanın değeri, sıkı politika + denetim logudur.
- **Gevşek OIDC subject.** `sub` wildcard veya yalnızca issuer doğrulaması, hesabınıza dış dünyadan giriş kapısı açar.
- **Sırrı environment değişkeni olarak container'a build zamanında gömmek.** Bu, image geçmişine kalıcı yazar. Runtime'da secret mount / kasa çekişi tercih edilir.
- **Denetim loglarını toplamamak.** KMS/Vault kullanıp CloudTrail/Audit Log akışını izlemezseniz, en güçlü tespit yeteneğinizi çöpe atarsınız.
- **Terraform/IaC state'ini korumasız bırakmak.** State dosyaları düz metin sır tutabilir; state'i şifreli ve erişimi kısıtlı bir backend'de tutun, repoya commit etmeyin.
- **Rotation'ı hiç yapmamak.** "Çalışıyor, dokunmayalım" ile yıllarca yaşayan bir anahtar, tek bir sızıntıda yıllara yayılmış bir risk demektir.

---

## Özet

Bulut sır yönetiminde olgunluk merdiveni nettir: (1) sırları koddan/imajdan çıkar ve merkezî **KMS destekli kasaya** al; (2) kasa erişimini **en az yetki + denetim** ile yönet; (3) mümkün olan her yerde statik sırrı **OIDC federasyonu ve managed identity** ile tamamen ortadan kaldır; (4) **secret sprawl**'ı tüm geçmiş, tüm katman ve tüm konfigürasyon yüzeyinde tara; (5) **KMS/Vault denetim loglarından anomali tespiti** kur; (6) sızıntıda birincil refleksi daima **iptal ve döndürme** yap. Kaybolan sır, çalınamaz; kısa ömürlü sır, uzun süre kötüye kullanılamaz.
