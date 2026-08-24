# Frontend Mimari (React ve Benzeri Kütüphaneler)

Modern web arayüzleri artık statik HTML sayfaları değil; kullanıcı etkileşimine anlık tepki veren, sunucudan bağımsız durum tutabilen, karmaşık veri akışlarını yöneten canlı uygulamalardır. Bu karmaşıklığı sürdürülebilir hale getirmek için ortaya çıkan yaklaşımların başında **bileşen tabanlı mimari** (component-based architecture) gelir. Bu makale, React'ı merkeze alarak modern frontend mimarisinin temel taşlarını (bileşen, tek yönlü veri akışı, state yönetimi ve render mekanizması) derinlemesine ele alır. Amaç bir API listesini ezberletmek değil; bu tasarımların *neden* böyle kurgulandığını, hangi problemi çözdüğünü ve nerede tökezlediğini akıl yürüterek anlatmaktır.

## Bileşen (Component) Kavramı

### Tanım

Bileşen, arayüzün bağımsız, yeniden kullanılabilir ve kendi mantığını kapsayan en küçük anlamlı parçasıdır. Bir düğme, bir form, bir yorum kartı ya da bütün bir sayfa birer bileşendir. React özelinde bileşen, girdi olarak bir `props` nesnesi alan ve çıktı olarak bir arayüz tanımı (React elementi) döndüren bir fonksiyondur:

```jsx
function KullaniciKarti({ isim, rol }) {
  return (
    <div className="kart">
      <h3>{isim}</h3>
      <span>{rol}</span>
    </div>
  );
}
```

Buradaki JSX (`<div>...</div>` sözdizimi) aslında JavaScript değildir; derleme aşamasında `React.createElement(...)` çağrılarına dönüştürülen bir söz dizimsel şekerdir (syntactic sugar). Yani JSX doğrudan DOM üretmez, sadece "arayüz şöyle görünmeli" diyen bir tarif (description) üretir. Bu ayrım, render mantığını anlamak için kritiktir.

### Kök Neden: Neden Bileşen?

Bileşen fikrinin altında yatan gerçek motivasyon, yazılım mühendisliğinin en eski ilkesidir: **karmaşıklığı yönetmek için parçalama ve kapsülleme** (decomposition and encapsulation). Bir arayüz büyüdükçe, tüm HTML'i, tüm CSS'i ve tüm etkileşim mantığını tek bir yerde tutmak imkânsız hale gelir. İnsan zihni belirli bir seferde ancak sınırlı sayıda ayrıntıyı tutabilir.

Bileşen, arayüzü **arayüz (interface)** ve **uygulama (implementation)** olarak ayırır. `KullaniciKarti` bileşenini kullanan kişi, onun içinde nasıl bir DOM yapısı olduğunu, hangi CSS sınıflarının kullanıldığını bilmek zorunda değildir; sadece `isim` ve `rol` göndermeyi bilir. Bu, tıpkı bir fonksiyonu çağırırken içindeki algoritmayı bilmemeniz gibidir. Kapsülleme sayesinde kartın iç yapısını değiştirseniz bile, onu kullanan kod bozulmaz. Bu, büyük ekiplerin aynı kod tabanında birbirini ezmeden çalışabilmesinin temelidir.

İkinci kök neden **birleştirilebilirliktir (composability)**. Küçük bileşenler birleşerek daha büyük bileşenleri oluşturur; onlar da birleşerek sayfaları oluşturur. Bir `Sayfa`, birden çok `Bolum`'den; bir `Bolum`, birden çok `Kart`'tan oluşur. Bu ağaç yapısı (component tree), zihinsel modelimizle örtüşür ve keyfi derinlikte karmaşıklığı düzenli tutmamızı sağlar.

### Somut Örnek ve Kompozisyon

Kalıtım (inheritance) yerine kompozisyonu tercih etmek, React felsefesinin merkezindedir. Bir bileşen, `children` prop'u aracılığıyla başka içerikleri sarmalayabilir:

```jsx
function Panel({ baslik, children }) {
  return (
    <section className="panel">
      <header>{baslik}</header>
      <div className="panel-govde">{children}</div>
    </section>
  );
}

// Kullanım
<Panel baslik="Ayarlar">
  <KullaniciKarti isim="Ayşe" rol="Yönetici" />
</Panel>
```

Burada `Panel`, içine ne konulacağını bilmez; sadece bir "boşluk" sunar. Bu, nesne yönelimli dünyada soyut sınıf kalıtımıyla çözülen problemi, çok daha esnek ve gevşek bağlı (loosely coupled) bir şekilde çözer. Kalıtım katı bir "bir çeşididir" (is-a) ilişkisi kurarken, kompozisyon esnek bir "içerir" (has-a) ilişkisi kurar ve bu esneklik arayüzlerin sürekli değişen doğasına çok daha uygundur.

## Tek Yönlü Veri Akışı (Unidirectional Data Flow)

### Tanım

Tek yönlü veri akışı, verinin uygulama içinde tek bir yönde, yukarıdan aşağıya (parent'tan child'a) aktığı bir tasarım ilkesidir. Üst bileşen, alt bileşenlere `props` aracılığıyla veri gönderir. Alt bileşen bu veriyi asla doğrudan değiştiremez; yalnızca okuyabilir. Değişiklik gerektiğinde, alt bileşen üst bileşene bir olay (event) bildirir ve değişikliği üst bileşenin kendisi yapar.

### Kök Neden: Neden İki Yönlü Değil de Tek Yönlü?

Bu, modern frontend mimarisinin belki de en önemli ve en yanlış anlaşılan kararıdır. Kök nedeni anlamak için bir önceki neslin problemine bakmak gerekir. AngularJS gibi erken dönem kütüphaneler **iki yönlü veri bağlama** (two-way data binding) sunuyordu: arayüzdeki bir değişiklik veriyi, verideki bir değişiklik arayüzü otomatik güncelliyordu. Kulağa büyülü gelir, ama büyüklük arttıkça kâbusa dönüşür.

Sorun şudur: iki yönlü bağlamada, uygulamanın herhangi bir anındaki durumunu (state) *hangi* değişikliğin tetiklediğini takip etmek imkânsız hale gelir. A bileşeni B'yi günceller, B'nin güncellenmesi C'yi tetikler, C de geri dönüp A'yı değiştirir. Bu, bir tür **kontrolsüz geri besleme döngüsü** (uncontrolled feedback loop) yaratır. Bir hata oluştuğunda, "bu değer neden bu hâle geldi?" sorusunun cevabı, birbirini tetikleyen onlarca gizli bağlantının içinde kaybolur.

Tek yönlü akış bu kaosu **öngörülebilirlik** (predictability) lehine feda eder. Veri her zaman aynı yönde aktığı için, ekranda gördüğünüz her şeyin kaynağı tek bir yere kadar izlenebilir. Uygulamanın durumu, bir anlık fotoğraf gibi düşünülebilir: "Şu andaki state buysa, arayüz kesinlikle şöyle görünür." Bu determinizm, hata ayıklamayı (debugging) inanılmaz derecede kolaylaştırır. Bir sorun gördüğünüzde, veriyi kaynağından ekrana doğru tek bir hat boyunca takip edersiniz; dallanan gizli yollar aramazsınız.

### Veri Aşağı, Olaylar Yukarı

Bu prensip genellikle "veri aşağı akar, olaylar yukarı kabarcıklanır" (data down, events up) şeklinde özetlenir. Alt bileşen, üst bileşenden aldığı bir fonksiyonu ("callback") çağırarak niyetini bildirir:

```jsx
function Ebeveyn() {
  const [sayac, setSayac] = React.useState(0);
  return <Cocuk deger={sayac} artir={() => setSayac(sayac + 1)} />;
}

function Cocuk({ deger, artir }) {
  return <button onClick={artir}>Sayı: {deger}</button>;
}
```

`Cocuk`, `sayac` değişkenine dokunamaz; sadece `artir` fonksiyonunu tetikler. Değişiklik kararını ve uygulamasını `Ebeveyn` verir. Böylece durum sahipliği (state ownership) her zaman açıktır. Bu netlik, "controlled component" (kontrollü bileşen) desenini mümkün kılar: form elemanlarının değeri her zaman React state'inden gelir, DOM'dan değil, ve tek gerçeklik kaynağı (single source of truth) korunur.

