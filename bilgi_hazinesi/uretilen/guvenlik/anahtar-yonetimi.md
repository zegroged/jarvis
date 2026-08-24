# Anahtar ve Sır Yönetimi

## Tanım: "Sır" nedir ve neden ayrı bir disiplin?

Bir yazılım sisteminin çalışabilmesi için başka sistemlere kendini kanıtlaması gerekir. Veritabanına bağlanır, bir ödeme sağlayıcısının API'sini çağırır, bir bulut kaynağına erişir. Bu kanıtlama işleminde kullanılan gizli değerlerin tümüne **sır (secret)** diyoruz: veritabanı parolaları, API anahtarları (API keys), OAuth `client_secret` değerleri, TLS özel anahtarları (private keys), imzalama anahtarları, SSH anahtarları, şifreleme anahtarları (encryption keys) ve token'lar.

Bu değerlerin ortak özelliği şudur: **onları bilen herkes, o sistemin kimliğine bürünebilir.** Bir parola sızarsa, saldırgan sizin uygulamanız gibi davranarak veritabanınızın tamamını okuyabilir. Bir imzalama anahtarı sızarsa, saldırgan geçerli görünen sahte token'lar üretebilir. İşte bu yüzden sır yönetimi (secret management) ve daha dar anlamda anahtar yönetimi (key management), güvenliğin en kritik ve en çok ihmal edilen alanlarından biridir.

Anahtar yönetimi, sırların **tüm yaşam döngüsünü** kapsar: üretim (generation), güvenli saklama (storage), dağıtım (distribution), kullanım, rotasyon (rotation) ve iptal/imha (revocation, destruction). Bu döngünün her aşamasında yapılan bir hata, en güçlü şifreleme algoritmasını bile anlamsız hale getirebilir. Kriptografide meşhur bir söz vardır: "Kimse şifreyi kırmaz, anahtarı çalar." Modern ihlallerin ezici çoğunluğu, algoritma zafiyetinden değil, kötü anahtar yönetiminden kaynaklanır.

## Kök Neden: Sırlar neden bu kadar sık sızar?

Sırların sızmasının teknik bir kaçınılmazlığı yoktur; bu tamamen bir **mimari ve süreç sorunudur**. Kök nedenleri anlamak, çözümü de anlamlı kılar.

### Neden 1: Sır, "veri" gibi davranır ama "kimlik" gibi davranmalıdır

Geliştiriciler bir parolayı, bir string olarak düşünür. String'ler kolayca kopyalanır: koda gömülür, bir Slack mesajına yapıştırılır, bir e-postaya eklenir, bir log satırına yazılır, bir ortam değişkenine (environment variable) konur ve oradan bir hata raporuna (crash dump) sızar. Sırrın bir kimlik olduğu gerçeği gözden kaçınca, ona bir string'e gösterilen özensizlik gösterilir. Kök neden budur: **sır, kopyalanabilir bir veri olarak muamele görür.**

### Neden 2: Sırlar zamanla çoğalır ve kimse takip etmez

Bir sistem büyüdükçe sır sayısı katlanır. Onlarca mikroservis, her biri birden çok veritabanı ve dış servis kullanır. Kimse "bu anahtar nerede kullanılıyor, kimin elinde, ne zaman üretildi" sorusunu cevaplayamaz hale gelir. Bu görünürlük kaybına **secret sprawl** (sır yayılması) denir. Görünmeyen bir sırrı rotasyona sokamaz, iptal edemez veya koruyamazsınız.

### Neden 3: Sırlar sürüm kontrolünde (version control) ölümsüzdür

Bir sır Git deposuna commit edildiğinde, onu sonraki bir commit'le silmek yetmez. Git geçmişi (history) o değeri sonsuza dek saklar. Depo bir kez `git clone` ile kopyalandıysa, sır artık sizin kontrolünüzde değildir. Public bir repoya kazayla push edilen bir AWS anahtarının, dakikalar içinde otomatik tarayıcı botlar tarafından bulunup kötüye kullanıldığı sayısız gerçek olay vardır. Bu, kök nedenlerin en somut ve en yıkıcı tezahürüdür.

