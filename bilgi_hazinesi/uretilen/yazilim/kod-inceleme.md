# Kod İnceleme (Code Review)

## Tanım

Kod inceleme, bir geliştiricinin yazdığı kaynak kodun, başka bir veya birden fazla insan tarafından ana koda (main/trunk) katılmadan önce okunması, tartışılması ve onaylanması sürecidir. Modern yazılım geliştirmede bu çoğunlukla bir **Pull Request** (GitHub) veya **Merge Request** (GitLab) etrafında döner: yazar bir dal (branch) üzerinde değişiklik yapar, bir istek açar, incelemeciler (reviewer) satır satır yorum bırakır, yazar düzeltir ve nihayetinde değişiklik birleştirilir (merge).

Ancak kod incelemeyi salt bir "onay kapısı" olarak görmek yüzeysel bir bakıştır. İncelemenin asıl işlevi çok katmanlıdır: hata yakalamak yalnızca bir boyuttur; asıl derin değeri **bilgi yayılımı**, **ortak kod sahipliği**, **tasarım tutarlılığı** ve **takım kültürünün şekillenmesidir**. Bir kod tabanının uzun vadeli sağlığı, çoğu zaman testlerin kapsamından çok inceleme kültürünün olgunluğuyla belirlenir.

## Kök Neden: İnceleme Neden İşe Yarar?

İncelemenin neden bu kadar etkili olduğunu anlamak için bir gerçeği kabul etmek gerekir: **yazar kendi kodunu nesnel okuyamaz.** Kodu yazan zihin, o kodun ne yapması *gerektiğini* zaten bildiği için, ne yaptığını değil ne yapmayı *amaçladığını* okur. Bu bilişsel yanlılığa "curse of knowledge" (bilgi laneti) denir. Yazarın gözünden kaçan bir off-by-one hatası, meseleye taze bakan bir incelemeci için ilk bakışta görünür olabilir çünkü incelemeci kodu amaçtan değil, yazıldığı halinden okur.

İkinci kök neden **istatistikseldir**. Yazılım hatalarının dağılımı düzgün değildir; belirli değişiklikler, belirli dosyalar ve belirli kalıplar orantısız risk taşır. İnsan gözü, statik analiz araçlarının kaçırdığı *anlamsal* (semantic) hataları — yani sözdizimsel olarak doğru ama mantıksal olarak yanlış kodu — yakalamada hâlâ üstündür. Bir `if (user.isAdmin = true)` atama hatasını linter yakalar; ama "bu yetki kontrolü aslında yanlış kullanıcı nesnesi üzerinde yapılıyor" tespitini çoğunlukla yalnızca bağlamı anlayan bir insan yapar.

Üçüncü ve en az konuşulan kök neden **sosyaldir**. İncelendiğini bilmek, yazarın kodunu daha dikkatli yazmasına yol açar. Bu, gözlemlenme etkisidir (bir tür Hawthorne etkisi). Kimse "acaba bunu Ayşe okuyunca ne düşünür" sorusunu içselleştirdiğinde özensiz iş çıkarmak istemez. Yani inceleme, kod daha yazılmadan önce kaliteyi yükseltmeye başlar.

## Neye Bakılır?

İyi bir incelemeci belirli bir öncelik sırasıyla okur, çünkü her şeye aynı anda bakmak dikkati dağıtır ve önemsiz ayrıntılar önemli sorunları gölgeler.

### 1. Doğruluk (Correctness)

En üstteki katman: Kod gerçekten amaçlanan işi yapıyor mu? Burada sınır durumlarına (edge cases) odaklanılır. Boş liste geldiğinde ne olur? `null`/`nil`/`None` durumu ele alınmış mı? Sayısal taşma (integer overflow) veya bölme sıfıra bölme gibi durumlar var mı? Eşzamanlılık söz konusuysa **race condition** ihtimali var mı — yani iki thread'in aynı veriye sıralamasız erişip tutarsız sonuç üretmesi mümkün mü?

Bir örnek üzerinden düşünelim:

```python
def bakiye_dus(hesap, miktar):
    if hesap.bakiye >= miktar:
        hesap.bakiye -= miktar
        return True
    return False
```

Bu kod tek başına doğru görünür. Ama incelemeci "bu fonksiyon eşzamanlı çağrılırsa?" diye sorar. İki istek aynı anda `hesap.bakiye >= miktar` kontrolünü geçerse, ikisi de düşme yapar ve bakiye negatife düşer — klasik bir **race condition**. Doğruluk incelemesi, kodun tek başına değil, çalışacağı *ortamda* doğru olup olmadığını sorgular.

