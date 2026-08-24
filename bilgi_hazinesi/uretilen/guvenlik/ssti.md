# Server-Side Template Injection (SSTI): Derinlemesine Uzman Rehberi

## Tanım

Server-Side Template Injection (SSTI), sunucu tarafında çalışan bir template motoruna
(Jinja2, Freemarker, Twig, Velocity, Thymeleaf gibi) kullanıcı girdisinin **template
sözdiziminin bir parçası olarak** yorumlanmasıyla ortaya çıkan bir güvenlik açığıdır.
Saldırgan, uygulamanın sunucuda derleyip çalıştırdığı şablon kaynağının içine kendi
ifadelerini enjekte edebilir. Bu, çoğu zaman bilgi ifşasından başlayıp uzaktan kod
çalıştırmaya (Remote Code Execution, RCE) kadar tırmanan çok ciddi bir sınıftır.

SSTI'yi Cross-Site Scripting (XSS) ile karıştırmamak gerekir. XSS'te girdi tarayıcıda
yorumlanır ve etki istemci tarafındadır. SSTI'de ise girdi **sunucuda** template motoru
tarafından yorumlanır; dolayısıyla etki alanı sunucunun kendisidir. Aynı payload bir
uygulamada sadece zararsız bir çıktı üretirken, template motorunun yeteneklerine göre
başka bir uygulamada tüm sunucunun ele geçirilmesine yol açabilir.

## Kök Neden: Neden Böyle Oluyor?

SSTI'nin kök nedeni tek cümleyle şudur: **veri ile kod arasındaki sınırın yanlış yerde
çizilmesi.** Template motorları, sabit bir şablon iskeleti ile o iskelete gömülecek
dinamik verileri birbirinden ayırmak için tasarlanmıştır. Doğru kullanımda şablon
geliştirici tarafından yazılan sabit bir metindir; kullanıcı verisi ise yalnızca bu
şablonun **içine bir değişken olarak aktarılan** veridir. Sorun, kullanıcı verisinin
şablonun kendisini oluşturmakta kullanılmasıyla başlar.

Bunu somutlaştıralım. İki farklı kullanım deseni vardır:

**Güvenli desen (context/parametre olarak aktarma):**

```python
# Jinja2 - güvenli
template = env.from_string("Merhaba {{ isim }}!")
output = template.render(isim=kullanici_girdisi)
```

Burada `kullanici_girdisi` ne olursa olsun sadece `isim` değişkeninin **değeri** olur.
Kullanıcı `{{ 7*7 }}` yazsa bile çıktı `Merhaba {{ 7*7 }}!` olur; motor bunu şablon
sözdizimi olarak yorumlamaz çünkü şablon zaten derlenmiştir.

**Tehlikeli desen (girdiyi şablona gömme):**

```python
# Jinja2 - AÇIK
template = env.from_string("Merhaba " + kullanici_girdisi + "!")
output = template.render()
```

Bu ikinci örnekte kullanıcı girdisi şablon **kaynağının** parçası hâline gelir. Kullanıcı
`{{ 7*7 }}` yazarsa çıktı `Merhaba 49!` olur. İşte SSTI'nin tam kalbi budur: `49`
görüldüğü an, motorun kullanıcı girdisini kod olarak değerlendirdiği kesinleşir.

Bu hatanın gerçek dünyada bu kadar sık görülmesinin nedeni, geliştiricilerin çoğu zaman
"dinamik şablonlar" istemesidir: e-posta şablonlarını kullanıcının düzenlemesine izin
vermek, çok dilli mesajları veritabanından çekip render etmek, kullanıcının profil
biyografisini bir template değişkeni yerine doğrudan şablona yerleştirmek gibi. Bir de
`str.format`, string birleştirme veya f-string ile şablon inşa etme alışkanlığı buna
eklenince açık kaçınılmaz olur. Kısaca kök neden mimari bir yanlış varsayımdır: "kullanıcı
verisini şablona koymak, veriyi bir değişkene koymakla aynı şeydir." Değildir.

## Tespit: SSTI Nasıl Bulunur?

### Polyglot ve motor-agnostik ilk dokunuş

Tespitin ilk adımı, girdinin sunucuda değerlendirilip değerlendirilmediğini anlamaktır.
Klasik yöntem matematiksel bir ifade göndermektir çünkü sonucu belirsizliğe yer
bırakmaz. `{{7*7}}`, `${7*7}`, `#{7*7}`, `<%= 7*7 %>` gibi ifadeler farklı motorların
sözdizimlerine karşılık gelir. Yanıt gövdesinde `49` görülürse motorun ifadeyi çalıştırdığı
anlaşılır.

