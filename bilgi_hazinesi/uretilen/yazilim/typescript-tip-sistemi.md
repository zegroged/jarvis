# TypeScript Tip Sistemi: Generics, Union/Intersection, Utility Types ve Narrowing

## Giriş: Tipler Neden Var?

TypeScript'in tip sistemi, çalışma zamanında (runtime) hiçbir iz bırakmayan, tamamen derleme zamanında (compile time) çalışan bir doğrulama katmanıdır. Bu ayrımı en baştan içselleştirmek gerekir çünkü TypeScript'te yazdığınız her tip, `tsc` derleyicisi JavaScript'e çevirdiğinde silinir; buna **type erasure** (tip silme) denir. Yani tipler, kodunuzun *nasıl davrandığını* değiştirmez; sadece kodunuzun *doğru olup olmadığını* siz kod yazarken kontrol eder.

Bu tasarım kararının kökeninde şu neden yatar: TypeScript, JavaScript'in üstüne oturan bir katman (superset) olmak zorundaydı. Var olan devasa JavaScript ekosistemiyle uyumlu kalmak için, tiplerin çalışma zamanı davranışına sızmaması gerekiyordu. Bunun bir sonucu, TypeScript'in tip sisteminin **yapısal (structural)** olmasıdır: iki tip aynı şekle sahipse birbiriyle uyumludur, isimlerinin aynı olmasına gerek yoktur. Bu, Java veya C# gibi **nominal** tip sistemine sahip dillerden gelen geliştiricilerin sık sık şaşırdığı bir noktadır.

```typescript
interface Nokta { x: number; y: number; }
function mesafe(p: Nokta): number { return Math.hypot(p.x, p.y); }

const obje = { x: 3, y: 4, renk: "kırmızı" };
mesafe(obje); // Geçerli! obje, Nokta'nın gerektirdiği tüm alanları içeriyor.
```

Burada `obje` bir `Nokta` olarak *bildirilmemiş* olmasına rağmen, `Nokta`'nın istediği `x` ve `y` alanlarını içerdiği için kabul edilir. Yapısal tipleme budur. Bu felsefe, tip sistemini anlamanın anahtarıdır; ilerideki her konu bu temele dayanır.

## Generics: Tip Düzeyinde Fonksiyonlar

### Tanım ve Kök Neden

Generics'i (jenerikler) anlamanın en doğru yolu, onları **tipler üzerinde çalışan fonksiyonlar** olarak düşünmektir. Sıradan bir fonksiyon değer alır ve değer döndürür; generic bir yapı ise tip alır ve tip döndürür. `T` gibi bir tip parametresi, tıpkı bir fonksiyon parametresi gibi, çağrı anında somut bir değerle (burada somut bir tiple) doldurulacak bir yer tutucudur.

Generics'in var olma nedeni şudur: Tip güvenliği ile yeniden kullanılabilirlik arasındaki gerilimi çözmek. Elinizde bir dizinin ilk elemanını döndüren bir fonksiyon olduğunu düşünün. Bunu her tip için ayrı ayrı yazmak (`ilkSayı`, `ilkString`...) sürdürülemez. Alternatif olarak `any` kullanırsanız tip bilgisini tamamen kaybedersiniz. Generics tam da bu ikilemi ortadan kaldırır: girdinin tipi ile çıktının tipi arasındaki **ilişkiyi** korur.

```typescript
function ilk<T>(dizi: T[]): T | undefined {
  return dizi[0];
}

const s = ilk([1, 2, 3]);        // s: number | undefined
const t = ilk(["a", "b"]);       // t: string | undefined
```

Dikkat edin, `T`'yi biz elle vermedik. TypeScript, argümana bakıp `T`'nin `number` olması gerektiğini **çıkarım (inference)** yoluyla anladı. Bu çıkarım mekanizması, generics'i pratikte kullanışlı kılan şeydir; aksi halde her çağrıda `ilk<number>([...])` yazmak zorunda kalırdık.

### Kısıtlar (Constraints) ve `extends`

