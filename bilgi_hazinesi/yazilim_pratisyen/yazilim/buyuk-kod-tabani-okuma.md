# Büyük/Yabancı Kod Tabanı Okuma ve Anlama

## 1. Problem ve bağlam

Yeni bir işe girdin, ya da mevcut şirkette başka bir ekibe geçtin. Karşında 400 bin, belki 2 milyon satırlık bir kod tabanı var. On yıl önce, artık şirkette olmayan insanlar tarafından yazılmış. Dokümantasyon ya yok ya da gerçeği yansıtmıyor ("bu README 3 yıl önce güncellendi, artık o servis bile yok"). Ve senden bir hafta içinde küçük bir bug'ı düzeltmen ya da bir feature eklemen bekleniyor.

Bu, kariyerinin geri kalanında en çok yapacağın iş. Acemi mühendisin kafasındaki "yazılım = kod yazmak" resmi yanlıştır. Kıdemli bir mühendisin zamanının büyük çoğunluğu **kod okumaya, var olan sistemi anlamaya** gider; yazmak buzdağının görünen ucudur. Bir çalışmada geliştiricilerin okuma/yazma oranının kabaca 10'a 1 olduğu söylenir; sayı tartışmalı olsa da yön doğrudur.

Asıl mesele şu: Sınırsız zamanın yok. Kodun tamamını okuyup anlaman imkânsız, gereksiz ve zararlı. Beceri, **tam da o görevi bitirmeye yetecek kadar** anlamayı, mümkün olan en az bilişsel yükle elde etmektir. Bu bir "hız" değil, bir "yön bulma" ve "nereye kadar kazacağını bilme" becerisidir. Bu metin o yargıyı aktarmaya çalışıyor.

Ne zaman devreye girer: yeni işe başlangıç, devralınan (legacy) bir sistemi düzeltme, açık kaynak bir projeye katkı, bir kütüphanenin neden beklediğin gibi davranmadığını çözme, üretimde çıkan ve senin yazmadığın bir kodda patlayan bir olayı (incident) çözme.

## 2. Metodoloji ve karar ağacı — asıl değer

### Önce niyetini netleştir: neden okuyorsun?

En büyük acemi hatası, amaçsız okumaktır. "Kod tabanını öğreneceğim" diye dosya dosya gezmek, ilk gün heyecan verici, üçüncü gün faydasızdır çünkü hiçbir şey akılda kalmaz. Kod ancak bir **soruyu** cevaplarken öğrenilir. Okumaya başlamadan önce kendine somut bir soru sor:

- "Kullanıcı 'kaydet'e bastığında veri nereye gidiyor?"
- "Bu 500 hatası hangi kod yolundan geliyor?"
- "Yeni bir ödeme sağlayıcısı eklemem için nereye dokunmam gerekir?"

Sorusu olmayan okuma, hafızasız okumadır. Pro her zaman bir **iz** (thread) peşinde koşar, haritayı ezberlemeye çalışmaz.

### Karar ağacı: hangi belirti, hangi yön

**Belirti: "Sistem ne yapıyor, büyük resim ne?" → Yukarıdan aşağı, dış kenarlardan başla.**
Kodu değil, sınırları oku. Şu sırayla:
1. **Nasıl çalıştırılıyor/deploy ediliyor?** `README`, `Makefile`, `docker-compose.yml`, CI pipeline dosyaları (`.github/workflows`, `.gitlab-ci.yml`), `package.json` scriptleri, `Procfile`. Bir sistemin nasıl ayağa kalktığı, mimarisinin en dürüst özetidir; çünkü çalışmak zorundadır, yalan söyleyemez. Kaç servis var, hangi portlar, hangi veritabanları, hangi dış bağımlılıklar — hepsi burada.
2. **Veri modeli.** Veritabanı şeması / migration dosyaları / ORM modelleri. **Tablolar, bir sistemin gerçek ontolojisidir.** Fowler'ın deyimiyle: bana veri yapılarını göster, akışları kendim çıkarırım. Entity'ler ve aralarındaki ilişkiler, iş mantığının iskeletini verir. UI değişir, endpoint'ler değişir, ama `users`, `orders`, `payments` tabloları sistemin ne olduğunu söyler.
3. **Giriş noktaları (entry points).** HTTP route tanımları, message queue consumer'ları, cron job'lar, CLI komutları. Dış dünya sisteme nereden dokunuyor? Route tablosu, feature'ların bir listesidir.
4. **Dizin yapısı.** Klasör isimleri mimariyi ele verir. `domain/`, `infrastructure/`, `handlers/`, `services/` — bunlar mimarın kafasındaki katman modelidir.