Ancak tek başına `49` yeterli bir sinyal değildir; çünkü aynı çıktı basit bir hesaplama
sonucu da olabilir. Bu yüzden pratikte **çarpım yerine ayırt edici bir polyglot** tercih
edilir. Yaygın bir yaklaşım `${{<%[%'"}}%\` benzeri, birden fazla motorun sözdizimini aynı
anda bozan/tetikleyen bir dizedir. Eğer sunucu bir template hatası (stack trace, "unexpected
token", "parse error") döndürürse, girdi şablon derleyicisine ulaşıyor demektir; bu güçlü
bir SSTI sinyalidir.

### Matematik testinden motor parmak izine

`49` alındıktan sonra sıradaki soru **hangi motorun** çalıştığıdır, çünkü sömürü zinciri
motora tamamen bağlıdır. Ayırıcı testler şu mantığa dayanır:

- `{{7*7}}` çalışıp `{{7*'7'}}` da çalışıyorsa (yani `7777777` gibi string tekrarı
  üretiyorsa) bu Python semantiğidir, yani büyük olasılıkla **Jinja2** veya benzeri bir
  Python motoru.
- `{{7*'7'}}` hata veriyor ama `{7*7}` veya `${7*7}` çalışıyorsa, farklı bir aile söz
  konusudur (Freemarker, Twig, Velocity vb.).
- `${7*7}` çalışıyorsa Java tabanlı bir motor (Freemarker, Velocity, Thymeleaf'in bazı
  ifade bağlamları) veya bir Expression Language (EL) muhtemeldir.
- `#{7*7}` gibi sözdizimleri Thymeleaf/JSF EL gibi bağlamlara işaret edebilir.

Buradaki felsefe şudur: her motorun kendine özgü sözdizimi, tip davranışı ve iç nesne
modeli vardır. Payload'lar da bu farklara göre dallanır. PortSwigger'ın yaygın olarak
atıfta bulunulan SSTI karar ağacı tam da bu ayırıcı testleri sistematik bir akışa döker.
Doğru motoru tespit etmeden atılan RCE payload'ları çoğu zaman boşa gider ve gereksiz gürültü
üretir.

### Kör (blind) SSTI

Bazı durumlarda çıktı doğrudan yansımaz; örneğin girdi bir e-posta şablonuna, bir PDF
üreticiye veya arka planda çalışan bir rapor motoruna gider. Bu **blind SSTI** senaryosunda
matematiksel yansıma göremezsiniz. Burada iki teknik öne çıkar: zaman tabanlı ispat (bir
uyku/gecikme komutu çalıştırıp yanıt süresini gözlemlemek) ve dışa-bant (out-of-band)
etkileşim (motorun DNS veya HTTP isteği yapmasını sağlayıp kendi kontrolünüzdeki bir
sunucuda bu isteği yakalamak). Blind senaryolar tespit ve sömürüyü zorlaştırır ama ortadan
kaldırmaz.

## Motor Bazında Sömürü Mantığı ve RCE Zinciri

Aşağıda üç yaygın motoru ele alıyoruz. Amaç ezberlenecek payload listesi vermek değil,
**neden çalıştıklarını** anlatmaktır; çünkü mekanizmayı anlarsan payload'u kendin türetirsin.

### Jinja2 (Python)

Jinja2 sandbox'sız kullanıldığında SSTI'nin RCE'ye dönüşmesinin klasik örneğidir. Çekirdek
fikir Python'un **introspection** yeteneğidir: her nesneden başlayıp nesne grafiğinde
gezinerek tehlikeli sınıflara ve fonksiyonlara ulaşabilirsiniz.

Zincirin mantığı kabaca şöyledir:

1. Herhangi bir nesneden başla (`''`, `{}`, `request`, `config` gibi bağlamda erişilebilir
   bir şey).
2. Python'un nesne modelinde yukarı çık: `__class__` ile nesnenin sınıfına, oradan
   `__mro__` (Method Resolution Order) veya `__bases__` ile üst sınıflara, en tepede
   `object` sınıfına ulaş.