## State (Durum) Yönetimi

### Tanım

State, bir bileşenin zamanla değişebilen ve arayüzü etkileyen özel verisidir. `props` dışarıdan gelen ve değişmeyen (bileşen açısından salt-okunur) veriyken, state bileşenin kendi kontrolündeki, değiştikçe yeniden render tetikleyen veridir. Örneğin bir arama kutusundaki metin, bir modalın açık/kapalı oluşu ya da sunucudan gelen kullanıcı listesi state'tir.

### Kök Neden: State Neden Özel Muamele Görür?

Saf bir fonksiyon aynı girdiye her zaman aynı çıktıyı verir. Ancak arayüzler doğaları gereği durumludur (stateful): kullanıcı yazdıkça değişir, tıkladıkça açılır. React'ın çözmesi gereken temel problem şudur: "Veri değiştiğinde ekranı nasıl güncelleyeceğim?"

İki seçenek vardır. Birincisi, geleneksel yol: veri değişince DOM'u elle bulup değiştirmek (`document.getElementById(...).textContent = ...`). Bu yol kırılgandır; hangi DOM parçasının hangi veriye bağlı olduğunu programcının aklında tutması gerekir ve bu, hata kaynağıdır. İkincisi, React'ın yolu: veriyi değiştir, gerisini kütüphaneye bırak. İşte `useState` gibi mekanizmaların kök nedeni budur. State'i "özel" yapan şey, onun *reaktif* olmasıdır; yani değiştiğinde React'a "beni kullanan arayüzü yeniden hesapla" sinyali göndermesidir.

`useState`'in bir "hook" olarak tasarlanmasının da derin bir nedeni vardır. React fonksiyon bileşenleri her render'da baştan çalışır; yerel değişkenler her seferinde sıfırlanır. Peki bileşen, render'lar arasında değerini nasıl "hatırlar"? React, her bileşen için perde arkasında bir hafıza hücresi (state slot) tutar ve hook'ları çağrılma sırasına göre bu hücrelerle eşleştirir. **Hook'ların döngü, koşul veya iç içe fonksiyon içinde çağrılamamasının kuralının kök nedeni tam olarak budur:** React hangi hook'un hangi hücreye ait olduğunu yalnızca çağrılma sırasından bilir. Sıra bozulursa, state yanlış hücreyle eşleşir.

### Yerel State, Kaldırılan State ve Global State

State yönetimi aslında bir soruya cevap verme sanatıdır: "Bu veri nerede yaşamalı?"

**Yerel state:** Yalnızca tek bir bileşeni ilgilendiren veri (bir açılır menünün açık olup olmadığı gibi) o bileşende, `useState` ile tutulur. En basit ve en tercih edilir yoldur.

**Kaldırılan state (lifting state up):** İki kardeş bileşen aynı veriyi paylaşması gerektiğinde, veri onların ortak atasına "kaldırılır" ve props aracılığıyla ikisine de gönderilir. Bu, tek yönlü akışın doğal bir sonucudur. Ortak ata, tek gerçeklik kaynağı olur.

**Global state:** Uygulamanın çok farklı köşelerindeki bileşenler aynı veriye ihtiyaç duyduğunda (giriş yapmış kullanıcının kimliği, tema tercihi, sepet içeriği gibi), state'i her seferinde onlarca katman aşağıya props ile taşımak dayanılmaz hale gelir. Bu soruna **"prop drilling"** (prop delme) denir.

### Kök Neden: Prop Drilling ve Çözümü Context

Prop drilling, aradaki hiçbir bileşenin kullanmadığı bir veriyi, sırf en dipteki bir bileşene ulaştırmak için katman katman props olarak geçirmektir. Bu, ara bileşenleri gereksiz yere kirletir ve onları taşıdıkları veriye bağımlı kılar. React'ın buna cevabı **Context API**'dir. Context, bir veriyi bileşen ağacının belli bir noktasından "yayınlamayı" ve alttaki herhangi bir bileşenin araya girmeden bu veriyi doğrudan "abone olarak" almasını sağlar.

