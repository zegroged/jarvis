# Web Cache Poisoning ve Web Cache Deception

## Tanım

**Web Cache Poisoning** (web önbelleği zehirlenmesi), bir saldırganın bir web önbelleğini (cache) kandırarak zararlı bir yanıt kaydetmesini ve bu zararlı yanıtın daha sonra başka kullanıcılara sunulmasını sağladığı bir saldırı sınıfıdır. Saldırgan bir kez zararlı yanıtı önbelleğe "enjekte" eder; ondan sonra o önbellek anahtarına (cache key) denk gelen her masum ziyaretçi, kendi hiçbir şey yapmasına gerek kalmadan zehirlenmiş içeriği alır. Bu yönüyle saldırı, tekil bir kurbana yönelik bir reflected XSS'i, geniş bir kitleye yayılan bir stored/persistent saldırıya dönüştürür. James Kettle'ın deyimiyle önbellek, "gizli bir saldırıyı bir megafona çevirir".

**Web Cache Deception** (web önbelleği aldatması) ise ters yönlü bir problemdir. Burada saldırgan zararlı içerik enjekte etmez; bunun yerine önbelleği kandırarak, aslında **kişiye özel ve gizli** olan dinamik bir yanıtı (örneğin kurbanın hesap sayfası, API anahtarı, oturum bilgileri) statik bir dosya sanıp önbelleğe kaydetmesini sağlar. Sonra saldırgan aynı URL'yi kendisi isteyerek önbellekten kurbanın gizli verisini çeker. Poisoning "herkese zararlı içerik dağıtma", deception ise "başkasının gizli verisini çalma" saldırısıdır.

İki saldırı da aynı temel kusurdan doğar: **önbelleğin bir isteği tanımlama biçimi (cache key) ile origin server'ın o isteği işleme biçimi arasındaki tutarsızlık.** Bu makalenin çekirdeği budur.

## Kök Neden: Cache Key ve Unkeyed Input Kavramı

Bir web önbelleğinin tek işi vardır: gelen bir isteğe karşılık daha önce hesaplanmış bir yanıtı diskten/bellekten hızlıca döndürmek, böylece origin server'ı yükten kurtarmak. Peki önbellek, "bu istek daha önce gördüğüm istekle aynı mı?" sorusunu neye göre yanıtlar? İşte cevap **cache key**'dir.

Cache key, isteğin belirli bileşenlerinden türetilen bir kimliktir. Tipik bir önbellek varsayılan olarak yalnızca şu iki şeye bakar: **HTTP metodu** ve **istenen URL** (bazı yapılandırmalarda `Host` başlığı ve birkaç seçili başlık da dahil edilir). Önbellek iki isteğin cache key'i aynıysa, ikisini "eşdeğer" kabul eder ve ikincisine birinci için kaydettiği yanıtı verir.

Buradaki kritik nokta şudur: **HTTP isteğinin cache key'e dahil edilmeyen her bileşeni, bir "unkeyed input"tur.** Yani `User-Agent`, `X-Forwarded-Host`, `X-Forwarded-Scheme`, çoğu özel başlık, bazen belirli çerezler ve hatta bazı query parametreleri, önbellek tarafından "aynılık" kararında dikkate alınmaz.

Şimdi zafiyetin doğduğu çelişkiyi görelim. Bir input aynı anda iki koşulu sağlıyorsa tehlikelidir:

1. Önbellek onu **unkeyed** kabul ediyor (yani cache key'e katmıyor, "önemsiz" sayıyor).
2. Origin server ise onu **yanıtı üretirken kullanıyor** (yani yanıtın içeriğini değiştiriyor).

Bu iki koşul birleştiğinde ortaya "gölge" bir kontrol yüzeyi çıkar: Saldırgan, önbelleğin görmezden geldiği ama sunucunun ciddiye aldığı bir girdiyi manipüle ederek, tüm bir cache key'e kaydedilecek yanıtı zehirleyebilir. Önbellek "aynı URL, aynı yanıt" varsayarken, aslında yanıt saldırganın gizli girdisiyle şekillenmiştir.

Kök nedeni tek cümlede özetlemek gerekirse: **Zafiyet, önbelleğin bir isteği ne kadar "kabaca" özdeşleştirdiği ile sunucunun aynı isteği ne kadar "ince ayrıntısıyla" işlediği arasındaki uyumsuzluktan doğar.** Poisoning'de bu uyumsuzluk başlıklar/parametreler düzeyindedir; deception'da ise URL yolunun (path) yorumlanması düzeyindedir.

## Web Cache Poisoning: Çalışma Mantığı ve Somut Örnek

### Klasik senaryo: unkeyed başlık ile URL enjeksiyonu

Birçok uygulama, yanıt içinde mutlak (absolute) URL'ler üretmek için `Host` veya `X-Forwarded-Host` başlığını kullanır. Örneğin canonical link üretmek, bir JavaScript dosyasını yüklemek, bir redirect hedefi kurmak ya da `<meta>` etiketi oluşturmak için.

Diyelim ki `https://ornek-site.com/` sayfası, aşağıdaki gibi bir script etiketi üretiyor ve bu URL'yi `X-Forwarded-Host` başlığından alıyor:

```
<script src="https://ornek-site.com/resources/analytics.js"></script>
```

Origin server bu başlığı body'e yansıtırken, önbellek `X-Forwarded-Host`'u cache key'e katmıyor. Saldırgan şu isteği gönderir:

```
GET / HTTP/1.1
Host: ornek-site.com
X-Forwarded-Host: saldirgan-alan-adi.com
```

Origin bu isteği işler ve yanıtın içine şunu koyar:

```
<script src="https://saldirgan-alan-adi.com/resources/analytics.js"></script>
```

Önbellek, cache key'i sadece `GET /` olarak gördüğü için bu zehirli yanıtı `/` yoluna kaydeder. Bundan sonra `/` sayfasını isteyen **her masum ziyaretçi**, saldırganın kontrolündeki sunucudan JavaScript yükler. Saldırgan `saldirgan-alan-adi.com/resources/analytics.js` altına zararlı bir script koyarak fiilen tüm ziyaretçilerde XSS elde eder. Bu, tekil bir reflected XSS'in kitlesel bir silaha dönüşmüş halidir.

### Neden bulmak zordur ve nasıl bulunur

Bu tür unkeyed input'ları elle bulmak zahmetlidir çünkü hangi başlığın hem unkeyed hem de yanıtı etkilediğini bilmek gerekir. Bu yüzden araştırma pratikte otomasyonla yapılır: James Kettle'ın geliştirdiği **Param Miner** Burp uzantısı, geniş bir başlık/parametre/çerez sözlüğünü tek tek deneyerek her birinin yanıtı değiştirip değiştirmediğini gözlemler. Buradaki püf nokta, testi yaparken **önbelleği zehirlememek** için genellikle her isteğe eşsiz bir cache-buster parametresi (örneğin `?cb=rastgele-deger`) eklenmesidir; böylece test edilen istek kendine ait ayrı bir cache key'e düşer ve gerçek kullanıcıların önbelleği kirlenmez.

Zafiyeti doğrulamanın klasik iki adımlı yöntemi: (1) Şüpheli girdiyi gönder, yanıtta yansıdığını gör. (2) Girdiyi göndermeden aynı URL'yi tekrar iste; eğer zehirli yanıt hâlâ dönüyorsa, önbellek onu kaydetmiş demektir. Yanıttaki `X-Cache: hit` / `X-Cache: miss`, `Age`, `CF-Cache-Status` gibi başlıklar, isteğin önbellekten mi yoksa origin'den mi geldiğini anlamak için değerli sinyallerdir.

### Diğer poisoning yüzeyleri

- **Unkeyed query parametreleri:** Bazı önbellekler cache key'i oluştururken query string'i tümüyle yok sayar veya belirli parametreleri "önemsiz" sayıp atar. Origin bu parametreyi yanıta yansıtıyorsa, aynı çelişki oluşur.
- **Unkeyed çerezler:** Çerezler çoğu önbellekte varsayılan olarak unkeyed'dir ama uygulama bunları yanıta yansıtabilir.
- **Fat GET / parametre kirliliği (parameter cloaking):** Önbellek ile origin'in aynı parametreyi farklı önceliklendirmesi ya da GET body'sini farklı yorumlaması, cache key ile işlenen değeri ayrıştırabilir.
- **Cache key normalizasyon farkları:** Önbellek URL'yi cache key üretirken normalize ederken (büyük/küçük harf, URL-encode çözme, path segment sadeleştirme), origin farklı normalize ederse, saldırgan görünürde farklı ama önbellek gözünde aynı olan bir istekle mağdurun anahtarını zehirleyebilir. Bu, "cache key entanglement" olarak adlandırılan daha ileri bir sınıftır.
- **Zincirleme (chaining):** Tek başına zararsız görünen bir unkeyed girdi, açık redirect, DoS (zararlı yanıtı önbelleğe kaydedip sayfayı fiilen erişilemez kılma) veya başlık yansıması yoluyla ciddi etkilere zincirlenebilir. Örneğin bir zararlı yanıtı 400/500 durum koduyla önbelleğe kaydetmek, "cache poisoning DoS" saldırısına dönüşebilir.

## Web Cache Deception: Çalışma Mantığı ve Somut Örnek

### Temel mekanizma: path confusion

Deception'ın kalbinde şu iki farklı görevin **farklı bileşenlerce** yapılması yatar:

- **Cache key**, yanıtın önbellekte hangi kimlikle saklanacağına karar verir.
- **Origin path**, isteği hangi uygulama handler'ının (endpoint) işleyeceğine karar verir.

Origin server, bir URL'yi işlerken onu kendi kurallarına göre parse eder: bazı karakterleri delimiter (ayraç) sayar, dot-segment'leri (`/../`, `/./`) çözer, encode edilmiş karakterleri decode eder. Önbellek ise çoğu zaman yalnızca **dosya uzantısına** ve statik dizin kurallarına bakarak "bu bir statik dosya, önbelleğe alabilirim" kararı verir. İşte bu iki parser'ın anlaşmazlığı saldırganın manevra alanıdır.

### Klasik örnek: sahte statik uzantı

Kurbanın gizli hesap sayfası `https://ornek-site.com/hesabim` olsun. Bu sayfa dinamiktir, oturuma özeldir ve normalde önbelleğe **alınmamalıdır**.

Saldırgan kurbanı şu URL'ye tıklatır:

```
https://ornek-site.com/hesabim/nonexistent.css
```

Şimdi iki parser'ın nasıl ayrıştığını görelim:

- **Origin server**, birçok framework'te URL'yi `/hesabim` endpoint'ine yönlendirir ve sondaki `/nonexistent.css` kısmını path parameter, PATH_INFO ya da anlamsız artık olarak yutup **yine de kurbanın gerçek hesap sayfasını döndürür** (200 OK).
- **Önbellek**, aynı URL'nin sonunda `.css` gördüğü için "bu statik bir stil dosyası, güvenle önbelleğe alınır" der ve **kurbanın kişisel hesap sayfasını** `/hesabim/nonexistent.css` cache key'iyle kaydeder.

Kurban linke tıkladığı anda, kendi gizli verisi bu sahte statik URL altında önbelleğe düşer. Saldırgan sonra aynı URL'yi kendi tarayıcısından (oturumsuz) ister ve önbellekten kurbanın verisini çeker. Kurbanın oturum çerezi olmadan bile içerik gelir, çünkü içerik artık origin'den değil önbellekten gelmektedir.

### Delimiter tutarsızlıkları ve normalizasyon istismarı

Deception yalnızca uzantı ekleme ile sınırlı değildir. Saldırganlar, önbellek ile origin'in **delimiter** karakterlerini farklı yorumlamasını kullanır. URL RFC'si bazı karakterleri ayraç olarak tanımlar (`;`, `?` gibi) ama spesifikasyon oldukça esnektir ve her uygulamanın kendi ek ayraçlarını tanımlamasına izin verir. Örneğin:

- **Origin'de** `;` bir ayraç olabilir: `/hesabim;foo.css` origin tarafında `/hesabim` olarak işlenir.
- **Önbellekte** ise `;` sıradan bir karakter sayılabilir, dolayısıyla önbellek tüm string'i `.css` ile biten statik bir yol sanar.

Benzer şekilde, **origin server normalization** ile oynanabilir: `/hesabim/%2e%2e/statik/dosya.css` gibi encode edilmiş dot-segment'ler, önbellek ve origin tarafından farklı çözülürse, cache key'de statik görünen ama origin'de dinamik endpoint'e giden bir yol elde edilir. Bunun ters yönü de mümkündür — **cache server normalization** istismarında önbellek yolu sadeleştirirken origin sadeleştirmez ve fark yine saldırganın lehine açılır.

Kısaca deception, "bir tarafın statik, diğer tarafın dinamik gördüğü aynı URL"yi bulma sanatıdır. Poisoning'de saldırgan **içerik** enjekte eder; deception'da saldırgan **sınıflandırma hatası** enjekte eder.

## Savunma: Hem Poisoning Hem Deception İçin

Savunmanın temel felsefesi tek cümlede toplanır: **Önbelleğin bir isteği tanımlama biçimi ile sunucunun aynı isteği işleme biçimi arasındaki her açığı kapat.** Uyumsuzluğu ortadan kaldırırsan, saldırının dayandığı çelişki de kaybolur.

### 1. Dinamik yanıtları asla önbelleğe aldırma

En sağlam ve en genel savunma budur. Kişiye özel, oturuma bağlı veya hassas her yanıt açıkça "önbelleklenemez" işaretlenmelidir:

```
Cache-Control: no-store, private
```

`no-store` önbelleğe "bu yanıtı hiçbir koşulda saklama" der; `private` ise paylaşımlı önbelleklerin (CDN, proxy) saklamasını engeller. Bu, özellikle deception'a karşı en etkili kalkandır: hesap sayfası hiçbir zaman önbelleğe girmezse, `.css` hilesi de anlamsız kalır.

**Kritik uyarı:** Birçok CDN'de, statik dosya uzantısına dayalı cache kuralları, origin'in gönderdiği `Cache-Control` başlığını **ezebilir** (override). Yani origin `no-store` dese bile, CDN "`.css` uzantılı her şeyi önbelleğe al" kuralı yüzünden yine de saklayabilir. Bu yüzden CDN yapılandırmasında origin başlıklarına saygı gösterildiğinden emin olmak ve cache kurallarının `Cache-Control`'ün önüne geçmemesini sağlamak şarttır. Bu ayar yapılamıyorsa, ilgili cache kuralları kapatılmalı ya da URL'yi origin'den farklı parse eden framework/CDN kombinasyonundan kaçınılmalıdır.

### 2. Cache key'i eksiksiz ve tutarlı yap

Poisoning'in kökü, yanıtı etkileyen bir girdinin cache key dışında kalmasıdır. Çözüm: **Yanıtı etkileyen her girdiyi ya cache key'e dahil et, ya da o girdiyi tümden yok say.** İkisinin ortası (unkeyed ama yansıtılan) tehlikeli bölgedir.

- Origin, `Host`/`X-Forwarded-Host` gibi başlıkları yanıt üretiminde kullanıyorsa, ya bu başlıklar cache key'e katılmalı (`Vary` başlığı ya da CDN'de custom cache key), ya da uygulama mutlak URL üretmeyi bırakıp göreli (relative) URL'lere geçmelidir. Göreli URL kullanımı bu sınıfı tümüyle kapatır çünkü yansıtacak bir host kalmaz.
- Uygulamanın gerçekte ihtiyaç duymadığı `X-Forwarded-Host`, `X-Forwarded-Scheme`, `X-Original-URL` gibi başlıklar reverse proxy katmanında **temizlenmeli** (strip edilmeli). Kullanılmayan bir girdi, hiç ulaşamayacağı için zehirlenemez.

