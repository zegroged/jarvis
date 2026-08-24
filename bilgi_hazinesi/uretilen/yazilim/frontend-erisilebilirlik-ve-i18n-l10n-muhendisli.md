# Frontend Erişilebilirlik (a11y) ve I18n/L10n Mühendisliği

## Giriş: Neden Bu İki Konu Birlikte Anılır?

Profesyonel frontend geliştirme, yalnızca "çalışan" bir arayüz üretmekle bitmez. Bir arayüzün **herkes tarafından** ve **her yerde** kullanılabilir olması gerekir. Bu iki gereksinim, iki ayrı mühendislik disiplinini doğurur:

- **Accessibility (a11y):** Görme, işitme, motor veya bilişsel farklılıkları olan kullanıcıların arayüzü ekran okuyucu, klavye, ses komutu gibi yardımcı teknolojilerle (assistive technology) kullanabilmesi.
- **Internationalization (i18n) ve Localization (l10n):** Arayüzün farklı diller, yazı yönleri, para birimleri, tarih formatları ve kültürel beklentilere uyarlanabilmesi.

"a11y" ve "i18n" kısaltmaları, kelimenin ilk ve son harfi arasında kaç harf olduğunu gösterir (accessibility = a + 11 harf + y). Bu iki alan sık sık birlikte anılır çünkü ikisi de **görünmeyen kullanıcıyı** düşünme disiplinidir: geliştiricinin kendi bağlamının dışındaki insanları ciddiye almasını gerektirir. Ayrıca teknik olarak çakışırlar; örneğin bir ekran okuyucunun metni doğru seslendirmesi için hem semantik doğru HTML (a11y) hem de doğru `lang` özniteliği (i18n) gerekir.

## Bölüm 1: Erişilebilirlik (a11y)

### 1.1 Semantik HTML: Temel Katman

Erişilebilirliğin kök nedeni şudur: yardımcı teknolojiler, ekrandaki pikselleri değil, **DOM'un semantik yapısını** okur. Ekran okuyucu (screen reader; örneğin NVDA, JAWS, VoiceOver) sayfayı, tarayıcının oluşturduğu **accessibility tree** üzerinden gezinir. Bu ağaç, her elemana bir **role** (rol), **name** (isim/etiket), **value** (değer) ve **state** (durum) atar.

Semantik HTML kullanmak, bu ağacı otomatik ve doğru inşa etmenin en güvenilir yoludur:

```html
<!-- Doğru: tarayıcı buna otomatik "button" rolü verir, -->
<!-- klavye ile odaklanabilir, Enter/Space ile tetiklenir -->
<button type="button" onclick="kaydet()">Kaydet</button>

<!-- Yanlış: bu sadece görsel olarak butona benzer -->
<!-- Klavye ile odaklanamaz, ekran okuyucu "button" demez -->
<div class="btn" onclick="kaydet()">Kaydet</div>
```

`<div>` ile buton "taklit etmek", en yaygın erişilebilirlik hatalarından biridir. `<div>`'i erişilebilir yapmak için `role="button"`, `tabindex="0"`, `onkeydown` (Enter ve Space için), `aria-pressed` gibi çok sayıda özniteliği elle eklemeniz gerekir; oysa `<button>` bunların hepsini ücretsiz verir. **Temel kural:** Her zaman doğru semantik elemanı tercih et, ARIA'ya ancak semantik HTML yetmediğinde başvur.

### 1.2 ARIA: Ne Zaman ve Nasıl

**ARIA (Accessible Rich Internet Applications)**, HTML'in tek başına ifade edemediği durumları accessibility tree'ye bildiren bir öznitelik kümesidir. Üç ana grubu vardır:

- **Roles:** `role="tablist"`, `role="dialog"`, `role="alert"` — elemanın ne olduğunu söyler.
- **Properties:** `aria-label`, `aria-labelledby`, `aria-describedby`, `aria-haspopup` — genellikle değişmeyen tanımlayıcı bilgiler.
- **States:** `aria-expanded`, `aria-checked`, `aria-disabled`, `aria-hidden` — dinamik olarak değişen durumlar.

ARIA'nın en kritik ve en çok ihlal edilen kuralı, resmî spesifikasyonda **"First Rule of ARIA"** olarak geçer: *Eğer bir HTML elemanı veya özniteliği ihtiyacınız olan semantiği zaten sağlıyorsa, ARIA kullanmayın.* Çünkü ARIA yalnızca accessibility tree'yi değiştirir; **davranış eklemez**. `role="button"` verdiğiniz bir `<div>`, tıklanabilir görünse de klavye olayını kendiliğinden işlemez.

İkinci kritik kural: **"No ARIA is better than bad ARIA"** — yanlış ARIA, hiç ARIA olmamasından kötüdür. Yanlış bir `aria-label` veya çelişkili bir `role`, ekran okuyucu kullanıcısını tamamen yanlış yönlendirebilir.

