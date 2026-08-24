# JavaScript Derinlemesine

JavaScript, tarayıcının tek yerel dili olması nedeniyle web'in vazgeçilmezidir;
Node.js ile sunucuda da çalışır. Basit görünür ama altında, onu doğru kullanmak
için anlaşılması şart olan birkaç güçlü ve tuzaklı mekanizma vardır: event loop,
closure, prototype zinciri, `this` bağlanması ve hoisting. Bu makale bunları
"neden böyle" sorusuyla ele alır.

## 1. Event Loop ve Eşzamanlılık Modeli

JavaScript **tek iş parçacıklıdır (single-threaded):** aynı anda tek bir kod
parçası çalışır. Peki tarayıcı nasıl aynı anda ağ isteği yaparken arayüzü donmadan
tutabiliyor? Cevap **event loop**'tur.

Model şu bileşenlerden oluşur:
- **Call stack (çağrı yığını):** o an çalışan fonksiyonların yığını.
- **Web API'ler / ortam:** `setTimeout`, `fetch`, DOM olayları gibi işleri asıl
  yürüten, JavaScript motorunun *dışındaki* mekanizmalar.
- **Task queue (makrotask kuyruğu)** ve **microtask queue.**
- **Event loop:** call stack boşaldığında kuyruklardaki işleri sırayla yığına alan
  döngü.

Kritik kural: JavaScript bir işi (ör. `fetch`) başlatır, ama beklemez;
tamamlanınca çalışacak callback'i kuyruğa bırakır ve devam eder. Yığın boşalınca
event loop kuyruktan bir sonraki işi alır. Yani "asenkron" demek "paralel" demek
değildir; **tek thread, sıralı ama bloklamayan** demektir.

**Microtask vs macrotask farkı önemlidir.** Promise callback'leri (`.then`,
`await` sonrası) **microtask** kuyruğuna girer; `setTimeout` ise **macrotask**.
Event loop, her macrotask'tan sonra *tüm* microtask kuyruğunu boşaltır. Bu yüzden:

```
console.log("1");
setTimeout(() => console.log("2"), 0);
Promise.resolve().then(() => console.log("3"));
console.log("4");
// Çıktı: 1, 4, 3, 2
```

`3` (microtask), `2`'den (macrotask) önce çalışır — `setTimeout(0)` bile olsa.
Bunu bilmemek, gerçek sıralama hatalarına yol açar.

**CPU-yoğun iş event loop'u bloklar.** Uzun süren senkron bir hesap, yığını meşgul
eder ve tüm callback'ler (arayüz dahil) bekler → sayfa donar. Çözüm: işi parçalara
böl, Web Worker'a taşı ya da asenkronlaştır.

## 2. Closure (Kapanış)

Closure, JavaScript'in en güçlü ve en çok yanlış anlaşılan özelliğidir. **Bir
fonksiyon, tanımlandığı sözcüksel (lexical) kapsamı, o kapsam dışında çağrılsa
bile hatırlar.** Yani fonksiyon, doğduğu ortamın değişkenlerine erişimini "yanında
taşır".

```
function sayacUret() {
  let sayi = 0;
  return function () {
    sayi += 1;
    return sayi;
  };
}
const artir = sayacUret();
artir(); // 1
artir(); // 2
```

`sayacUret` bittikten sonra bile, döndürdüğü fonksiyon `sayi` değişkenini canlı
tutar. `sayi` dışarıdan doğrudan erişilemez — bu, **veri gizleme (encapsulation)**
sağlar; closure, modül desenlerinin ve özel (private) durumun temelidir.

**Klasik tuzak — döngüde `var`:**

```
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// Beklenen: 0,1,2 — Gerçek: 3,3,3
```

`var` fonksiyon kapsamlıdır; üç callback de *aynı* `i`'yi paylaşır ve döngü bitince
`i` zaten `3` olmuştur. `let` blok kapsamlı olduğu için her yinelemede yeni bir
bağlanma yaratır ve `0,1,2` verir. Bu örnek, closure'ın "değeri değil, değişkeni
yakaladığını" gösterir.

## 3. Prototype Zinciri ve Kalıtım

JavaScript, sınıf-tabanlı değil, **prototype-tabanlı** bir dildir. Her nesnenin
gizli bir bağı (`[[Prototype]]`, erişimi `Object.getPrototypeOf` ya da eski
`__proto__`) vardır; bu bağ başka bir nesneyi işaret eder. Bir özelliğe
eriştiğinde motor önce nesnenin kendisine, yoksa prototype'ına, yoksa onun
prototype'ına... `null`'a ulaşana dek bakar. Buna **prototype chain** denir.

```
const hayvan = { nefesAl() { return "..."; } };
const kedi = Object.create(hayvan);
kedi.miyavla = () => "miyav";
kedi.nefesAl(); // kedi'de yok -> hayvan'dan bulunur
```