### 2. Tasarım ve Mimari

Kod işini yapıyor olabilir ama yanlış yerde duruyor olabilir. Bu sorumluluk bu katmana mı ait? Var olan bir soyutlama (abstraction) tekrar mı yazılmış? Değişiklik, sistemin bağımlılık yönünü bozuyor mu (örneğin bir alt katman üst katmana bağımlı hale mi geliyor)? Tasarım geri bildirimi en değerli ama aynı zamanda en pahalı geri bildirimdir, çünkü kabul edilirse yazarın işi baştan yapması gerekebilir. Bu yüzden mümkünse mimari tartışması **kod yazılmadan önce**, tasarım aşamasında yapılmalıdır; PR aşamasında büyük mimari itirazlar hem geç hem yıkıcıdır.

### 3. Okunabilirlik ve İsimlendirme

Kod bir kez yazılır, onlarca kez okunur. Değişken ve fonksiyon isimleri niyeti açıklıyor mu? `data`, `temp`, `x` gibi isimler bağlamı gizler. Bir fonksiyon tek bir işi mi yapıyor yoksa üç ayrı sorumluluğu mu üstlenmiş? Karmaşık bir koşulun neden orada olduğunu açıklayan bir yorum var mı? Buradaki altın kural: yorumlar kodun *ne* yaptığını değil, *neden* öyle yaptığını anlatmalıdır. `i++ // i'yi bir artır` değersizdir; `// API rate limit nedeniyle 100ms bekliyoruz` değerlidir.

### 4. Test Kapsamı

Yeni davranış test edilmiş mi? Testler yalnızca mutlu yolu (happy path) mı kapsıyor, yoksa hata durumlarını da mı? Testler kırılgan mı — yani gereksiz yere iç detaya (implementation detail) mı bağlı, yoksa gözlemlenebilir davranışı mı doğruluyor? İyi bir incelemeci bazen "bu test aslında hiçbir şeyi doğrulamıyor" diyebilir; örneğin bir mock'un kendi kendini test ettiği durumlar.

### 5. Güvenlik ve Kaynak Yönetimi

Bu katman kendi başlığını hak edecek kadar önemlidir; aşağıda ayrıca ele alıyoruz. Kısaca: kullanıcı girdisi güvenilmez kabul ediliyor mu, kaynaklar (dosya tanıtıcıları, bağlantılar) düzgün kapatılıyor mu, sırlar (secret) koda gömülmüş mü?

## Güvenlik İncelemesi: Ayrı Bir Zihniyet

Güvenlik incelemesi, normal incelemeden farklı bir düşünce biçimi ister. Normal inceleme "bu kod ne yapar?" diye sorar; güvenlik incelemesi "bu kod **kötü niyetli bir girdiyle** ne yapmaya *zorlanabilir*?" diye sorar. Yani saldırganın gözünden okumak gerekir.

### Girdi Güvenilmezliği İlkesi

Güvenlik incelemesinin kök ilkesi şudur: **sistem sınırından içeri giren her veri, aksi kanıtlanana kadar düşmandır.** HTTP parametreleri, form alanları, dosya isimleri, HTTP başlıkları, hatta veritabanından okunan ve daha önce başka bir yerden gelmiş veriler (second-order injection) dahil.

En klasik örnek **SQL injection**'dır. İncelemede şuna benzer bir satır görürseniz alarm çalmalıdır:

```python
sorgu = "SELECT * FROM users WHERE name = '" + kullanici_adi + "'"
```

Buradaki kök neden, *kod* ile *veri*nin string birleştirmesiyle karıştırılmasıdır. Kullanıcı `kullanici_adi` olarak `' OR '1'='1` gönderirse, veri sözdizimine dönüşür. Doğru çözüm parametreli sorgulardır (prepared statements); bu, veriyi sözdiziminden yapısal olarak ayırır, dolayısıyla veri asla komuta dönüşemez. Aynı mantık kabuk komutları (command injection), LDAP, ve tarayıcıda **XSS** (Cross-Site Scripting) için de geçerlidir: her yerde çözüm, girdiyi *doğru bağlamda kodlamak/escape etmek* veya yapısal olarak ayırmaktır.

### İnceleme Sırasında Aranan Güvenlik Kalıpları

**Yetkilendirme kontrolleri.** En sık gözden kaçan zafiyet sınıflarından biri budur. Kod bir kaynağa erişirken "bu isteği yapan kullanıcı *bu belirli* kaynağa erişmeye yetkili mi?" kontrolünü yapıyor mu? Sadece "giriş yapmış mı" (authentication) yetmez; "bu kayıt gerçekten ona mı ait" (authorization) sorusu ayrıdır. Kullanıcının kendi ID'sini başkasınınkiyle değiştirerek başkasının verisine ulaşabildiği zafiyete genellikle **IDOR** (Insecure Direct Object Reference) denir ve otomatik araçların yakalaması en zor sınıflardan biridir, çünkü kod teknik olarak "çalışır".