**Belirti: "Şu spesifik davranışı/bug'ı anlamam lazım" → Aşağıdan yukarı, izle-ve-takip et.**
Büyük resmi çıkarmaya çalışma; bu tuzaktır. Tek bir iz seç ve onu uçtan uca takip et. En güçlü teknik: **kullanıcıdan gelen isteği koddaki fiziksel yerinden yakala, aşağı doğru in.** Görünen bir string (buton yazısı, hata mesajı, log satırı) her zaman en iyi giriş kancasıdır — çünkü aramada tektir. `grep` ile o stringi bul, oradan çağrı zincirini izle.

**Belirti: "Bu değişiklik güvenli mi, nereye dokunuyorum?" → Etki analizi (blast radius) yönüne git.**
Değiştireceğin fonksiyonun/sınıfın çağrılarını (call sites) bul. "Kim beni çağırıyor?" ve "Ben kimi çağırıyorum?" — IDE'nin "Find Usages / Find References" özelliği burada altındır. Test dosyaları da paha biçilmezdir: bir fonksiyonun testi, o fonksiyonun **niyetinin** en dürüst dokümantasyonudur; yorumlar yalan söyler, geçen testler söylemez.

**Belirti: "Kod tabanının bütünü kaotik, nereden tutacağımı bilmiyorum" → İki uçtan sıkıştır.**
Bir uçta veri modeli (ne var), diğer uçta giriş noktaları (dışarıdan ne tetikleniyor). İş mantığı bu ikisinin arasında bir yerdedir. Bir feature seç, giriş noktasından başla, veri modeline kadar in — ortadaki katmanlar kendini gösterir. Tüm sistemi değil, **bir dikey dilimi** (vertical slice) baştan sona anla; bir dilimi anlayınca kalıp tekrar eder, ikinci feature'ı çok daha hızlı çözersin. Çoğu kod tabanı "aynı deseni 200 kez tekrarlar"; bir örneği tam anladığında geri kalanı tanıma (pattern matching) işine döner.

### Kritik ilke: git geçmişi bir zaman makinesidir

Acemi kodu "şu an" olarak okur. Pro kodu **"nasıl bu hale geldi"** olarak okur. Anlamadığın, tuhaf duran bir satır gördüğünde ilk refleks `git blame` olmalı. O satırı hangi commit ekledi? Commit mesajı ne diyor? Hangi issue/PR ile geldi? Çoğu zaman "neden burada bu garip null kontrolü var?" sorusunun cevabı, 4 yıl önce bir üretim olayını çözen commit'in içindedir.

`git log -p <dosya>` bir dosyanın tüm evrimini gösterir. `git log -S "aramaString"` (pickaxe) belirli bir kod parçasının kod tabanına ne zaman girdiğini/çıktığını bulur — inanılmaz güçlü, az bilinen bir araç. **Chesterton'ın Çiti** ilkesi burada geçer: bir çitin neden orada olduğunu anlamadan onu kaldırma. Tuhaf gelen kod genelde bir yarayı sarıyordur.

### Bilinçli olarak yüzeysel kal (dikey vs yatay okuma)

En önemli disiplin: **ne zaman durmayı bileceksin.** Bir çağrı zincirini izlerken her fonksiyonun içine dalarsan (dikey), 20 dakika sonra çağrı yığınında (call stack) 15 kat derinde kaybolursun ve nereden başladığını unutursun. Pro yatay okur: bir fonksiyona girer, ne yaptığını **isminden ve imzasından** bir kutu (black box) olarak kabul eder, "bunun `X` döndürdüğünü varsayıyorum" der ve devam eder. İçine ancak o kutu şüpheliyse iner. Soyutlamalara güvenmek bir zayıflık değil, hayatta kalma stratejisidir. İçine dalman gereken katmanı yanlış seçmek, zaman kaybının bir numaralı sebebidir.

### Zihinsel model kur, notunu tut

