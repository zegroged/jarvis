# Prototype Pollution — Derin Dalış

Bu metin, Prototype Pollution'ı mekanizmadan tespit ve savunmaya kadar uygulamalı biçimde ele alır. Amaç eğitim ve savunma: zafiyetin nasıl ortaya çıktığını, sahada gerçek CVE kayıtlarında nasıl göründüğünü, hangi savunma seçeneklerinin hangi bedelle geldiğini ve geliştiricilerin hangi tuzaklara düştüğünü anlamak. Canlı bir saldırı reçetesi değil; kirlenmenin nasıl doğduğunu ve nasıl kesileceğini gösteren bir laboratuvar defteridir.

Ön koşul olarak şunu kabul ediyoruz: JavaScript'te sıradan her nesne `Object.prototype`'ı ortak ata olarak paylaşır ve bir nesnede bulunmayan bir özellik okunduğunda motor bu paylaşılan atada arar. `__proto__`, `constructor` ve `constructor.prototype` bu paylaşılan atayı hedefleyen yazma yollarıdır. Kirlenme, uygulamanın kullanıcı kontrollü **anahtar isimlerini** güvenilir sayıp nesnelere yazmasından doğar.

---

## 1. Çözümlü yürüyüş

Somut, gerçekçi bir senaryo üzerinden gidelim: bir Node.js/Express API'sinin kullanıcı tercihlerini (settings) kaydeden bir uçu. İstemci bir JSON gövdesi gönderiyor, sunucu bunu mevcut varsayılan tercihlerle **derin birleştirme** (deep merge) yaparak birleştiriyor. Bu, sahada en çok görülen Prototype Pollution girdi noktasıdır.

### Adım 1 — Zafiyetli/hatalı kod

```javascript
// prefs-store.js  (ZAFIYETLI)
const express = require('express');
const app = express();
app.use(express.json());

// Her kullanıcı için tutulan sunucu tarafı varsayılanlar
const defaults = { theme: 'light', pageSize: 20 };

// Naif özyinelemeli derin birleştirme
function deepMerge(target, source) {
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object') {
      if (!target[key]) target[key] = {};
      deepMerge(target[key], source[key]);   // özyineleme
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

app.post('/api/prefs', (req, res) => {
  // Kullanıcının gönderdiği JSON, varsayılanların bir kopyasıyla birleştiriliyor
  const merged = deepMerge({ ...defaults }, req.body);
  res.json({ ok: true, prefs: merged });
});

// Uygulamanın başka bir yerinde, admin paneli erişim kontrolü:
function isPrivileged(user) {
  return user.isAdmin === true;   // user nesnesinde kendi isAdmin yoksa prototipten okunur
}

app.listen(3000);
```

Görünüşte masum. `deepMerge` iki nesneyi iç içe birleştiriyor, `isPrivileged` bir bayrağa bakıyor. İkisi de tek başına doğru "gibi" duruyor.

Saldırgan şu gövdeyi gönderdiğinde ne olur:

```
POST /api/prefs
Content-Type: application/json

{ "__proto__": { "isAdmin": true } }
```

### Adım 2 — Sorunun kavramsal olarak ortaya çıkışı

Kritik ayrıntı `express.json()`'un ürettiği nesnededir. `JSON.parse('{"__proto__": {...}}')` çağrısı, `__proto__` adında **normal, sıralanabilir (enumerable), kendi (own)** bir özelliğe sahip bir nesne üretir. Bu, obje literali `{ __proto__: {} }` yazmaktan tamamen farklıdır: literalde `__proto__` prototip ataması olarak yorumlanır; JSON'da ise düz veri olur. Bu yüzden `for (const key in source)` döngüsü `__proto__` anahtarını gerçek bir anahtar olarak görür.

Döngü `key === "__proto__"` iken şu satıra girer:

```javascript
if (!target[key]) target[key] = {};
deepMerge(target[key], source[key]);
```

Burada `target["__proto__"]` **okuması**, `target`'ın prototipini, yani `Object.prototype`'ı döndürür (setter değil getter; okuma prototipe erişir). Dolayısıyla özyineleme `deepMerge(Object.prototype, { isAdmin: true })` olarak devam eder ve bir sonraki turda:

