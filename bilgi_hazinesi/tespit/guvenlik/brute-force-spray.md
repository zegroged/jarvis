# Brute Force / Password Spray — Tespiti

> İlke: "Hırsızı tanımadan mücevheri koruyamazsın." Önce saldırının mantığını anlayacağız, sonra bu mantığın logda bıraktığı izleri gerçek Sigma kurallarına demirleyerek nasıl alarma çevireceğimizi göreceğiz. Amaç savunma ve tespittir; canlı saldırı reçetesi değil.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Brute force ve password spray, aynı ailenin iki ucudur. İkisi de kimlik doğrulama (authentication) mekanizmasının temel bir gerçeğini istismar eder: bir hesaba erişmenin en gürültülü ama en garantili yolu, doğru parolayı **deneme-yanılma** ile bulmaktır. Sistem, "yanlış parola" ile "doğru parola"yı ayırt etmek zorundadır ve bu ayrımı yaptığı her an saldırgana bir bit bilgi sızdırır: "bu değil" ya da "bu doğru".

Klasik **brute force**, tek bir hesabı hedef alıp o hesaba karşı çok sayıda parolayı hızla dener. Kavramsal olarak "dar ve derin" bir saldırıdır: bir kullanıcı adı, binlerce parola denemesi. Bu yaklaşımın zayıflığı, savunmacının en kolay yakaladığı desendir — tek hesapta kısa sürede onlarca/yüzlerce başarısız giriş, account lockout politikalarını da tetikler.

**Password spray** ise bu problemi tersine çevirir. Saldırgan mantığı şudur: "Bir hesaba yüz parola denemek yerine, yüz hesaba bir (zayıf ama olası) parola deneyeyim." `Summer2024!`, `Sirket2024`, `Welcome1`, `Parola123` gibi kurumsal ortamlarda istatistiksel olarak sık kullanılan parolalar, geniş bir kullanıcı listesine karşı yayılır (spray = püskürtme). Böylece:

- Hiçbir tekil hesap, lockout eşiğini (örneğin 5 başarısız deneme) aşacak kadar denenmez. Saldırı, kilitlenmenin **altından** geçer.
- Deneme başına başarı olasılığı düşüktür ama hesap sayısı yüksektir; büyük bir organizasyonda birinin `Welcome1` kullanıyor olması neredeyse kesindir.
- Saldırı "yatay ve sığ"dır: çok kullanıcı, az deneme. Bu, tek hesap odaklı klasik alarmların gözünden kaçar.

Saldırgan, bu teknikleri gerçek dünyada birkaç kavramsal katmanla süsler. **Kaynak dağıtımı**: denemeleri tek IP yerine çok sayıda IP (proxy, VPN, residential botnet) üzerinden yaparak "tek kaynaktan çok hata" desenini bozmaya çalışır. **Zaman yayma (low-and-slow)**: denemeleri saatlere, hatta günlere yayarak eşik tabanlı sayaçların sıfırlanmasını bekler. **Legacy protokol istismarı**: modern MFA'yı devreye sokmayan eski kimlik doğrulama uç noktalarını (legacy authentication) tercih eder, çünkü buralarda bir parola doğruysa MFA sorulmadan oturum açılabilir.

Password spray sadece web/bulut oturum açmayla sınırlı değildir. Aynı deneme-yanılma mantığı ağ altyapısında da görülür: RDP servislerine karşı, hatta yönlendirme protokollerine (BGP, LDP) karşı MD5 authentication anahtarını kırmaya yönelik denemeler de aynı ailedendir. Ortak payda, "kimlik doğrulama başarısızlıklarının anormal yoğunluğu"dur.

Saldırganın kararlarını yönlendiren birkaç kavramsal kısıt vardır ve bunları anlamak, tespiti nereye kuracağımızı belirler. Birincisi **lockout eşiği**: kurum hesap başına kaç başarısız denemeye izin veriyorsa, spray o eşiğin bir altında kalacak şekilde ayarlanır — tipik olarak deneme başına hesap başına bir veya iki parola. İkincisi **parola seçimi**: saldırgan rastgele parola denemez; mevsim+yıl (`Sonbahar2024`), şirket adı türevleri, klavye desenleri (`Qwerty123`) ve sızmış parola listelerinden derlenen "en sık kullanılanlar" gibi insan davranışına dayalı, yüksek isabet olasılıklı adaylar seçer. Üçüncüsü **hedef önceliklendirme**: enumerasyonla (kullanıcı adı sıralama) elde edilmiş geçerli hesap listeleri, özellikle MFA'sı zayıf veya legacy protokole açık olanlar öne alınır.