`class` sözdizimi (ES6) bunun üstüne konmuş **şekersel (syntactic sugar)** bir
katmandır; altında yine prototype vardır. `class` yazmak dili sınıf-tabanlı
yapmaz, sadece prototype kurulumunu okunaklı hâle getirir.

**Güvenlik/tuzak — prototype pollution:** Kullanıcı verisiyle `__proto__` gibi
özel anahtarlara yazmaya izin veren birleştirme (merge) fonksiyonları,
`Object.prototype`'ı kirletip *tüm* nesnelerin davranışını değiştirebilir; bu
ciddi bir zafiyet sınıfıdır. Girdi anahtarlarını doğrula, `Object.create(null)`
veya `Map` kullan.

## 4. `this` Bağlanması

`this`'in değeri, fonksiyonun *nerede tanımlandığına değil, nasıl çağrıldığına*
göre belirlenir. Kuralları:

1. **Metot çağrısı:** `nesne.metot()` → `this` = `nesne`.
2. **Yalın fonksiyon çağrısı:** `f()` → `this` = (strict mode'da) `undefined`,
   yoksa global nesne. Çok yaygın hata kaynağı.
3. **`call`/`apply`/`bind`:** `this`'i açıkça belirler.
4. **`new` ile:** `this` = yeni oluşturulan nesne.
5. **Arrow fonksiyon:** Kendi `this`'i **yoktur**; tanımlandığı yerdeki (lexical)
   `this`'i kullanır. Bu yüzden callback'lerde `this` kaymasını çözmek için
   arrow fonksiyon idealdir.

Klasik tuzak: bir metodu callback olarak geçince (`setTimeout(nesne.metot, 100)`)
bağ kopar; `this` artık `nesne` değildir. Çözüm: `nesne.metot.bind(nesne)` ya da
arrow ile sarmalamak.

## 5. Hoisting

Motor kodu çalıştırmadan önce bildirimleri "yukarı kaldırır" (hoist) gibi davranır:

- **`var`:** bildirimi kapsamın başına kalkar ama ilk değeri `undefined`'dır
  (atama yerinde kalır). Bu yüzden atamadan önce erişmek hata değil `undefined`
  verir — sinsi bir tuzak.
- **`let`/`const`:** hoist edilir ama **Temporal Dead Zone (TDZ)** içindedir;
  bildirim satırından önce erişim `ReferenceError` fırlatır. Bu, `var`'ın sessiz
  `undefined`'ından daha güvenlidir.
- **Fonksiyon bildirimleri (`function f(){}`):** tümüyle hoist edilir, bildirimden
  önce çağrılabilir. Fonksiyon *ifadeleri* (`const f = () => {}`) ise değişken
  kuralına tabidir.

Pratik sonuç: `var` yerine `let`/`const` kullan; TDZ hataları erken yakalanır,
`var`'ın öngörülemez `undefined`'ı gizli bug üretir.

## 6. Diğer Önemli Noktalar ve Güvenli Kullanım

- **Eşitlik:** `==` tip zorlaması (coercion) yapar ve şaşırtıcı sonuçlar verir
  (`0 == ""`, `null == undefined`). Neredeyse her zaman `===` kullan.
- **Asenkron kod:** `async/await`, promise'lerin okunaklı hâlidir; ama `await`
  bir microtask sınırıdır (bkz. bölüm 1). Hataları `try/catch` ile yakala,
  yakalanmamış promise reddi (unhandled rejection) bırakma.
- **Güvenlik:** `eval`, `new Function` ve string alan `setTimeout` kod
  enjeksiyonuna açar — kullanma. DOM'a kullanıcı verisi yazarken `innerHTML`
  yerine `textContent` tercih et (DOM-based XSS'ten kaçınmak için). Node'da
  `child_process` çağrılarında shell enjeksiyonuna dikkat et. npm bağımlılık
  zinciri (supply chain) riskine karşı bağımlılıkları denetle ve sabitle.
- **Immutability:** `const` yalnızca *bağlanmayı* sabitler, nesne içeriğini değil;
  gerçek değişmezlik için `Object.freeze` ya da değişmez veri desenleri gerekir.

## Özet

JavaScript'in "tuhaflıkları" aslında tutarlı kuralların sonucudur: tek thread +
event loop asenkronluğu açıklar; lexical scope + closure durum gizlemeyi ve döngü
tuzaklarını açıklar; prototype zinciri kalıtımı açıklar; çağrı-biçimi `this`'i
açıklar; hoisting/TDZ ise bildirim sırasını açıklar. Bu beş mekanizmayı bilen bir
geliştirici için JavaScript öngörülemez olmaktan çıkar; bilmeyen için sonu gelmez
bir sürpriz kaynağı olur.