### 3. Cache key normalizasyonunu güvenli yönet

Deception'a karşı önemli bir ilke: **Bir cache delimiter'dan sonraki eki (suffix) origin'e olduğu gibi iletme ve cache key'in gereksiz normalizasyonundan kaçın.** İdeal olan, önbellek ile origin'in **aynı** URL parse mantığını kullanmasıdır. Aynı normalizasyon kurallarını paylaşan bir cache/origin çiftinde, "bir taraf statik görür diğeri dinamik" durumu oluşamaz.

Pratikte:
- Statik içerik ile dinamik içeriği **farklı, ayrık yol alanlarına** (path space) koy. Statik dosyalar yalnızca `/static/...` altında yaşasın; uygulama endpoint'leri asla o dizin altında olmasın. Önbellek yalnızca `/static/` önekini önbelleklesin, uzantıya değil.
- Önbelleği "sadece izin verilenler" (allowlist) mantığıyla kur: uzantıya bakıp "her `.css`'i önbelleğe al" yerine, açıkça belirlenmiş statik yolları önbelleğe al.

### 4. Sunucu tarafında yanıt kodu ve içerik doğrulama

Origin, var olmayan bir statik dosya isteğine (`/hesabim/nonexistent.css`) hesap sayfasını 200 ile döndürmek yerine, gerçekten var olmayan bir kaynak için **404** dönmelidir. Endpoint'ler, kendilerine eklenmiş anlamsız path uzantılarını sessizce yutmak yerine reddedecek şekilde katı (strict) route eşleştirmesi yapmalıdır. Bu, deception'ın "origin yine de gizli sayfayı döndürüyor" ön koşulunu ortadan kaldırır.