Ancak burada kritik bir tuzak vardır: Context bir **state yönetim aracı değildir**, bir **veri taşıma mekanizmasıdır**. Context değeri değiştiğinde, o context'i tüketen *tüm* bileşenler yeniden render olur. Sık değişen bir değeri (örneğin her tuş vuruşunda güncellenen bir form) tek bir dev context'e koymak, gereksiz render fırtınalarına yol açan yaygın bir hatadır.

### Harici State Kütüphaneleri Ne Zaman?

Uygulama büyüdükçe, karmaşık ve sık güncellenen paylaşımlı state için Redux, Zustand, Jotai gibi kütüphaneler devreye girer. Bunların kök amacı, state güncelleme mantığını bileşenlerden ayırıp merkezî, öngörülebilir ve test edilebilir bir yere toplamaktır. Redux'ın felsefesi bu prensibi uç noktaya taşır: state salt-okunurdur ve yalnızca saf fonksiyonlar (reducer) aracılığıyla, açıkça tanımlanmış "action"larla değiştirilebilir. Bu katılık, büyük ekiplerde state değişikliklerinin izlenebilir ve tekrar oynatılabilir (time-travel debugging) olmasını sağlar.

Önemli bir ayrım da **sunucu state'i** (server state) ile **istemci state'i** (client state) arasındadır. Sunucudan gelen ve önbelleklenmesi, tazelenmesi, senkronize edilmesi gereken veri (kullanıcı listeleri, ürünler) aslında bir *önbellek yönetimi* problemidir; saf istemci durumu değildir. Bu yüzden TanStack Query (React Query) gibi araçlar, bu iki sorumluluğu ayırmak için doğmuştur. Sunucu verisini Redux gibi genel bir store'a elle koymaya çalışmak, önbellek geçersizleştirme ve senkronizasyon karmaşasını yeniden icat etmeye zorlar; bu, çok yaygın bir mimari hatadır.

## Render Mekanizması ve Virtual DOM

### Tanım

Render, React'ın bir bileşeni çağırıp döndürdüğü arayüz tarifini hesaplaması sürecidir. Bu tarif, gerçek DOM değil, hafızadaki hafif bir JavaScript nesne ağacıdır: **Virtual DOM** (sanal DOM). React bu sanal ağacı gerçek tarayıcı DOM'una uygulayarak ekranı günceller.

### Kök Neden: Neden Virtual DOM?

Bunun kök nedeni performans ve programlama modeli arasındaki gerilimdir. En rahat programlama modeli şudur: "Veri her değiştiğinde, bütün arayüzü sıfırdan çiz." Bu, zihinsel olarak muazzam basittir çünkü kısmi güncelleme mantığını hiç düşünmezsiniz. Ancak gerçek DOM işlemleri (düğüm oluşturma, silme, yeniden yerleşim/reflow) tarayıcıda pahalıdır. Her veri değişiminde tüm DOM'u yeniden kurmak, arayüzü kabul edilemez derecede yavaşlatır.

Virtual DOM, bu iki dünyanın arasında bir köprüdür. React'a "tüm arayüzü baştan tarif et" dersiniz (ucuz, çünkü sadece JavaScript nesneleri), React da yeni tarifi bir öncekiyle karşılaştırır (**reconciliation** / uzlaştırma) ve *yalnızca gerçekten değişen minimum farkı* gerçek DOM'a uygular. Böylece siz basit modelle programlarken, kütüphane pahalı DOM işlemlerini en aza indirir. Kısaca Virtual DOM, "kolay yaz, verimli çalış" hedefinin bir aracıdır.

### Reconciliation ve `key`'in Kök Nedeni

Karşılaştırma algoritması, iki ağacı verimli eşleştirmek için sezgisel kurallar (heuristics) kullanır. Aynı konumdaki aynı tipteki elementi "aynı element" sayar ve içini günceller; tip değişmişse tüm alt ağacı söküp yeniden kurar.