```javascript
target["isAdmin"] = true;   // target artık Object.prototype
```

Bu satır `Object.prototype.isAdmin = true` demektir. O andan itibaren süreçteki **her** sıradan nesne için `nesne.isAdmin` sorgusu `true` döner — nesnenin kendisinde `isAdmin` olmasa bile. `isPrivileged(user)` fonksiyonu, `user` nesnesinde kendi `isAdmin` alanı yoksa prototipten `true` okur ve rastgele bir kullanıcıyı ayrıcalıklı sayar. Üstelik bu Node.js'te **tek süreç** olduğu için kirlenme o sürece gelen **tüm kullanıcıların** isteklerini etkiler ve süreç yeniden başlayana kadar kalıcıdır. Bu "durum sızması" (state leakage) sunucu tarafını istemciden çok daha tehlikeli yapar.

Doğrulamayı hızlıca REPL'de görelim:

```javascript
Object.prototype.isAdmin = true;
const kullanici = { ad: "sıradan_kullanıcı" };
console.log(kullanici.isAdmin);        // true  — kendi özelliği yok, zincirden geldi
console.log("isAdmin" in kullanici);   // true
console.log(Object.hasOwn(kullanici, "isAdmin")); // false — kendi özelliği DEĞİL
```

Son satır çözümün ipucunu da veriyor: kirlenmiş değer `in` ile görünür ama `Object.hasOwn` ile görünmez.

### Adım 3 — Düzeltilmiş/doğru kod

Düzeltme iki katmanlıdır: (a) birleştirmeyi tehlikeli anahtarlara karşı sağlamlaştırmak, (b) güvenlik kararını prototipten değil kendi özellikten okumak. Ek olarak süreç başında `Object.prototype`'ı dondurmak geniş bir emniyet ağı sağlar.

```javascript
// prefs-store.js  (DÜZELTİLMİŞ)
const express = require('express');
const app = express();
app.use(express.json());

// (c) Süreç başlangıcında prototipi dondur — geniş sertleştirme
Object.freeze(Object.prototype);

const defaults = { theme: 'light', pageSize: 20 };

const YASAK = new Set(['__proto__', 'constructor', 'prototype']);

// (a) Tehlikeli anahtarları eleyen, prototipsiz ara nesneler kullanan güvenli birleştirme
function safeMerge(target, source) {
  // Yalnızca kaynağın KENDİ, sıralanabilir anahtarları
  for (const key of Object.keys(source)) {
    if (YASAK.has(key)) continue;               // __proto__ / constructor / prototype reddet
    const val = source[key];
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      // Alt nesneyi prototipsiz oluştur ki iç içe kirlenme de imkânsız olsun
      if (!Object.hasOwn(target, key) || typeof target[key] !== 'object') {
        target[key] = Object.create(null);
      }
      safeMerge(target[key], val);
    } else {
      target[key] = val;
    }
  }
  return target;
}

app.post('/api/prefs', (req, res) => {
  const merged = safeMerge(Object.create(null), req.body);
  // { ...defaults } yerine defaults'u da güvenli biçimde alta ekleyelim
  for (const [k, v] of Object.entries(defaults)) {
    if (!Object.hasOwn(merged, k)) merged[k] = v;
  }
  res.json({ ok: true, prefs: merged });
});

// (b) Güvenlik kararı DAİMA kendi özellikten okunur
function isPrivileged(user) {
  return Object.hasOwn(user, 'isAdmin') && user.isAdmin === true;
}

app.listen(3000);
```

Neyin değiştiğine dikkat: `for...in` yerine `Object.keys` (yalnızca kendi, sıralanabilir anahtarlar), açık bir `YASAK` reddi, iç içe nesnelerin `Object.create(null)` ile prototipsiz kurulması, güvenlik kararının `Object.hasOwn` ile kendi özelliğe bağlanması ve son kalkan olarak `Object.freeze(Object.prototype)`. Bu katmanların hepsi aynı anda gerekmese de birlikte "derinlemesine savunma" oluşturur: biri atlanırsa diğeri tutar. Örneğin `YASAK` listesini `constructor` için unutsanız bile prototip donduğu için yazma etkisiz kalır; freeze'i unutsanız bile `Object.keys` + reddetme kirlenmeyi keser.