## Yaygın Hatalar

- **"CDN'im var, güvendeyim" yanılgısı.** CDN'ler saldırıyı bitirmez; aksine geniş kitleye dağıtım gücü verdikleri için poisoning'in **etkisini** artırırlar. Yanlış yapılandırılmış bir CDN, saldırının hem yüzeyi hem de megafonu olur.
- **`Cache-Control` başlığını gönderip yeterli sanmak.** Origin'in `no-store` göndermesi, CDN uzantı-tabanlı kuralları onu ezerse hiçbir işe yaramaz. Başlığın gerçekten önbellek katmanınca **onurlandırıldığı** uçtan uca test edilmelidir.
- **Cache key'i test etmeden varsaymak.** Hangi başlık/parametrenin keyed, hangisinin unkeyed olduğunu belgeye güvenerek varsaymak hatalıdır; her katman (CDN, reverse proxy, uygulama önbelleği) farklı davranabilir. Fiili davranış, cache-buster'lı testlerle ölçülmelidir.
- **Uzantıya güvenip URL'yi statik saymak.** `.css`, `.js`, `.jpg` ile biten her şeyi kör biçimde statik kabul edip önbelleğe almak, deception'ın tam da beslendiği hatadır.
- **Kullanılmayan başlıkları temizlememek.** `X-Forwarded-Host` gibi başlıklara uygulama "ihtiyaç duymuyorum" dese bile, bir framework ya da kütüphane bunları sessizce kullanıyor olabilir. Strip edilmeyen her başlık potansiyel bir unkeyed giriş kapısıdır.
- **Zararlı yanıtı önbellekten temizlememek.** Bir poisoning tespit edilince kök nedeni düzeltmek yetmez; halihazırda zehirlenmiş cache girdileri (özellikle CDN edge'lerinde) aktif olarak purge/invalidate edilmelidir; aksi halde saldırı düzeltmeden sonra bir süre daha canlı kalır.
- **Test ederken üretim önbelleğini kirletmek.** Cache-buster kullanmadan yapılan zafiyet testleri, gerçek kullanıcılara zehirli içerik servis edilmesine yol açabilir; sorumlu test bunu her zaman izole eder.

## En İyi Pratikler

1. **Göreli URL'leri tercih et.** Yanıt gövdesinde mutlak URL üretmek zorunda değilsen üretme. Host/scheme'e dayanan mutlak URL üretimi, poisoning'in en verimli girişidir; göreli URL'ler bu kapıyı tamamen kapatır.
2. **Statik ve dinamik içeriği fiziksel olarak ayır.** Ayrık yol alanları ve allowlist tabanlı önbellekleme, hem poisoning hem deception yüzeyini büyük ölçüde kaldırır.
3. **Hassas her yanıta `Cache-Control: no-store, private` uygula** ve bu başlığın CDN katmanınca ezilmediğini uçtan uca doğrula.
4. **Reverse proxy'de bilinmeyen ve kullanılmayan başlıkları temizle.** Uygulamaya yalnızca ihtiyaç duyulan, keyed ve doğrulanmış başlıklar ulaşsın.
5. **Önbellek ile origin arasında URL parse ve normalizasyon mantığını hizala.** İki taraf aynı kuralları paylaştığında path confusion mantıksal olarak imkânsız hale gelir.
6. **Cache key'i bilinçli tasarla.** Yanıtı etkileyen her girdi ya keyed olsun ya da hiç iletilmesin; "unkeyed ama yansıtılan" gri bölgeyi ortadan kaldır.
7. **Sürekli tara ve izle.** Param Miner benzeri araçlarla düzenli olarak unkeyed input araması yap; `X-Cache`, `Age`, `CF-Cache-Status` gibi başlıkları izleyerek beklenmedik cache davranışlarını yakala. Yeni bir CDN, yeni bir başlık ya da yeni bir route eklendiğinde önbellek davranışını yeniden test et.
8. **Olay müdahalesinde purge'ü unutma.** Bir zehirlenme tespit edilirse, kod düzeltmesiyle eşzamanlı olarak etkilenen cache girdilerini tüm edge katmanlarında geçersiz kıl.

Sonuç olarak Web Cache Poisoning ve Web Cache Deception, egzotik birer "kelebek etkisi" zafiyeti değil; ölçeklenme uğruna araya konan önbellek katmanının, origin ile aynı gerçekliği paylaşmamasının doğal sonucudur. Savunma da tek bir sihirli başlıkta değil, **"önbelleğin gördüğü istek ile sunucunun işlediği istek birebir aynı olsun"** disiplinini mimarinin her katmanına yaymakta yatar.