Özetle saldırganın istismar ettiği şey teknik bir açık değil, bir **istatistiksel gerçeklik ve gürültüde saklanma** stratejisidir: yeterince çok kapı çalarsan biri açıktır ve her kapıya yalnızca bir kez vurursan kimse gürültüyü fark etmez. Savunmanın işi tam da bu gürültüyü — dağıtılmış, seyrek, ama korelasyonu olan bu deseni — toplulaştırıp görünür kılmaktır.

---

## 2. Bıraktığı izler / artefaktlar

Deneme-yanılmanın güzel yanı, gürültülü olmasıdır. Saldırgan ne kadar yaymaya çalışsa da, her deneme bir log satırı üretir. Tespit mühendisinin işi bu satırları doğru kaynaktan toplamaktır.

**Azure AD / Microsoft Entra ID izleri (bulut kimlik):**
- **Sign-in logs (`signinlogs`)**: Her oturum açma denemesi burada `Status` (Success/Failure), `userAgent`, kaynak IP, kullanıcı, uygulama ve conditional access sonucu ile kayıt olur. Password spray'de tipik desen: kısa bir pencerede **çok sayıda farklı kullanıcı**, çok sayıda **failure** ve bunların ardından **tek tük Success**.
- **Risk detection logs (`riskdetection`)**: Microsoft'un kendi Identity Protection motoru, dağıtılmış başarısızlık desenlerini toplulaştırıp `riskEventType: passwordSpray` olarak işaretler. Bu, ham logdan türetilmiş, yüksek değerli bir sinyaldir.
- **Legacy authentication izi**: `userAgent` alanında `BAV2ROPC`, `CBAinPROD`, `CBAinTAR` gibi değerler, modern kimlik doğrulama akışını atlayan eski istemcilere işaret eder. Bir password spray'in MFA'yı atlatarak başarıya ulaştığının güçlü göstergesidir.

**Windows / Active Directory izleri (şirket içi):**
- **Event ID 4625** (An account failed to log on): Başarısız oturum açma. Password spray'de aynı DC üzerinde kısa sürede birçok **farklı** `Target User Name` için 4625 birikir; `Logon Type` (3 = network, 10 = RemoteInteractive/RDP) ve `Status`/`SubStatus` kodları (örn. `0xC000006A` yanlış parola, `0xC0000064` kullanıcı yok) atağın niteliğini gösterir.
- **Event ID 4624** (successful logon) ve **4768/4771** (Kerberos TGT istek/ön kimlik doğrulama başarısızlığı): Başarısızlık denizinin içinde beliren başarı, korele edilmesi gereken kritik andır.
- **Account lockout — Event ID 4740**: Klasik brute force'ta patlar; password spray bunu *bilerek* tetiklemez, dolayısıyla 4740'ın **yokluğu** ama 4625 bolluğu spray'e özgü bir imzadır.

**Ağ / altyapı izleri:**
- **RDP (Zeek `rdp` logu)**: Yönlendirilebilir (routable) veya iç IP aralıklarından RDP dinleyicisine gelen bağlantılar. Kavramsal olarak, internete açık bir RDP servisi brute force için birinci sınıf hedeftir; `id.orig_h` kaynak IP'nin özel/iç aralıkta olup olmaması, servisin maruziyetini gösterir.
- **Cisco BGP logları (`bgp` servisi)**: `:179` portu ve `IP-TCP-3-BADAUTH` gibi anahtar kelimeler, BGP oturumunda MD5 authentication başarısızlığını gösterir — yönlendirmeyi manipüle etmeye yönelik brute force emaresi.
- **Cisco LDP logları (`ldp` servisi)**: `SOCKET_TCP_PACKET_MD5_AUTHEN_FAIL` veya `TCPMD5AuthenFail` anahtar kelimeleri, MPLS label dağıtımında MD5 kimlik doğrulama hatasına işaret eder.

**Komut satırı / araç izleri:** Ortamda kalan araç kalıntıları da artefakttır — password spray araçlarının kullanıcı listesi ve parola sözlüğü dosyaları, PowerShell çağrılarında geniş kullanıcı döngüleri, ya da tek bir kaynak makineden çok sayıda hedefe giden kısa aralıklı authentication istekleri. Bunlar ağ ve endpoint loglarında birlikte değerlendirilir.