Bir uyarı: `Object.freeze(Object.prototype)` non-strict modda **sessizce** başarısız olur — yazma denemesi hata fırlatmaz, sadece etkisiz kalır. Bu iyi haber (saldırı etkisiz), ama test ederken "yazma neden hata vermiyor?" diye şaşırmayın. Strict mode'da (`'use strict'`) ise `TypeError` fırlatır ve bunu bir alarm sinyali olarak loglayabilirsiniz.

### Adım 4 — Kirlenmeden gadget'a: etkinin nasıl büyüdüğü

Yukarıdaki `isPrivileged` bir "gadget" örneğidir: uygulamada zaten var olan, kirletilebilir bir özelliği güvenlik kararında okuyan kod. Gadget kavramını netleştirmek önemli, çünkü Prototype Pollution'ın gerçek ciddiyetini gadget belirler. Kirlenme tek başına "saldırganın belirlediği bir özellik her nesnede görünür oldu" demektir; bunun bir güvenlik ihlaline dönüşmesi için, uygulamanın (veya bir bağımlılığının) kodunda o kirlenmiş özelliği **tehlikeli bir işlemde okuyan** bir parça bulunması gerekir. Saldırgan kendi kodunu enjekte etmez; mevcut kodun kirlenmiş prototipten okuduğu bir değeri yanlış amaçla kullanmasını sağlar. Mantık, ROP (return-oriented programming) gadget zincirine benzer: hazır parçaları birleştirirsiniz.

Aynı kirlenme, ortamdaki gadget'a göre çok farklı sonuçlar verir:

- **Yetki yükseltme (gördüğümüz senaryo):** `user.isAdmin` gibi bir bayrak prototipten okunuyorsa, kirlenme doğrudan ayrıcalık kazandırır.
- **DoS:** `toString`, `valueOf` veya `hasOwnProperty` gibi temel metotların kirletilmesi, uygulamanın her yerinde beklenmedik tür hataları veya sonsuz özyineleme doğurup süreci çökertir. Bu gadget gerektirmez; CVE-2018-16472'de gördüğümüz gibi doğrudan kirlenmeden doğar.
- **RCE (sunucuda):** Bazı şablon motorları, çıktı üretmeden önce şablonu bir fonksiyon dizesi olarak derler; kirlenmiş bir yapılandırma alanı bu derleme adımına sızabilirse sunucuda keyfi kod çalışabilir. Benzer şekilde çocuk süreç (child process) başlatma çağrılarında komut yolu veya argümanlar bir config nesnesinden okunuyorsa, kirlenmiş prototip bunları ele geçirebilir.
- **DOM tabanlı XSS (istemcide):** Yüklü bir kütüphane kirlenmiş bir özelliği HTML üretiminde veya `src`/`onerror` gibi bir öznitelik varsayılanında okursa, saldırgan script çalıştırabilir.

Bu yüzden ciddiyet değerlendirmesinde "bu prototip alanı hangi tehlikeli işlemde okunuyor?" sorusu, "kirlenme oldu mu?" sorusundan daha belirleyicidir. Spesifik kütüphane sürümlerini veya tam gadget zincirlerini varsaymak yerine bu soruyla ilerlemek doğru yaklaşımdır.

### Adım 5 — Tespit: kirlenmeyi nasıl yakalarsınız

Savunmanın gözden kaçan yarısı tespittir. Üretimde ucuz ve etkili bir kanarya (canary), süreç başında prototipi dondurup strict modda yazma denemesini bir alarma çevirmektir:

```javascript
'use strict';
// Süreç başında: hem sertleştir hem gözle
try {
  Object.defineProperty(Object.prototype, '__proto_canary__', {
    configurable: false, enumerable: false, writable: false, value: undefined
  });
} catch (_) {}
Object.freeze(Object.prototype);

// Periyodik veya istek sonrası basit bütünlük kontrolü
function prototipTemizMi() {
  const bos = {};
  // Beklenmedik, kendi-olmayan ama görünür bir alan var mı?
  for (const k in bos) {
    // bos.__proto__ zinciri kirlendiyse buraya sıralanabilir bir anahtar düşer
    return false;
  }
  return true;
}
```