Okurken kafanda tutmaya çalışma; kafan kova değil, süzgeçtir. Basit bir kutu-ok diyagramı çiz (kağıt, Excalidraw, whiteboard fark etmez). "İstek → Controller → Service → Repository → DB" gibi. Anlamadığın yerlere soru işareti koy. Bu diagram senin **çalışan hipotezindir** ve okudukça güncellenir. Bu haritayı ekibe göstermek ayrıca altındır: kıdemliler senin yanlış anladığın oku anında düzeltir ("hayır, o servis artık kullanılmıyor, orası ölü kod").

## 3. Gerçek senaryo üzerinden yürüyüş

Diyelim ki devraldığın bir e-ticaret sisteminde şu bug var: **"Bazı kullanıcılara sipariş onay e-postası gitmiyor, ama sipariş oluşuyor."** Sen bu kodu hiç görmedin. Dil fark etmez; mantığı takip et.

**Adım 1 — Kancayı bul.** E-posta gitmiyor. En somut, en tekil dize e-posta ile ilgili bir şeydir. Şablon adını ya da log satırını ararsın:

```
grep -rn "order_confirmation" .
grep -rn "sipariş onay" .
```

Bu seni `notifications/email_service` içinde bir `send_order_confirmation(order)` fonksiyonuna götürür. Kancayı yakaladın.

**Adım 2 — Yukarı doğru izle: bunu kim çağırıyor?** IDE'de "Find Usages". Tek bir çağıran var:

```python
def place_order(cart, user):
    order = create_order(cart, user)      # DB'ye yazar, commit eder
    charge_payment(order)                  # ödeme
    send_order_confirmation(order)         # e-posta
    return order
```

İlk bakışta mantıklı görünüyor. Ama "bazı kullanıcılara gitmiyor, siparişse oluşuyor" belirtisi kritik: sipariş DB'ye yazılıyor (adım 1 başarılı), ama e-posta atılamıyor. Demek ki `charge_payment` ile `send_order_confirmation` arasında ya da e-posta gönderiminde, **bazı** durumlarda bir kopukluk var.

**Adım 3 — Teşhis: içine in, ama seçici in.** `send_order_confirmation`'a bakarsın:

```python
def send_order_confirmation(order):
    template = render_template("order_confirmation", {
        "name": order.user.full_name,
        "items": order.items,
        "total": order.total,
    })
    smtp_client.send(to=order.user.email, body=template)
```

Şimdi "bazı kullanıcılar" ipucunu kovalarsın. `order.user.full_name` ya da `order.user.email` bazı kullanıcılarda `None` olabilir mi? `git blame` ile `full_name` alanına bakarsın — 6 ay önceki bir commit `first_name`/`last_name` alanlarını `full_name` ile değiştirmiş ama eski kullanıcılarda `full_name` migration'ı tam çalışmamış. `render_template` içinde `None.strip()` gibi bir çağrı **exception fırlatıyor**.

**Adım 4 — Asıl kök neden burada.** Exception fırlıyor ama sipariş neden hâlâ oluşuyor? `place_order`'ı çağıran controller'a çıkarsın:

```python
def handle_checkout(request):
    try:
        order = place_order(request.cart, request.user)
    except Exception as e:
        log.error("checkout failed")   # sadece loglar, yutar
    return redirect("/orders")
```

İşte gerçek suçlu: **çıplak `except Exception` her şeyi yutuyor.** E-posta gönderimindeki exception yakalanıyor, loglanıyor (o da genel bir mesajla, stack trace olmadan), ama sipariş zaten `create_order` içinde commit'lenmiş olduğu için DB'de duruyor. Kullanıcı siparişi görüyor, e-posta gelmiyor, kimse de exception'ı fark etmiyor çünkü log mesajı gürültüde kayboluyor.

**Düzeltilmiş hali** iki katmanda:

```python
# 1. Şablonu savunmacı yap
"name": order.user.full_name or order.user.email or "Değerli müşterimiz",

# 2. E-posta gönderimini sipariş işleminden ayır (transactional outbox / kuyruk)
def place_order(cart, user):
    order = create_order(cart, user)
    charge_payment(order)
    enqueue_email("order_confirmation", order.id)  # kuyruğa at, senkron gönderme
    return order

# 3. Çıplak except'i öldür — en azından yeniden fırlat/spesifik yakala
except PaymentError as e:
    log.error("payment failed", order_id=order.id, exc_info=True)
    raise
```