## Kodan Ayırma: En temel ilke

Sır yönetiminin birinci kuralı basittir ama çoğu ihlalin kökü tam da bunun ihlalidir: **sırlar asla kaynak koda gömülmemelidir.** Buna "hardcoded secrets" (koda gömülü sırlar) denir ve neredeyse tüm statik güvenlik tarama araçlarının (SAST) ilk aradığı şeydir.

### Neden koda gömmek bu kadar tehlikeli?

Kod, doğası gereği paylaşılan ve çoğaltılan bir varlıktır. Bir sırrı koda gömdüğünüzde onu şunlarla eşitlemiş olursunuz:

- Depoya erişimi olan her geliştirici, artık o sırrı bilir. İşten ayrılan bir çalışan bile eski bir clone ile o sırra sahiptir.
- CI/CD sistemleri, yedekler (backups), IDE önbellekleri ve fork'lar sırrı çoğaltır.
- Kod ile sır aynı yaşam döngüsüne hapsolur: sırrı değiştirmek (rotasyon), artık bir kod değişikliği, bir code review ve bir deploy gerektirir. Bu sürtünme yüzünden rotasyon fiilen hiç yapılmaz.

Buradaki temel prensip, güvenlikte "konfigürasyon ile kodun ayrılması" ilkesidir. On İki Faktör Uygulama (Twelve-Factor App) yaklaşımının söylediği gibi, koda bağlı olmayan her değer konfigürasyondur ve konfigürasyon koddan ayrı yönetilmelidir. Sırlar, konfigürasyonun en hassas alt kümesidir.

### Ortam değişkenleri: İyi bir başlangıç ama son durak değil

Sırları koddan çıkarmanın ilk adımı genellikle onları ortam değişkenlerine (environment variables) taşımaktır. Bu, koda gömmekten kesinlikle daha iyidir çünkü sır artık kod deposunda yaşamaz. Ancak ortam değişkenleri de zayıflıklar taşır ve bir son çözüm değildir:

- Ortam değişkenleri process'in tüm alt process'lerine miras kalır; kötü niyetli veya zafiyetli bir alt process bunları okuyabilir.
- Çoğu platformda `/proc/<pid>/environ` üzerinden veya bir hata anında crash dump'a sızabilirler.
- Rotasyon için process'in yeniden başlatılması gerekir.
- Sık sık bir `.env` dosyasında saklanırlar ve bu dosya yanlışlıkla commit'lenir. `.gitignore` disiplini kırılgandır.

Bu yüzden olgun sistemler ortam değişkeninden bir adım öteye geçerek **secret manager** kullanır.

## Secret Manager: Sırların merkezi otoritesi

Bir secret manager, sırları güvenli biçimde saklayan, erişimi denetleyen ve dağıtan özelleşmiş bir sistemdir. HashiCorp Vault gibi kendi kendine barındırılan (self-hosted) çözümler ile bulut sağlayıcıların yönetilen servisleri (AWS Secrets Manager, Azure Key Vault, Google Secret Manager gibi) bu kategoridedir.

### Bir secret manager tam olarak hangi sorunu çözer?

Değerini anlamak için sunduğu somut yetenekleri kök nedenlerle eşleştirelim:

1. **Merkezi ve tek doğruluk kaynağı.** Tüm sırlar tek bir denetlenen yerdedir. Bu, secret sprawl'ı çözer: artık "hangi sır nerede" sorusunun bir cevabı vardır.

2. **Erişim denetimi (access control).** Her uygulama, kullanıcı veya servis yalnızca ihtiyacı olan sırlara, ihtiyacı olan sürede erişebilir. Bir servis hesabının veritabanı parolasına erişmesi gerekiyorsa, imzalama anahtarına erişmesine gerek yoktur. Bu, **en az yetki ilkesini (principle of least privilege)** sırlara uygular.