Generic bir tip parametresi varsayılan olarak "herhangi bir tip" anlamına gelir, dolayısıyla onun üzerinde hiçbir varsayımda bulunamazsınız. Örneğin `T` tipindeki bir değerin `.length` özelliğine erişemezsiniz, çünkü her tipin böyle bir özelliği yoktur. İşte burada **kısıtlar** devreye girer: `extends` anahtar kelimesiyle, `T`'nin en azından belirli bir şekle uymasını şart koşarsınız.

```typescript
function uzunluk<T extends { length: number }>(x: T): number {
  return x.length;
}

uzunluk("merhaba");      // 7 — string'in length'i var
uzunluk([1, 2, 3]);      // 3 — array'in length'i var
uzunluk({ length: 10 }); // 10
// uzunluk(42);          // Hata: number'ın length'i yok
```

Buradaki `extends` kelimesi bir kalıtım (inheritance) değil, bir **alt-tip kısıtıdır**: "T, bu şekle atanabilir olmalı" der. Bu ayrım önemlidir; TypeScript'te `extends` bağlama göre farklı anlamlar taşır ve bu ilerideki koşullu tiplerde tekrar karşımıza çıkacaktır.

### Neden `any` Değil de Generics?

Yaygın bir hata, "nasılsa esneklik istiyorum" diyerek `any` kullanmaktır. Aradaki fark şudur: `any` tip sisteminden *çıkış kapısıdır*, tip kontrolünü tamamen kapatır ve hatalar sessizce çalışma zamanına sızar. Generics ise tip kontrolünü *korur*, sadece somut tipi ertelemenizi sağlar. `any` ile bir dizinin ilk elemanını alırsanız dönüş tipi de `any` olur ve o değere `.topaç()` gibi anlamsız bir çağrı yapsanız bile derleyici susar. Generics ile böyle bir hata anında yakalanır.

## Union ve Intersection Tipleri

### Union: "Şu VEYA Bu"

Union tipi (`A | B`), bir değerin *birkaç olası tipten biri* olabileceğini ifade eder. Kök mantığı **küme birleşimidir**: `string | number`, "string olabilecek tüm değerler ile number olabilecek tüm değerlerin birleşimi" demektir. Bu, JavaScript'in doğasıyla derinden uyumludur, çünkü gerçek dünyada bir fonksiyon pekâlâ ID olarak hem `string` hem `number` kabul edebilir.

Union'ın kritik ve sezgiye aykırı özelliği şudur: Bir union tipiyle çalışırken, TypeScript size yalnızca **tüm üyelerde ortak olan** üyelere erişim izni verir. Neden? Çünkü değerin gerçekte hangisi olduğunu bilmeden, yalnızca her ihtimalde güvenli olan işlemleri yapmanıza izin verilebilir.

```typescript
function biçim(id: string | number) {
  // id.toUpperCase(); // Hata! number'da toUpperCase yok.
  return id.toString(); // Geçerli, ikisinde de var.
}
```

Bu davranış can sıkıcı görünebilir ama aslında sizi hataya karşı korur. Değerin `string` olduğundan emin olmadan `toUpperCase()` çağırmak, çalışma zamanında çökebilecek bir koddur. Bu kısıtı aşmanın yolu **narrowing**'dir ve bir sonraki bölümün konusudur.

### Intersection: "Şu VE Bu"

Intersection tipi (`A & B`), bir değerin *aynı anda birden fazla tipin tüm özelliklerine* sahip olması gerektiğini söyler. Kök mantığı ilk bakışta kafa karıştırır: küme kesişimi gibi görünse de, nesne tiplerinde aslında **özelliklerin birleşimini** üretir.

```typescript
interface Kimlikli { id: string; }
interface Zamanlı { olusturulma: Date; }

type Kayit = Kimlikli & Zamanlı;
// Kayit hem id hem olusturulma içermek ZORUNDA.

const k: Kayit = { id: "abc", olusturulma: new Date() };
```

