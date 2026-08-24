# Gizli Bilgi (Secrets) Yönetimi ve CI/CD İçinde Sızıntı Önleme

## Giriş: Bu Konu Neden Ayrı Bir Başlık Olarak Ele Alınmalı

Kriptografideki "anahtar yönetimi" konusu, esas olarak kriptografik anahtarların (şifreleme anahtarları, imzalama anahtarları) matematiksel yaşam döngüsüyle ilgilenir: üretim, rotasyon, iptal. DevSecOps bakış açısındaki "secrets yönetimi" ise çok daha geniş ve gündelik bir mühendislik problemidir: API anahtarları, veritabanı parolaları, bulut sağlayıcı erişim anahtarları (access key), OAuth client secret'ları, TLS özel anahtarları, SSH anahtarları, imzalama sertifikaları ve CI/CD sistem değişkenleri gibi *her türlü* hassas verinin, insanların ve otomasyon sistemlerinin (pipeline, konteyner, sunucu) günlük operasyonlarında **yanlışlıkla veya kötü niyetle açığa çıkmasını** engellemekle ilgilenir.

Bu ayrımın pratik önemi şudur: kriptografi mühendisi "AES-256 anahtarını nasıl üretirim, nasıl rotate ederim" sorusuyla ilgilenirken; DevSecOps mühendisi "bu anahtar git repository'sine, log dosyasına, Docker image katmanına, Slack mesajına veya CI çıktısına yanlışlıkla nasıl sızar, bunu nasıl otomatik tespit ederim, sızdıktan sonra nasıl geri dönüşü olmayan hasarı sınırlarım" sorusuyla ilgilenir. Bu, saf kriptografiden çok, **insan hatası, araç zinciri (toolchain) tasarımı ve otomasyon güvenliği** meselesidir. Sektör verilerine göre (kesin sayıları uydurmadan söylemek gerekirse) sızan secrets'ların büyük çoğunluğu kriptografik bir kırılmadan değil, birinin `.env` dosyasını `git add .` ile commit'lemesinden, bir CI log'unun debug modunda değişkeni bastırmasından veya bir Docker image'ının önceki katmanında silinmiş ama hâlâ erişilebilir bir anahtar bırakmasından kaynaklanır.

## Kök Neden: Secrets Neden Sızar

Sızıntının kök nedenini anlamak için üç farklı katmanda düşünmek gerekir.

### 1. İnsan/İş Akışı Katmanı

Geliştiriciler hız ve kolaylık ister. Yerel geliştirme ortamında bir API anahtarını ortam değişkenine koymak yerine doğrudan kod içine yazmak (hardcode) daha "hızlı" görünür. Bu davranış genellikle şu senaryolarla gerçekleşir:

- Bir örnek/test amaçlı kodda gerçek bir anahtar kullanılır ve "sonra değiştiririm" denir, değiştirilmez.
- `.env` dosyası `.gitignore`'a eklenmeyi unutur veya proje `.gitignore`'dan önce zaten commit edilmiştir (bu durumda `.gitignore`'a eklemek dosyayı geçmişten silmez).
- Bir hata ayıklama (debug) oturumunda geliştirici anahtarı bir log satırına, bir issue yorumuna veya bir Slack mesajına yapıştırır.
- Kod inceleme (code review) sürecinde reviewer diff'te secrets olup olmadığını kontrol etmez; otomatik kontrol yoktur.

Kök neden burada **"secrets'ı elde etmenin en kolay yolu, en güvensiz yol olması"**dır. Güvenli yol (bir secrets manager'dan çekmek) geliştiriciye ekstra adım olarak göründüğü sürece, insanlar kestirme yolu seçer. Bu yüzden iyi bir secrets yönetim stratejisi, güvenli yolu *en kolay* yol haline getirmeyi hedefler.

### 2. Araç Zinciri / CI Sistemi Katmanı

CI/CD sistemleri (GitHub Actions, GitLab CI, Jenkins vb.) doğası gereği secrets ile çalışmak zorundadır: bir deployment adımı bulut sağlayıcıya kimlik doğrulaması yapmalı, bir test adımı veritabanına bağlanmalıdır. Bu sistemlerin çalışma mantığı üç riskli noktayı doğurur:

- **Log'lara sızma**: Çoğu CI sistemi komut çıktısını olduğu gibi log'a yazar. Eğer bir script `echo $DATABASE_PASSWORD` ya da `curl -v` (verbose mod, header'ları da basar) çalıştırırsa, secret log dosyasında düz metin olarak kalır. CI sağlayıcılarının çoğu bilinen secret değerlerini log'da otomatik maskeler (mask/redact), ama bu maskeleme yalnızca *tanımlı* secret değişkenlerini tanır; değişken bir dönüşümden geçmişse (örn. base64'e çevrilmişse) maskeleme çalışmayabilir.
- **Fork/PR tetikleyicili pipeline'larda secrets sızıntısı**: Açık kaynak projelerde dış katkıcıların açtığı pull request'ler pipeline'ı tetiklediğinde, eğer pipeline yapılandırması dikkatsizce secrets'ı fork'tan gelen koda da enjekte ediyorsa, kötü niyetli bir PR "secrets'ı bana log'la yazdır" şeklinde bir adım ekleyerek repository secrets'larını çalabilir. Bunun kök nedeni, CI sistemlerinin varsayılan olarak "güvenilir" ve "güvenilmeyen" kod arasında ayrım yapmasının zor olmasıdır.
- **Build önbelleği / artifact'larda kalıntı**: Bir build adımı geçici olarak bir secret'ı bir dosyaya yazar (örneğin bir `.npmrc` token dosyası), sonra bu dosyayı silmeyi unutur ve dosya artifact olarak veya sonraki bir katmanda paylaşılır.

### 3. Depolama / Dağıtım Katmanı (Konteyner ve İmaj Katmanları)

Docker/OCI imaj formatının katmanlı (layered) yapısı özel bir tuzak yaratır. Bir Dockerfile'da şu şekilde bir yapı kurulursa:

```
RUN echo "API_KEY=xxxx" > /app/.env
RUN some-build-step
RUN rm /app/.env
```

`rm` komutu son katmanda dosyayı "görünmez" yapar, ama önceki katman hâlâ image içinde fiziksel olarak durur ve `docker history`, katman dosya sistemini export etme veya basit bir `docker save` + arşiv inceleme ile o katmandaki `.env` dosyası geri çıkarılabilir. Kök neden, **katmanlı dosya sisteminin "silme" işleminin bir üstteki katmanda bir "tombstone" (silindi işareti) eklemesi, alttaki veriyi fiziksel olarak yok etmemesi**dir. Bu, kriptografideki "güvenli silme" problemine benzer ama disk düzeyinde değil, imaj katmanı düzeyinde yaşanır.

Benzer bir mantık build cache'leri, multi-stage build'lerin ara imajları ve CI runner'ların paylaşılan disk önbellekleri için de geçerlidir: bir sistemin *ne yaptığını* değil, *hangi katmanlarda hangi veriyi kalıcı olarak sakladığını* anlamak, sızıntı yüzeyini anlamanın anahtarıdır.

## Savunma Katman 1: Secrets'ı Koddan Ayırmak (Externalization)

En temel ilke şudur: **hiçbir secret, kaynak koduyla aynı yaşam döngüsünde (repository'de) bulunmamalıdır.** Bunun pratik uygulaması "12 Factor App" metodolojisinin "config" ilkesiyle örtüşür: konfigürasyon (ve secrets bunun bir alt kümesidir) ortam değişkenlerinden veya çalışma zamanında enjekte edilen bir kaynaktan gelmelidir, koda gömülü olmamalıdır.

Ancak ortam değişkeni tek başına yeterli bir çözüm değildir; sadece "secrets'ı kod dışına taşımanın" ilk adımıdır. Ortam değişkenleri process listesinde (`/proc/[pid]/environ`), çocuk process'lere miras yoluyla, veya yanlışlıkla loglanarak hâlâ sızabilir. Bu yüzden olgun bir mimari, secrets'ı **merkezi bir secrets yönetim sistemi (secrets manager)** üzerinden, ihtiyaç anında (just-in-time) çeker.

### Secrets Manager / Vault Yaklaşımının Çalışma Mantığı

HashiCorp Vault, AWS KMS/Secrets Manager, Azure Key Vault, GCP Secret Manager gibi sistemlerin ortak çalışma mantığı şudur:

1. **Merkezi, erişim kontrollü depolama**: Secrets tek bir yerde, şifrelenmiş halde tutulur; erişim IAM/RBAC politikalarıyla kısıtlanır.
2. **Dinamik secrets (mümkün olduğunda)**: Statik bir parola yerine, sistem her istekte *kısa ömürlü, tek kullanımlık* kimlik bilgisi üretir (örneğin Vault'un veritabanı için anlık kullanıcı/parola üretmesi). Bu, "sızan bir secret'ın değeri" kavramını kökten değiştirir: sızsa bile birkaç dakika içinde geçersiz olur.
3. **Denetim izi (audit log)**: Kim, ne zaman, hangi secret'a eriştiğini kaydeder — bu, sızıntı sonrası adli analiz (forensics) için kritiktir.
4. **Rotasyon otomasyonu**: Secrets belirli aralıklarla veya bir olaydan sonra (ör. bir çalışanın işten ayrılması) otomatik yenilenir.
5. **En az ayrıcalık (least privilege) ile kapsam daraltma**: Her servis sadece ihtiyacı olan secret'a, sadece ihtiyacı olan işlem için (örn. sadece okuma) erişebilir.

Bu yaklaşımın "neden" işe yaradığını anlamanın anahtarı şudur: statik, uzun ömürlü bir secret'ın güvenliği tamamen *sızmamasına* bağlıdır — bu tek nokta hatasıdır (single point of failure). Dinamik, kısa ömürlü secrets modeli ise sızıntıyı *varsayarak* tasarlanır; sızıntının etkisini zaman ve kapsam olarak sınırlar. Bu, güvenlik mühendisliğindeki "defense in depth" ve "assume breach" felsefesinin doğrudan uygulamasıdır.

### CI/CD Sistemlerinin Kendi Secrets Mekanizması

GitHub Actions "encrypted secrets", GitLab CI "CI/CD variables (protected/masked)", Jenkins "Credentials Plugin" gibi yerleşik mekanizmalar da bir secrets yönetim katmanıdır, ama bunların sınırlarını bilmek gerekir:

- Bu mekanizmalar genellikle secrets'ı pipeline çalışması sırasında ortam değişkeni olarak enjekte eder; log maskeleme yapar ama %100 garanti değildir (özellikle değişken bir dönüşümden geçirilirse).
- "Protected" ve "masked" gibi bayraklar, secret'ın yalnızca belirli branch'lerde veya tag'lerde kullanılabilmesini ve log'da gizlenmesini sağlar; bu bayrakların doğru yapılandırılması insan sorumluluğundadır — varsayılan olarak her zaman en güvenli seçenek açık gelmeyebilir.
- Bu yerleşik mekanizmalar genelde dinamik/kısa ömürlü secrets üretmez; statik değerleri saklarlar. Bu yüzden büyük organizasyonlar CI'nin kendi secrets deposunu, harici bir Vault/KMS ile entegre ederek "CI sadece kısa ömürlü bir token alır, gerçek secret Vault'ta kalır" modelini tercih eder.

En iyi pratik, CI pipeline'ının doğrudan uzun ömürlü bulut kimlik bilgisi (örn. statik AWS access key) tutmak yerine, **OIDC (OpenID Connect) tabanlı federasyon** kullanmasıdır: CI runner, bulut sağlayıcıya "ben şu repository'nin şu branch'inden çalışan bir iş akışıyım" diyen kısa ömürlü bir token sunar, bulut sağlayıcı bunu doğrulayıp geçici (birkaç dakikalık) bir erişim kimlik bilgisi verir. Bu modelde ortada hiçbir zaman uzun ömürlü, sızdırılabilir statik bir anahtar bulunmaz — kök neden ortadan kaldırılmış olur, sadece azaltılmış değil.

## Savunma Katman 2: Tespit (Detection) — Secrets Scanning

Önleme her zaman yeterli olmaz; bu yüzden ikinci savunma katmanı **sızıntının erken tespiti**dir. Burada iki farklı zaman noktası önemlidir: commit *öncesi* (pre-commit) ve commit *sonrası* / sürekli tarama (post-commit, CI içinde, repository genelinde).

### Çalışma Mantığı: Secrets Scanner'lar Nasıl Tespit Eder

Araçlar (git-secrets, gitleaks, trufflehog ve benzerleri) temelde iki tespit stratejisi kullanır:

1. **Desen (pattern/regex) eşleştirme**: Bilinen secret formatlarına (AWS access key'in `AKIA` ile başlaması gibi, veya belirli uzunluk/karakter setine sahip token formatları) karşı regex kalıpları çalıştırılır. Bu yöntem hızlıdır ama yalnızca *bilinen* formatları yakalar; rastgele bir iç API anahtarının formatı tanımlı değilse kaçabilir.
2. **Entropi analizi (entropy analysis)**: Bir string'in Shannon entropisi hesaplanır. Gerçek metin (İngilizce kelimeler, kod) düşük-orta entropiye sahipken, rastgele üretilmiş bir anahtar veya token yüksek entropiye sahiptir. Araç, belirli bir eşiğin üzerindeki entropiye sahip string'leri "potansiyel secret" olarak işaretler. Bu yöntemin mantığı şudur: format bilinmese bile, *rastgeleliğin kendisi* bir sinyaldir.

Bu iki yöntem birlikte kullanıldığında hem bilinen sağlayıcı formatları (yüksek kesinlik, düşük yanlış pozitif) hem de bilinmeyen/özel formatlar (daha geniş kapsam, daha yüksek yanlış pozitif oranı) yakalanabilir.

### Nerede Çalıştırılmalı: Katmanlı Tarama Stratejisi

- **Pre-commit hook**: Geliştirici makinesinde, commit oluşturulmadan hemen önce çalışır. En erken müdahale noktasıdır; sızıntı hiç repository'ye girmeden engellenir. Kök neden mantığı: "en ucuz düzeltme, en erken düzeltmedir" — bir secret bir kez merkezi repository'ye push edilip sonra silinse bile, git geçmişinde (ve olası fork/clone'larda) kalıcı olarak var olmaya devam eder.
- **Pre-receive / server-side hook veya CI pipeline adımı**: Geliştirici pre-commit hook'unu atlarsa (`--no-verify`) veya hook'u hiç kurmamışsa diye bir ikinci savunma hattı gerekir. Bu, merkezi olarak zorunlu kılınabilir (developer'ın atlayamayacağı bir kontrol noktası).
- **Repository genelinde periyodik/geçmiş taraması**: Yeni bir araç kurulduğunda veya bir olay şüphesi doğduğunda, sadece yeni commit'leri değil, *tüm git geçmişini* taramak gerekir — çünkü bir secret geçmişte bir commit'te var olup sonradan "silinmiş" görünse bile git geçmişinde erişilebilir kalır.
- **Konteyner imajı ve artifact taraması**: Build çıktıları (Docker image katmanları, derlenmiş binary'ler, sıkıştırılmış artifact'lar) da ayrıca taranmalıdır; kaynak kodu temiz olsa bile build süreci sırasında bir secret imaja "sızmış" olabilir.

### Yaygın Tuzaklar

- **Sadece pre-commit hook'a güvenmek**: Hook, geliştiricinin makinesinde çalışır ve `git commit --no-verify` ile bilinçli/bilinçsiz atlanabilir. Bu yüzden merkezi/CI tarafında da zorunlu bir kontrol olmalıdır — pre-commit sadece "hızlı geri bildirim" katmanıdır, tek güvenlik sınırı değildir.
- **Sadece yeni commit'leri taramak, geçmişi taramamak**: Bir araç yeni kurulduğunda geçmiş taranmazsa, geçmişte kalmış secrets fark edilmeden kalır.
- **Yanlış pozitif yorgunluğu (alert fatigue)**: Entropi tabanlı tespit çok fazla yanlış pozitif üretirse (örneğin base64 encode edilmiş ama hassas olmayan veri, ya da hash değerleri), ekipler zamanla uyarıları görmezden gelmeye başlar. Bu yüzden allowlist/baseline mekanizmaları (bilinen zararsız yüksek-entropi string'leri hariç tutma) doğru yapılandırılmalıdır — ama bu allowlist'in kendisi de dikkatsizce genişletilirse gerçek bir secret'ı gizleyen bir kör nokta haline gelebilir.
- **Tespit edilen secret'ı sadece silmek, rotate etmemek**: Bir secret git geçmişinden temizlense (history rewrite) bile, o secret zaten bir noktada dışarıya açık olarak var olmuştur — clone'lanmış kopyalar, CI log önbellekleri, üçüncü taraf tarama botları (GitHub'ın kendi otomatik tarayıcısı dahil, dış aktörler de public repoları sürekli tarar) tarafından zaten görülmüş olabilir. **Kök neden düzeltmesi her zaman: sızan secret'ı geçersiz kıl (rotate/revoke), sonra geçmişi temizle.** Sıra bu şekilde olmalıdır; sadece geçmişi temizlemek, "kilidi değiştirmeden anahtarın fotoğrafını silmeye" benzer.

## Savunma Katman 3: CI/CD Pipeline'ının Kendi Güvenliği

Secrets scanning ve secrets manager kullanımı yeterli değildir; pipeline'ın kendisinin de güvenli tasarlanması gerekir.

### En Az Ayrıcalık ve Kapsam Daraltma

Her pipeline job'u yalnızca ihtiyacı olan secret'a erişmelidir. Örneğin bir "test" job'unun production veritabanı kimlik bilgisine ihtiyacı yoktur; buna rağmen tüm secrets'ı tüm job'lara global olarak enjekte etmek, sızıntı yüzeyini gereksiz yere büyütür. Kök neden mantığı: bir job'da bir bağımlılık (dependency) güvenliği ihlal edilirse (örneğin bir npm paketi zararlı kod içeriyorsa — tedarik zinciri saldırısı), o job'un erişebildiği *her şey* saldırganın eline geçer. Kapsamı daraltmak, olası bir ihlalin "blast radius"ını (etki alanını) küçültür.

### Üçüncü Taraf Eylemler/Eklentiler (Third-party Actions/Plugins) Riski

CI sistemlerinin çoğu (özellikle GitHub Actions) topluluk tarafından yazılmış "action"ları çalıştırmaya izin verir. Bu action'lar pipeline içinde tam yetkiyle çalışır ve tanım gereği pipeline'daki tüm ortam değişkenlerine (dolayısıyla secrets'a) erişebilir. Bir action'ın kötü niyetli veya ele geçirilmiş (compromised) bir sürümü, secrets'ı sessizce dışarıya sızdırabilir. Bunun kök nedeni, CI sistemlerinin "eklenti = güvenilir kod" varsayımıyla tasarlanmış olmasıdır. En iyi pratikler:

- Üçüncü taraf action'ları **tam sürüm hash'ine (commit SHA) sabitlemek**, hareketli bir tag'e (`@v1` gibi) değil — çünkü tag'in işaret ettiği içerik sonradan değiştirilebilir.
- Action'ların istediği izinleri (`permissions:` bloğu) en aza indirmek.
- Mümkünse action'ları organizasyon içinde onaylanmış bir listeyle sınırlamak (allowlist).

### Fork/PR Kaynaklı Pipeline Tetikleyicileri

Daha önce kök neden bölümünde değinildiği gibi, dış katkıcıların PR'larının secrets'a erişebildiği bir yapılandırma ciddi risk taşır. Doğru yaklaşım, dış/güvenilmeyen kaynaklardan tetiklenen pipeline çalışmalarında secrets'ı hiç enjekte etmemek veya yalnızca minimal, salt-okunur, kapsamı son derece dar bir token vermektir; asıl deploy/yayınlama adımlarını yalnızca ana branch'e merge sonrası, güvenilir bağlamda çalıştırmaktır.

### Log Hijyeni

Pipeline script'lerinde şu tür alışkanlıklardan kaçınılmalıdır: `set -x` (bash'te her komutu ve değişken değerini log'a basan debug modu) secrets içeren bir script üzerinde açık bırakmak, `curl -v`/`--verbose` ile header içindeki Authorization token'ını log'a yazdırmak, hata mesajlarına (stack trace, exception detail) yanlışlıkla secret gömmek. Kök neden: log sistemleri genelde "her şeyi kaydet, sonra filtrele" mantığıyla çalışır; bu yüzden *üretilen* log'un içeriğini kaynağında kontrol etmek, log'u sonradan filtrelemekten çok daha güvenilirdir.

## Bir Sızıntı Gerçekleştiğinde: Olay Müdahalesi Mantığı

Tespit sistemleri "önce" değil "sonra" da devreye girer; bir sızıntı fark edildiğinde izlenecek mantıksal sıra şudur:

1. **Kapsamı belirle**: Hangi secret, ne zaman, hangi commit/log/imajda açığa çıktı; kimler görebilmiş olabilir (public repo ise potansiyel olarak herkes, hatta otomatik tarayan botlar dakikalar içinde).
2. **Derhal geçersiz kıl (revoke/rotate)**: Bu, en kritik ve zaman-duyarlı adımdır. Secret hâlâ geçerliyse, geçmişi temizlemenin hiçbir faydası yoktur.
3. **Etkiyi denetle (audit)**: Secret'ın erişebildiği kaynaklarda yetkisiz kullanım oldu mu, denetim loglarından kontrol et.
4. **Kaynağı temizle**: Git geçmişini yeniden yaz (gerekirse), CI log önbelleklerini temizle, sızan imajları registry'den kaldır.
5. **Kök nedeni düzelt**: Neden bu secret koda gömüldü / neden tarama onu yakalamadı / neden pre-commit hook atlandı — süreci, bir daha aynı hatanın olmayacağı şekilde güncelle (örneğin zorunlu CI kontrolü ekle, geliştirici eğitimini güçlendir).

Bu sıralama önemlidir çünkü adli analiz ve temizlik, geçerli bir secret'ın hâlâ kötüye kullanılabildiği bir pencerede yapılırsa, saldırgan o pencerede zaten hasar vermiş olabilir.

## Sonuç: Zihniyet Değişimi

Bu konunun özeti tek bir cümlede toplanabilir: **secrets yönetimi, "secrets'ı gizlemek" değil, "secrets'ın sızma yüzeyini daraltmak, sızıntıyı erken yakalamak ve sızsa bile etkisini sınırlamak" üzerine kurulu bir mühendislik disiplinidir.** Statik, uzun ömürlü, geniş yetkili secrets'lardan; dinamik, kısa ömürlü, dar yetkili secrets'lara geçiş — tıpkı ağ güvenliğinde çevre (perimeter) savunmasından "zero trust"a geçiş gibi — bu alandaki olgunlaşmanın temel yönüdür. Araçlar (gitleaks, git-secrets, Vault, KMS) bu felsefeyi uygulamanın *araçlarıdır*; felsefenin kendisi olmadan araçlar yanlış yapılandırılır ve sahte bir güvenlik hissi (false sense of security) yaratır.