`for (const k in bos)` boş bir nesne üzerinde normalde hiç dönmez; döndüyse `Object.prototype`'a sıralanabilir bir özellik enjekte edilmiş demektir. Bu kontrolü sağlık ucu (health endpoint) veya istek-sonu ara katmanına (middleware) koymak, kirlenmeyi erken yakalar. Testlerde ise şu iddia (assertion) değerlidir: her test dosyası sonunda `Object.getOwnPropertyNames(Object.prototype)`'ın beklenen sabit listeye eşit olduğunu doğrulamak — bir bağımlılık güncellemesi sessizce kirlenme getirdiyse CI'da yakalanır.

Statik tarafta, `grep`/lint kuralları ile `for (… in …)` üzerinden yapılan kullanıcı-verisi birleştirmelerini, `[req.body...]` benzeri dinamik atamaları ve `_.merge`/`extend`/`defaultsDeep` çağrılarını işaretlemek düşük maliyetli bir erken uyarıdır. Bağımlılık taramasında (`npm audit` ve benzeri advisory kaynakları) bu ailenin bilinen CVE'lerini izlemek de tespidin bir parçasıdır.

---

## 2. Gerçek dünya (CVE ile)

Prototype Pollution'ın sahadaki hikâyesinin büyük bölümü, tam da yukarıdaki `deepMerge` örneğinin kütüphaneleştirilmiş halleridir: npm ekosistemindeki popüler "derin birleştir / genişlet / klonla" yardımcılarının naif implementasyonları. 2018'in sonunda HackerOne üzerinden peş peşe raporlanan bir seri, bu sınıfın ne kadar yaygın olduğunu gösterir.

**CVE-2018-16487 (lodash).** En çok bilineni budur: lodash'un 4.17.11 öncesi sürümlerinde `merge`, `mergeWith` ve `defaultsDeep` fonksiyonları, `Object.prototype`'a özellik ekleyip değiştirmeye kandırılabiliyordu. lodash o dönemde JavaScript ekosisteminin en çok indirilen kütüphanelerinden biri olduğu için etki yüzeyi devasaydı: uygulama kodunuz `__proto__` içeren bir JSON'u doğrudan işlemese bile, bir `_.merge(config, kullaniciVerisi)` çağrısı üzerinden dolaylı olarak kirlenebiliyordunuz. Bu, "kendi merge fonksiyonumu yazmıyorum, güvendeyim" varsayımının neden yanlış olduğunu gösterir — güven, kütüphanenin implementasyonuna kayar. Kayıt CWE-400 (Denial of Service) altında sınıflandırılmış olsa da, uygun gadget'ların bulunduğu ortamlarda etki DoS'un çok ötesine geçebilir.

**CVE-2018-16486 (defaults-deep) ve CVE-2018-16489 (just-extend).** Bu ikisi, aynı desenin daha küçük ama yine yaygın yardımcılarda tekrarıdır. `defaults-deep <=0.2.4` ve `just-extend <4.0.0`, kullanıcının `Object.prototype`'a özellik enjekte etmesine izin veriyordu. Buradaki öğretici nokta, zafiyetin **fonksiyonun amacında** gizli olmasıdır: "eksik alanları varsayılanlarla derinlemesine doldur" işlevi, doğası gereği kaynaktaki her anahtarı hedefe yazmaya çalışır — `__proto__` dahil. Yani zafiyet bir "bug" değil, güvenli olmayan bir tasarımın doğal sonucudur; düzeltme, anahtar filtreleme ve prototipsiz ara yapıların eklenmesiyle geldi.

**CVE-2018-16472 (cached-path-relative).** Bu kayıt, etkinin nasıl "sadece" DoS olarak da kalabileceğini gösterir. `cached-path-relative <=1.0.1`, `Object.prototype`'a enjekte edilen özelliklerin prototip zinciri üzerinden tüm nesnelere miras kalmasıyla bir hizmet reddi (DoS) doğuruyordu. Burada gadget bir RCE'ye tırmanmıyor; bunun yerine kirlenmiş prototip, kütüphanenin kendi iç mantığını (yol önbelleği) bozarak süreci tutarsız hale getiriyor. Bu, "her Prototype Pollution RCE demek değildir; etki tümüyle mevcut gadget'a bağlıdır" ilkesinin somut kanıtıdır.