3. `object.__subclasses__()` ile çalışma zamanında yüklenmiş tüm sınıfların listesine eriş.
   Bu liste içinde dosya açan, süreç başlatan veya modül yükleyen sınıflar (örneğin
   `subprocess.Popen`, `os`'a erişim sağlayan sınıflar, `warnings.catch_warnings` üzerinden
   `__builtins__`'e ulaşma gibi) bulunur.
4. O sınıfın uygun bir metodunu/constructor'ını çağırarak komut çalıştır.

Kavramsal olarak zincir şuna benzer:

```
'' -> __class__ -> __mro__ / __bases__ -> object
   -> __subclasses__() -> (uygun sınıfı seç) -> __builtins__ / os / subprocess -> komut
```

Ek olarak Jinja2/Flask bağlamında `request`, `config`, `self` gibi nesneler sıklıkla
erişilebilir olur ve `config` üzerinden hassas ayarların (SECRET_KEY vb.) sızdırılması bile
başlı başına ciddi bir etkidir. `__builtins__` üzerinden `eval`, `exec`, `__import__` gibi
fonksiyonlara ulaşmak da yaygın bir hedeftir.

Burada dikkat edilmesi gereken önemli bir gerçek: `__subclasses__()` listesinin **indeksi
Python sürümüne, yüklü kütüphanelere ve import sırasına göre değişir.** Bu yüzden internetteki
"şu indeksi kullan" tarzı sabit payload'lar çoğu ortamda kırılır. Uzman yaklaşım, listeyi
önce enumerate edip aradığı sınıfı **isimle filtrelemektir**; sabit indekse güvenmek amatör
işaretidir.

Jinja2 bir de **sandbox** (`SandboxedEnvironment`) sunar. Sandbox, `__class__`,
`__subclasses__` gibi tehlikeli attribute erişimlerini engellemeye çalışır. Ancak tarih,
sandbox bypass'larıyla doludur: filtreler, `attr`/`map` gibi dolaylı erişim yolları, string
formatlama nesneleri ve motorun kendi yardımcı fonksiyonları zaman zaman kaçış yolu
sağlamıştır. Yani sandbox savunmayı derinleştirir ama tek başına RCE'yi imkânsız kılan bir
duvar değildir.

### Freemarker (Java)

Freemarker, Java dünyasında yaygın bir template motorudur ve varsayılan yapılandırmasında
güçlü yerleşik (built-in) yeteneklere sahiptir. RCE'ye giden klasik yol, Freemarker'ın
`api` veya nesne sarmalayıcı (object wrapper) yetenekleriyle Java'nın `Runtime` /
`ProcessBuilder` sınıflarına ulaşmaktır. Kavramsal olarak saldırgan, bir "yeni nesne
oluşturma" yerleşiğini (yaygın olarak `?new` benzeri bir mekanizma veya
`freemarker.template.utility.Execute` gibi bir yardımcı sınıf) kullanarak sunucu üzerinde
işletim sistemi komutu çalıştırır.

Buradaki kök mesele şudur: Freemarker, tasarımı gereği bazı ortamlarda template yazarına
neredeyse tam Java erişimi verir. Eğer template kaynağına güvenilmeyen girdi karışıyorsa, bu
"özellik" doğrudan RCE'ye dönüşür. Freemarker güvenli kullanım için `TemplateClassResolver`
ile sınıf çözümlemesini kısıtlama ve tehlikeli yerleşikleri kapatma imkânı sunar
(`Configuration` üzerinden). Yani savunma motor seviyesinde mümkündür ama **varsayılan
güvenli değildir**; bilinçli olarak sıkılaştırılması gerekir.

### Twig (PHP)

Twig, Symfony ekosisteminde standarttır. Modern Twig sürümleri güvenlik açısından oldukça
olgunlaşmıştır ve varsayılan olarak keyfi PHP fonksiyon çağrılarına izin vermez. Ancak
tarihsel olarak Twig SSTI'leri, motorun iç API'sine (`_self`, `env` gibi nesneler üzerinden)
erişip oradan PHP'nin `system`, `passthru`, `call_user_func` gibi fonksiyonlarına ulaşmakla
gerçekleşmiştir. Bazı Twig sürümlerinde `filter`, `map`, `sort` gibi yapıların bir callback
kabul etmesi, saldırganın rasgele PHP fonksiyonunu callback olarak geçirmesine imkân
tanımıştır.

Twig'in dersi çift yönlüdür: Bir yandan modern sürümde varsayılan yüzey daralmıştır; öte
yandan Twig'i bir "kullanıcının düzenleyebildiği şablon dili" olarak sunmak (örneğin bir CMS
içinde) yeniden büyük risk açar. Symfony'nin sunduğu **sandbox** politikası (izin verilen
tag, filtre, fonksiyon ve metotların beyaz listesi) bu senaryoda kritik savunmadır.