Bu neden "kesişim" olarak adlandırılır da özellikleri birleştirir? Çünkü tipleri, o tipe atanabilecek *değerlerin kümesi* olarak düşünmelisiniz. `Kimlikli` olan değerler kümesi ile `Zamanlı` olan değerler kümesinin *kesişimi*, her iki gereksinimi de sağlayan değerlerdir; ki bunlar da ister istemez her iki özelliği birden taşır. Terminoloji değerler kümesine göre doğrudur, özellik listesine göre ters görünür.

Intersection'ın bir tuzağı, **çakışan ilkel tiplerdir**. `string & number` gibi bir intersection `never` tipini üretir, çünkü hiçbir değer aynı anda hem string hem number olamaz; bu kümelerin kesişimi boştur.

## Narrowing: Tip Daraltma

### Tanım ve Kök Neden

**Narrowing** (tip daraltma), TypeScript'in bir kod bloğu içinde, çalışma zamanı kontrollerine bakarak bir değişkenin tipini daha spesifik bir tipe *indirgemesidir*. Bu, tip sisteminin belki de en zarif özelliğidir çünkü TypeScript, sizin yazdığınız normal JavaScript kontrol akışını (`if`, `typeof`, `instanceof`...) **anlar** ve tip bilgisini ona göre günceller. Bu yeteneğe **control flow analysis** (kontrol akışı analizi) denir.

Kök neden şudur: Union tipler size güvenli ama kısıtlı erişim verir. Ancak gerçek kodda, çoğu zaman değerin hangi türden olduğunu çalışma zamanında ayırt edebiliriz. Narrowing, bu çalışma zamanı bilgisini derleme zamanı tip bilgisine tercüme ederek union'ların kısıtını mantıklı bir şekilde gevşetir.

```typescript
function biçim(id: string | number) {
  if (typeof id === "string") {
    return id.toUpperCase(); // Burada id artık sadece string!
  }
  return id.toFixed(2);      // Burada id artık sadece number!
}
```

`if` bloğunun içinde TypeScript, `id`'nin `string` olduğunu *biliyor*, çünkü `typeof` kontrolünü mantıksal olarak takip etti. `else` dalında ise geriye yalnızca `number` kaldığını çıkardı. Hiçbir tip cast'i (`as`) yazmadığımıza dikkat edin; daraltma tamamen otomatiktir.

### Narrowing Teknikleri

TypeScript'in tanıdığı başlıca daraltma araçları şunlardır ve her biri farklı bir senaryoya hitap eder:

- **`typeof` koruması:** İlkel tipler (`string`, `number`, `boolean`, `symbol`, `bigint`, `undefined`, `function`, `object`) için kullanılır.
- **`instanceof` koruması:** Sınıflar ve prototype zinciri olan nesneler için (`if (hata instanceof Error)`).
- **`in` operatörü:** Bir özelliğin varlığına göre daraltma (`if ("wingCount" in hayvan)`), özellikle nesne union'larında güçlüdür.
- **Eşitlik kontrolleri:** `if (x === null)` veya `if (x !== undefined)` gibi kontroller, `null` ve `undefined`'ı ayıklamak için kullanılır.
- **Truthiness (doğruluk) kontrolü:** `if (deger)` yazarak `null`, `undefined`, `0`, `""` gibi falsy değerleri elemek. Ama dikkat: `0` ve `""` de falsy'dir, bu yüzden sayısal veya string değerlerde bu yöntem tuzak barındırır.

### Discriminated Unions: Narrowing'in Zirvesi

Narrowing'in en güçlü ve en çok önerilen kalıbı **discriminated union** (ayırt edici union) kalıbıdır. Buradaki fikir, union'ın her üyesine ortak isimli fakat farklı **literal** değerli bir "etiket" alanı koymaktır. TypeScript bu etikete bakarak hangi üyede olduğunuzu kusursuzca çıkarır.

```typescript
type Sekil =
  | { tur: "daire"; yariCap: number }
  | { tur: "kare"; kenar: number }
  | { tur: "dikdortgen"; en: number; boy: number };

function alan(s: Sekil): number {
  switch (s.tur) {
    case "daire":     return Math.PI * s.yariCap ** 2;
    case "kare":      return s.kenar ** 2;
    case "dikdortgen": return s.en * s.boy;
  }
}
```

