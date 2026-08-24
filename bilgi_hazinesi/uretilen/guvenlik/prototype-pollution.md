# Prototype Pollution (Prototip Kirlenmesi)

## Tanım

Prototype Pollution, JavaScript'in prototip tabanlı nesne modelindeki bir tasarım gerçeğinin kötüye kullanıldığı bir güvenlik açığı sınıfıdır. Saldırgan, uygulamanın beklemediği bir noktada `Object.prototype` nesnesine (yani tüm sıradan nesnelerin ortak atası olan prototipe) bir özellik ekleyebilir ya da var olan bir özelliği değiştirebilirse, bu değişiklik o çalışma ortamındaki **tüm** nesnelere yansır. Çünkü JavaScript'te bir nesnenin kendisinde bulunmayan bir özelliğe eriştiğinizde, motor prototip zinciri (prototype chain) boyunca yukarı doğru arama yapar ve `Object.prototype` üzerindeki değeri bulup kullanır.

Sonuç olarak tek bir yazma işlemi, uygulamanın her yerinde "her nesnede varmış gibi görünen" küresel (global) bir yan etki yaratır. Bu, klasik bellek bozma (memory corruption) açıklarından farklıdır: burada bellek taşması yoktur, mantık katmanı kirlenir. Etkisi denial of service'ten yetki yükseltmeye (privilege escalation), sunucu tarafında ise uzaktan kod çalıştırmaya (remote code execution, RCE) kadar gidebilir. Bu yüzden görünüşte "sadece bir özellik atama" olan bir işlem, gerçekte kritik seviyeli bir zafiyete dönüşür.

## Kök Neden: Prototip Zinciri Neden Böyle Çalışır

Prototype Pollution'ı gerçekten anlamak için önce JavaScript'in nesne modelinin nasıl çalıştığını ve bu açığın neden bir "hata" değil, meşru dil davranışının istismarı olduğunu görmek gerekir.

JavaScript'te neredeyse her nesnenin gizli bir bağlantısı vardır: `[[Prototype]]`. Bu bağlantıya kod içinden `__proto__` erişimcisiyle veya `Object.getPrototypeOf()` ile ulaşılır. Sıradan bir nesne oluşturduğunuzda (`const o = {}`), bu nesnenin prototipi otomatik olarak `Object.prototype` olur. Bir özelliğe eriştiğinizde arama şöyle işler:

1. Önce nesnenin **kendi** özelliklerine (own properties) bakılır.
2. Bulunamazsa `[[Prototype]]` üzerinden bir üst nesneye geçilir.
3. Bu zincir `Object.prototype`'a, oradan da `null`'a kadar sürer.

Kritik nokta şudur: `Object.prototype` tek bir paylaşılan nesnedir. Bir çalışma ortamındaki (realm) tüm sıradan nesneler, sözlükler, hatta çoğu framework nesnesi aynı `Object.prototype`'ı üst ata olarak paylaşır. Dolayısıyla `Object.prototype.isAdmin = true` gibi bir yazma, o andan itibaren `({}).isAdmin` ifadesinin `true` dönmesine yol açar; çünkü boş nesnenin kendisinde `isAdmin` yoktur, motor onu prototip zincirinde bulur.

Peki saldırgan bu paylaşılan nesneye nasıl yazabilir? İşte kök neden burada. `__proto__` özel bir erişimcidir (getter/setter): bir nesnede `obj.__proto__` üzerinden yazma yaptığınızda aslında o nesnenin özelliğini değil, prototipini değiştirirsiniz. Benzer şekilde `obj.constructor.prototype` de `Object.prototype`'a ulaşan bir yoldur. Zafiyetin özü, uygulamanın **kullanıcıdan gelen anahtar isimlerini (property key)** güvenilir kabul edip nesnelere yazmasıdır. Eğer saldırgan anahtar olarak `__proto__`, `constructor` veya `prototype` gibi değerleri geçirebilirse, hedef nesnenin kendi özelliğini değil, prototip zincirinin üst katmanlarını kirletir.