```html
<!-- Özel bir açılır menü (custom dropdown), semantik HTML yetmediğinde -->
<button aria-haspopup="listbox" aria-expanded="false" aria-controls="dil-listesi" id="dil-btn">
  Dil: Türkçe
</button>
<ul role="listbox" id="dil-listesi" aria-labelledby="dil-btn" hidden>
  <li role="option" aria-selected="true">Türkçe</li>
  <li role="option">English</li>
</ul>
```

Burada `aria-expanded` durumunu JavaScript ile menü açılıp kapandıkça **güncellemek zorundasınız**. Statik ARIA, kullanıcıya yalan söyler.

### 1.3 Klavye Erişilebilirliği ve Odak Yönetimi

Motor engelli, kör veya "power user" birçok kişi fareyi hiç kullanmaz. Bu yüzden **her etkileşimli eleman klavye ile erişilebilir olmalıdır**. Temel ilkeler:

- **Focus order:** Tab tuşuyla gezinme sırası, görsel/mantıksal sırayla uyumlu olmalı. Bunu DOM sırasıyla sağlayın; `tabindex="0"` doğal akışa katar, `tabindex="-1"` programatik odak için (kullanıcı Tab ile ulaşamaz ama JS `.focus()` ile odaklayabilir) kullanılır. **Pozitif `tabindex` (1, 2, 3...) neredeyse her zaman bir hatadır** çünkü doğal sırayı bozar ve bakımı imkânsızlaşır.
- **Focus visible:** Odaklanan elemanın görsel bir göstergesi (focus ring) olmalı. `outline: none` yazıp yerine bir şey koymamak, klavye kullanıcısını nerede olduğunu göremez hâle getirir — ciddi bir erişilebilirlik hatasıdır. Modern çözüm `:focus-visible` sözde-sınıfıdır; fareyle tıklamada halka göstermez, klavyeyle gezinirken gösterir.
- **Focus trapping:** Bir modal dialog açıldığında odak modalın içinde hapsedilmeli (Tab modalın dışına kaçmamalı), modal kapanınca odak onu açan elemana geri dönmelidir. Bu "focus restoration", çok atlanan ama kritik bir detaydır.

```css
/* Klavye kullanıcısı için görünür, fare kullanıcısını rahatsız etmeyen odak halkası */
:focus-visible {
  outline: 2px solid #005fcc;
  outline-offset: 2px;
}
```

### 1.4 Görsel ve Algısal Gereksinimler

- **Renk kontrastı:** WCAG, normal metin için en az **4.5:1**, büyük metin için **3:1** kontrast oranı önerir (AA seviyesi). Bilgiyi **yalnızca renkle** aktarmayın; renk körü kullanıcılar için ikon, metin veya desenle destekleyin. "Kırmızı alanlar hatalı" demek yerine bir hata ikonu da ekleyin.
- **Alternatif metin (alt text):** Anlam taşıyan görsellere `alt` özniteliği verin. Yalnızca dekoratif görseller için `alt=""` (boş) bırakılır; bu ekran okuyucuya "bu görseli atla" der. `alt`'yi tümden silmek ise ekran okuyucunun dosya adını okumasına yol açar — kötüdür.
- **`prefers-reduced-motion`:** Vestibüler bozukluğu olan kullanıcılar için, bu medya sorgusuyla animasyonları azaltın veya kaldırın.

### 1.5 WCAG ve POUR İlkeleri

**WCAG (Web Content Accessibility Guidelines)**, W3C tarafından yayımlanan uluslararası standarttır. Dört temel ilke üzerine kuruludur; kısaltması **POUR**:

- **Perceivable (Algılanabilir):** İçerik, kullanıcının algılayabileceği bir biçimde sunulmalı (alt text, altyazı, kontrast).
- **Operable (Kullanılabilir):** Arayüz klavye dâhil farklı yöntemlerle çalıştırılabilmeli.
- **Understandable (Anlaşılabilir):** İçerik ve davranış öngörülebilir olmalı.
- **Robust (Sağlam):** İçerik, farklı yardımcı teknolojilerle uyumlu çalışabilmeli.

Uyum seviyeleri **A, AA, AAA** olarak artar. Sektörde yaygın hedef **AA** seviyesidir; birçok kamu ve kurumsal düzenleme (örneğin AB'nin EN 301 549 standardı, ABD'de Section 508) bunu referans alır. AAA çoğu içerik için gerçekçi bir hedef değildir. Sürüm olarak WCAG 2.1 ve 2.2 yaygın kullanımdadır; 2.2, dokunmatik hedef boyutu ve odak görünürlüğü gibi ek kriterler getirmiştir.

## Bölüm 2: Internationalization (i18n) ve Localization (l10n)

