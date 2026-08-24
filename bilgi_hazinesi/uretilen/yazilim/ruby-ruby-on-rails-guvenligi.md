# Ruby / Ruby on Rails Güvenliği: Mass Assignment, YAML.load, ERB SSTI ve Deserialization

## Giriş: Neden Bu Konu Kapsanmalı

Ruby ve Ruby on Rails, güvenlik literatüründe genellikle PHP veya Java kadar öne çıkmaz; oysa 2010'ların başında Rails ekosisteminde ortaya çıkan bir dizi zafiyet, "framework varsayılanlarının güvenlik üzerindeki etkisi" konusunda sektörün en çok referans verdiği vakalardan biri haline gelmiştir. Rails'in "convention over configuration" (yapılandırma yerine kural) felsefesi, geliştiriciye hız kazandırırken, güvenlik açısından "varsayılan olarak açık" (secure-by-default olmayan) davranışlar üretmiştir. Bu makalede ele alacağımız dört konu -- mass assignment, `YAML.load` kaynaklı deserialization, ERB tabanlı Server-Side Template Injection (SSTI) ve Rails'e özgü `Marshal.load` zincirleri -- birbirinden bağımsız gibi görünse de aslında ortak bir kök nedene sahiptir: **kullanıcıdan gelen veriyi, onu üreten kodun güvendiği kadar güvenilir sanmak**.

Bu yazı, bir saldırı kılavuzu değil, bir **savunma ve tespit** kılavuzudur. Amaç; bu zafiyet sınıflarının neden var olduğunu, hangi mimari kararların onları doğurduğunu ve bir mühendisin kod tabanında bunları nasıl tespit edip önleyeceğini anlamaktır.

---

## 1. Mass Assignment: "Kullanıcı ne gönderirse modele o yazılır" Problemi

### Tanım