`tur` alanı burada **discriminant** (ayırt edici) rolündedir. `case "daire"` içine girdiğinizde TypeScript, `s`'nin yalnızca `{ tur: "daire"; yariCap: number }` olabileceğini bilir ve `s.yariCap`'e güvenle erişmenize izin verir. Bu kalıbın gücü, kodun hem tip güvenli hem de okunabilir olmasında yatar. Ayrıca sonraki bölümde göreceğimiz **exhaustiveness checking** (bütünlük kontrolü) ile birlikte kullanıldığında, ileride yeni bir şekil eklerseniz derleyici eksik `case`'i size gösterir.

### `never` ve Bütünlük Kontrolü

`never` tipi, "hiçbir zaman gerçekleşmeyecek değer" anlamına gelir ve narrowing ile derin bir ilişkisi vardır. Bir union'ın tüm olasılıklarını tükettiğinizde, geriye `never` kalır. Bunu bir güvenlik ağı olarak kullanabilirsiniz:

```typescript
function alan(s: Sekil): number {
  switch (s.tur) {
    case "daire":      return Math.PI * s.yariCap ** 2;
    case "kare":       return s.kenar ** 2;
    case "dikdortgen": return s.en * s.boy;
    default:
      const _tuketilmemis: never = s; // Yeni bir şekil eklenirse burada hata!
      throw new Error(`Bilinmeyen şekil: ${_tuketilmemis}`);
  }
}
```

Eğer `Sekil` union'ına dördüncü bir üye (mesela üçgen) eklerseniz ve `case`'ini yazmayı unutursanız, `s` `default` dalında artık `never` olmayacak, dolayısıyla `never` tipine atama hata verecektir. Bu, derleyiciyi bir muhasebeci gibi kullanmanın klasik ve çok değerli bir örneğidir.

## Utility Types: Hazır Tip Dönüşümleri

### Tanım ve Kök Neden

**Utility types** (yardımcı tipler), TypeScript'in yerleşik olarak sunduğu, var olan bir tipten yeni bir tip *türeten* generic yapılardır. Var olma nedenleri **DRY (Don't Repeat Yourself)** ilkesidir: Bir tipi bir kez tanımlayıp, onun "salt okunur hali", "kısmi hali", "yalnızca bazı alanları" gibi varyasyonlarını elle tekrar yazmak yerine türetmek. Bu, tipler arasındaki ilişkiyi de canlı tutar; kaynak tip değişirse türetilen tip otomatik güncellenir.

Bu yardımcı tiplerin çoğu, aslında **mapped types** ve **conditional types** gibi daha temel mekanizmalar üzerine inşa edilmiştir; yani sihir değildirler, siz de benzerlerini yazabilirsiniz.

### En Sık Kullanılanlar ve Ne İşe Yaradıkları

`Partial<T>`, bir tipin tüm alanlarını isteğe bağlı (optional) yapar. Kök mantığı, her alana `?` işareti eklemektir. Tipik kullanımı, bir güncelleme fonksiyonudur; bir nesnenin yalnızca bazı alanlarını güncellerken diğerlerini zorunlu tutmak istemezsiniz.

```typescript
interface Kullanici { ad: string; yas: number; email: string; }

function guncelle(mevcut: Kullanici, degisiklik: Partial<Kullanici>): Kullanici {
  return { ...mevcut, ...degisiklik };
}
guncelle(user, { yas: 31 }); // Yalnızca yas'ı vermek yeterli.
```

`Required<T>`, `Partial`'ın tersidir; tüm alanları zorunlu yapar. `Readonly<T>`, tüm alanları `readonly` yaparak yeniden atamayı derleme zamanında engeller (ama unutmayın, bu sadece yüzeysel/shallow bir korumadır ve iç içe nesneleri dondurmaz).

`Pick<T, K>` bir tipten yalnızca belirttiğiniz `K` alanlarını seçerek yeni bir tip oluşturur; `Omit<T, K>` ise tam tersine, belirttiğiniz alanları *çıkararak* yeni tip üretir. Bu ikisi, büyük tiplerden odaklı alt kümeler türetmek için vazgeçilmezdir.