### 2.1 Tanımlar ve Ayrım

Bu iki terim sık karıştırılır:

- **Internationalization (i18n):** Yazılımı, **kod değişikliği gerektirmeden** farklı dillere ve bölgelere uyarlanabilir hâle getirme *mühendisliği*. Bu bir mimari hazırlıktır: metinleri koddan ayırmak, tarih/sayı formatlamayı locale'e devretmek, RTL'i desteklemek.
- **Localization (l10n):** Belirli bir hedef için gerçek uyarlama *işi*: çeviri, yerel para birimi, kültürel imgeler, yasal metinler.

Kısa formül: **i18n altyapıyı hazırlar, l10n içeriği doldurur.** i18n'i baştan yapmazsanız, l10n imkânsız veya çok pahalı olur. Sonradan i18n eklemek, tüm string'leri koddan çıkarmak anlamına gelir — çok maliyetli bir refactor.

### 2.2 String Externalization ve Çeviri Anahtarları

i18n'in kalbi, kullanıcıya gösterilen tüm metinleri koddan çıkarıp **kaynak dosyalarına (resource bundles)** taşımaktır. Kod, metnin kendisini değil bir **anahtar (key)** referans alır:

```js
// Yanlış: metin koda gömülü, çevrilemez
button.textContent = "Sepete Ekle";

// Doğru: anahtar üzerinden, aktif locale'e göre çözülür
button.textContent = t("cart.addButton");
```

```json
// tr.json
{ "cart.addButton": "Sepete Ekle" }
// en.json
{ "cart.addButton": "Add to Cart" }
```

**Yaygın hata — string concatenation:** Cümleyi parçalayıp birleştirmek, çeviriyi bozar çünkü diller kelime sırasını farklı kurar:

```js
// Yanlış: "You have " + count + " messages"
//   Türkçe'de sıra farklı, çoğul kuralı farklı, bu yaklaşım çöker.
// Doğru: parametreli, tam cümle şablonu
t("inbox.count", { count: 5 });
// tr: "{count} mesajınız var"  |  en: "You have {count} messages"
```

### 2.3 Pluralization (Çoğullaştırma): Sanılandan Zor

Çoğul kuralları dile göre kökten değişir. İngilizce'de iki biçim vardır (1 → "message", diğerleri → "messages"). Ama:

- **Türkçe'de** sayı belirtildiğinde isim tekil kalır: "5 mesaj", "1 mesaj" — İngilizce'deki gibi "5 mesajlar" **denmez**. Bu, çeviride sık yapılan bir hatadır.
- **Lehçe, Rusça, Arapça** gibi diller 3-6 farklı çoğul kategorisine sahiptir (few, many, other...).

Bu yüzden çoğullaştırmayı elle `if (count === 1)` ile yönetmek yanlıştır. Standart çözüm, Unicode **CLDR (Common Locale Data Repository)** plural kurallarını kullanan kütüphaneler ve tarayıcıdaki `Intl.PluralRules` API'sidir. Format olarak **ICU MessageFormat** yaygın standarttır:

```
{count, plural, one {# mesaj} other {# mesaj}}
```

### 2.4 Locale-Aware Formatlama: `Intl` API

Tarih, sayı, para birimi ve sıralama formatlarını **asla elle** kurmayın. Tarayıcıların yerleşik **`Intl`** nesnesi bunu locale verisiyle doğru yapar:

```js
// Sayı ve para birimi
new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY" })
  .format(1234.5);   // "₺1.234,50"  (binlik ayıracı nokta, ondalık virgül)
new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })
  .format(1234.5);   // "$1,234.50"  (tam tersi ayıraçlar)

// Tarih
new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" })
  .format(new Date()); // "5 Temmuz 2026"

// Sıralama (Türkçe'de ç, ğ, ı, ö, ş, ü doğru sıralanır)
["zebra", "çilek", "armut"].sort(new Intl.Collator("tr").compare);
```

**Kritik nokta — Türkçe "i" sorunu:** Türkçe'de küçük "i"nin büyük hâli noktalı "İ", büyük "I"nın küçük hâli noktasız "ı"dır. `str.toLowerCase()` gibi locale'siz çağrılar bunu bozar; `"I".toLowerCase()` çoğu ortamda "i" üretir ama Türkçe bağlamda "ı" olmalıdır. Locale duyarlı `toLocaleLowerCase("tr")` kullanın. Bu, özellikle case-insensitive karşılaştırmalarda (örneğin kullanıcı adı doğrulama) gerçek hatalara yol açar.

### 2.5 RTL (Right-to-Left) Desteği

Arapça, İbranice, Farsça gibi diller sağdan sola yazılır. RTL desteği yalnızca metni ters çevirmek değildir; tüm **düzenin yönü** değişir: menü sağda başlar, ilerleme çubukları sağdan sola dolar, oklar yön değiştirir.