Bu ailenin diğer üyeleri de aynı imzayı taşır: **CVE-2018-16490 (mpath)** yol-tabanlı atamada, **CVE-2018-16491 (node.extend)** ve **CVE-2018-16492 (extend)** klasik "genişlet/birleştir" işlevinde `Object.prototype`'a keyfi özellik enjeksiyonuna izin veriyordu. Hepsi kısa süre içinde, aynı savunma prensipleriyle yamalandı. Alınacak ders: Prototype Pollution tek bir kütüphanenin hatası değil, bütün bir işlev sınıfının (deep merge/extend/clone/set-by-path) ortak kör noktasıdır. Bu yüzden bağımlılık taraması (dependency scanning) ve düzenli güncelleme, bu sınıfa karşı savunmanın ayrılmaz parçasıdır.

**CVE-2011-10019 (Spreecommerce) — farklı bir açı.** Bu kayıt, listedeki JavaScript örneklerinden ayrışır ve öğretici bir kontrast sunar. Spreecommerce 0.60.2 öncesinde, arama işlevindeki `search[send][]` parametresi Ruby'nin `send` metoduna dinamik olarak aktarılıyordu; bu da kimlik doğrulaması olmadan uzaktan komut çalıştırmaya (RCE) yol açıyordu. CVSS v4.0 skoru 10 (CRITICAL). İlginç olan, bu kaydın hem CWE-94 (Code Injection) hem de CWE-1321 (Improperly Controlled Modification of Object Prototype Attributes — yani Prototype Pollution'ın resmî CWE'si) altında sınıflandırılmış olmasıdır. Buradaki mesaj kavramsaldır: "kullanıcı kontrollü bir anahtar/isim ismini, güvenilir bir dilsel mekanizmaya (Ruby `send`, JS özellik ataması) doğrudan besleme" hatası dile özgü değildir. JavaScript'te `Object.prototype`'ı kirletir, Ruby'de bir metodu çağırır; kök neden aynı sınıftandır — **isim/anahtar de saldırgan kontrollü bir girdidir**.

---

## 3. Karşılaştırma / karar

Prototype Pollution'a karşı birden fazla savunma tekniği vardır ve hiçbiri tek başına "her derde deva" değildir. Doğru mimari, bunları katmanlayan ama bedellerini bilerek seçen mimaridir.

**Kara liste (blacklist) — `__proto__`/`constructor`/`prototype` anahtarlarını reddetmek.** En hızlı uygulanan önlem. Mevcut merge/set kodunun içine bir `if (YASAK.has(key)) continue;` eklemek yeterlidir; performans maliyeti neredeyse sıfırdır ve mevcut davranışı bozmaz. Bedeli: eksik kalmaya çok yatkındır. `constructor.prototype` gibi dolaylı yollar, kodlama/normalizasyon varyasyonları veya unuttuğunuz bir anahtar filtreyi delebilir. **Ne zaman:** hızlı bir yama olarak, ama asla tek başına değil — her zaman yapısal bir önlemle birlikte.

**Prototipsiz nesneler — `Object.create(null)`.** Sözlük (map) olarak kullanılan her nesneyi prototipsiz kurmak. Bu nesnelerde `__proto__` sıradan bir string anahtar gibi davranır ve zincir kirlenmesi imkânsızlaşır. Bedeli: `obj.hasOwnProperty(...)`, `toString()` gibi prototipten gelen kolaylıklar artık yoktur (bunları `Object.hasOwn`/`Object.prototype.toString.call` ile çağırmanız gerekir); ayrıca bazı kütüphaneler nesnelerinizin `Object.prototype`'a sahip olmasını bekler ve prototipsiz nesnelerle beklenmedik davranabilir. **Ne zaman:** dinamik/kullanıcı-kontrollü anahtarlarla veri sakladığınız her yerde ilk tercih.

**`Map` kullanmak.** Prototipsiz nesneden bir adım öteye gitmek: string-anahtarlı sözlükler için gerçek `Map`. Anahtarlar ayrı bir depoda tutulur, özellik erişim mekanizmasından ve prototip zincirinden tümüyle izole. Bedeli: API farklıdır (`.get`/`.set`), JSON serileştirmesi doğrudan çalışmaz, mevcut nesne-tabanlı kodu yeniden yazmak gerekir. **Ne zaman:** yeni kod yazarken ve veri gerçekten bir "sözlük" ise (rastgele anahtar → değer); en temiz ve en güvenli seçenek budur.