Bu neden bu kadar yaygın? Çünkü modern JavaScript kodu sürekli olarak "dinamik anahtarlı yazma" yapar: derin nesne birleştirme (deep merge), klonlama, iç içe yapıyı düzleştirme/geri kurma, query string ayrıştırma, JSON'dan gelen veriyi bir yapılandırma nesnesine yayma. Bu işlemlerin naif implementasyonları `target[key] = value` ya da özyinelemeli `target[key1][key2] = value` desenini kullanır ve `key` değerinin `__proto__` olabileceğini hesaba katmaz. Yani zafiyet dilin kötü olmasından değil, geliştiricinin "anahtar isimleri de saldırgan kontrollü bir girdidir" gerçeğini gözden kaçırmasından doğar.

## Somut Örnekler

### Örnek 1: Güvensiz derin birleştirme (deep merge)

Prototype Pollution'ın klasik girdi noktası, iki nesneyi özyinelemeli birleştiren bir yardımcı fonksiyondur:

```javascript
function merge(target, source) {
  for (const key in source) {
    if (typeof source[key] === 'object' && source[key] !== null) {
      if (!target[key]) target[key] = {};
      merge(target[key], source[key]);   // özyineleme
    } else {
      target[key] = source[key];
    }
  }
  return target;
}
```

Bu fonksiyon dışarıdan kontrol edilen bir JSON ile beslenirse, örneğin:

```json
{ "__proto__": { "isAdmin": true } }
```

Birleştirme sırasında `key` değeri `__proto__` olur. `merge(target["__proto__"], { isAdmin: true })` çağrısı, `target`'ın prototipine, yani `Object.prototype`'a `isAdmin` özelliğini yazar. Bundan sonra uygulamada oluşturulan **her** sıradan nesne için `nesne.isAdmin` sorgusu `true` döner. Yetki kontrolü `if (user.isAdmin)` şeklinde yapılıyorsa ve `user` nesnesinde kendi `isAdmin` özelliği yoksa, saldırgan kendisini yönetici seviyesine çıkarmış olur.

Dikkat edilmesi gereken bir ayrıntı: eğer birleştirme `JSON.parse` ile üretilmiş bir nesne üzerinden dönüyorsa, `for...in` döngüsü `__proto__` anahtarını gerçekten kendi özellik olarak görebilir. Çünkü `JSON.parse('{"__proto__": {}}')` sonucu, `__proto__` adında normal (enumerable, own) bir özelliğe sahip bir nesne üretir. Bu, obje literali (`{ __proto__: {} }`) yazmaktan farklıdır; literalde `__proto__` prototip atama olarak yorumlanır, JSON'da ise düz veri olur. Bu ince ayrım, JSON kaynaklı Prototype Pollution'ı çok yaygın kılar.

### Örnek 2: Yol tabanlı (path) atama

Birçok kütüphane, `lodash.set` benzeri "bir yolu ver, iç içe nesnede o konuma yaz" işlevi sunar:

```javascript
setByPath(config, "a.b.c", value);
```

Eğer yol dizesi kullanıcıdan geliyorsa, saldırgan `"__proto__.polluted"` ya da `"constructor.prototype.polluted"` gibi bir yol geçirerek zincirin tepesine ulaşır. Ayrıştırıcı yolu noktalardan bölüp segment segment içeri iner ve son adımda `Object.prototype`'a yazar. Query string ayrıştırıcıları da benzer bir tehlike taşır: `?a[__proto__][isAdmin]=true` gibi bir istek, iç içe nesne kuran naif bir ayrıştırıcıda prototip kirlenmesine yol açabilir.

### Örnek 3: Kirlenmiş prototipin gözlemlenmesi

Kirlenmeden sonra etki her yere yayılır:

```javascript
Object.prototype.polluted = "kirli";
const bos = {};
console.log(bos.polluted);        // "kirli"  (kendi özelliği yok, zincirden geldi)
console.log("polluted" in bos);   // true
```

Buradaki tehlike, kodun hiçbir yerinde `bos.polluted` atanmamış olmasıdır; değer tamamen kirlenmiş prototipten sızar.

## Gadget Kavramı: Kirlenme Nasıl Gerçek Bir Saldırıya Dönüşür

Prototype Pollution tek başına genellikle "saldırganın kontrol ettiği bir özellik, uygulamanın her nesnesinde görünür hale geliyor" demektir. Bu, doğrudan felaket olmayabilir. Zafiyeti gerçek bir güvenlik etkisine çeviren şey **gadget**'lardır.