3. **Denetim kaydı (audit log).** Kimin, hangi sırra, ne zaman eriştiği kayıt altına alınır. Bir ihlal sonrası "bu anahtar kimin eline geçmiş olabilir" sorusu ancak böyle cevaplanabilir.

4. **Dinamik sırlar (dynamic secrets).** Bu, en güçlü özelliklerden biridir ve genellikle atlanır. Statik bir veritabanı parolası saklamak yerine, secret manager talep anında veritabanında kısa ömürlü, uygulamaya özel bir kullanıcı **üretir** ve bu kimlik bilgisi birkaç dakika veya saat sonra otomatik olarak geçersiz kılınır. Böylece sır, sızsa bile çok kısa süre işe yarar. Bu yaklaşım rotasyon problemini kökten değiştirir: sır zaten kısa ömürlü doğduğu için ayrıca rotasyona gerek kalmaz.

5. **Merkezi şifreleme.** Sırlar diskte şifreli (encryption at rest) saklanır; şifreleme anahtarları da bir üst anahtarla (bkz. KMS/HSM ve envelope encryption) korunur.

### Uygulama sırra nasıl ulaşır? Bootstrap sorunu

Burada ince bir tehlike vardır. Uygulama, secret manager'dan sır çekebilmek için önce secret manager'a kendini kanıtlamalıdır. Peki bu kanıtlamada kullanılan kimlik nereden gelir? Bu, **secret zero** veya **bootstrapping** problemidir. Eğer secret manager'a erişim için bir başka parolayı koda gömerseniz, sorunu bir seviye ötelemiş ama çözmemiş olursunuz.

Doğru çözüm, uygulamanın **çalıştığı ortamın kendisinden gelen, kopyalanamaz bir kimliğe** dayanmaktır. Bulutta bu genellikle örneğe (instance) veya iş yüküne (workload) atanmış bir kimliktir: bulut sağlayıcı, üzerinde çalışan koda kısa ömürlü bir kimlik jetonu verir; secret manager bu jetonu bulut sağlayıcıya doğrulatarak uygulamanın gerçekten o ortamda çalıştığını teyit eder. Kubernetes'te bu rol service account token'ları ve workload identity ile oynanır. Buradaki fikir şudur: kanıtlama, kopyalanabilir bir string'e değil, ortamın doğrulanabilir bir özelliğine dayanır. Böylece "secret zero" hiçbir yere yazılmaz.

## KMS ve HSM: Anahtarları koruyan anahtarlar

Sırları şifreli saklamak istiyoruz. Ama şifrelemek için bir anahtara ihtiyacımız var. O anahtarı nerede saklayacağız? Bu döngü, en tepede fiziksel olarak korunan bir noktaya varmalıdır. İşte bu nokta **HSM**'dir.

### HSM (Hardware Security Module) nedir ve neden donanım?

HSM, kriptografik anahtarları üreten, saklayan ve onlarla işlem yapan, kurcalamaya dayanıklı (tamper-resistant) özel bir donanımdır. HSM'in temel ve devrimsel özelliği şudur: **özel anahtar (private key) donanımın içinden asla çıkmaz.**

Bunun neden bu kadar önemli olduğunu düşünelim. Normal bir sunucuda bir imzalama anahtarı kullandığınızda, o anahtar bir an için RAM'e yüklenir. RAM'e yüklenen her şey, yeterince yetkili bir saldırgan tarafından okunabilir; bir memory dump, bir zafiyet veya kötü niyetli bir yönetici anahtarı ele geçirebilir. HSM bu modeli tersine çevirir: veriyi HSM'e gönderirsiniz, HSM içeride imzalar/şifreler ve size **sonucu** döndürür; anahtarın kendisini asla vermez. Anahtar donanımdan hiç ayrılmadığı için, sunucu tamamen ele geçirilse bile saldırgan anahtarı kopyalayamaz; yalnızca HSM erişimi olduğu sürece onu **kullanabilir**, ki bu erişim de denetlenir ve kesilebilir.