Bu yürüyüşte dikkat et: kodun tamamını okumadım. Tek bir izi (e-posta gitmiyor) yakaladım, yukarı-aşağı takip ettim, `git blame` ile tarihsel bağlamı aldım, ve kök nedeni (yutulan exception + eksik migration) buldum. 2 milyon satırın belki 40'ını okudum. **Doğru 40 satır** buydu.

Bir not daha: "bazı kullanıcılar" ifadesi teşhisin pusulasıydı. Belirtiyi ciddiye al. "Herkeste bozuk" başka yere, "bazılarında bozuk" başka yere, "belirli saatlerde bozuk" bambaşka bir yere (zamanlama/kaynak/tutarlılık) işaret eder. Pro, koda dalmadan önce **belirtinin şeklini** okur; belirtinin şekli, kod tabanının hangi bölgesine bakacağını daraltır. Reprodüksiyon adımlarını netleştirmeden koda dalmak, karanlıkta el yordamıyla yürümektir. Önce "bunu ben nasıl tetiklerim?" sorusunu cevapla; tetikleyebildiğin bug, çözülmüş bug'ın yarısıdır. Debugger'ı ancak reprodüksiyonun varsa anlamlı biçimde kullanabilirsin.

## 4. Acemi vs pro

**Acemi: baştan başlar.** `main.py`'yi açar, satır satır okumaya çalışır. Pro dış kenardan (deploy, veri, giriş noktaları) ya da bir izden başlar. Kod bir roman değildir; başından sonuna okunmaz.

**Acemi her şeyi anlamaya çalışır, pro yeterince anlar.** Acemi bir fonksiyonu tam kavramadan devam edemez, her çağrının içine dalar ve boğulur. Pro kara-kutu soyutlamaya güvenir, sadece gereken derinliğe iner.

**Acemi tek geçişte anlamayı bekler, kendini aptal sanır.** Büyük kod kafa karıştırıcıdır — bu senin eksikliğin değil, sistemin doğasıdır. En kıdemli mühendis bile tanımadığı kodda ilk saatler bocalar. Fark, pro'nun bunu normal karşılaması ve sistematik ilerlemesidir; acemi utanıp soru sormaz, saatlerce debat eder.

**Acemi yorumlara ve isimlere güvenir, pro davranışa güvenir.** Yorum "bu fonksiyon fiyatı KDV dahil döndürür" der ama kod 3 yıl önce değişmiş, artık KDV hariç döndürüyor. Kod yalan söylemez, yorum söyler. Pro şüpheliyse **debugger'a atar, gerçek değeri görür.**

**Acemi kodu statik okur, pro çalıştırır.** Kafada yorumlamak (interpretering in your head) yavaş ve hataya açıktır. Pro breakpoint koyar, gerçek çağrı yığınını görür, gerçek değişken değerlerine bakar. Beş dakikalık bir debugger oturumu, yarım saatlik statik okumadan daha çok öğretir.

**"İşe yarar gibi görünüp üretimde patlayan" tuzaklar:**