```typescript
type PublicKullanici = Omit<Kullanici, "email">;  // ad ve yas kaldı
type Kimlik = Pick<Kullanici, "ad" | "email">;    // sadece ad ve email
```

`Record<K, V>`, anahtarları `K`, değerleri `V` tipinde olan bir nesne (sözlük/map) tipi kurar. `Record<string, number>` gibi. `Exclude<T, U>` ve `Extract<T, U>` ise union tipleri üzerinde çalışır: `Exclude` belirtilen üyeleri union'dan atar, `Extract` yalnızca eşleşenleri tutar. `NonNullable<T>` ise `null` ve `undefined`'ı bir tipten söküp atar.

Fonksiyonlarla ilgili olanlar da vardır: `ReturnType<F>` bir fonksiyon tipinin dönüş tipini çıkarır, `Parameters<F>` parametre tiplerini bir tuple olarak verir. Bunlar, başka birinin yazdığı fonksiyonların tiplerini "geri mühendislikle" çıkarmak istediğinizde çok değerlidir.

### Utility Types'ın Perde Arkası: Mapped Types

`Partial`'ın nasıl çalıştığını anlamak, tip sistemini gerçekten kavradığınızı gösterir. Tanımı aşağı yukarı şöyledir:

```typescript
type Partial<T> = {
  [K in keyof T]?: T[K];
};
```

Buradaki `[K in keyof T]` ifadesi bir **mapped type**'tır: `T`'nin tüm anahtarları (`keyof T`) üzerinde döngü kurar, her `K` anahtarı için `T[K]` tipini alır (buna **indexed access** denir) ve başına `?` ekleyerek isteğe bağlı yapar. Yani utility types sihirli değil, sizin de yazabileceğiniz mapped type kalıplarıdır. Bu iç görü, kendi ihtiyaçlarınıza özel utility'ler yazmanın kapısını açar.

## Yaygın Hatalar ve Tuzaklar

**`any`'yi bir çözüm sanmak.** En sık ve en zararlı hata budur. `any`, karşılaştığınız bir tip hatasını "susturur" ama sorunu çözmez; yalnızca çalışma zamanına erteler. Zorunlu kaldığınızda `any` yerine `unknown` kullanın. `unknown` da her değeri kabul eder ama farkı, siz narrowing yapmadan o değerle *hiçbir şey yapmanıza izin vermez*. Yani `unknown`, sizi güvenli olmaya zorlar; `any` ise tüm koruma bariyerlerini kaldırır.

**Tip iddiasını (`as`) narrowing sanmak.** `deger as string` yazmak, TypeScript'e "bana güven, bu bir string" demektir; herhangi bir çalışma zamanı kontrolü yapmaz. Eğer değer aslında string değilse, TypeScript susar ama kod çalışma zamanında çöker. `as`, tip sistemine yalan söyleme aracıdır ve yalnızca derleyicinin sizden daha az bilgiye sahip olduğu dar durumlarda, bilinçli olarak kullanılmalıdır. Gerçek daraltma için her zaman `typeof`, `instanceof`, `in` gibi çalışma zamanı kontrollerini tercih edin.

**Union'da ortak olmayan üyeye erişmeye çalışmak.** Yukarıda değindiğimiz gibi, daraltma yapmadan bir union üyesinin özel özelliğine erişemezsiniz. Bunu `as` ile aşmaya çalışmak yerine, `in` operatörü veya discriminated union kalıbı ile doğru şekilde daraltın.

**Fonksiyon çağrısından sonra kaybolan narrowing.** İnce bir tuzak: Bir değişkeni daralttıktan sonra bir fonksiyon çağırırsanız, TypeScript o fonksiyonun değişkeni değiştirmiş olabileceğini varsayar ve bazı durumlarda daraltmayı geçersiz kılar. Bu özellikle nesne özelliklerinde görülür. Çözüm genellikle daraltılmış değeri yerel bir `const` değişkene almaktır; `const`'lar yeniden atanamayacağı için TypeScript daraltmayı korur.