**Sır yönetimi.** API anahtarları, parolalar, tokenlar koda veya konfigürasyon dosyasına düz metin gömülmüş mü? Bir sır bir kez commit tarihine girdiyse, sonradan silinse bile git geçmişinde kalır; bu yüzden inceleme bu tür sızıntıları *birleşmeden önce* durdurmalıdır. Sırlar ortam değişkenleri veya özel bir sır yönetim sistemi (secrets manager) üzerinden gelmelidir.

**Kriptografi kullanımı.** Burada temkinli olmak şart. Parolalar **hash** ile mi saklanıyor, yoksa şifreleme (encryption) ile mi karıştırılmış? Doğrusu, parolaların geri döndürülemez, tuzlanmış (salted) ve kasıtlı olarak yavaş bir algoritma ile hash'lenmesidir. Kendi kripto algoritmanı yazmak neredeyse her zaman hatadır ("don't roll your own crypto"). İncelemede biri özel bir şifreleme rutini yazdıysa, bu kırmızı bayraktır.

**Kaynak tüketimi ve DoS.** Kullanıcı girdisiyle boyutu belirlenen bir döngü, sınırsız bir dosya yükleme, veya derinliği kontrolsüz bir özyineleme (recursion), hizmet reddi (Denial of Service) riskidir. Ayrıca kullanıcı girdisiyle oluşturulan **regular expression** veya kötü yazılmış bir regex, üstel zamanda çalışıp CPU'yu kilitleyebilir (ReDoS).

Dürüst bir uyarı: Güvenlik incelemesi uzmanlık ister ve insan gözü tek başına yeterli değildir. Bu yüzden ciddi projeler bunu **SAST** (Static Application Security Testing) araçları, bağımlılık tarayıcıları ve gerektiğinde profesyonel penetrasyon testleriyle katmanlar. İnceleme bir savunma katmanıdır, tek katman değil.

## Kültür: İncelemenin Görünmeyen Motoru

Teknik olarak kusursuz bir inceleme süreci, kötü bir kültür üzerine kurulduğunda işe yaramaz. İnsanlar geri bildirimden kaçmaya, incelemeyi hızla "LGTM" (Looks Good To Me) yazıp geçmeye ya da tam tersine incelemeyi bir güç gösterisine dönüştürmeye başlar. Kültür, sürecin fiilen ne kadar değer ürettiğini belirler.

### İnceleme İnsanı Değil Kodu Hedef Alır

Kültürün temel taşı budur. "Sen bunu neden böyle yaptın?" ile "Bu yaklaşım şu durumda sorun çıkarabilir, ne dersin?" arasında devasa bir fark vardır. İlki savunmacılık üretir, ikincisi iş birliği. Yorumlar koda yöneltilmeli, kişiye değil. Küçük ama etkili bir alışkanlık: "sen" yerine "bu kod" veya "biz" demek. "Kodun şurada null dönebilir" cümlesi, "sen null kontrolünü unutmuşsun" cümlesinden psikolojik olarak çok daha kolay kabul edilir, oysa aynı bilgiyi taşırlar.

### Öneri ile Zorunluluğu Ayırmak

Her yorum aynı ağırlıkta değildir ve bunu belirtmemek büyük bir gerilim kaynağıdır. Deneyimli takımlar yorumları etiketler. Yaygın bir konvansiyon: **nit** (nitpick — küçük, isteğe bağlı bir tercih), **öneri** (düşünmeye değer ama zorunlu değil), ve **blocker** (birleşmeden önce çözülmesi şart). Bir yorumun başına "nit:" yazmak, yazarın onu reddetme hakkını açıkça tanır ve gereksiz çekişmeleri ortadan kaldırır. Bu etiketleme olmadan, bir virgül tartışması ile ciddi bir güvenlik açığı aynı görsel ağırlıkta görünür ve yazar hangisine öncelik vereceğini bilemez.

### Küçük PR Kültürü

Bu hem teknik hem kültürel bir meseledir. İnceleme kalitesi PR boyutuyla ters orantılıdır. 50 satırlık bir değişiklik dikkatle okunur; 2000 satırlık bir değişiklik "LGTM" damgasını yer, çünkü insan zihni o hacmi anlamlı biçimde denetleyemez. Büyük bir PR aslında incelemeyi *tiyatroya* dönüştürür: süreç işliyormuş gibi görünür ama kimse gerçekten okumaz. Sağlıklı bir kültür, işi küçük ve bağımsız parçalara bölmeyi teşvik eder ve büyük PR'ı bir kalite sorunu olarak görür.