Listelerde ise problem çıkar: React, listedeki hangi öğenin hangisine karşılık geldiğini konumdan bilemez. Bir öğe başa eklendiğinde, konum bazlı eşleştirme tüm öğeleri "değişmiş" sanır. İşte `key` prop'unun kök nedeni budur. `key`, her liste öğesine kararlı bir kimlik verir; böylece React öğeleri konumdan değil kimlikten eşleştirir. **Liste `key`'i olarak dizi indeksini kullanmak yaygın bir hatadır**, çünkü öğeler eklenip silindikçe indeksler kayar, kimlik bozulur ve React yanlış öğeleri yeniden kullanarak state karışıklığı ile hatalı arayüze yol açar. `key` her zaman verinin kendisinden gelen kararlı bir kimlik (örneğin veritabanı `id`'si) olmalıdır.

### Render Ne Zaman Tetiklenir?

Bir bileşen üç durumda yeniden render olur: kendi state'i değiştiğinde, aldığı props değiştiğinde ya da üst bileşeni yeniden render olduğunda. Buradaki en kritik ve en yanlış anlaşılan nokta üçüncüsüdür: **bir bileşen render olduğunda, propları değişmese bile varsayılan olarak tüm alt ağacı da yeniden render eder.** Bu genellikle bir sorun değildir çünkü render "ucuzdur" (sadece Virtual DOM hesabı; gerçek DOM ancak fark varsa güncellenir). Ancak alt ağaç büyük ve hesap pahalıysa, gereksiz render'lar performans sorununa dönüşür.

### Somut Örnek: Gereksiz Render

```jsx
function Uygulama() {
  const [sayi, setSayi] = React.useState(0);
  return (
    <>
      <button onClick={() => setSayi(sayi + 1)}>{sayi}</button>
      <PahaliListe />  {/* sayi değişince bu da render olur */}
    </>
  );
}
```

Burada `PahaliListe` sayacı hiç kullanmasa da, `Uygulama` her tıklamada render olduğu için o da render olur. Çözümler `React.memo` ile bileşeni props'una göre "hafızalamak", pahalı hesapları `useMemo` ile önbelleklemek ve callback fonksiyonlarını `useCallback` ile sabitlemektir. Ancak burada da bir tuzak vardır: bu optimizasyonlar bedelsiz değildir; karşılaştırma ve hafıza maliyeti taşırlar. **Erken optimizasyon**, yani her bileşeni ölçmeden `memo`'ya sarmak, kodu karmaşıklaştırır ve çoğu zaman ölçülebilir bir fayda getirmez. Doğru yaklaşım önce ölçmek (React DevTools Profiler ile), sonra gerçek darboğazı optimize etmektir.

## Yaygın Hatalar

Deneyimli mühendislerin bile sık düştüğü kalıcı tuzaklar vardır ve bunların çoğu, önceki bölümlerdeki kök nedenlerin yanlış anlaşılmasından doğar.

**State'i doğrudan mutasyona uğratmak.** `state.liste.push(x)` yapıp sonra state'i güncellemek işe yaramaz. React, değişikliği referans karşılaştırmasıyla (aynı nesne mi?) tespit eder. Diziyi yerinde değiştirmek referansı korur, React değişikliği fark etmez ve render tetiklenmez. Doğrusu yeni bir referans üretmektir: `setListe([...liste, x])`. Bu immutability (değişmezlik) ilkesi kaprisli bir kural değil; hızlı değişiklik tespitinin doğrudan bir gereğidir.

**Stale closure (bayat kapanış).** Bir olay dinleyicisi ya da `setTimeout`, tanımlandığı andaki state değerini "dondurur". Sonraki güncellemelerde bu fonksiyon hâlâ eski değeri görür. Bu, `useEffect` bağımlılık dizisinin eksik doldurulmasıyla sık yaşanır. Çözüm, state'e bağımlıyken güncelleyici fonksiyon biçimini kullanmaktır: `setSayi(onceki => onceki + 1)`.

**`useEffect`'i yanlış anlamak.** `useEffect`, bileşeni dış dünya ile (ağ istekleri, abonelikler, zamanlayıcılar) senkronize etmek içindir. Onu bir "değer değişince şunu hesapla" tetikleyicisi gibi kullanıp, effect içinde başka bir state güncelleyip zincirleme render'lar yaratmak yaygın bir anti-patterndir. Render sırasında türetilebilen bir değer için effect'e hiç gerek yoktur; doğrudan render sırasında hesaplanmalıdır.

**Effect temizliğini (cleanup) unutmak.** Bir abonelik açan ya da zamanlayıcı kuran effect, temizlik fonksiyonu döndürmezse; bileşen kaldırıldığında (unmount) ya da effect yeniden çalıştığında **memory leak** (bellek sızıntısı) ve hayalet güncellemeler oluşur. Örneğin bir WebSocket açıp kapatmayı unutmak, kaldırılmış bir bileşeni güncellemeye çalışmaya yol açar.

**Koşullu hook çağrısı.** Yukarıda açıklanan hook sırası kuralı ihlal edilir; `if (x) { useState(...) }` yazmak, sıra tutarsızlığından dolayı state hücrelerini karıştırır.

## En İyi Pratikler

**State'i mümkün olduğunca aşağıda ve yerel tutun.** Her veri global olmak zorunda değildir. State'i gerçekten ihtiyaç duyulan en dar kapsamda tutmak, gereksiz render'ları ve karmaşıklığı azaltır. State'i ancak paylaşım gerektiğinde "kaldırın".

**Tek gerçeklik kaynağını (single source of truth) koruyun.** Aynı bilgiyi iki yerde tutup senkron tutmaya çalışmak, tutarsızlık hatalarının ana kaynağıdır. Bir veri başka bir veriden türetilebiliyorsa, onu ayrı state'te saklamayın; render sırasında hesaplayın.

**Bileşenleri küçük ve tek sorumluluklu tutun.** Bir bileşen hem veri çekip hem karmaşık arayüz çiziyor hem de iş mantığı barındırıyorsa, büyümüş demektir. Veri getirme ile sunumu (presentational / container ayrımı ya da custom hook'larla mantık ayrımı) ayırmak, test edilebilirliği ve yeniden kullanımı artırır.

**Sunucu state'ini istemci state'inden ayırın.** Sunucudan gelen veriyi bir önbellek olarak düşünün ve TanStack Query gibi araçlarla yönetin; onu manuel olarak global store'a kopyalamayın. Bu ayrım, önbellek tazeleme ve yükleme/hata durumları gibi tekrar eden karmaşıklığı ortadan kaldırır.

**Önce ölçün, sonra optimize edin.** `memo`, `useMemo`, `useCallback` güçlü ama maliyetli araçlardır. Profiler ile gerçek darboğazı bulmadan geniş çaplı hafızalama yapmak, kodu karmaşıklaştırıp genellikle net bir kazanç sağlamaz.

**Değişmezliğe (immutability) sadık kalın.** State güncellemelerinde her zaman yeni referanslar üretin. Bu, hem React'ın değişiklik tespitini doğru çalıştırır hem de kodun akıl yürütülmesini kolaylaştırır.

**`key` için kararlı kimlikler kullanın.** Liste render'larında dizi indeksinden kaçının; verinin gerçek kimliğini kullanın. Bu, hem doğruluğu hem performansı güvenceye alır.

## Sonuç

Modern frontend mimarisinin dört sütunu (bileşen, tek yönlü veri akışı, state yönetimi ve render) birbirinden bağımsız kurallar değil, tek bir tutarlı felsefenin farklı yüzleridir: **arayüzü, verinin bir fonksiyonu olarak görmek.** Bileşenler bu fonksiyonun yapı taşlarıdır; tek yönlü akış girdinin nereden geldiğini netleştirir; state yönetimi bu girdinin nasıl değiştiğini düzene sokar; render mekanizması ise fonksiyonun çıktısını verimlice ekrana taşır. Bu bakış açısı içselleştirildiğinde, karşılaşılan çoğu tuzak "kural ezberi" olmaktan çıkıp öngörülebilir sonuçlar hâline gelir. İyi bir frontend mühendisi API'leri değil, bu kök nedenleri bilir; çünkü kütüphaneler değişse de (React, Vue, Svelte, Solid) bu temel ilkeler büyük ölçüde aynı kalır.