HSM'ler ayrıca fiziksel kurcalamaya karşı korumalıdır: kasa açılmaya çalışıldığında anahtarları silen mekanizmalar içerirler. Bu yüzden kök sertifika otoriteleri (root CA), ödeme sistemleri ve yüksek değerli imzalama işlemleri HSM ile korunur. Güvenilirlik seviyelerini belirlemek için FIPS 140-2/140-3 gibi standartlara göre sertifikalanırlar (kesin seviye numarasını, ilgili ürünün belgesinden doğrulamanızı öneririm).

### KMS (Key Management Service) ve envelope encryption

Her uygulamanın kendi HSM'ini yönetmesi pahalı ve karmaşıktır. Bulut sağlayıcılar bu yeteneği bir servis olarak sunar: **KMS**. KMS, arka planda genellikle HSM'lere dayanan, anahtar üretimi, saklama, rotasyon ve erişim denetimini bir API arkasında sunan yönetilen bir hizmettir.

KMS'in çalışma mantığındaki merkezi teknik, **envelope encryption** (zarf şifreleme) desenidir. Neden gereklidir? Çünkü kök anahtarı (master key) doğrudan büyük veri hacimlerini şifrelemek için kullanmak hem yavaştır hem de kök anahtarı sürekli ağ üzerinden trafiğe maruz bırakır. Bunun yerine iki katmanlı bir yapı kurulur:

1. Veriyi şifrelemek için yerel olarak rastgele bir **Data Encryption Key (DEK)** üretilir. Veri hızlıca bu DEK ile şifrelenir.
2. Sonra DEK'in kendisi, KMS'te güvenle saklanan **Key Encryption Key (KEK)** (kök anahtar) ile şifrelenir. Şifrelenmiş DEK, şifreli verinin yanında saklanabilir; çünkü onu açacak KEK, KMS'in (ve dolayısıyla HSM'in) içindedir ve dışarı çıkmaz.
3. Veriyi çözmek gerektiğinde şifreli DEK, açılması için KMS'e gönderilir; KMS açık DEK'i döndürür; uygulama veriyi çözer ve açık DEK'i bellekten hızla siler.

Bu desenin zarafeti şudur: kök anahtar (KEK) asla korunan alandan çıkmaz, milyonlarca dosyayı ayrı ayrı DEK'lerle şifreleyebilirsiniz ve kök anahtarı rotasyona sokmak istediğinizde tüm veriyi yeniden şifrelemeniz gerekmez; yalnızca DEK'leri saran KEK'i değiştirmeniz yeterli olabilir.

## Rotasyon: Neden ve nasıl döndürülür?

**Rotasyon**, bir sırrı düzenli aralıklarla veya bir olay sonrası yeni bir değerle değiştirmektir. Rotasyonun kök mantığı istismar penceresini daraltmaktır.

### Rotasyonun kök mantığı: Sızmayı varsaymak

Modern güvenliğin temel varsayımı şudur: **sır er ya da geç sızacaktır.** Bir sızmanın olup olmayacağı değil, ne zaman fark edileceği sorudur. Uzun ömürlü (long-lived) bir sır, bir kez sızdığında, siz bunu fark edene kadar (ki bu aylar sürebilir) saldırgana sınırsız erişim penceresi tanır. Rotasyon bu pencereyi keser: sır düzenli olarak değiştiğinde, sızmış eski değer belirli bir süre sonra otomatik olarak işe yaramaz hale gelir. Saldırganın kazandığı erişim, rotasyon aralığı kadar bir ömre sahip olur.

Bu mantığı en uç noktaya götüren yaklaşım, sırrı en baştan kısa ömürlü (short-lived, ephemeral) yapmaktır. Dakikalarca geçerli bir token, "rotasyon" ihtiyacını büyük ölçüde ortadan kaldırır çünkü zaten sürekli yenilenmektedir. Yukarıda anlatılan dinamik sırlar bu felsefenin ürünüdür.