### Hız ve Karşılıklılık

İnceleme bir kişinin işini bloke eder; bu yüzden **incelemeye yanıt hızı** bir takım normudur. Bir PR günlerce bekliyorsa, yazar bağlamı unutur, dal ana koddan uzaklaşır (merge conflict riski artar) ve motivasyon düşer. Sağlıklı takımlar inceleme isteğini yüksek öncelikli sayar — genellikle "bugün içinde" gibi bir norm benimsenir. Bir diğer önemli nokta karşılıklılıktır: Sürekli incelenen ama hiç incelemeyen kıdemli geliştirici, hem darboğaz yaratır hem de bilgi silosu oluşturur. İnceleme herkesin işidir.

### Kıdem Dinamiği

Kıdemli birinin kodunu kıdemsiz birinin incelemesi kültürel olarak zor ama son derece değerlidir. Kıdemsiz geliştiriciye "sorman gereken aptalca soru yoktur" güvencesi verilmelidir, çünkü onun "bunu neden böyle yapıyoruz?" sorusu çoğu zaman kimsenin sorgulamadığı bir varsayımı açığa çıkarır. Tersi yönde, kıdemli incelemeci öğretme fırsatını kullanmalı ama ezici olmamalıdır — her yorumda 20 iyileştirme sıralamak, yeni birini boğar. Bazen en iyi mentorluk, üç önemli noktayı vurgulayıp gerisini geçmektir.

## Otomasyon: İnsanı Değerli İşe Ayırmak

Otomasyonun amacı incelemeyi yok etmek değil, **insan dikkatini makinelerin yapamayacağı işe yöneltmektir.** İnsan bir incelemecinin biçim (formatting), stil veya önemsiz sözdizimi tutarlılığı üzerine yorum yapması saf israftır — bunlar deterministik kurallardır ve makineye devredilmelidir. İnsan zamanı, tasarım ve doğruluk gibi yargı gerektiren işler için ayrılmalıdır.

### Katman Katman Otomasyon

**Biçimlendiriciler (formatters).** Kod stilini tartışmayı tamamen ortadan kaldırırlar. Kod belirli bir biçime otomatik dönüştürüldüğünde, "girinti 2 mi 4 boşluk mu" tartışması ölür. Bu tartışmanın ölmesi tek başına muazzam bir kültürel kazanımdır, çünkü bu tür tartışmalar duygusal olarak orantısız yük taşır.

**Linter'lar ve statik analiz.** Kullanılmayan değişkenler, olası `null` erişimleri, şüpheli tip dönüşümleri gibi kalıpları yakalar. Bunlar insanın gözünden kaçabilecek ama makinenin güvenilir biçimde bulduğu şeylerdir.

**Test ve kapsam kapıları (CI).** Bir **CI** (Continuous Integration) hattı, PR açıldığında testleri çalıştırır. Testler geçmeden inceleme başlamamalıdır — kırık bir PR'ı incelemek zaman israfıdır. Kapsam (coverage) eşiği belirlenebilir, ancak dikkat: kapsam yüzdesini kör bir hedefe dönüştürmek, anlamsız testler yazılmasına yol açar. Kapsam bir *gösterge*dir, bir *amaç* değil.

**Güvenlik otomasyonu.** Bağımlılık tarayıcıları, bilinen zafiyetli kütüphaneleri işaretler. Sır tarayıcıları (secret scanners), commit'e sızmış API anahtarlarını yakalar. SAST araçları, yaygın zafiyet kalıplarını statik olarak arar. Bunların hepsi insan incelemesinden *önce* çalışmalı ki incelemeci temiz bir zeminde başlasın.

### Otomasyonun Sınırı

Burada dürüst olmak gerekir: otomasyon anlam kavrayamaz. Bir linter, bir fonksiyonun *yanlış* bir hesaplama yaptığını anlayamaz — sadece kodun kurallara uyup uymadığını görür. "Bu değişken adı yanıltıcı", "bu soyutlama sızdırıyor", "bu iş kuralı yanlış anlaşılmış" türü tespitler yargı gerektirir ve insana aittir. En tehlikeli yanılgı, yeşil CI'ı "kod doğru" olarak okumaktır. Yeşil CI yalnızca "yazdığımız kurallar ihlal edilmedi" demektir — kuralların *ötesindeki* hataları hiçbir otomasyon garanti edemez.