Gadget, uygulamanın veya bir bağımlılığın kodunda zaten var olan, **kirletilebilir bir özelliği tehlikeli bir işlemde okuyan** kod parçasıdır. Saldırgan kendi kodunu enjekte etmez; onun yerine mevcut kodun, kirlenmiş prototipten okuduğu bir değeri yanlış amaçla kullanmasını sağlar. Bu mantık, ROP (return-oriented programming) saldırılarındaki gadget zinciri fikrine benzer: hazır parçaları birleştirerek amaca ulaşırsınız.

Gadget'ları anlamanın anahtarı, JavaScript kodunun sıklıkla şu deseni kullanmasıdır:

```javascript
const opsiyon = ayarlar.timeout || 5000;
```

Burada `ayarlar` nesnesinde `timeout` yoksa, kod bunu prototip zincirinden okur. Kirlenme varsa, `Object.prototype.timeout` saldırgan tarafından belirlenmiş olabilir. Tehlikeli olan gadget'lar, kirlenebilir bir alanı şu tür bağlamlarda kullananlardır:

- **Şablon motorlarında** derleme sırasında kullanılan bir yapılandırma alanı. Bazı şablon motorları, çıktı üretmeden önce şablon kaynağını bir fonksiyon dizesi olarak derler. Kirlenmiş bir özellik bu derleme adımına enjekte edilebilirse, sunucu tarafında keyfi kod çalışabilir.
- **Çocuk süreç başlatma (child process)** çağrılarında, komut yolu veya argümanların bir yapılandırma nesnesinden okunduğu yerler. Kirlenmiş bir prototip, komut yolunu ya da ortam değişkenlerini kontrol etmeye izin verirse RCE mümkün olur.
- **Güvenlik kontrolleri**: yetki, kimlik doğrulama bayrakları, "izinli mi" kararlarının prototip zincirinden okunabildiği kod. Bu, yetki yükseltmenin klasik gadget'ıdır.