Artefaktları okurken dikkat edilmesi gereken bir nüans, **başarısızlık kodlarının anlamıdır**. Windows tarafında 4625 olayının `Status`/`SubStatus` alanları saldırının şeklini ele verir: `0xC000006A` (doğru kullanıcı, yanlış parola) yoğunluğu, saldırganın geçerli kullanıcı adlarını zaten bildiğine — yani hedefli bir spray'e — işaret ederken, `0xC0000064` (kullanıcı yok) yoğunluğu daha çok kör bir kullanıcı-adı enumerasyonuna benzer. `0xC0000234` (hesap kilitli) görülüyorsa spray'in eşiği aşmaya başladığı, klasik brute force'a kaydığı anlaşılır. Bulut tarafında da benzer biçimde, sign-in loglarındaki hata kodları (örneğin conditional access veya MFA gerektiren sonuçlar) başarının neden gelmediğini ya da hangi yoldan geldiğini açıklar.

Bir diğer önemli artefakt **zamansal desendir**: password spray'de başarısızlıklar genellikle düzenli aralıklarla, otomasyon ritmiyle gelir (insan elinin doğal düzensizliği yerine makine düzenliliği). Aynı saniyeye kümelenmiş çok kullanıcılı failure'lar veya sabit periyotlu denemeler, meşru kullanıcı davranışından ayrışan güçlü bir sinyaldir.

Bu artefaktların ortak dili şudur: **başarısızlıkların anormal dağılımı ve yoğunluğu**, ardından **beklenmedik bir başarı**. Tespit mantığı da bu iki olayı yakalamak üzerine kurulur.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Buradaki tespitlerin tümü, göreve eklenen gerçek Sigma kurallarının log kaynaklarına ve alanlarına demirlenmiştir. Uydurma field veya event kullanmıyoruz.

### 3.1 Bulut tarafı: türetilmiş risk sinyaline güven

En temiz sinyal, sağlayıcının kendi topladığı risktir. `Password Spray Activity` kuralı (id `28ecba0a-...`) şunu der:

- **logsource**: `product: azure`, `service: riskdetection`
- **detection**: `riskEventType` alanı `passwordSpray` değerine eşitse alarm.
- **level**: high

Mantık basittir ama güçlüdür: Microsoft'un motoru, ham sign-in gürültüsünü dağıtılmış hesap ve IP korelasyonuyla zaten işlemiş ve "bu bir password spray" demiştir. Bir tespit mühendisi olarak burada eşik ayarlamaya gerek yok; sinyal geldiğinde iş, kuralın da önerdiği gibi bu oturumu **aynı kullanıcının diğer oturumları bağlamında** incelemektir. Yani alarm bir son değil, bir soruşturma başlangıcıdır.

### 3.2 Bulut tarafı: legacy authentication ile MFA bypass

İkinci gerçek kural, `Potential MFA Bypass Using Legacy Client Authentication` (id `53bb4f7f-...`), spray'in *başarıya ulaştığı ve MFA'yı atladığı* anı yakalar:

- **logsource**: `product: azure`, `service: signinlogs`
- **detection**: `Status` alanı `Success` **ve** `userAgent` alanı `BAV2ROPC`, `CBAinPROD` veya `CBAinTAR` değerlerinden birini içeriyorsa.
- **level**: high

Buradaki dâhiyane nokta şudur: legacy authentication (örneğin Basic auth / ROPC akışı) modern conditional access ve MFA'yı devreye sokmaz. Dolayısıyla bir saldırgan spray ile doğru parolayı bulduysa ve legacy uç noktadan **başarılı** giriş yaptıysa, MFA sorulmadan oturum açmış olabilir. Kural, "başarı + legacy user agent" kombinasyonunu tehdit sayar. Tek başına başarısızlık saymaz; tehlikeli olan başarılı ve MFA'sız oturumdur.

### 3.3 Ağ tarafı: internete açık RDP maruziyeti

`Publicly Accessible RDP Service` kuralı (id `1fc0809e-...`), brute force için zemin oluşturan maruziyeti yakalar:

- **logsource**: `product: zeek`, `service: rdp`
- **detection mantığı**: `id.orig_h` (kaynak IP) özel/loopback/link-local aralıklarda (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`, IPv6 `fc00::/7`, `fe80::/10` vb.) **değilse** — yani kaynak internetten routable bir IP ise — alarm (`condition: not selection`).

Mantık: RDP dinleyicisine iç ağ dışından, gerçek internet IP'sinden bağlantı geliyorsa, servis muhtemelen internete açıktır ve brute force'a birebir açık hedeftir. Kural, onaylı istisnalar için yorum satırında bir `approved_rdp` filtresi bırakmıştır; kurumda meşru şekilde açık bir RDP varsa oraya eklenip elenir.

### 3.4 Altyapı tarafı: yönlendirme protokolü kimlik doğrulama hataları

`Cisco BGP Authentication Failures` (id `56fa3cd6-...`) ve `Cisco LDP Authentication Failures` (id `50e606bf-...`) kuralları, brute force mantığını ağ omurgasına taşır:

- BGP: `product: cisco`, `service: bgp`; anahtar kelimeler `:179` ve `IP-TCP-3-BADAUTH` birlikte görülürse alarm. `level: low`.
- LDP: `product: cisco`, `service: ldp`; `selection_protocol` `LDP` **ve** `selection_keywords` (`SOCKET_TCP_PACKET_MD5_AUTHEN_FAIL` veya `TCPMD5AuthenFail`) birlikte görülürse alarm.

Mantık: BGP/LDP oturumları TCP MD5 authentication kullanır. Bu doğrulamanın başarısız olması, ya bir yanlış yapılandırma ya da MD5 anahtarını tahmin etmeye/manipüle etmeye çalışan bir aktördür. Her iki kural da `low` seviyede, çünkü yanlış yapılandırma yaygın bir yanlış pozitiftir; ama tekrarı ve deseni brute force'a işaret edebilir.

### 3.5 Basit Sigma-benzeri tespit mantığı örnekleri

Aşağıdaki iki örnek, yukarıdaki gerçek kuralların log kaynağı ve alanlarına sadık kalarak yazılmıştır; yeni field icat etmez.

**Örnek A — Legacy authentication ile başarılı giriş (MFA bypass şüphesi):**

```yaml
title: Legacy User Agent ile Basarili Oturum (Spray/MFA Bypass Suphesi)
logsource:
    product: azure
    service: signinlogs
detection:
    selection:
        Status: 'Success'
        userAgent|contains:
            - 'BAV2ROPC'
            - 'CBAinPROD'
            - 'CBAinTAR'
    condition: selection
level: high
```

Bu, `53bb4f7f-...` kuralının mantığını birebir taşır: başarı + legacy user agent = incelenecek oturum.

**Örnek B — RDP maruziyeti üstüne bina edilmiş bir hipotez:**

```yaml
title: Internetten Gelen RDP Baglantisi (Brute Force Zemini)
logsource:
    product: zeek
    service: rdp
detection:
    internal_src:
        id.orig_h|cidr:
            - '10.0.0.0/8'
            - '172.16.0.0/12'
            - '192.168.0.0/16'
            - '127.0.0.0/8'
            - '169.254.0.0/16'
    condition: not internal_src
```

`1fc0809e-...` ile aynı mantık: kaynak iç aralıkta değilse RDP internete açıktır ve brute force denemelerinin geleceği kapıdır. Bu tespiti, aynı kaynak IP'den kısa sürede tekrar eden RDP bağlantılarıyla zenginleştirmek, maruziyeti aktif saldırıya dönüştürecek erken uyarıyı verir.

### 3.6 Genel tespit felsefesi

Bu kuralları birlikte okuduğumuzda ortaya çıkan tespit stratejisi katmanlıdır:
1. **Türetilmiş sinyale güven** (riskdetection / passwordSpray) — sağlayıcı zaten korele etti.
2. **Başarı + zayıf yol** (signinlogs Success + legacy user agent) — atağın kazandığı anı yakala.
3. **Maruziyeti yakala** (Zeek RDP) — saldırının zeminini kapat.
4. **Omurgayı izle** (Cisco BGP/LDP auth fail) — altyapı düzeyi brute force'u kaçırma.

Eşiklerin (kaç deneme = alarm) tam değeri kuruma göre ayarlanır, ama yön hep aynıdır: seyrek dağıtılmış başarısızlıkları toplulaştır, arasından beliren başarıyı öne çıkar.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan bu tespiti nasıl atlatmaya çalışır?

**1. Kaynak IP dağıtımı.** Tek IP'den çok hata deseni, kaynak-tabanlı sayaçları tetikler. Saldırgan denemeleri residential proxy'lere, VPN'lere ve botnet'lere yayarak "her IP birkaç deneme" haline getirir. **Karşı-tespit**: Kaynak IP yerine **hedef hesap kümesine** ve **kullanıcı çeşitliliğine** odaklanın. `riskdetection`/`passwordSpray` sinyali tam da IP dağıtımına dayanıklı olacak şekilde, hesap düzleminde korelasyon yapar. Sign-in loglarında "kısa pencerede N farklı kullanıcıya failure, sonra M başarı" deseni IP'den bağımsızdır.

**2. Low-and-slow (zaman yayma).** Denemeleri saatlere/günlere yayarak pencere-tabanlı eşiklerin sıfırlanmasını beklerler. **Karşı-tespit**: Pencereyi genişletin ve kayan (rolling) sayaçlar kullanın; günlük/haftalık taban çizgisi (baseline) çıkarıp sapmaları izleyin. Tek bir başarılı legacy-auth girişi bile (Örnek A) zamandan bağımsız yakalanır — yavaşlık, başarı anını gizlemez.

**3. Legacy protokolü tercih.** MFA'yı devreye sokmayan uç noktalardan giderek başarılı girişi "sessiz" yapmaya çalışırlar. **Karşı-tespit**: `53bb4f7f-...` kuralı zaten bu davranışı hedefler. Stratejik savunma ise legacy authentication'ı mümkün olan her yerde **tamamen kapatmaktır** — atlatılacak yol ortadan kalkınca tespit yükü de azalır.

**4. Gürültünün içine gömülme.** Denemeleri normal iş saatlerine ve meşru user agent'lara yaymaya çalışırlar. **Karşı-tespit**: Başarı/başarısızlık oranını ve hesap-çeşitliliğini korelasyon anahtarı yapın; tek bir alarm yerine katmanlı sinyalleri (risk + legacy success + kaynak maruziyeti) birleştirin.

### Tipik false positive kaynakları ve nasıl ayıklanır

Kuralların kendi `falsepositives` notları bize yol gösterir:

- **Bilinen legacy hesaplar** (`53bb4f7f-...`): Bazı eski uygulama servis hesapları meşru olarak `BAV2ROPC` benzeri legacy istemci kullanır. **Ayıklama**: Bu hesapları bir izin listesine (allowlist) alın, ama düzenli gözden geçirin ve mümkünse modern kimlik doğrulamaya taşıyın. Allowlist bir "unut-git" değil, bir teknik borç kaydıdır.

- **Kullanıcının kendi meşru oturumları** (`28ecba0a-...`): Risk sinyali bazen kullanıcının seyahat, yeni cihaz, VPN gibi meşru koşullarında tetiklenebilir. **Ayıklama**: Kuralın önerdiği gibi, alarmı **aynı kullanıcının diğer sign-in'leri bağlamında** değerlendirin — tutarlı bir kullanıcı, cihaz ve konum geçmişi false positive lehine kanıttır.

- **Onaylı/meşru açık RDP** (`1fc0809e-...`): Kimi kurumlarda belirli sunucular kasıtlı ve onaylı biçimde RDP'ye açık olabilir. **Ayıklama**: Kuralın bıraktığı `approved_rdp` filtresine bu hedef IP'leri ekleyin; böylece meşru maruziyet elenirken bilinmeyen açık RDP'ler alarm üretmeye devam eder.

- **Yanlış yapılandırma kaynaklı BGP/LDP hataları** (`56fa3cd6-...`, `50e606bf-...`): Bu kuralların `falsepositives` notu açıkça "misconfigurations" der ve seviyeleri bu yüzden `low`'dur. Yeni bir peering, anahtar rotasyonu ya da hatalı MD5 anahtarı bu alarmları tetikler. **Ayıklama**: Değişiklik yönetimi (change management) kayıtlarıyla korele edin; planlı bir bakım penceresine denk gelen tekil hatalar gürültüdür, tekrar eden ve plan dışı olanlar incelenmelidir.

### Savunmacının bütünsel duruşu

False positive ile gerçek tehdidi ayırt etmenin anahtarı **korelasyon ve bağlam**tır. Tek bir başarısız giriş bir şey söylemez; dağıtılmış başarısızlıkların ardından beliren, üstelik legacy yoldan gelen bir başarı çok şey söyler. Tespit mühendisi olarak stratejiniz üç ayak üzerine oturur: (1) sağlayıcının türettiği yüksek değerli sinyalleri (passwordSpray riski) tüketmek, (2) atağın kazandığı anı yakalayan kuralları (legacy + Success) öncelemek, ve (3) saldırının zeminini (açık RDP, savunmasız protokol auth) daraltarak deneme yüzeyini baştan küçültmek.

Sonuçta brute force ve password spray'e karşı en iyi savunma, tespiti güçlendirmenin yanında **atlatılacak yolları kapatmaktır**: legacy authentication'ı devre dışı bırakmak, RDP'yi internete kapatıp VPN/bastion arkasına almak, MFA'yı zorunlu kılmak ve zayıf parolaları politika ile engellemek. Hırsızı tanıdıktan sonra iş, hem alarmı kurmak hem de kırılacak kilidi baştan sağlamlaştırmaktır.