**`Object.freeze(Object.prototype)`.** Süreç başında tüm prototipi kilitlemek. Tek satır, geniş kapsam: kirlenme kaynağını nerede kaçırırsanız kaçırın, yazma etkisiz kalır. Bedeli: bazı (özellikle eski) kütüphaneler `Object.prototype`'a meşru yazma yapıyorsa bozulur; non-strict modda sessiz başarısızlık davranışı hata ayıklamayı zorlaştırır; ve bir kez donduktan sonra geri alınamaz. **Ne zaman:** sunucu uygulamalarında, kapsamlı uyumluluk testinden sonra, güçlü bir emniyet ağı olarak. İstemci tarafında üçüncü taraf kütüphane uyumsuzluğu riski daha yüksek olduğu için daha temkinli değerlendirilir.

**Şema doğrulama (allow-list).** Gelen veriyi derin birleştirmeye sokmadan önce katı bir JSON Schema (veya benzeri) ile doğrulayıp yalnızca beklenen alanları kabul etmek. Bedeli: şema bakımı iş yükü getirir; şemayı `additionalProperties: false` ile doğru yapılandırmazsanız `__proto__` yine sızabilir. **Ne zaman:** API sınırında, "yalnızca izin verileni al" prensibini uygulamak için — bu, savunmanın en sürdürülebilir katmanıdır çünkü kirlenmeyi kaynağında keser.

**Karar özeti.** İstemci tarafında öncelik güvenli kütüphane seçimi ve DOM sink'lerinin sertleştirilmesidir (freeze burada daha riskli). Sunucu tarafında öncelik sırası kabaca şöyledir: (1) API sınırında allow-list şema doğrulama, (2) dinamik veri için `Map`/`Object.create(null)`, (3) güvenlik/config değerlerini `Object.hasOwn` ile okumak, (4) emniyet ağı olarak `Object.freeze(Object.prototype)`. Kara liste bunların hiçbirinin yerini tutmaz; yalnızca acil bir yama olarak eklenir.

---

## 4. Hata-modu kataloğu

Aşağıdakiler, geliştiricilerin ve savunmacıların Prototype Pollution konusunda tekrar tekrar düştüğü tipik hatalardır.

1. **Yalnızca `__proto__` dizesini engellemek.** Filtreyi sadece `__proto__`'ya bakacak şekilde yazmak, `constructor.prototype` üzerinden gelen dolaylı yolu ve normalizasyon varyasyonlarını atlar. Kara liste yaklaşımı bu açıkta neredeyse her zaman eksik kalır.

2. **`obj.hasOwnProperty(key)`'i güvenli sanmak.** Bu çağrının kendisi kirlenmeye açıktır: `hasOwnProperty` metodu prototipten gelir, dolayısıyla kirletilebilir veya `obj` prototipsizse hiç bulunmaz. Doğrusu `Object.prototype.hasOwnProperty.call(obj, key)` ya da `Object.hasOwn(obj, key)`'dir.

3. **JSON kaynağını obje literaliyle karıştırmak.** `{ __proto__: {} }` yazınca prototip atandığını herkes bilir, ama `JSON.parse('{"__proto__":{}}')` çıktısında `__proto__`'nun düz, kendi bir veri özelliği olarak geldiği gözden kaçar. Kirlenmenin büyük çoğunluğu, kaynağı JSON olan verinin naif birleştirmeye sokulmasından doğar.

4. **`Object.assign` ve spread'i derin birleştirme sanmak.** `Object.assign(hedef, kaynak)` ve `{...kaynak}` yalnızca birinci seviye kendi özellikleri kopyalar, `__proto__`'yu prototip ataması olarak yorumlamaz ve derine inmez — bu yüzden nispeten güvenlidirler. Hata, iç içe yapıyı korumak için sonradan naif özyinelemeli birleştirmeye dönmek ve "ama ben spread kullanmıştım" diye rahatlamaktır.