### İki tür rotasyon tetikleyicisi

- **Zamanlı (proaktif) rotasyon:** Belirli bir takvimde otomatik olarak yapılır. Amaç, herhangi bir sızmanın ömrünü sınırlamaktır. Kritik olan, bunun otomatik olmasıdır; elle yapılan rotasyon çoğu ekipte fiilen hiç yapılmaz.
- **Olay tetikli (reaktif) rotasyon:** Bir çalışan işten ayrıldığında, bir sır sızmış olabileceği şüphesi doğduğunda veya bir bağımlılıkta zafiyet çıktığında **hemen** yapılır. Bu senaryoda hız hayatidir.

### Rotasyonun teknik zorluğu: Kesintisiz geçiş

Rotasyonun en çok atlanan yönü, onu **kesintisiz (zero-downtime)** yapmaktır. Bir anahtarı bir anda eski değerden yeni değere geçirirseniz, eski anahtarla imzalanmış ama henüz doğrulanmamış istekler geçersiz olur; hâlâ eski parolayı önbelleğinde tutan bir servis bağlantısı kopar. Bu yüzden rotasyon genellikle şu desenlerle yapılır:

- **Çoklu geçerli anahtar (overlap / grace period):** Belirli bir süre hem eski hem yeni anahtar geçerli sayılır. Yeni imzalar yeni anahtarla atılırken, eski anahtarla imzalanmış geçerli token'lar doğrulanmaya devam eder. Geçiş penceresi kapanınca eski anahtar iptal edilir. JWT gibi imzalı token'larda `kid` (key ID) alanı tam da bunun için vardır: her token hangi anahtarla imzalandığını taşır, doğrulayan taraf doğru anahtarı seçer.
- **İki kimlik bilgisi deseni (AWS Secrets Manager'ın veritabanı rotasyonunda kullandığı gibi):** İki değişimli kullanıcı/kimlik tutulur; biri aktifken diğeri yenilenir, sonra trafik yeni olana kaydırılır. Böylece hiçbir an geçerli bir kimlik bilgisi olmaksızın kalınmaz.

Anahtar noktası şudur: **rotasyon bir "kesme" değil, bir "geçiş" olarak tasarlanmalıdır.** Bu tasarlanmazsa, ekipler rotasyonun kesinti riskinden korkar ve hiç yapmaz.

## Sömürü Mantığı: Saldırgan sırları nasıl ele geçirir?

Savunmayı doğru kurmak için saldırganın nasıl düşündüğünü bilmek gerekir. Sır avcılığı, modern saldırıların en verimli aşamalarından biridir çünkü tek bir geçerli sır, tüm zincirin atlanmasını sağlayabilir.

- **Depo ve geçmiş taraması:** Saldırganlar, halka açık depoları ve sızmış özel depoları otomatik araçlarla tarar. `git log`, `git blame` ve tüm geçmiş dallar (branch) taranır; bir sır silinmiş olsa bile geçmişte durur. Anahtarlar genellikle tanınabilir desenlere sahiptir (belirli önekler, sabit uzunluklar), bu yüzden regex ile hızla bulunurlar.
- **Log ve hata çıktısı madenciliği:** Uygulamalar sıklıkla istek başlıklarını, tam URL'leri (query string içinde token barındırabilir) veya hata anındaki değişken içeriklerini loglar. Log toplama sistemlerine erişebilen bir saldırgan burada sır bulur.
- **CI/CD ve build ortamı:** Build pipeline'ları sırları ortam değişkeni olarak enjekte eder. Zafiyetli bir build betiği (örneğin log'a `env` döken bir adım) tüm sırları açığa çıkarır. Zehirlenmiş bir bağımlılık (supply chain attack) build sırasında ortam değişkenlerini dışarı sızdırabilir.
- **Bellek ve process incelemesi:** Ele geçirilmiş bir sunucuda saldırgan `/proc/<pid>/environ`'u okuyabilir, memory dump alabilir veya çalışan process'e attach olabilir. Ortam değişkenindeki sırlar bu yüzden nihai koruma değildir.
- **SSRF ile metadata servisi istismarı:** Bulutta, bir Server-Side Request Forgery (SSRF) zafiyeti üzerinden uygulama, kendi metadata servisine (instance kimlik bilgilerini veren iç uç nokta) çağrı yapmaya zorlanabilir ve o kimlik bilgileri sızdırılabilir. Bu yüzden metadata servislerinin güncel, oturum-zorunlu (session-required) sürümleri kullanılmalıdır.

