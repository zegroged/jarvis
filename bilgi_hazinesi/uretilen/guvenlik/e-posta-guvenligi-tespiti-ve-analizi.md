# E-posta Güvenliği Tespiti ve Analizi

## Giriş ve Kapsam

Bir SOC (Security Operations Center) analistinin günlük iş yükünün önemli bir kısmı, kullanıcıların "phishing" olarak bildirdiği veya otomatik sistemlerin işaretlediği şüpheli e-postaları teknik olarak incelemektir. Bu inceleme, saldırganın niyetini tahmin etmekten çok, e-postanın taşıdığı **doğrulanabilir teknik kanıtları** okumaya dayanır: mesaj nereden geldi, hangi sunuculardan geçti, kimlik doğrulama (authentication) zinciri geçerli mi, gömülü bağlantılar ve ekler ne yapıyor?

Bu makale, phishing saldırısının *nasıl yapıldığını* değil, savunma tarafında bir mesajın *nasıl analiz edileceğini* anlatır. Header/routing analizi, SPF/DKIM/DMARC üçlüsünün mantığı ve atlatılma (bypass) yöntemlerinin tespiti, phishing kit'lerinin yapısı ve e-posta ağ geçidi (secure email gateway) telemetrisini ele alır.

## E-posta Header ve Routing Analizi

### Tanım

Bir e-posta iletisi iki katmandan oluşur: zarf (SMTP envelope) ve mesajın kendisi (header + body). Zarf, sunucular arası iletişimdeki `MAIL FROM` ve `RCPT TO` komutlarıyla taşınan adreslerdir ve alıcı görmez. Mesaj header'ları ise (`From:`, `To:`, `Subject:`, `Received:` vb.) ietide gömülüdür ve analizin ana kaynağıdır.