5. **`for...in` ile kaynak nesneyi gezmek.** `for...in` sıralanabilir prototip özelliklerini de dolaşır ve JSON kaynaklı `__proto__`'yu kendi anahtar olarak görür. `Object.keys`/`Object.entries` daha güvenli tabandır çünkü yalnızca kendi, sıralanabilir anahtarları verir.

6. **Kirlenmeyi "zararsız fazladan özellik" sanmak.** "Ne olacak, sadece bir alan ekleniyor" düşüncesi tehlikelidir. Etki tümüyle mevcut gadget'lara bağlıdır; bugün zararsız görünen bir kirlenme, yarın eklenen bir bağımlılığın gadget'ıyla RCE'ye tırmanabilir. Ciddiyet, gadget varlığından bağımsız olarak "yüksek potansiyel" kabul edilmelidir.

7. **Config değerlerini `ayarlar.x || varsayilan` ile okumak.** Bu desen, `ayarlar` nesnesinde `x` yoksa değeri prototip zincirinden okur ve kirlenmiş bir `Object.prototype.x`'i doğrudan gadget'a besler. Doğrusu, kritik alanları `Object.hasOwn(ayarlar, 'x')` ile kendi özellik olarak doğrulamaktır.

8. **İstemci ve sunucu etkisini eşit sanmak.** Sunucuda tek süreç tüm kullanıcılara hizmet ettiği için bir kirlenme tüm istekleri etkiler ve süreç yeniden başlayana kadar kalıcı olabilir. İstemcide etki tek kurbanın oturumuyla sınırlıdır. Savunma önceliğini bu farka göre ayarlamamak, sunucu tarafını hafife almaya yol açar.

9. **`Object.freeze(Object.prototype)`'ın sessiz başarısızlığına güvenmek/şaşırmak.** Non-strict modda dondurulmuş prototipe yazma hata fırlatmaz, sadece etkisiz kalır. Bunu bilmeyen geliştirici ya "freeze çalışmıyor" diye yanlış sonuca varır ya da strict modda beklenmedik `TypeError` alır. Davranışı bilerek, freeze'i alarm sinyali olarak kullanmak gerekir.

10. **İç içe/derin kirlenmeyi unutmak.** Birinci seviye anahtarları filtrelemek ama alt nesneleri özyinelemede sıradan `{}` ile kurmak, `{"a":{"__proto__":{...}}}` gibi bir seviye içeriden gelen kirlenmeyi kaçırır. Ara nesneleri de `Object.create(null)` ile kurmak veya her seviyede filtre uygulamak gerekir.

11. **Kütüphaneye kör güvenmek.** "Kendi merge'imi yazmıyorum, lodash kullanıyorum, güvendeyim" varsayımı CVE-2018-16487'nin tam olarak çürüttüğü şeydir. Güven, kendi kodunuzdan kütüphanenin sürümüne kayar; yamasız bir sürüm sizi de kirletir. Bağımlılıkları taramadan ve güncellemeden güven olmaz.

12. **Şemada `additionalProperties: false` koymamak.** Allow-list doğrulaması uyguladığını sanmak ama şemayı tanımsız alanlara açık bırakmak, `__proto__` gibi anahtarların doğrulamadan geçmesine izin verir. Şema doğrulamasının koruma sağlaması, fazladan/beklenmedik özellikleri açıkça reddetmesine bağlıdır.

---

## Kapanış

Prototype Pollution, JavaScript'in paylaşılan prototip modelinin, kullanıcı kontrollü anahtar isimleriyle buluştuğu noktada doğan yapısal bir risktir. `deepMerge` örneğinde gördüğümüz gibi, tek bir naif `target[key] = value` deseni, tek bir yazmayı süreç genelinde küresel bir yan etkiye dönüştürür. 2018 npm CVE serisi (lodash, defaults-deep, just-extend, extend, node.extend, mpath, cached-path-relative) bu desenin bütün bir işlev sınıfında ne kadar yaygın olduğunu; Spreecommerce'in CWE-1321 kaydı ise kök nedenin dile özgü olmadığını gösterir. Savunmanın özü, saldırganın anahtarları kontrol edebileceğini kabul edip yazma yollarını (allow-list, reddetme), veri yapılarını (`Map`/`Object.create(null)`), okuma desenlerini (`Object.hasOwn`) ve emniyet ağını (`Object.freeze`) katmanlı biçimde sertleştirmektir.