### Savunma, sömürü mantığının aynasıdır

Her istismar yolunun bir savunma karşılığı vardır ve bunlar doğrudan yukarıdaki listeyle eşleşir:

- Depo taramasına karşı: **secret scanning** araçlarını hem commit öncesi (pre-commit hook) hem de sunucu tarafında (push protection) çalıştırın; sızan sır bulunursa onu **derhal iptal edin** (silmek yetmez, çünkü zaten kopyalanmış olabilir). Sızan bir sır ölü sır değildir; rotasyona sokulana kadar canlıdır.
- Log madenciliğine karşı: sırları loglamayı yapısal olarak imkânsızlaştırın; log kütüphanelerinde bilinen sır alanlarını maskeleyin, tam URL yerine sadeleştirilmiş yolları loglayın.
- CI/CD istismarına karşı: sırları build çıktısında değil, çalışma anında (runtime) ve mümkünse kısa ömürlü olarak enjekte edin; OIDC tabanlı, kısa ömürlü bulut kimliklerini statik anahtarlara tercih edin.
- Bellek istismarına karşı: en kritik anahtarları HSM/KMS içine hapsedin ki uygulama belleğinde hiç bulunmasınlar.
- SSRF'e karşı: metadata servisinin sıkılaştırılmış sürümünü zorunlu kılın ve uygulamada giden isteklerde iç adreslere erişimi kısıtlayın.

## Yaygın Hatalar

Deneyimli ekiplerin bile düştüğü tekrar eden hatalar vardır. Bunları isimlendirmek, onlardan kaçınmanın ilk adımıdır.

- **Sırrı silerek "temizlediğini" sanmak.** Bir sır repoya girdiyse, onu commit ile silmek geçmişten silmez ve kopyalanmasını geri almaz. Tek doğru tepki: sırrı iptal etmek/rotasyona sokmak. Kod temizliği ikincildir.
- **Rotasyonu hiç yapmamak.** En sık hata budur. Ekipler sırları oluşturur ve yıllarca dokunmaz. Uzun ömürlü sırlar, sessizce biriken bir borç gibidir; bir gün patlar.
- **Aynı sırrı her ortamda kullanmak.** Geliştirme (dev), test (staging) ve üretim (production) ortamlarında aynı anahtarı kullanmak, en zayıf ortamın (genelde dev) güvenliğini üretime taşır. Ortamlar sır düzeyinde ayrılmalıdır.
- **En az yetki yerine "her şeye erişim" vermek.** Kolaylık olsun diye her servise tüm sırlara erişim tanımak, tek bir servisin ele geçirilmesini tüm sistemin ele geçirilmesine dönüştürür. Patlama yarıçapı (blast radius) böyle büyür.
- **Secret zero'yu koda gömmek.** Secret manager'a geçmek ama ona erişim anahtarını yine koda gömmek, tüm mimariyi anlamsızlaştırır. Bootstrap kimliği ortamdan gelmelidir.
- **Şifrelemeyi yapıp anahtarı yanına koymak.** Veriyi şifreleyip, çözme anahtarını aynı veritabanında veya aynı erişim alanında saklamak, kilidi kapatıp anahtarı kapının önündeki paspasın altına koymaya benzer. Anahtar ile veri farklı güven alanlarında (trust boundaries) durmalıdır. Envelope encryption tam da bunu sağlar.
- **Kendi kriptografini yazmak.** Anahtar üretiminde zayıf rastgelelik (weak randomness) kaynağı kullanmak veya elle şifreleme kurmak. Anahtarlar kriptografik olarak güvenli rastgele üreteçlerden (CSPRNG) gelmeli; şifreleme için denenmiş kütüphaneler ve KMS kullanılmalıdır.
- **Denetim ve görünürlük eksikliği.** Kimin hangi sırra eriştiğini bilmemek, bir ihlali fark etmeyi ve kapsamını ölçmeyi imkânsızlaştırır. Audit log olmayan bir sır sistemi, kör bir sistemdir.