Kritik ayrım: kullanıcının gördüğü `From:` başlığı (RFC 5322 "header From" veya `From` domain'i) ile zarftaki `MAIL FROM` adresi (RFC 5321 "envelope from" / `return-path` / `MailFrom`) **farklı olabilir**. SPF zarf adresini doğrular, DMARC ise header `From` ile SPF/DKIM arasındaki uyumu (alignment) kontrol eder. Bu ayrımı kavramak, tüm e-posta kimlik doğrulama mantığının temelidir.

### Çalışma Mantığı: Received zinciri

Her SMTP sunucusu mesajı bir sonrakine devrederken en üste bir `Received:` başlığı ekler. Dolayısıyla başlıklar **ters kronolojik** sırayla okunur: en alttaki `Received` mesajın kaynağına en yakın, en üstteki alıcı tarafına en yakındır. Analistin izlediği yol:

1. En alttan başlayarak mesajın gerçek kaynak IP'sini bul. Saldırganlar üstteki `Received` başlıklarını taklit (spoof) edebilir çünkü onları kendileri yazabilir; ama mesaj sizin güvendiğiniz altyapıya girdiği andan itibaren eklenen başlıklar güvenilirdir. Yani **kendi kontrolünüzdeki ilk sunucunun eklediği** `Received` başlığı güven sınırıdır (trust boundary).
2. Kaynak IP'nin PTR (reverse DNS) kaydını, ait olduğu ASN'yi ve coğrafi konumu çıkar.
3. `Received` başlıklarındaki zaman damgalarını incele. Sunucular arası büyük zaman atlamaları veya tutarsız saat dilimleri, relaylenmiş veya enjekte edilmiş mesajlara işaret edebilir.

### Önemli Header Alanları

- **`Return-Path:`** — Genellikle zarf `MAIL FROM` değerini yansıtır; teslim edilemeyen mesajların (bounce) döneceği adres. `From:` ile uyumsuzluğu tek başına kötü niyet göstermez ama SPF alignment için kritiktir.
- **`Message-ID:`** — Genellikle gönderen sunucunun domain'ini içerir. `From` domain'i ile Message-ID domain'inin tutarsızlığı zayıf ama dikkate değer bir sinyaldir.
- **`Authentication-Results:`** — Alıcı tarafın kimlik doğrulama sunucusunun eklediği özet: `spf=pass/fail`, `dkim=pass/fail`, `dmarc=pass/fail`. Bu başlık **yalnızca kendi güvendiğiniz sunucunuz eklediyse** güvenilirdir; body içinde taklit edilmiş bir `Authentication-Results` görebilirsiniz.
- **`Reply-To:`** — Yanıtların gideceği adres. Phishing'de sık sık `From` görünürde meşru bir markayken `Reply-To` saldırganın kontrolündeki bir adrestir.
- **`X-*` başlıkları** — Ağ geçitleri ve istemcilerin eklediği özel başlıklar (`X-Originating-IP`, `X-Mailer`, ağ geçidine özgü tarama skorları). `X-Mailer`, bazen otomatik gönderim araçlarını veya phishing framework'lerini ele verir.

### Yaygın Hata

Analistlerin en sık yaptığı hata, mesajın *herhangi bir* `Received` başlığındaki IP'yi kaynak sanmaktır. Saldırgan kendi ürettiği alt başlıkları istediği gibi yazabilir; sadece güven sınırından itibaren eklenenler kanıt değeri taşır. İkinci yaygın hata, body içine gömülmüş sahte bir `Authentication-Results`'a güvenmektir.

## SPF: Sender Policy Framework

### Tanım ve Çalışma Mantığı

SPF, bir domain sahibinin "benim adıma e-posta göndermeye şu IP adresleri/sunucular yetkilidir" beyanını DNS'te bir `TXT` kaydı olarak yayımlamasıdır. Alıcı sunucu, gelen mesajın **zarf `MAIL FROM` domain'ini** alır, o domain'in SPF kaydını sorgular ve bağlantının geldiği IP'nin izinli olup olmadığını kontrol eder.

Örnek bir SPF kaydı:

```
v=spf1 ip4:192.0.2.0/24 include:_spf.google.com include:sendgrid.net -all
```

- `ip4:` / `ip6:` — doğrudan izinli IP blokları.
- `include:` — başka bir domain'in SPF politikasını dahil eder (bulut e-posta sağlayıcıları için tipik).
- `-all` (hard fail), `~all` (soft fail), `?all` (neutral), `+all` (herkes izinli — tehlikeli). Sondaki mekanizma, listede eşleşme olmadığında ne yapılacağını belirler.

### SPF'in Yapısal Sınırları ve Bypass Tespiti

SPF'in bilinmesi gereken üç zayıflığı, analistin doğru yorum yapması için kritiktir:

1. **SPF zarfı doğrular, kullanıcının gördüğü `From`'u değil.** Saldırgan, kendi kontrolündeki bir domain'i (`MAIL FROM: bounce@saldirgan-altyapisi.com`) SPF-pass yapacak şekilde ayarlayıp, header `From`'a meşru markayı yazabilir. SPF `pass` olur ama gösterilen gönderen sahtedir. Bu yüzden **SPF pass tek başına mesajın güvenilir olduğunu göstermez** — DMARC'ın alignment kontrolü tam da bunun için vardır.

2. **10 DNS-lookup sınırı.** SPF değerlendirmesi, iç içe `include`/`redirect`/`a`/`mx` mekanizmaları nedeniyle 10 DNS sorgusunu aşarsa `permerror` üretir. Kötü yapılandırılmış kayıtlar `permerror`/`none` durumuna düşerek fiilen korumasız kalır. Analist, doğrulama sonucunun `none`, `permerror` veya `softfail` olduğu durumları ayrı ele almalıdır — bunlar `fail` kadar net değildir.

3. **Ortak altyapı (shared infrastructure) sorunu.** Birçok kurum bir bulut e-posta platformunu `include` ettiğinde, o platformdaki *başka* bir müşteri de teknik olarak aynı IP'lerden gönderim yapabildiği için SPF pass alabilir. Bu, SPF'i tek başına marka taklidine karşı zayıf bırakır.

4. **Yönlendirme (forwarding) SPF'i bozar.** Bir mesaj bir aracı sunucudan yönlendirildiğinde (mailing list, "forward" kuralı), gönderen IP değişir ve orijinal domain'in SPF'i artık eşleşmez. Bu, meşru mesajların SPF-fail almasının başlıca sebebidir ve bir analistin SPF-fail'i otomatik olarak "kötü" saymamasının nedenidir. (SRS — Sender Rewriting Scheme — bu sorunu kısmen çözer.)

**Tespit yaklaşımı:** SPF sonucunu izole bir sinyal değil, DMARC alignment bağlamında değerlendirin. `MAIL FROM` domain'i ile header `From` domain'inin farklı organizasyonlara ait olduğu ama SPF'in yine de pass olduğu durum, klasik "SPF uyumsuzluğu (misalignment)" göstergesidir.

## DKIM: DomainKeys Identified Mail

### Tanım ve Çalışma Mantığı

DKIM, giden mesaja gönderen sunucunun **kriptografik bir imza** eklemesidir. Gönderen, mesajın seçilmiş başlıklarını ve gövdesinin bir özetini (hash) alır, özel anahtarıyla imzalar ve `DKIM-Signature:` başlığı olarak ekler. Karşılık gelen açık anahtar (public key), gönderen domain'in DNS'inde bir `TXT` kaydı olarak yayımlanır ve bir "selector" ile adreslenir (`selector._domainkey.domain.com`).

Alıcı, `DKIM-Signature` başlığındaki `d=` (imzalayan domain) ve `s=` (selector) alanlarını okur, DNS'ten açık anahtarı çeker, imzayı doğrular. `pass` sonucu iki şeyi kanıtlar: (a) mesaj `d=` domain'i tarafından yetkilendirilmiş, (b) imzalı alanlar transit sırasında değişmemiş.

`DKIM-Signature` başlığındaki önemli alanlar:

- `d=` — imzalayan domain. DMARC alignment burada `From` domain'iyle karşılaştırılır.
- `s=` — selector.
- `h=` — imzaya dahil edilen başlıkların listesi.
- `bh=` — gövde hash'i; `b=` — imzanın kendisi.
- `l=` — (opsiyonel) imzalanan gövde uzunluğu.

### DKIM Zayıflıkları ve Bypass Tespiti

1. **`l=` (body length) etiketi kötüye kullanımı.** `l=` etiketi gövdenin yalnızca ilk N baytının imzalanmasını sağlar. Saldırgan, imzalı orijinal içeriğin *sonuna* ek zararlı içerik ekleyerek DKIM'i hâlâ `pass` tutabilir. **Tespit:** `DKIM-Signature`'da `l=` etiketinin varlığını bir risk sinyali olarak işaretleyin.

2. **Zayıf anahtar boyutu.** Tarihsel olarak 512-bit ve altındaki RSA anahtarları kırılabilir kabul edilir; günümüzde en az 1024-bit, tercihen 2048-bit beklenir. DNS'te yayımlanan anahtarın uzunluğu incelenebilir bir kontroldür.

3. **DKIM imzasız alanların manipülasyonu.** `h=` listesinde olmayan başlıklar imzaya dahil değildir; saldırgan bu başlıkları (örn. ikinci bir `Subject`) ekleyebilir veya değiştirebilir. Bazı istemciler imzalanmamış tekrar eden başlıkları farklı yorumlar (DKIM `From` başlığını genelde imzalar, ama analist `h=` içeriğini incelemelidir).

4. **"Replay" saldırıları.** Geçerli DKIM imzalı bir mesaj alan saldırgan, aynı imzalı mesajı çok sayıda alıcıya yeniden gönderebilir; imza teknik olarak `pass` verir. Bu, itibar tabanlı filtrelemeyi (reputation) hedefler.

5. **Selector'ın DNS'ten kaldırılması / anahtar sızması.** İmzalayan domain'in özel anahtarı sızarsa, saldırgan o domain adına geçerli imza üretebilir. Bu yüzden anahtar rotasyonu ve eski selector'ların temizlenmesi savunma açısından önemlidir.

**Tespit yaklaşımı:** DKIM `pass` gördüğünüzde `d=` domain'inin *hangi* domain olduğunu daima kontrol edin. Saldırgan kendi domain'iyle geçerli DKIM imzalar (kendi anahtarıyla `pass` alır) ama `d=` header `From`'la hizalı değilse bu bir kırmızı bayraktır — yine alignment'a döneriz.

## DMARC: Politika ve Alignment Katmanı

### Tanım ve Çalışma Mantığı

DMARC (Domain-based Message Authentication, Reporting and Conformance), SPF ve DKIM'in üzerine oturan **politika ve hizalama (alignment)** katmanıdır. İki temel işlevi vardır:

1. **Alignment:** SPF ve/veya DKIM'in doğruladığı domain'in, kullanıcının gördüğü header `From` domain'iyle **eşleşmesini** zorunlu kılar. DMARC "pass" için en az birinin (SPF *veya* DKIM) hem geçerli hem hizalı olması gerekir.
   - **SPF alignment:** `MAIL FROM` domain'i, header `From` domain'iyle eşleşmeli.
   - **DKIM alignment:** DKIM `d=` domain'i, header `From` domain'iyle eşleşmeli.
   - Eşleşme "strict" (tam eşit) veya "relaxed" (organizational domain düzeyinde, alt domain'lere izin verir) olabilir; `aspf=` ve `adkim=` etiketleriyle ayarlanır.

2. **Politika beyanı:** Domain sahibi, DMARC başarısız olduğunda alıcının ne yapmasını istediğini belirtir.

Örnek DMARC kaydı (`_dmarc.domain.com` üzerinde `TXT`):

```
v=DMARC1; p=reject; rua=mailto:raporlar@domain.com; pct=100; aspf=r; adkim=s
```

- `p=none` — sadece izle/raporla, işlem yapma (monitoring modu).
- `p=quarantine` — spam/karantinaya al.
- `p=reject` — tümüyle reddet.
- `rua=` — toplu (aggregate) raporların gönderileceği adres.
- `ruf=` — adli (forensic/failure) raporlar; gizlilik nedeniyle daha az yaygın.
- `pct=` — politikanın uygulanacağı mesaj yüzdesi (kademeli geçiş için).
- `sp=` — alt domainler için ayrı politika.

### DMARC Neden Kritik?

SPF ve DKIM tek başlarına, kullanıcının gördüğü `From` domain'ini *doğrudan* korumaz — ikisi de farklı bir domain'i doğrulayabilir. DMARC, "doğrulanan domain ile gösterilen domain aynı olmalı" kuralını getirerek **doğrudan domain taklidini (exact-domain spoofing)** kapatır. `p=reject` ile yayımlanmış bir domain'i, saldırgan o domain'in *tam adını* kullanarak taklit edemez.

### DMARC'ın Kapatamadığı Boşluklar (Bypass Tespiti)

DMARC güçlü olsa da analist şu kalan saldırı yüzeylerini bilmelidir:

1. **Lookalike / cousin domain'ler.** DMARC yalnızca *tam* domain eşleşmesini korur. `micros0ft.com`, `microsoft-support.com` gibi benzer domain'ler kendi geçerli SPF/DKIM/DMARC kayıtlarıyla `pass` alır — çünkü saldırgan o domain'in gerçek sahibidir. DMARC bunu engellemez; tespit, görsel benzerlik ve yeni kayıt (newly registered domain) analizine düşer.

2. **Display name spoofing.** `From: "Microsoft Güvenlik" <rastgele@saldirgan.com>` biçiminde gösterim adı taklidi. Birçok istemci yalnızca gösterim adını gösterir; domain saldırgana aittir ve DMARC kendi domain'i için pass verir. Tespit, gösterim adı ile gerçek domain arasındaki uyumsuzluğu yakalamaya dayanır.

3. **`p=none` yaygınlığı.** Çok sayıda domain DMARC'ı sadece izleme modunda (`p=none`) yayımlar; bu, taklide karşı fiili koruma sağlamaz, sadece rapor toplar. Analist, gönderen domain'in DMARC politikasının *enforcement* düzeyini (`none` mı `reject` mi) ayırt etmelidir.

4. **Subdomain ve `sp` boşlukları.** Ana domain `reject` olsa da `sp=` tanımlı değilse veya alt domainler yönetilmiyorsa, kullanılmayan alt domainler istismar edilebilir.

5. **Yönlendirme kaynaklı yanlış-fail.** SPF forwarding'de bozulduğu için, DMARC yalnızca SPF'e dayansaydı meşru forward'lar fail alırdı; bu yüzden DKIM alignment'ın hayatta kalması önemlidir. ARC (Authenticated Received Chain), aracı sunucuların orijinal doğrulama sonucunu kriptografik olarak taşımasını sağlayarak bu sorunu hafifletir; `ARC-Seal` ve `ARC-Message-Signature` başlıklarıyla çalışır.

### DMARC Raporlarının Analitik Değeri

`rua` toplu raporları XML formatında gelir ve domain sahibine, *kendi domain'i adına* dünyada kimlerin e-posta gönderdiğini ve bunların ne kadarının doğrulamayı geçtiğini gösterir. Bir savunma ekibi bu raporları kullanarak: meşru üçüncü taraf gönderenleri (SPF/DKIM'e eklenmesi gerekenler) keşfeder, taklit denemelerinin kaynak IP'lerini görür ve `p=none`'dan `reject`'e güvenli geçişi planlar.

## Phishing Kit Analizi

### Tanım

Phishing kit, bir sahte kimlik toplama (credential harvesting) sitesini "kutudan çıkar kur" haline getiren, önceden paketlenmiş dosya setidir: sahte giriş sayfalarının HTML/CSS/JS'i, girilen bilgileri saldırgana ileten sunucu tarafı script'leri (genelde PHP), yapılandırma dosyaları ve sıklıkla e-posta/Telegram üzerinden veri sızdıran kod. SOC ve threat-intel açısından, bir phishing URL'sinin arkasındaki kit'i incelemek; kampanyayı ilişkilendirmeye (attribution), diğer kurbanları bulmaya ve tespit imzası üretmeye yarar.

### Yapısal Bileşenler ve İnceleme Mantığı

Bir kit analiz edilirken şu unsurlara bakılır (statik, izole/sandboxed ortamda):

- **Credential exfiltration mekanizması.** Toplanan verinin nereye gittiği: sabit kodlanmış bir e-posta adresi (`mail()` çağrıları), Telegram bot token'ı, bir "results.txt"/loglama dosyası veya uzak bir C2 endpoint'i. Bu göstergeler, farklı sitelerdeki aynı kiti ilişkilendirmede güçlü IOC'lerdir (Indicator of Compromise).
- **Anti-analiz ve hedefleme.** Kit'ler sık sık güvenlik tarayıcılarını, bilinen bot IP aralıklarını ve belirli ASN'leri (örneğin bulut/tarama sağlayıcıları) engelleyen "blocklist" dosyaları içerir; ayrıca yalnızca belirli ülke/dilden kurbanları hedeflemek için coğrafi filtreleme yapar. Bu dosyaların varlığı kit'i teşhis eder.
- **Marka varlıkları.** Taklit edilen markanın logoları, birebir kopyalanmış CSS'i; bazen doğrudan gerçek siteden çekilen kaynaklar (hotlinking).
- **Kit imzaları.** Birçok kit, yazarının bıraktığı yorum satırları, benzersiz dizin yapıları veya değişken adları taşır; bunlar farklı kampanyaları aynı geliştiriciye bağlamayı sağlar.
- **Açık dizin (open directory) ve `.zip` kalıntısı.** Saldırganlar kit'i sunucuya bir arşiv olarak yükleyip açtıktan sonra arşivi silmeyi unutabilir; erişilebilir bir `kit.zip` tüm kaynak kodu ele verir.

### Tespit ve Savunma

- **URL/domain telemetrisi:** Yeni kayıtlı domain'ler, marka adı + "-login/-secure/-verify" gibi kalıplar, ücretsiz TLS sertifikası anında yayımlanan (Certificate Transparency loglarından izlenebilir) hostlar.
- **İçerik tabanlı imzalar:** Bilinen kit'lerin HTML yapısına, JS fonksiyon adlarına veya benzersiz string'lerine dair YARA benzeri kurallar.
- **Favicon/hash eşleştirme:** Sahte sayfaların favicon veya sayfa hash'i, aynı kiti kullanan diğer siteleri toplu keşfetmeye yarar.
- **Kurumsal savunma:** Kullanıcı tarafında phishing-resistant MFA (FIDO2/WebAuthn) devreye almak, credential toplansa bile oturum ele geçirmeyi büyük ölçüde engeller — çünkü kit çalınan parolayı gerçek siteye giremez.

### Yaygın Hata

Canlı bir phishing kit'ini kendi kurumsal ağınızdan, kimlik gizlemeden ziyaret etmek; hem saldırganın hedefleme/loglama mekanizmasını tetikler hem de sizi filtrelerine göre "gerçek kurban" gibi kaydettirebilir. Analiz izole, atfedilemez altyapıda yapılmalıdır.

## E-posta Ağ Geçidi (Secure Email Gateway) Telemetrisi

### Tanım

Secure Email Gateway (SEG), gelen ve giden e-postayı posta kutusuna ulaşmadan önce inceleyen katmandır: spam/kimlik doğrulama filtreleri, sandbox'lı ek analizi, URL yeniden yazma (rewriting) ve tehdit istihbaratı eşleştirmesi yapar. SOC için SEG, en zengin e-posta telemetrisi kaynağıdır.

### URL ve Ek Yeniden Yazma (Rewriting) Mantığı

Modern SEG'lerin en önemli özelliği, mesajdaki bağlantıları **kendi tıklama-zamanı koruma (time-of-click) proxy'sine** yeniden yazmasıdır. Kullanıcı bir bağlantıya tıkladığında istek önce ağ geçidinin altyapısından geçer; bağlantı o an yeniden değerlendirilir. Bu, gönderim anında temiz görünüp sonradan zararlı hale gelen ("weaponize edilen") URL'leri yakalamayı amaçlar. Analist için bunun anlamı:

- Header/body'de gördüğünüz URL genellikle SEG'in sarmalayıcı (wrapper) domain'idir; **gerçek hedefi çıkarmak için sarmalayıcıyı çözmeniz (decode)** gerekir. Orijinal URL genelde base64/URL-encoded biçimde parametre içinde saklıdır.
- Ekler benzer biçimde sandbox'a alınır; SEG loglarında ekin hash'i, sandbox verdiği hüküm (verdict) ve tetiklenen davranışlar bulunur.

### Analist İçin Kritik SEG Telemetri Alanları

- **Kimlik doğrulama sonuçları:** SEG'in ürettiği SPF/DKIM/DMARC hükümleri (kendi güven sınırınızdan geldiği için güvenilir).
- **Verdict ve neden kodları:** Mesajın neden bloklandığı/geçtiği (spam skoru, tehdit imzası, itibar).
- **Tıklama telemetrisi:** Yeniden yazılmış URL'ye kimin, ne zaman tıkladığı — bir kullanıcının zararlı bağlantıya *tıklayıp tıklamadığını* belirlemek, olay müdahalesinde (incident response) kapsam tespiti için kritiktir.
- **Kampanya kümeleme:** SEG'ler benzer konusu/gönderen/URL'yi paylaşan mesajları kampanya olarak gruplar; bir kullanıcı bildirdiğinde aynı kampanyanın diğer alıcılarını toplu bulup temizlemenizi (retroactive purge / clawback) sağlar.

### Tespit ve Savunma İş Akışı

Tipik bir triage akışı:

1. Kullanıcı bildirimini al; ham mesajı (`.eml` / `.msg`) izole olarak elde et.
2. Header/routing analiziyle gerçek kaynağı ve `Authentication-Results`'ı doğrula.
3. SPF/DKIM/DMARC zincirini, özellikle alignment'ı, misalignment ve `p=none` boşlukları açısından oku.
4. Gömülü URL'leri SEG sarmalayıcısından çöz, gerçek hedefi izole ortamda/URL sandbox'ında değerlendir.
5. IOC'leri (gönderen IP/domain, URL, ek hash) çıkarıp SIEM'de retrospektif arama yap: aynı kampanyaya kimler maruz kaldı, tıklayan/kimlik giren oldu mu?
6. Gerekirse aynı kampanyanın mesajlarını posta kutularından toplu geri çek, IOC'leri engelleme listelerine ekle, etkilenen hesapları (tıklamış/giriş yapmış) parola sıfırlama ve oturum iptaliyle ele al.

### Yaygın Hatalar

- **SEG sarmalayıcı URL'sini gerçek hedef sanmak.** Her zaman çözerek asıl domain'e bakın.
- **Kimlik doğrulama pass'ini "güvenli" ile eşitlemek.** SPF/DKIM/DMARC pass; mesajın *o domain'den yetkiyle geldiğini* söyler, içeriğinin iyi niyetli olduğunu değil. Ele geçirilmiş meşru bir hesaptan (Business Email Compromise) gelen mesaj tüm kontrolleri geçer.
- **Tek sinyale bakmak.** Doğru triage, header tutarlılığı + kimlik doğrulama alignment + URL/ek itibarı + gönderen davranışını birlikte değerlendirir.

## Özet

E-posta güvenlik analizinin özü üç katmanı doğru okumaktır: **routing** (mesaj gerçekten nereden geldi, güven sınırı nerede), **authentication** (SPF zarfı, DKIM imzayı doğrular; DMARC bunları kullanıcının gördüğü `From` ile *hizalar*) ve **içerik/altyapı** (phishing kit yapısı, SEG'in yeniden yazdığı URL'lerin çözülmesi). En kritik kavramsal nokta, kimlik doğrulamanın *doğrulama* olduğunu ama *iyi niyet garantisi olmadığını* kavramaktır: `pass` bir başlangıç filtresidir, sonuç değil. Lookalike domain'ler, display-name spoofing, `p=none` boşlukları ve ele geçirilmiş meşru hesaplar, tüm bu kontrolleri geçebilir — bu yüzden analist, teknik kanıtları bağlam ve davranışla birlikte yorumlamalıdır.