**`Object.keys` ve tip genişlemesi.** `Object.keys(nesne)` her zaman `string[]` döndürür, `(keyof T)[]` değil. Bu, TypeScript'in kasıtlı bir güvenlik kararıdır çünkü çalışma zamanında nesnede tipte bildirilmemiş fazladan anahtarlar olabilir (yapısal tipleme nedeniyle). Bunu bilmeden `keyof` beklerseniz şaşırırsınız.

**Aşırı generik yazmak.** Her fonksiyonu generic yapmak bir erdem değildir. Eğer bir tip parametresi yalnızca tek bir yerde geçiyor ve girdi-çıktı arasında bir ilişki kurmuyorsa, muhtemelen o generic gereksizdir ve kodu okunmaz kılar. Generics, iki veya daha fazla nokta arasında tip *ilişkisi* olduğunda anlamlıdır.

## En İyi Pratikler

**`strict` modunu açık tutun.** `tsconfig.json` içindeki `strict` bayrağı, `strictNullChecks` dahil bir dizi katı kontrolü etkinleştirir. Özellikle `strictNullChecks`, `null` ve `undefined`'ı tip sisteminde birinci sınıf vatandaş yapar ve "cannot read property of undefined" gibi JavaScript'in en yaygın çalışma zamanı hatalarını derleme zamanına taşır. Yeni projede bunu kapatmak, tip sisteminin en büyük faydasından vazgeçmek demektir.

**Union modellerken discriminated union'ı tercih edin.** Bir değerin birkaç farklı "durumu" varsa (yükleniyor / başarılı / hatalı gibi), her duruma ortak bir `tur` veya `durum` alanı ekleyin. Bu, hem narrowing'i kusursuz kılar hem de `never` ile bütünlük kontrolü yapmanıza olanak tanır.

**`unknown`'ı dış dünyanın kapısında kullanın.** API yanıtları, `JSON.parse` çıktısı, kullanıcı girdisi gibi tipini gerçekten bilmediğiniz veriler için `any` yerine `unknown` kullanın ve içeri girer girmez narrowing veya bir doğrulama (validation) kütüphanesiyle tipi güvenceye alın. Böylece güvensiz veri, kod tabanınızın derinlerine tipsiz sızmaz.

**Tipleri türetin, tekrar yazmayın.** Aynı şekli iki yerde elle tanımlamak yerine, birini kaynak alıp diğerini utility types (`Pick`, `Omit`, `Partial`) ile türetin. Tek bir doğruluk kaynağı (single source of truth) tutmak, tiplerin zamanla birbirinden kopmasını (drift) engeller.

**Kısıtları (`extends`) generic'lerde cömertçe kullanın.** Bir generic fonksiyon içinde tip parametresinin bir özelliğine erişecekseniz, o özelliği garanti eden bir kısıt koyun. Bu hem derleyiciye ne beklediğinizi anlatır hem de fonksiyonu çağıranlara net bir sözleşme sunar.

**`as` kullanımını gerekçelendirin.** Tip iddiasını mecbur kaldıkça, mümkünse bir yorum satırıyla *neden* güvenli olduğunu açıklayarak kullanın. `as any` ve ardından `as` zinciri (`x as unknown as Y`) gördüğünüzde bu, tip modelinizde bir sorun olduğunun kuvvetli bir işaretidir; kaçmak yerine tasarımı düzeltmeye çalışın.

## Sonuç

TypeScript'in tip sistemi, yüzeyde bir sözdizimi yığını gibi görünse de altında tutarlı bir mantık yatar: tipler değer *kümeleridir*, generics bu kümeler üzerinde çalışan fonksiyonlardır, union ve intersection bu kümeleri birleştirip kesiştirir, narrowing ise çalışma zamanı bilgisini kullanarak kümeleri daraltır. Utility types ise bu temellerin üstüne kurulmuş hazır araçlardır. Bu mekanizmaları "ne yaptıklarını" ezberleyerek değil, "neden böyle davrandıklarını" anlayarak öğrendiğinizde, tip sistemi sizi kısıtlayan bir bürokrasi olmaktan çıkıp, hataları siz daha kodu çalıştırmadan yakalayan güçlü bir yardımcıya dönüşür.