## En İyi Pratikler

Yukarıdaki tüm mantığı somut, uygulanabilir ilkelere indirgeyelim.

1. **Sırları koddan kesin olarak ayırın.** Hiçbir sır kaynak koda, konfigürasyon dosyalarına veya container imajlarına gömülmesin. Bu, tartışılmaz temeldir.
2. **Merkezi bir secret manager kullanın.** Sırlar tek bir denetlenen, erişim kontrollü otoritede saklansın. Bu, secret sprawl'ı çözer ve denetim, rotasyon, iptal yeteneklerini kazandırır.
3. **Mümkün olan her yerde kısa ömürlü ve dinamik sırlara geçin.** Statik uzun ömürlü anahtar yerine, talep anında üretilen ve kısa sürede geçersizleşen kimlikler kullanın. En iyi rotasyon, sırrın zaten kısa ömürlü olmasıdır.
4. **Rotasyonu otomatikleştirin ve kesintisiz tasarlayın.** Elle rotasyon yapılmaz; otomatik olsun. Geçiş dönemi (overlap) ve anahtar kimliği (`kid`) desenleriyle kesintisiz geçiş sağlayın. Hem zamanlı hem olay tetikli rotasyonu destekleyin.
5. **Kök anahtarları HSM/KMS ile koruyun ve envelope encryption kullanın.** En değerli anahtarlar korunan donanımdan hiç çıkmasın; büyük veriyi DEK ile, DEK'i KEK ile şifreleyin.
6. **En az yetki ilkesini sırlara uygulayın.** Her kimlik yalnızca ihtiyacı olan sırra, ihtiyacı olan sürede erişsin. Ortamları (dev/staging/prod) sır düzeyinde tam ayırın. Patlama yarıçapını daraltın.
7. **Secret scanning'i pipeline'a zorunlu koyun.** Commit öncesi ve push sırasında otomatik tarama olsun. Bir sır sızdığında refleksiniz "sil" değil, "iptal et ve döndür" olsun.
8. **Sırları loglamayı yapısal olarak engelleyin.** Log ve hata çıktılarında sır alanlarını maskeleyin; sırları asla URL query string'inde taşımayın.
9. **Bootstrap'ı ortam kimliğine dayandırın.** Secret zero'yu hiçbir yere yazmayın; uygulamanın çalıştığı ortamın doğrulanabilir kimliğini (workload/instance identity, OIDC) kullanın.
10. **Denetlenebilirlik kurun.** Her sır erişimi loglansın; anormal erişimler için uyarı üretin. Görünürlük olmadan güvenlik olmaz.

Son söz olarak: anahtar ve sır yönetimi, tek seferlik bir kurulum değil, sürekli işleyen bir disiplindir. En güçlü şifreleme, en iyi mimari, kötü yönetilen tek bir anahtarla çöker. Bu alandaki olgunluk, "sır sızmayacak" varsaymaktan vazgeçip "sır sızacak, o zaman zarar ne kadar sınırlı olur" diye sormakla başlar. Kısa ömürlülük, en az yetki, merkezi denetim ve otomatik rotasyon; hepsi bu tek soruya verilmiş cevaplardır.