- **Ölü kod / kullanılmayan yol.** Bir fonksiyonu bulur, mantığını çözer, saatler harcarsın — sonra o kodun hiç çağrılmadığını fark edersin. Önce "bu gerçekten çalışıyor mu?" diye sor (call sites, feature flag durumu, `git log`'daki son değişiklik tarihi). Ölü koda benzeyen ama nadir bir yolda çalışan koda dokunmak da tehlikeli — ikisini karıştırma; kanıt topla.
- **Kopyala-yapıştır ikizler.** Aynı mantığın 5 yerde kopyası vardır. Sen birini düzeltirsin, diğer 4'ü patlar. `grep` ile benzer kod ara.
- **Yan etkiler ve gizli bağlantı.** Fonksiyon `calculate_total` ismine sahip ama içeride sessizce DB'ye yazıyor ya da global state değiştiriyor. İsim masum, davranış değil. Pro "bu fonksiyonun yan etkisi var mı?" diye özellikle bakar.
- **Feature flag / config'e bağlı davranış.** Kod bir yolu gösteriyor ama üretimde flag kapalı, tamamen başka bir yol çalışıyor. Kodu okurken flag'lerin gerçek üretim değerini bilmeden yanlış hipotez kurarsın.
- **Async ve zamanlama.** Kod sıralı okunur ama gerçekte kuyruk, event, callback ile asenkron çalışır. "Bu satırdan sonra veri hazır" varsayımı üretimde race condition olarak patlar.
- **`git blame`'i atlamak.** Tuhaf bir kontrolü "gereksiz" diye silersin, iki hafta sonra o kontrolün önlediği üretim olayı geri gelir. Chesterton'ın çiti.

## 5. Araçlar ve saha notları

**IDE / dil sunucusu (LSP).** En temel silahın. "Go to Definition", "Find All References", "Call Hierarchy", "Go to Implementation". Dinamik dillerde (Python, JS) bunlar bazen eksik/yanılabilir — statik tipli dillerde (Go, Java, Rust, TypeScript) altın gibi çalışır. Type bilgisi olan bir kod tabanı, tiplerin kendisiyle okumayı hızlandırır; imza sana çok şey söyler.

**grep / ripgrep (`rg`).** Kaba ama vazgeçilmez. IDE'nin göremediği yerleri (string'ler, config, dinamik çağrılar, başka dildeki dosyalar) yakalar. `rg -n "pattern"` hızlıdır. Route ararken, string ararken, "bu değer nereden geliyor" derken ilk aracın. IDE'nin "find references"ı semantiktir ama dinamik/reflection çağrılarını kaçırır; `rg` metinseldir, hepsini görür (ama gürültülü).

**git: `blame`, `log -p`, `log -S` (pickaxe), `log --follow`.** Tarihsel bağlam. Bir dosyanın neden bu halde olduğunu, bir satırı kimin/neden eklediğini bulur. `git log --oneline -- <dosya>` bir dosyanın değişim sıklığını gösterir — çok değişen dosya ya kalp ya da sorun kaynağıdır.

**Debugger.** Statik okumanın çözemediğini beş dakikada çözer. Breakpoint koy, isteği tetikle, **gerçek** çağrı yığınını ve değişken değerlerini gör. "Bu fonksiyona bu değer nereden gelmiş?" sorusunun en hızlı cevabı call stack'tir. Statik olarak izi geriye sürmek yerine debugger'da yığına bakmak dakikalarını saatlerden korur. Uzaktan/üretim benzeri ortamda debugger takamıyorsan, geçici log ekle ve gerçek değeri gör.

**Observability: loglar, trace'ler, metrikler.** Üretimde çalışan bir sistemi anlamanın en dürüst yolu. Distributed tracing (Jaeger, Zipkin, OpenTelemetry, Datadog vb.) bir isteğin servisler arası gerçek yolunu gösterir — mikroservis mimarisinde kodu okuyarak asla çıkaramayacağın çağrı grafiğini canlı verir. Bir isteği trace ID ile takip etmek, 6 servisin kaynak kodunu okumaktan hızlıdır. Loglarda `grep` atarak "bu kod yolu gerçekten çalışıyor mu, ne sıklıkta" sorusunu cevaplarsın.

**Çağrı grafiği ve bağımlılık görselleştirme.** Büyük kod tabanında modüller arası bağımlılığı çıkaran araçlar (dile göre: `pydeps`, `madge` JS için, IDE'lerin dependency diagram'ları) mimari resmi hızlı verir. Ama körü körüne güvenme; üretilen grafik bazen gürültülü olur.

**Test paketi = spesifikasyon.** Bir modülü anlamak istiyorsan **önce testlerini oku.** Testler girdiyi-çıktıyı, edge case'leri, niyeti gösterir — hem de çalışan, doğrulanmış halde. Bir fonksiyonun ne yaptığını en hızlı anlama yolu, ona küçük bir test yazıp (ya da var olanı çalıştırıp) breakpoint koymaktır. Bu aynı zamanda anlayışını **doğrular**: hipotezini teste çevir, geçerse doğru anlamışsın.