Yapay zeka destekli inceleme araçları bu sınırı genişletmeye başlamıştır ve giderek daha kullanışlı özet ve öneriler üretmektedir. Ancak bunlar da bir *yardımcı*dır; nihai yargı ve sorumluluk hâlâ insandadır. AI'ın önerdiği bir düzeltmeyi körü körüne kabul etmek, insan incelemecinin önerisini körü körüne kabul etmekten daha güvenli değildir.

## Yaygın Hatalar

**"LGTM" tiyatrosu.** İncelemeyi okumadan onaylamak, incelemenin en zararlı başarısızlığıdır, çünkü hem hatayı geçirir hem de takıma "burada gerçek denetim var" yanılsaması verir. Denetimsizlik, denetim varmış gibi yapmaktan daha az tehlikelidir çünkü en azından dürüsttür.

**Bikeshedding.** Önemsiz ayrıntılara (değişken adı, boşluk) saatler harcayıp mimari bir sorunu es geçmek. İnsan zihni, kolay anladığı şey hakkında konuşmayı, zor olanı ihmal ederek tercih eder. İyi incelemeci bu eğilime karşı bilinçli direnir.

**Ego savaşı.** İncelemeyi kimin haklı olduğunu kanıtlama alanına çevirmek. Çözülmeyen bir tartışma uzarsa, doğru refleks eş zamanlı bir konuşmaya (sesli/yüz yüze) geçmektir; yazılı kanal, ton kaybı nedeniyle çatışmayı büyütür.

**Aşırı büyük PR.** Yukarıda değinildi; incelemeyi anlamsızlaştıran tek başına en yaygın teknik hata budur.

**Otomasyona devredilebilir işi insana yaptırmak.** Biçim yorumlarıyla dolu bir inceleme, hem incelemecinin zamanını hem yazarın moralini israf eder ve asıl önemli yorumları gürültüde boğar.

**Bağlamsız yorum.** "Bu yanlış" demek ama neden yanlış olduğunu ve alternatifin ne olabileceğini açıklamamak. İyi yorum sorunu, nedenini ve mümkünse bir yön gösterir.

## En İyi Pratikler

- **Kendini önce incele.** PR'ı açmadan önce yazarın kendi değişikliğini "diff" olarak baştan sona okuması, incelemeciye giden gürültünün büyük kısmını daha kaynağında temizler.
- **PR'a bağlam ekle.** Açıklamada "ne yaptığını" değil "neden yaptığını" ve nasıl test edildiğini anlat. İyi bir açıklama, incelemenin süresini yarıya indirir.
- **Küçük tut.** Bir PR tek bir mantıksal değişikliği kapsamalı. Refactor ile davranış değişikliğini asla aynı PR'da karıştırma — incelemeci hangi satırın neyi değiştirdiğini ayırt edemez.
- **Öncelik sırasıyla oku:** önce doğruluk ve güvenlik, sonra tasarım, en son stil. Otomasyona bırakılabilecek her şeyi otomasyona bırak.
- **Yorumları etiketle** (nit / öneri / blocker) ki yazar önceliği görsün.
- **Soru sor, buyruk verme.** "Şunu yap" yerine "şu durumda ne olur?" daha iyi düşünce ve daha az direnç üretir.
- **Onaylarken de gerekçe belirt.** İyi bir yaklaşımı fark edip "bunu böyle çözmen zarif olmuş" demek, kültürü kritikten çok daha fazla besler.
- **Güvenliği katmanla.** İnsan incelemesini SAST, sır tarama ve bağımlılık tarama ile birlikte kullan; hiçbirine tek başına güvenme.
- **Hızlı yanıtla.** İncelemeyi bloke eden bir görev olarak gör; yazarın işini bekletmek görünmez bir maliyettir.
- **Yeşil CI'ı doğruluk kanıtı sanma.** Otomasyon kural ihlallerini yakalar, mantık hatalarını değil.

## Kapanış

Kod incelemenin gerçek çıktısı, birleşen bir dal değil; zamanla oluşan bir *ortak akıldır*. Her iyi yürütülen inceleme, hem kodu iyileştirir hem de iki kişinin sistemi biraz daha benzer biçimde anlamasını sağlar. Bu yüzden inceleme, teknik bir kapı olmanın ötesinde bir öğrenme ve hizalanma ritüelidir. Otomasyon bu ritüelin mekanik yükünü kaldırdıkça, insanın işi giderek daha saf biçimde en zor ve en değerli şeye — yargıya — indirgenir. İyi bir inceleme kültürü kurmak yıllar alır ama bir kod tabanına yapılabilecek en yüksek getirili yatırımlardan biridir.