Mass assignment (toplu atama), bir web isteğindeki (ör. form POST'u veya JSON body) tüm alanların, tek bir çağrıyla doğrudan bir modelin (ActiveRecord nesnesinin) özniteliklerine (attributes) atanmasıdır. Rails'te klasik örnek şudur:

```ruby
# Denetimsiz (naif) kullanım
@user = User.new(params[:user])
@user.save
```

Burada `params[:user]` içinde ne varsa -- `name`, `email` gibi beklenen alanlar kadar `is_admin`, `role`, `account_balance` gibi beklenmeyen alanlar da -- doğrudan nesneye yazılır.

### Kök Neden

Kök neden, **veri modelinin dışa açık arayüzü ile iç durumu arasında bir ayrım (whitelist/izin listesi) olmamasıdır**. ActiveRecord, bir sütun veritabanı şemasında varsa, onu otomatik olarak bir "atanabilir öznitelik" (assignable attribute) olarak treat eder. Bu, ORM'in rahatlık sağlama amacıyla verdiği bir kolaylıktır ama aynı zamanda modelin *hangi alanların dışarıdan değiştirilebilir olduğu* konusunda hiçbir görüş belirtmemesi anlamına gelir.

Bunu şöyle düşünebiliriz: HTTP katmanı ile veritabanı şeması arasında doğrudan bir "boru hattı" kurulmuştur; aradaki iş mantığı katmanı (hangi alanların kullanıcı tarafından değiştirilebileceğine dair kural) atlanmıştır. Saldırgan, formda görünmeyen ama modelde var olan bir alanı (`admin`, `role`, `verified` gibi) HTTP isteğine manuel olarak ekleyerek, uygulamanın hiçbir yerinde yazılmamış bir "yetki yükseltme" (privilege escalation) yolu bulur. Buna literatürde bazen "parameter pollution" veya daha spesifik olarak Rails bağlamında yaygınca "mass assignment vulnerability" denir.

### Tarihsel Bağlam

Rails, bu sorunu zamanla iki aşamalı olarak ele almıştır:

1. **`attr_accessible` / `attr_protected` dönemi**: Model seviyesinde, hangi özniteliklerin toplu atamaya izin verdiğini (whitelist) veya vermediğini (blacklist) tanımlayan bir mekanizma. Sorun: bu **opt-in** bir korumaydı, yani geliştirici bunu unutursa model tamamen açık kalırdı. Blacklist yaklaşımı da doğası gereği kırılgandı çünkü yeni eklenen her hassas alanın blacklist'e manuel eklenmesi gerekiyordu -- "unutulan bir satır" tüm korumayı devre dışı bırakabiliyordu.

2. **Strong Parameters (Rails 4+)**: Koruma, model katmanından controller katmanına taşındı ve **varsayılan olarak kapalı** hale geldi. `params.require(:user).permit(:name, :email)` gibi bir çağrı olmadan hiçbir parametre modele geçirilemez; izin verilmeyen alanlar sessizce (veya `ActionController::UnpermittedParameters` uyarısıyla) filtrelenir. Bu, "secure by default" prensibinin somut bir uygulamasıdır: geliştirici hiçbir şey yapmasa bile varsayılan davranış güvenlidir, sadece izin verilen alanlar geçer.

### Doğru Kullanım ve Tuzaklar

- **Her zaman explicit whitelist kullanın.** `permit!` (tüm parametrelere izin veren "kaçış kapısı") kullanmayın; bu, Strong Parameters'ı tamamen devre dışı bırakır ve eski `attr_accessible` öncesi duruma geri döner.
- **Nested attributes tuzağı**: `accepts_nested_attributes_for` kullanılan ilişkilerde, iç içe geçmiş parametrelerin (`user[account_attributes][role]` gibi) her katmanının ayrı ayrı `permit` edilmesi gerekir. Geliştiriciler genellikle üst seviye alanları whitelist'e alır ama nested attribute'ları unutur; bu da "gizli" bir mass assignment kapısı bırakır.
- **Rol/yetki alanları asla kullanıcı formundan gelmemeli.** `role`, `is_admin`, `permissions` gibi alanlar, controller içinde ayrı ve açık bir iş mantığıyla (ör. sadece bir admin panelinden, ayrı bir endpoint'ten) değiştirilmelidir; asla genel "update profile" akışının parametre listesine dahil edilmemelidir.
- **API/JSON body'lerde de aynı disiplin geçerlidir.** JSON tabanlı API'lerde geliştiriciler bazen "JSON zaten yapılandırılmış veri, güvenlidir" yanılgısına düşer; oysa mass assignment açısından JSON body ile form POST'u arasında hiçbir fark yoktur.

### Tespit

Kod incelemesinde şu desenler kırmızı bayraktır:
- `Model.new(params[...])` veya `Model.update(params[...])` çağrısında `permit` çağrısının olmaması.
- `permit!` kullanımı.
- Controller'da `params.permit` listesinin, modelin hassas alanlarını (rol, bakiye, doğrulama durumu) içermesi.
- Statik analiz araçları (ör. Brakeman gibi Rails'e özgü güvenlik tarayıcıları) bu deseni otomatik olarak işaretleyebilir; CI/CD hattına böyle bir taramanın entegre edilmesi, mass assignment'ın "insan hatası" ile geri dönmesini büyük ölçüde engeller.

---

## 2. `YAML.load` ve Rails'e Özgü Deserialization Zincirleri

### Tanım

YAML (YAML Ain't Markup Language), Ruby ekosisteminde yapılandırılmış veriyi seri hale getirmek (serialize) için yaygın kullanılan bir formattır. Ruby'nin standart kütüphanesindeki `Psych` (YAML işleyicisi), `YAML.load` metoduyla bir YAML string'ini Ruby nesnelerine dönüştürür. Sorun şudur: YAML formatı, sade veri türlerinin (string, integer, hash, array) yanı sıra **keyfi Ruby sınıflarının nasıl örneklendirileceğini** de tanımlayabilir (`!ruby/object:SinifAdi` etiketiyle).

`YAML.load`, varsayılan olarak bu "hangi sınıfın örnekleneceği" bilgisine güvenir ve saldırgan kontrolündeki bir YAML string'i verildiğinde, uygulamanın hiç beklemediği sınıflardan nesneler oluşturabilir.

### Kök Neden: Deserialization Neden Tehlikelidir

Bu noktada genel deserialization güvenlik prensibini anlamak önemlidir: **deserialization, bir sınıfın constructor'ını (veya ona eşdeğer bir başlatma mekanizmasını) saldırganın kontrol ettiği veriyle çalıştırma yeteneğidir.** Eğer bir uygulamada, örnekleme (instantiation) sırasında veya nesnenin bir yan etkisi olarak (ör. `initialize`, `to_s`, bir callback, bir `method_missing`) tehlikeli bir işlem (dosya okuma/yazma, komut çalıştırma, obje enjeksiyonu) tetiklenen **herhangi bir sınıf** class-path üzerinde bulunuyorsa, saldırgan bu sınıfı YAML içinde referans göstererek o yan etkiyi tetikleyebilir.

Bunun klasik örneği, Ruby standart kütüphanesindeki veya yaygın gem'lerdeki "gadget zincirleri"dir (gadget chain): doğrudan zararlı olmayan, meşru amaçlarla yazılmış sınıflar zincirlenerek, sonunda rastgele kod çalıştırma (Remote Code Execution, RCE) elde edilir. Rails ekosisteminde bilinen ve sektörde yaygın referans verilen vakalardan biri, Active Support/Active Record'un JSON/XML parametre işleme yollarının, arka planda `YAML.load`'a (veya benzer güvensiz deserialization'a) düşmesiyle ortaya çıkan zincirlerdi -- bu, 2013 civarında Rails topluluğunda ciddi bir "acil güvenlik güncellemesi" dalgasına yol açmış, yaygın bilinen bir CVE grubudur (tam CVE numarasını ve kesin sürüm aralığını burada telaffuz etmek yerine, okuyucuya bu sınıfın **var olduğunu ve gerçek dünyada yıkıcı sonuçlar doğurduğunu** vurguluyorum; kesin numaraları resmi Rails güvenlik danışma kayıtlarından teyit ediniz).

`Marshal.load` da kavramsal olarak aynı kategoridedir: Ruby'nin ikili (binary) serileştirme formatıdır ve `YAML.load`'dan bile daha az kısıtlayıcıdır çünkü hemen hemen her Ruby nesnesini olduğu gibi bayt akışından geri kurabilir. Güvenilmeyen kaynaktan (kullanıcı cookie'si, cache içeriği, harici mesaj kuyruğu) gelen veriyi `Marshal.load` ile açmak, YAML'dekiyle aynı sınıfta ama genelde daha geniş saldırı yüzeyine sahip bir risktir.

### Neden Sadece "JSON Kullan" Demek Yeterli Değil

Doğal soru şu olur: "Neden hâlâ YAML/Marshal kullanılıyor?" Cevap, bu formatların Ruby'nin *native* nesne modelini (semboller, aralıklar, özel sınıflar, döngüsel referanslar) JSON'un aksine kayıpsız temsil edebilmesidir. Rails'in bazı iç mekanizmaları (ör. eski session store'lar, bazı cache serializer'ları) tarihsel olarak bu zenginlik nedeniyle YAML/Marshal'a dayanmıştır. Session cookie'lerinin (`ActionDispatch::Session::CookieStore`) şifrelenmemiş/imzalanmamış veya zayıf yapılandırılmış olduğu senaryolarda, saldırganın kendi hazırladığı serileştirilmiş veriyi cookie olarak sunması, doğrudan sunucu tarafında deserialization tetiklemesi anlamına gelebilir -- bu yüzden "session bütünlüğü" (imzalama/MAC doğrulama) ile "deserialization güvenliği" birbirini tamamlayan iki savunma katmanıdır; biri diğerinin yokluğunu telafi etmez.

### Doğru Kullanım ve En İyi Pratikler

- **`YAML.load` yerine `YAML.safe_load` kullanın.** `safe_load`, varsayılan olarak yalnızca temel türlere (String, Integer, Array, Hash, nil, boolean) izin verir; keyfi sınıf örneklemesine (`!ruby/object`) izin vermez. Modern Psych sürümlerinde `YAML.load` bile daha güvenli varsayılanlara kaymıştır, ancak **hangi sürümde hangi davranışın varsayılan olduğunu varsaymak yerine, açıkça `safe_load` ve izin verilen sınıf listesini (`permitted_classes:`) belirtmek** en sağlam yaklaşımdır.
- **Güvenilmeyen kaynaktan asla `Marshal.load` çağırmayın.** Marshal, tasarım gereği süreç-içi/güvenilir veri için düşünülmüştür (ör. aynı uygulamanın kendi ürettiği cache verisi); dış girdi için uygun bir format değildir.
- **Session store seçimini bilinçli yapın.** Cookie tabanlı session store kullanıyorsanız, `secret_key_base`'in gizliliğinin ve imzalama/şifreleme mekanizmasının bütünlüğünün, deserialization saldırılarına karşı ilk savunma hattı olduğunu unutmayın. Sunucu taraflı session store (Redis, veritabanı) kullanmak, cookie içeriğinin saldırganın doğrudan kontrolünde olmasını engelleyerek saldırı yüzeyini daraltır.
- **Bağımlılıkları güncel tutun.** Gadget zincirleri genellikle framework'ün kendisinde değil, class-path'te bulunan *herhangi bir* gem'de yaşayabilir. Bu yüzden "ben YAML.load kullanmıyorum, güvendeyim" savunması yeterli değildir -- eğer bağımlılıklarınızdan biri iç mekanizmasında YAML/Marshal kullanıyorsa risk devam eder.

### Tespit

- Kod tabanında `YAML.load(`, `Marshal.load(`, `Psych.load(` aramaları yapın; her birinin girdi kaynağını (kullanıcıdan mı, dahili cache'ten mi) izleyin.
- Statik analiz araçları bu çağrıları genellikle "güvensiz deserialization" olarak işaretler.
- Rails ve tüm gem bağımlılıklarının güvenlik danışma (security advisory) akışını takip edin; bu sınıf zafiyetler framework güncellemeleriyle kapatılır, bu yüzden bağımlılık güncelliği burada doğrudan bir güvenlik kontrolüdür.

---

## 3. ERB ve Server-Side Template Injection (SSTI)

### Tanım

ERB (Embedded Ruby), Rails'in varsayılan template motorudur; `<%= ... %>` ve `<% ... %>` etiketleriyle HTML içine Ruby kodu gömülmesini sağlar. SSTI, **kullanıcı girdisinin, template motoru tarafından "kod" olarak değerlendirilmesi** durumunda ortaya çıkar -- yani template'in kendisi (statik yapı) değil, template motoruna verilen *string'in kendisi* dinamik ve saldırgan kontrolünde olduğunda.

Tehlikeli desen şudur:

```ruby
# Tehlikeli: kullanıcı girdisi template olarak render ediliyor
render inline: params[:template]
```

veya bir view içinde kullanıcı girdisinin doğrudan `ERB.new(user_input).result` ile işlenmesi.

### Kök Neden

XSS (Cross-Site Scripting) ile SSTI arasındaki farkı netleştirmek kök nedeni anlamayı kolaylaştırır:
- **XSS**'te kullanıcı girdisi, render edilmiş **çıktıya** (HTML/JS) enjekte edilir; tarayıcıda çalışır.
- **SSTI**'de kullanıcı girdisi, render edilme **öncesinde** template motorunun *girdisine* (template kaynağının kendisine) karışır; sunucuda, template motorunun tam ifade gücüyle çalışır.

ERB söz konusu olduğunda bu ifade gücü, saf bir "template dili" değil, **tam teşekküllü Ruby'dir**. Yani ERB'de SSTI, diğer bazı template motorlarındaki (sınırlı ifade dili olan) SSTI'lardan çok daha vahimdir: saldırgan `<%= system('...') %>` benzeri bir payload'ı template kaynağına sokabilirse, doğrudan Ruby seviyesinde -- dolayısıyla işletim sistemi seviyesinde -- kod çalıştırma elde eder. Kök neden, template motorunun "görüntüleme mantığı" ile "genel amaçlı programlama dili" arasındaki sınırın ERB'de fiilen olmamasıdır.

### Yaygın Hatalar

1. **Kullanıcı tarafından özelleştirilebilir "template" özellikleri.** Ör. bir e-posta bildirim şablonunu kullanıcının kendisinin düzenleyebildiği bir sistem (pazarlama e-postası şablonları, otomatik yanıt mesajları) tasarlanırken, bu şablonun `render inline:` veya `ERB.new` ile doğrudan işlenmesi.
2. **"Sadece iç kullanıcılar/adminler girebiliyor, güvenli" yanılgısı.** Yetki seviyesi ne olursa olsun, template motoruna *kod olarak* geçirilen her girdi, o yetki seviyesinin ötesine (sunucu süreci düzeyine) çıkma potansiyeli taşır -- bu bir yetki sınırı ihlalidir (privilege boundary violation), sadece "güvenilir kullanıcı" varsayımıyla kapatılamaz.
3. **String interpolation ile template üretme.** Dinamik olarak `"<%= #{user_input} %>"` gibi bir string kurup bunu ERB'ye vermek, girdinin şablon *yapısına* karışmasına izin verir; bu SSTI'nın doğrudan tarifidir.

### Doğru Kullanım ve En İyi Pratikler

- **Kullanıcı girdisini asla template kaynağı olarak kullanmayın.** Kullanıcı girdisi her zaman template'in *değişkeni* (yani `<%= @kullanici_adi %>` gibi bir yer tutucuya beslenen veri) olmalı, template'in *metni* olmamalıdır.
- **Eğer gerçekten kullanıcı tanımlı şablonlama gerekiyorsa**, sınırlı ifade gücüne sahip bir "sandboxed" veya "logic-less" template dili (ör. yalnızca değişken değiştirme ve basit koşullar sunan, keyfi kod çalıştırmaya izin vermeyen bir motor) tercih edilmelidir. Genel amaçlı ERB'yi sandbox'lamaya çalışmak (belirli metodları kara listeye almak gibi) kırılgan bir yaklaşımdır çünkü Ruby'nin dinamik doğası (metaprogramlama, `method_missing`, `send`) kara listeleri atlatmak için sayısız yol sunar.
- **Rails'in otomatik HTML kaçışını (auto-escaping) SSTI ile karıştırmayın.** `<%= %>` çıktısının HTML-escape edilmesi, XSS'e karşı korur ama SSTI'ya karşı hiçbir koruma sağlamaz çünkü SSTI, çıktının escape edilip edilmemesinden önceki bir aşamada (template'in derlenmesi/değerlendirilmesi aşamasında) gerçekleşir.

### Tespit

- `render inline:`, `ERB.new(`, `template.result(` gibi çağrıların girdi kaynağını denetleyin.
- Kod incelemesinde "kullanıcı kendi şablonunu tanımlayabilir" özelliği olan her yer, ayrı bir tehdit modellemesi (threat modeling) oturumu gerektirir.
- Dinamik template derleme özelliği ürün gereksinimi olarak talep edildiğinde, mühendislik ekibi bunu bir "genel kod çalıştırma" özelliği olarak ele almalı ve buna göre izole edilmiş (sandboxed, ayrı süreç/konteyner) bir mimari önermelidir.

---

## 4. Ortak Zemin: Bu Dört Zafiyetin Birleştiği Nokta

Mass assignment, güvensiz deserialization ve SSTI, yüzeyde farklı teknik mekanizmalar olsa da hepsi aynı mimari hataya işaret eder: **"veri" ile "kontrol/yapı" arasındaki sınırın bulanıklaşması.**

- Mass assignment'ta: kullanıcı verisi ile modelin *hangi alanlarının yazılabilir olduğuna dair kural* arasındaki sınır kayboluyor.
- Deserialization'da: seri hale getirilmiş veri ile *hangi sınıfın nasıl örnekleneceğine dair kod* arasındaki sınır kayboluyor.
- SSTI'da: görüntülenecek veri ile *template'in yapısını tanımlayan kod* arasındaki sınır kayboluyor.

Bu, güvenlik mühendisliğinde tekrar eden evrensel bir örüntüdür (SQL injection'daki sorgu/veri karışımı, command injection'daki komut/argüman karışımı ile aynı ailedendir). Rails'in tarihi, bu sınırları *varsayılan olarak* çizmenin (Strong Parameters'ın zorunlu whitelist yapması, `safe_load`'ın varsayılan güvenli davranışı gibi) framework düzeyinde ne kadar etkili bir savunma olduğunu göstermiştir.

### Genel Savunma İlkeleri (Özet)

1. **Varsayılan olarak reddet, açıkça izin ver (deny-by-default, explicit allow).** Strong Parameters bunun ders kitabı örneğidir.
2. **Girdi kaynağının güven seviyesini asla varsaymayın.** "Sadece adminler erişebiliyor" veya "bu iç API" gerekçeleri, deserialization ve template injection risklerini ortadan kaldırmaz.
3. **Bağımlılık güncelliğini bir güvenlik kontrolü olarak görün**, sadece bir bakım işi değil. Gadget zincirleri framework dışında, bağımlılık grafiğinin herhangi bir yerinde yaşayabilir.
4. **Statik analiz araçlarını (Rails ekosistemine özgü güvenlik tarayıcıları) CI/CD'ye entegre edin.** Bu sınıf zafiyetlerin çoğu (mass assignment, güvensiz `YAML.load`, `render inline:` kullanımı) otomatik taramayla insan gözünden kaçmadan önce yakalanabilir.
5. **Derinlemesine savunma (defense in depth) uygulayın.** Session bütünlüğü, sunucu taraflı session store, minimum ayrıcalık ilkesiyle çalışan süreçler -- bunların hiçbiri tek başına yeterli değildir ama bir arada, tek bir zafiyetin tam sistem ele geçirmeye (full compromise) dönüşme olasılığını azaltır.

## Sonuç

Ruby ve Rails'in bu güvenlik geçmişi, aslında bir framework'ün olgunlaşma hikayesidir: erken dönemde geliştirici kolaylığına öncelik veren tasarım kararları (otomatik mass assignment, esnek deserialization, güçlü template motoru), zamanla "secure by default" prensibine doğru evrilmiştir. Bir mühendis için buradaki ders, sadece "bu üç API'yi kullanma" listesi ezberlemek değil, her yeni framework veya kütüphaneyi değerlendirirken şu soruyu sormaktır: *bu araç, kullanıcı girdisini nerede ve nasıl "kod" veya "yapı" seviyesine yükseltiyor, ve bu yükseltme varsayılan olarak mı yoksa açık bir izinle mi gerçekleşiyor?* Cevap "varsayılan olarak" ise, orada bir tehdit modellemesi borcu vardır.