### Genel RCE zinciri felsefesi

Motor ne olursa olsun zincir aynı üç halkadan oluşur:

1. **Değerlendirme kanıtı:** Girdi kod olarak yorumlanıyor mu? (`7*7 = 49`).
2. **İç nesne modeline ulaşma:** Motorun/host dilin nesne grafiğinde gezinerek tehlikeli
   yeteneklere (dosya, süreç, modül) erişim.
3. **İşletim sistemi komutu / dosya erişimi:** RCE, dosya okuma/yazma veya sır sızdırma.

Bu üç halkanın herhangi biri kopartıldığında zincir tamamlanamaz; savunmanın hedefi de tam
olarak bu halkaları kırmaktır.

## Savunma: Katmanlı Bir Yaklaşım

SSTI savunmasında tek bir sihirli çözüm yoktur; savunma katmanlıdır ve **en güçlü katman
mimaridir.**

### 1. Kullanıcı girdisini asla şablon kaynağına koyma (birincil savunma)

En temel ve en etkili kural budur. Kullanıcı verisi her zaman **şablona aktarılan bir
değişken** olmalıdır, asla şablonun kendisini oluşturan bir metin parçası olmamalıdır.
Uygulamada bu şu demektir: `from_string(user_input)`, string birleştirme, `str.format`,
f-string ile şablon inşa etmekten kaçının. Şablonlar mümkünse **statik dosyalardan** yüklensin
ve değişkenler `render(context)` yoluyla geçsin.

Bu tek kural doğru uygulandığında SSTI'nin büyük çoğunluğu kökten yok olur, çünkü açığın kök
nedenini (veri/kod sınırı ihlali) ortadan kaldırır. Diğer tüm önlemler bu mimari kararın
etrafındaki güvenlik ağlarıdır.

### 2. Kullanıcının şablon düzenlemesi gerekiyorsa: logic-less motor kullan

Bazı ürünlerde kullanıcının gerçekten şablon yazması gerekir (e-posta şablonları, bildirim
metinleri). Böyle durumlarda **mantık içermeyen (logic-less)** bir motor tercih edin.
Mustache gibi motorlar tasarımı gereği keyfi ifade çalıştırmaz; yalnızca değişken yerleştirme
ve basit döngü/koşul sunar. İfade yürütme yeteneği olmayan bir motor, RCE zincirinin ikinci
ve üçüncü halkasını baştan imkânsız kılar. Doğru araç seçimi, en pahalı sömürüden daha ucuz
bir savunmadır.

### 3. Sandbox uygulaması (ikincil savunma)

Eğer güçlü bir motor kullanmak zorundaysanız, motorun sandbox modunu etkinleştirin:
Jinja2'de `SandboxedEnvironment`, Twig'de Symfony sandbox politikası, Freemarker'da
`TemplateClassResolver` ile sınıf erişimini kısıtlama. Sandbox, tehlikeli attribute ve
metotlara erişimi engellemeye çalışır. Ancak sandbox'ı **birincil değil, ikincil** savunma
olarak konumlandırın; çünkü sandbox bypass'ları tarih boyunca defalarca ortaya çıkmıştır.
Sandbox "derinlemesine savunma"nın (defense in depth) bir katmanıdır, tek başına yeterli bir
garanti değildir.

### 4. Girdiyi doğrula, çıktıyı kaçış (escape) et