**"Deneme değişikliği" tekniği.** Bir şeyin ne yaptığını anlamıyorsan, onu **kır**. Değeri değiştir, satırı yorum satırı yap, exception fırlat. Ne bozuldu? Test kırmızıya döndü mü, hangi test? Bu, kodun gerçek etkisini pasif okumadan çok daha net gösterir. (Tabii kendi branch'inde, üretimde değil.)

**Saha notları / sertleşmiş yargılar:**

- **İlk gün ortamı ayağa kaldır.** Kodu okumadan önce çalıştır. Local'de build alıp testleri koşturmak, mimariyi anlamanın yarısıdır ve seni "çalışan sistem" gerçekliğine bağlar. Ayağa kaldıramadığın sistemi tam anlayamazsın.
- **İnsan en hızlı arama motorudur.** Saatlerce tek başına debat etmek kahramanlık değil, verimsizliktir. Kıdemli birine "şu akışı 5 dakika anlatır mısın?" demek 3 saatini kurtarır. Ama önce kendi araştırmanı yap; boş soru değil, "ben şuraya kadar geldim, burada takıldım" sorusu sor. Kimse sıfırdan anlatmayı sevmez, ama iyi hazırlanmış soruyu herkes cevaplar.
- **Değiştirdiğin şeyi anla, gerisini değil.** "Kod tabanının tamamını anlayana kadar dokunmam" tuzağına düşme; o gün asla gelmez. Görev için gereken minimum bölgeyi anla, güvenli değişikliği yap, test et.
- **Sık değişen + karmaşık dosyaları işaretle.** `git log` sıklığı yüksek, satır sayısı çok, herkesin korktuğu dosyalar sistemin risk merkezleridir. Buraları erken tanı.
- **Kodun kokusunu güven olarak oku.** Tutarlı isimlendirme, iyi testler, temiz katmanlar gördüğün bölgelere daha çok güven; her yeri kaos olan bölgelerde her varsayımını doğrula.
- **Yorumlara değil, üretim davranışına inan.** Şüphede kaldığın her yerde: log, trace, debugger, test. Gerçek her zaman çalışan sistemde, kodun ve yorumun anlattığı hikâyede değil.
- **Anladığını yazıya dök, unutmadan.** Bir akışı çözdüğünde iki cümlelik bir not bırak — yorum satırı, ekip wiki'si, ya da PR açıklaması. Bu hem seni altı ay sonra kurtarır hem de en dürüst dokümantasyondur, çünkü sen tam da o kodu yeni anlamış biri olarak yazıyorsun; senden sonra gelen aynı labirentte kaybolmaz. Kıdemli mühendisin ekibe bıraktığı en kalıcı miras, kodun kendisi değil, kodun **haritasıdır.**
- **AI/arama araçlarını hipotez üreteci gibi kullan, doğrulayıcı değil.** "Bu fonksiyon ne yapıyor?" diye bir modele sormak hızlı bir başlangıç hipotezi verir, ama nihai gerçek yine call site'ta, testte, debugger'dadır. Aracın verdiği cevabı bir yere kadar yürüt, sonra kendi gözünle doğrula. Yanlış ama kendinden emin bir özet, hiç özet olmamasından tehlikelidir.

Son bir yargı: büyük kod okuma becerisi, sabırla değil **disiplinli sabırsızlıkla** gelişir. Her satırı anlamaya çalışan sabırlı kişi boğulur; hiçbir şeyi anlamadan atlayan sabırsız kişi yanlış değişiklik yapar. Doğru denge, "şu an bu görev için bunu bilmem gerekiyor mu?" sorusunu her fonksiyonda yeniden sormaktır. Gerekmiyorsa geç, gerekiyorsa kaz. Bu soruyu yüzlerce kez sormayı içselleştirdiğinde, tanımadığın devasa bir sistemde bir yabancı gibi değil, haritası olan bir kâşif gibi dolaşırsın.

Özetle: büyük yabancı kod okumak bir "zekâ" değil, bir **yöntem** işidir. Bir soru seç, bir iz yakala, dış kenardan ya da somut bir dizeden başla, seçici derinliğe in, git geçmişini zaman makinesi olarak kullan, hipotezini debugger/test ile doğrula, ve ne zaman durmayı bileceğini bil. Bunu yapan mühendis, tanımadığı 2 milyon satırlık bir sistemde bir hafta içinde faydalı olur; yapmayan ise altı ay sonra hâlâ "sistemi öğreniyorum" der.