Kök mekanizma, HTML'deki `dir="rtl"` özniteliği ve CSS'in **logical properties** (mantıksal özellikler) sistemidir:

```css
/* Yanlış: fiziksel yön, RTL'de bozulur */
.card { margin-left: 16px; padding-right: 8px; }

/* Doğru: mantıksal yön, dir'e göre otomatik uyum sağlar */
.card { margin-inline-start: 16px; padding-inline-end: 8px; }
```

`margin-inline-start`, LTR'de sol, RTL'de sağ kenar anlamına gelir; tarayıcı `dir`'e göre çözer. `left/right/text-align: left` yerine `start/end` kullanmak, tek kod tabanıyla iki yönü de desteklemenin doğru yoludur. Ayrıca `<html lang="ar" dir="rtl">` doğru ayarlanmalıdır; `lang` özniteliği hem ekran okuyucunun doğru dilde seslendirmesi (a11y ile kesişim) hem de doğru yazı tipi/tireleme için gereklidir.

### 2.6 Metin Genişlemesi ve Layout Dayanıklılığı

Aynı anlam, farklı dillerde çok farklı uzunlukta olur. Almanca ve Fince metinler İngilizce'ye göre **%30-40'a kadar daha uzun** olabilir; kısa etiketlerde bu oran daha da yükselir. Sabit genişlikli butonlar ve tek satıra sıkıştırılmış tasarımlar bu yüzden taşar. Kural: **layout'u metin uzamasına dayanıklı tasarlayın** — sabit yükseklik/genişlik yerine esneyen kutular, `overflow` kesme yerine kaydırma veya sarma.

## Bölüm 3: Test, Tespit ve Doğru Süreç

### 3.1 Otomatik ve Manuel Test Dengesi

Otomatik araçlar (örneğin `axe-core` motoru, Lighthouse'un a11y denetimi) faydalıdır ama **erişilebilirlik sorunlarının yalnızca bir kısmını** yakalar; genel kabul, otomatik testlerin WCAG ihlallerinin kabaca üçte birini bulabildiğidir. Kalan kısmı yalnızca manuel test ortaya çıkarır:

- **Klavye testi:** Fareyi bırakın, tüm akışı yalnızca Tab, Shift+Tab, Enter, Space, ok tuşlarıyla tamamlamayı deneyin.
- **Ekran okuyucu testi:** NVDA (Windows, ücretsiz) veya VoiceOver (macOS/iOS) ile gerçekten dinleyin.
- **Zoom/reflow:** Sayfayı %200 büyütün, yatay kaydırma çıkmamalı.

i18n tarafında **pseudo-localization** güçlü bir tekniktir: metinleri yapay olarak uzatıp aksanlı karakterlerle değiştirerek (örneğin "Kaydet" → "[Ķàÿđéţ~~~]") çeviriye hazır olmayan, koda gömülü string'leri ve taşan layout'ları çeviriyi beklemeden görünür kılar.

### 3.2 Yaygın Hatalar Özeti

- **`<div>` ile buton/link taklidi** — semantik eleman kullanın.
- **`outline: none`** ile odak halkasını yok etmek — `:focus-visible` ile geri getirin.
- **Placeholder'ı label yerine kullanmak** — placeholder odaklanınca kaybolur ve düşük kontrastlıdır; her zaman gerçek `<label>` kullanın.
- **Yalnızca renkle bilgi vermek** — ikon/metin ekleyin.
- **String concatenation ile cümle kurmak** — parametreli şablon kullanın.
- **Elle tarih/sayı formatlama** — `Intl` API'ye devredin.
- **`toLowerCase()` ile Türkçe karakter bozmak** — `toLocaleLowerCase("tr")`.
- **Fiziksel CSS yönleri (`left/right`)** RTL'i kırar — logical properties.
- **`lang` özniteliğini atlamak** — hem a11y hem doğru yazı tipi için gerekli.
- **Statik ARIA state** — `aria-expanded` gibi durumları JS ile güncelleyin.

## Sonuç

Erişilebilirlik ve uluslararasılaştırma, "sonradan eklenecek" özellikler değil, mimarinin başında alınması gereken kararlardır. İkisinin de ortak dersi şudur: **arayüzü, sizin gibi olmayan ve sizin bağlamınızda olmayan kullanıcılar için tasarlayın.** Semantik HTML, doğru ARIA, klavye erişilebilirliği; string externalization, CLDR tabanlı çoğullaştırma, `Intl` formatlama ve logical properties — bunlar profesyonel frontend'in ayırt edici, ölçülebilir kalite göstergeleridir. Doğru yapıldığında yalnızca engelli veya farklı dildeki kullanıcılara değil, tüm kullanıcılara daha sağlam, daha öngörülebilir bir deneyim sunar.