Buradaki önemli nokta şudur: aynı Prototype Pollution açığı, hangi gadget'ın mevcut olduğuna göre farklı sonuçlar doğurur. Bir uygulamada yalnızca DoS'a yol açarken, bir başkasında (uygun şablon motoru gadget'ı varsa) RCE'ye kadar tırmanabilir. Bu yüzden ciddiyet değerlendirmesi yaparken hem kirlenme kaynağını hem de erişilebilir gadget'ları birlikte düşünmek gerekir. Emin olmadığınız spesifik kütüphane sürümlerini veya tam gadget zincirlerini varsaymak yerine, "bu prototip alanı hangi tehlikeli işlemde okunuyor?" sorusuyla ilerlemek doğru yaklaşımdır.

## Sömürü/İstismar Mantığı

Saldırganın perspektifinden istismar üç aşamalıdır ve her aşamayı ayrı düşünmek gerekir.

**1. Kirlenme kaynağını (source) bulmak.** Saldırgan, uygulamanın kullanıcı kontrollü anahtarları nesnelere yazdığı bir noktayı arar. Tipik kaynaklar: JSON body ayrıştırıp bir yapılandırmayla birleştiren API uçları, query string / form ayrıştırıcıları, kullanıcı verisini derin klonlayan veya birleştiren fonksiyonlar. Client tarafında ise URL fragment'ı, `location.hash`, `postMessage` verisi gibi girdiler sıklıkla iç içe nesnelere dönüştürülür.

**2. Kirlenmeyi doğrulamak.** Saldırgan zararsız bir işaretçi (probe) enjekte eder, örneğin rastgele bir özellik adı, ve sonra uygulamanın bir yerinde bu özelliğin sızıp sızmadığını gözlemler. Kara kutu testinde bu bazen hata mesajı, davranış değişikliği ya da yansıyan bir çıktı üzerinden anlaşılır. Bu adım, körlemesine payload atmak yerine "gerçekten prototip kirlendi mi" sorusunu yanıtlamaktır.

**3. Bir gadget'a zincirlemek.** Kirlenme doğrulandıysa, saldırgan hedef ortamdaki tehlikeli gadget'ı belirler ve o gadget'ın okuduğu tam özellik adını/değerini kirletir. Client tarafında en yaygın sonuç DOM tabanlı XSS'tir: kirlenmiş bir özellik, bir kütüphanenin HTML üreten veya `src`/`onerror` gibi öznitelik belirleyen bir varsayılan değerini ele geçirebilirse, saldırgan script çalıştırabilir. Server tarafında ise gadget uygunsa RCE, değilse yetki yükseltme veya DoS elde edilir.

DoS'un mekanizması da öğreticidir: `toString`, `hasOwnProperty` veya `valueOf` gibi temel metotların kirletilmesi, uygulamanın her yerinde beklenmedik tür hataları veya sonsuz özyinelemeler doğurabilir ve süreci çökertebilir. Bu, gadget gerektirmeyen, sadece kirlenmenin kendisinden doğan bir etkidir.

## Savunma: Kirlenmeyi Baştan Engellemek

Savunmanın en sağlam prensibi, saldırganın anahtar isimlerini kontrol edebildiği gerçeğini kabul edip yazma yollarını bu doğrultuda sertleştirmektir. Tek bir sihirli çözüm yerine katmanlı önlemler gerekir.

**Tehlikeli anahtarları reddetmek.** Kullanıcıdan gelen anahtarları nesnelere yazan her kod, `__proto__`, `constructor` ve `prototype` anahtarlarını açıkça reddetmelidir. Ancak bu tek başına yeterli değildir; çünkü `constructor.prototype` gibi dolaylı yollar da vardır. Bu yüzden reddetme, aşağıdaki yapısal önlemlerle birlikte kullanılmalıdır.

**Prototipsiz nesneler kullanmak.** Sözlük (map) olarak kullanılan nesneler için `Object.create(null)` ile oluşturulan, prototipi olmayan nesneler idealdir. Bu nesnelerde `__proto__` sıradan bir özellik gibi davranır ve zincir kirlenmesine yol açmaz. Daha da iyisi, string-anahtarlı sözlükler için gerçek `Map` yapısını kullanmaktır; `Map`, prototip zinciriyle karışmaz, çünkü anahtarlar ayrı bir depoda tutulur ve özellik erişim mekanizmasından etkilenmez.

**Prototipi dondurmak.** `Object.freeze(Object.prototype)` çağrısı, prototipe yeni özellik yazılmasını engeller. Bu güçlü bir önlemdir ama dikkatli olunmalıdır: bazı kütüphaneler `Object.prototype`'a yazma yaparsa (nadiren de olsa) bozulabilir; ayrıca `freeze` sessizce başarısız olabilir (strict mode dışında yazma denemesi hata fırlatmaz, sadece etkisiz kalır). Yine de birçok sunucu uygulaması için pratik ve etkili bir sertleştirmedir.

**Güvenli ayrıştırma ve doğrulama.** Gelen JSON'u doğrudan derin birleştirmeye sokmak yerine, katı bir şema doğrulaması (schema validation) ile yalnızca beklenen alanları kabul eden bir allow-list yaklaşımı uygulanmalıdır. JSON Schema tabanlı doğrulayıcılar, yalnızca tanımlı özelliklere izin verecek şekilde yapılandırıldığında `__proto__` gibi beklenmedik anahtarları eleyebilir. Ilkesel olarak: "her şeyi al, sonra temizle" değil, "yalnızca izin verileni al" yaklaşımı tercih edilmelidir.

**Güvenli kütüphaneler ve güncel sürümler.** Derin birleştirme, klonlama ve yol atama işlevi sunan kütüphanelerin Prototype Pollution'a karşı yamalanmış sürümlerini kullanmak önemlidir. Bu tür açıklar zaman içinde birçok popüler yardımcı kütüphanede rapor edilmiş ve düzeltilmiştir; bu yüzden bağımlılık taraması (dependency scanning) ve düzenli güncelleme savunmanın ayrılmaz parçasıdır. Belirli bir kütüphanenin belirli bir sürümünün güvenli olduğunu varsaymak yerine, güncel danışma kayıtlarını (advisory) kontrol etmek gerekir.

## Gadget'lara Karşı Savunma

Kirlenmeyi tümüyle engelleyemediğiniz durumlar için ikinci savunma hattı, gadget'ların oluşmasını zorlaştırmaktır:

- **Yapılandırma değerlerini prototip zincirinden okumamak.** `ayarlar.timeout || varsayilan` gibi desenler yerine, `Object.prototype.hasOwnProperty.call(ayarlar, 'timeout')` ile yalnızca **kendi** özelliğin var olup olmadığını kontrol edin. Böylece kirlenmiş prototipten değer sızması engellenir. Bu, gadget'ın en yaygın besleme yolunu keser.
- **Güvenlik kararlarını kendi özelliklerle vermek.** Yetki, kimlik ve erişim bayraklarını daima nesnenin kendi özelliği olduğundan emin olarak okuyun. `if (user.isAdmin)` yerine `user`'ın bu alanı gerçekten kendisinde taşıdığını doğrulayın; ya da bu tür durumsal veriyi `Map` içinde tutun.
- **Şablon ve komut çalıştırma sınırlarını daraltmak.** Sunucuda şablon derleme, `eval` benzeri işlemler ve çocuk süreç başlatma noktaları en tehlikeli gadget bölgeleridir. Bu bölgelerde kullanılan yapılandırmanın kullanıcı verisinden ve prototip zincirinden izole edildiğinden emin olun.

Bu iki katmanın birlikte çalışması önemlidir: kirlenmeyi engelleyen önlemler ana savunmadır, gadget sertleştirmesi ise "derinlemesine savunma" (defense in depth) olarak bir kirlenme kaçtığında etkiyi sınırlar.

## Client ve Server Tarafı Etki Farkları

Prototype Pollution'ın etkisi, çalıştığı ortama göre nitelik değiştirir ve bunu ayrı değerlendirmek gerekir.

**Client tarafı (tarayıcı).** Kirlenme kaynağı genellikle URL parametreleri, `location.hash`, `postMessage` gibi kullanıcı kontrollü DOM girdileridir. Baskın sonuç DOM tabanlı XSS'tir: sayfada yüklü bir kütüphane, kirlenmiş bir prototip özelliğini HTML üretiminde, `innerHTML` benzeri bir yerde ya da bir öznitelik varsayılanında okursa, saldırgan script çalıştırabilir. Etki, kurbanın oturumu, çerezleri ve tarayıcı bağlamıyla sınırlıdır ama oturum çalma ve hesap ele geçirme için yeterlidir. Client tarafı gadget'lar çoğunlukla yüklü üçüncü taraf kütüphanelerin içinde yaşar, bu yüzden hangi kütüphanelerin sayfada olduğu doğrudan risk yüzeyini belirler.

**Server tarafı (Node.js).** Burada tek bir süreç birçok kullanıcıya hizmet ettiği için kirlenme çok daha tehlikelidir: bir `Object.prototype` kirlenmesi o süreçteki tüm istekleri, tüm kullanıcıların isteklerini etkiler. Bu, yetki yükseltmeyi (bir kullanıcının kendini yönetici yapması ve bunun diğer istekleri de etkilemesi), süreç genelinde DoS'u ve uygun gadget varsa RCE'yi mümkün kılar. Server tarafında kirlenme kalıcı da olabilir: eğer bir istek prototipi kirletir ve süreç yeniden başlamazsa, etki sonraki tüm isteklere taşınır. Bu "durum sızması" (state leakage) client tarafında görülmeyen, sunucuya özgü ve daha ağır bir sonuçtur.

Bu ayrım savunma önceliğini de belirler: sunucuda `Object.freeze(Object.prototype)`, katı şema doğrulaması ve süreç izolasyonu daha yüksek önceliklidir; client tarafında ise güvenli kütüphane seçimi ve DOM sink'lerinin sertleştirilmesi öne çıkar.

## Yaygın Hatalar

**"Sadece `__proto__`'yu engellemek yeterli" yanılgısı.** Anahtar filtresini yalnızca `__proto__` dizesine bakacak şekilde yazmak, `constructor.prototype` gibi dolaylı yolları ve kodlama/normalizasyon varyasyonlarını atlar. Kara liste (blacklist) yaklaşımı bu açıkta neredeyse her zaman eksik kalır; yapısal önlemler (prototipsiz nesne, `Map`, freeze) daha güvenilirdir.

**Kirlenmeyi zararsız sanmak.** "Sadece fazladan bir özellik ekleniyor, ne olacak ki" düşüncesi tehlikelidir. Etki tümüyle mevcut gadget'lara bağlıdır ve bugün zararsız görünen bir kirlenme, yarın eklenen bir bağımlılığın getirdiği gadget'la RCE'ye dönüşebilir. Ciddiyeti gadget varlığından bağımsız olarak "yüksek potansiyel" kabul etmek doğru duruştur.

**`hasOwnProperty`'yi güvenli sanıp yanlış çağırmak.** `obj.hasOwnProperty(key)` çağrısının kendisi kirlenmeye açıktır: `hasOwnProperty` metodu prototipten geldiği için kirletilebilir veya `obj` prototipsizse bu metot hiç bulunmaz. Doğru kullanım `Object.prototype.hasOwnProperty.call(obj, key)` ya da yeni ortamlarda `Object.hasOwn(obj, key)` biçimidir.

**JSON kaynağını obje literaliyle karıştırmak.** Geliştiriciler `{ __proto__: {} }` yazınca prototip atandığını bilir ama `JSON.parse` çıktısında `__proto__`'nun düz bir veri özelliği olarak geldiğini gözden kaçırır. Kirlenmenin çoğu, kaynağı JSON olan verinin naif birleştirmeye sokulmasından doğar.

**`Object.assign` ve spread'i tümüyle güvenli sanmak.** `Object.assign(hedef, kaynak)` ve `{...kaynak}` yalnızca **birinci seviye kendi özellikleri** kopyalar; `__proto__`'yu prototip atama olarak yorumlamaz ve derine inmez. Bu onları naif özyinelemeli birleştirmeden daha güvenli kılar, ama iç içe yapıyı korumadıkları için birçok kod yine de tehlikeli derin birleştirmeye döner. Yani "spread kullanıyorum, güvendeyim" varsayımı, koddaki gerçek birleştirme mantığı incelenmeden yapılmamalıdır.

## En Iyi Pratikler

Tüm bu analizi pratik bir kontrol listesine indirgersek, öncelik sırasıyla:

1. **Sözlükler için `Map` veya `Object.create(null)` kullanın.** Kullanıcı verisini dinamik anahtarlarla saklayan her yapı için varsayılan tercih bu olmalıdır; prototip zincirini tamamen devre dışı bırakır.
2. **Girdiyi allow-list ile doğrulayın.** Katı şema doğrulaması ile yalnızca beklenen alanları kabul edin. Bilinmeyen ve tehlikeli anahtarları kaynakta eleyin.
3. **Sunucuda `Object.prototype`'ı dondurun.** Uygulama başlangıcında `Object.freeze(Object.prototype)` çağırmak, geniş bir sertleştirme sağlar; uyumluluk testinden sonra üretime alın.
4. **Yapılandırma ve güvenlik değerlerini kendi özelliklerle okuyun.** `Object.hasOwn` / `Object.prototype.hasOwnProperty.call` kullanarak prototipten değer sızmasını kesin. Bu, gadget beslemesini engelleyen tek en etkili kod düzeyi önlemdir.
5. **Bağımlılıkları güncel ve taranmış tutun.** Derin birleştirme, klonlama ve yol atama kütüphanelerinin yamalı sürümlerini kullanın; düzenli danışma (advisory) taraması yapın.
6. **Derinlemesine savunmayı benimseyin.** Hiçbir tek önleme güvenmeyin; kaynağı (input hardening), zinciri (prototipsiz yapılar) ve etkiyi (gadget sertleştirme) ayrı ayrı ele alan katmanlı bir yaklaşım kurun.

Özetle Prototype Pollution, JavaScript'in paylaşılan prototip modelinin, kullanıcı kontrollü anahtar isimleriyle buluştuğu noktada ortaya çıkan yapısal bir risktir. Zafiyeti anlamanın anahtarı, tek bir yazmanın nasıl küresel bir yan etkiye dönüştüğünü ve bu yan etkinin mevcut gadget'lar aracılığıyla nasıl gerçek bir güvenlik ihlaline tırmandığını görmektir. Doğru savunma, saldırganın anahtarları kontrol edebileceğini kabul etmek ve yazma yollarını, veri yapılarını ve okuma desenlerini buna göre sertleştirmektir.