Girdi doğrulama (allowlist) faydalıdır ama SSTI'de **tek başına güvenilmez.** Çünkü template
sözdizimi çok esnektir ve karakter kara listesi (`{{`, `}}` engelleme gibi) kolayca aşılır
(kodlama, alternatif sözdizimi, filtre zincirleri). Yine de bağlama uygun beyaz liste ("sadece
alfanümerik isim") anlamlı bir daraltmadır. Çıktı kaçışı (auto-escaping) XSS'e karşı önemlidir
ama **SSTI'yi engellemez**; çünkü sömürü çıktının HTML olarak render edilmesinden değil,
şablonun sunucuda çalıştırılmasından kaynaklanır. Bu ayrımı karıştırmak yaygın bir hatadır.

### 5. En az yetki ve izolasyon (etki sınırlama)

Zincirin son halkasını (RCE'nin sonuçlarını) sınırlamak için uygulamayı en az yetkiyle
çalıştırın, container/namespace izolasyonu kullanın, dışa giden ağ trafiğini kısıtlayın
(blind SSTI'nin out-of-band tekniklerini zorlaştırmak için) ve dosya sistemi erişimini
daraltın. Bu önlemler açığı kapatmaz ama sömürünün maliyetini ve etkisini ciddi biçimde
düşürür. Savunma sadece "girmesini engelle" değil, aynı zamanda "girse bile ne yapabilir"
sorusunu da kapsamalıdır.

## Yaygın Hatalar

- **`{{`/`}}` kara listesine güvenmek.** Karakter engelleme, template dillerinin esnekliği
  yüzünden neredeyse her zaman aşılabilir. Kara liste bir çözüm değil, en fazla bir gürültü
  azaltıcıdır.

- **SSTI'yi XSS ile karıştırmak ve auto-escape'i yeterli sanmak.** Auto-escaping çıktının
  HTML anlamını nötralize eder; şablonun sunucuda çalışmasını engellemez. Motor `{{7*7}}`'yi
  zaten çalıştırmıştır; çıktının kaçışlanması bunu değiştirmez.

- **Sandbox'ı aşılamaz sanmak.** Sandbox faydalıdır ama tarih bypass'larla doludur.
  Sandbox'a tek savunma olarak yaslanmak yanlış bir güven duygusu yaratır.

- **Sabit `__subclasses__()` indeksleri kullanmak.** İnternetten kopyalanan sabit indeksli
  Jinja2 payload'ları ortam değiştiğinde kırılır. Doğru yaklaşım isimle enumerate etmektir.

- **"Kullanıcı sadece isim giriyor, ne olacak ki" varsayımı.** Girdi ne kadar masum
  görünürse görünsün, şablon kaynağına karışıyorsa risk mevcuttur. Etkiyi belirleyen girdinin
  içeriği değil, girdinin **nereye** aktığıdır.

- **Framework'ün "güvenli" olduğunu varsaymak.** Modern Twig veya sandbox'lı Jinja2 daha
  güvenli olabilir ama yanlış kullanım (dinamik şablon, sandbox'sız `from_string`) bu
  güvenliği tümüyle iptal eder. Güvenlik motorda değil, kullanım şeklindedir.

- **Tespit ile sömürüyü karıştırıp motor tespitini atlamak.** `49` görmek "açık var"
  demektir ama motoru doğru tespit etmeden atılan RCE payload'ları hem başarısız olur hem de
  gereksiz iz bırakır.

## En İyi Pratikler (Özet)

1. **Mimari kural birincidir:** Kullanıcı girdisini şablon kaynağına asla koyma; her zaman
   `render()` bağlamında bir değişken olarak geçir. Şablonları statik dosyalardan yükle.

2. **Doğru aracı seç:** Kullanıcının şablon düzenlemesi gerekiyorsa logic-less bir motor
   (Mustache benzeri) kullan; keyfi ifade yürüten motorlara güvenilmeyen girdi verme.

3. **Sandbox'ı derinlemesine savunma olarak kullan:** Güçlü motor zorunluysa sandbox'ı aç,
   ama onu tek garanti sayma.

4. **Girdi allowlist + bağlama uygun doğrulama** uygula, ama bunu SSTI'nin tek çözümü olarak
   görme.

5. **En az yetki, izolasyon, dışa giden trafik kısıtlaması** ile sömürünün etkisini sınırla;
   RCE gerçekleşse bile hasarı daralt.

6. **Tespit sürecini sistematikleştir:** Önce değerlendirme kanıtı (`7*7`), sonra ayırıcı
   testlerle motor parmak izi, sonra motora özgü zincir. Kör senaryolar için zaman tabanlı ve
   out-of-band teknikleri hazır tut.

7. **Bağımlılıkları güncel tut:** Template motorlarının sandbox bypass ve güvenlik düzeltmeleri
   sürümlerle gelir; eski sürümlerde kapatılmış zannettiğin yollar açık olabilir.

## Kapanış

SSTI'nin özü tek bir cümlede toplanır: **veriyi kod olarak yorumlatmak.** Motor Jinja2,
Freemarker ya da Twig olsun, mekanizma hep aynıdır; motorun iç nesne modelinden host dilin
tehlikeli yeteneklerine uzanan bir köprü kurulur ve bu köprü çoğu zaman RCE'ye çıkar. Bu
yüzden en sağlam savunma bir payload filtresi değil, bir mimari karardır: kullanıcı verisini
şablonun içine değil, şablona aktarılan bir değişkenin değerine yerleştirmek. Geri kalan her
şey (sandbox, allowlist, izolasyon) bu temel kararın etrafına örülen ve gerçek dünyanın
belirsizliğine karşı koruma sağlayan katmanlardır.
