# Erlang/Elixir ve BEAM VM Güvenliği: Atom Tablosu Tükenmesi ve Dağıtık Node Güvenliği

## Giriş: BEAM Neden Farklı Bir Güvenlik Modeli Gerektirir?

Erlang ve Elixir, aynı sanal makine olan **BEAM** (Bogdan/Björn's Erlang Abstract Machine) üzerinde çalışan iki dildir. Bu platform, telekomünikasyon altyapılarında (Ericsson'un AXD301 telefon santrali gibi), mesajlaşma sistemlerinde (WhatsApp'ın backend'i yıllarca Erlang üzerine kuruluydu), gerçek zamanlı sistemlerde (Discord, RabbitMQ) ve dağıtık veritabanlarında (Riak, CouchDB) yaygın olarak kullanılır. Ortak paydası şudur: **çok yüksek eşzamanlılık** (concurrency) ve **hata toleransı** (fault tolerance).

BEAM'in güvenlik açısından ilginç olmasının nedeni, tasarım felsefesinin klasik dillerden çok farklı olmasıdır. C/C++'ta bellek güvenliği (memory safety) merkezi bir konudur; buffer overflow, use-after-free gibi zafiyetler ön plandadır. BEAM ise **managed** bir ortamdır: garbage collection vardır, işaretçi aritmetiği yoktur, süreçler (process) birbirinden bellek düzeyinde izoledir. Dolayısıyla klasik bellek bozma saldırıları BEAM üzerinde büyük ölçüde geçersizdir.

Ancak BEAM kendine özgü, dile ve çalışma zamanına özgü zafiyet sınıfları getirir. Bunların en ünlü ikisi bu makalenin konusu:

1. **Atom table exhaustion** — dinamik olarak atom üretilmesinin yol açtığı, geri döndürülemez bir kaynak tükenmesi (DoS).
2. **Distributed node security** — BEAM node'larının birbirine bağlanma modelindeki, cookie tabanlı zayıf kimlik doğrulama.

Bu iki konu, "yeni bir dil öğrenmek" ile "bir dilin güvenlik modelini anlamak" arasındaki farkı çok iyi gösterir.

---

## Bölüm 1: Atom Nedir ve Neden Tehlikelidir?

### Tanım: Atom Kavramı

Erlang/Elixir'de **atom**, kendi adı değeri olan bir sabittir. Erlang'da `ok`, `error`, `undefined` gibi küçük harfle başlayan tanımlayıcılar atomdur; Elixir'de `:ok`, `:error` gibi iki nokta önekiyle yazılırlar. Modül adları (`GenServer`), boolean değerler (`true`, `false`, `nil` — bunlar aslında atomdur) hep atom sınıfındandır.

Atom'un cazibesi performanstan gelir. Bir atom, çalışma zamanında **global bir tabloya** (atom table) bir kez kaydedilir ve o andan sonra sadece bir **tamsayı indeks** ile temsil edilir. İki atomu karşılaştırmak, iki string'i karakter karakter karşılaştırmak yerine iki tamsayıyı karşılaştırmak kadar hızlıdır — O(1). Pattern matching, mesaj etiketleme, durum makineleri (state machine) hep bu ucuzluktan faydalanır.

### Kök Neden: Atomlar Garbage Collect EDİLMEZ

Kritik nokta şudur: **atom tablosuna eklenen atomlar asla silinmez.** BEAM'in garbage collector'ı süreç heap'lerini temizler, ama global atom tablosuna dokunmaz. Bir atom bir kez oluşturulduğunda, node yeniden başlatılana kadar bellekte kalır.

Bu, tasarımın bilinçli bir sonucudur: Atomların "sadece bir tamsayı" olabilmesi için, o tamsayı ile gerçek isim arasındaki eşlemenin kalıcı ve değişmez olması gerekir. Eğer atomlar toplanabilir olsaydı, indekslerin yeniden kullanılması gerekir ve bu da atom karşılaştırmasının O(1) güvencesini ve tüm sistemin tutarlılığını bozardı.

Atom tablosunun ayrıca bir **üst sınırı** vardır. Varsayılan olarak yaklaşık **1.048.576 (2^20)** atom kapasitesi vardır (bu sınır, VM başlatılırken `+t` bayrağıyla ayarlanabilir; kesin varsayılan sürümler arası küçük farklılıklar gösterebilir, ama mertebe olarak "milyonun biraz üzeri" doğrudur). Bu sınıra ulaşıldığında BEAM **kurtarılamaz biçimde çöker** — `system_limit` hatası verir ve node ölür. Bu bir process crash değil, tüm VM'in ölümüdür.

### Saldırı Mekanizması: Nasıl Sömürülür?

Zafiyet, **kullanıcı tarafından kontrol edilen (attacker-controlled) verinin dinamik olarak atoma dönüştürülmesinden** doğar. Kritik fonksiyon: `list_to_atom/1` (Erlang) veya `String.to_atom/1` (Elixir).

Kavramsal örnek — tehlikeli kod:

```elixir
# TEHLİKELİ: Dışarıdan gelen string'i doğrudan atoma çeviriyor
def parse_param(user_input) do
  String.to_atom(user_input)
end
```

Bir saldırgan, her istekte farklı bir string göndererek (`"aaaa1"`, `"aaaa2"`, `"aaaa3"`...) her seferinde yeni bir atom yaratılmasına neden olabilir. Her benzersiz string, tabloya kalıcı bir giriş ekler. Yeterince farklı değer gönderildiğinde tablo dolar ve tüm node çöker. Bu klasik bir **kaynak tükenmesi DoS'udur** (Denial of Service), ama iki özelliği onu özellikle sinsi yapar:

- **Kalıcıdır ve birikimlidir:** Trafik durdurulduğunda tablo boşalmaz. Saldırı yavaş yavaş, günlere yayılarak yapılabilir; her kötü niyetli istek tabloya kalıcı bir tuğla koyar.
- **Tek bir çökme yeterlidir:** BEAM'in fault-tolerance felsefesi "let it crash" (bırak çöksün, supervisor yeniden başlatsın) üzerine kuruludur. Ama burada çöken şey bir süreç değil, **tüm VM**'dir. Supervisor ağacı bile kurtaramaz.

Gerçek dünyada bunun klasik örneği, **JSON/XML ayrıştırıcılarının** anahtarları (key) atoma çevirmesidir. Eğer bir web servisi gelen JSON'un anahtarlarını otomatik olarak atoma dönüştürüyorsa, saldırgan `{"rastgele_anahtar_9832": 1}` gibi payload'larla tabloyu şişirebilir.

### Doğru Kullanım ve Savunma

**1. Güvenli dönüşüm fonksiyonunu kullan: `list_to_existing_atom` / `String.to_existing_atom`**

Bu fonksiyonlar yalnızca **zaten var olan** bir atomu döndürür; yoksa hata (`ArgumentError`) fırlatır, yeni atom yaratmaz.

```elixir
# GÜVENLİ: Sadece kod tabanında zaten tanımlı atomlara izin verir
def parse_status(user_input) do
  try do
    String.to_existing_atom(user_input)
  rescue
    ArgumentError -> :unknown
  end
end
```

Buradaki mantık şudur: Uygulamanızın meşru atomları (durum adları, mesaj etiketleri) kod derlendiğinde veya modüller yüklendiğinde zaten tabloya girmiştir. Dolayısıyla meşru girdiler `to_existing_atom` ile başarıyla eşleşir; saldırganın uydurduğu rastgele string'ler ise eşleşmez ve reddedilir.

**2. Atom yerine string/binary ile çalış**

Çoğu zaman atoma hiç ihtiyaç yoktur. HTTP header'ları, JSON anahtarları, kullanıcı adları gibi verileri **binary (string)** olarak tutmak hem güvenli hem de yeterlidir. Atom'u yalnızca **kapalı, sonlu bir küme** (örneğin durum makinesi durumları) söz konusuysa kullanın.

**3. Kütüphane yapılandırmasını denetle**

Elixir'de `Jason` gibi modern JSON kütüphaneleri **varsayılan olarak** anahtarları string olarak döndürür; atoma çevirme (`keys: :atoms`) yalnızca açıkça istenirse yapılır ve dokümantasyonda "güvenilmeyen girdide kullanmayın" uyarısı vardır. Eski `Poison` ve benzeri araçlarda bu davranış farklı olabilir. Bağımlılıklarınızın atom üretip üretmediğini bilmelisiniz.

**4. Atom sayısını izle (detection)**

`:erlang.system_info(:atom_count)` ve `:erlang.system_info(:atom_limit)` ile o anki atom sayısını ve sınırını okuyabilirsiniz. Üretimde bu değeri periyodik olarak metrik sistemine (Prometheus vb.) gönderip, sürekli artan bir atom sayısını alarm koşulu yapmak güçlü bir tespit yöntemidir. Sağlıklı bir uygulamada atom sayısı başlangıçtan sonra **plato** yapmalıdır; monoton artış bir sızıntı ya da saldırı işaretidir.

### Yaygın Hatalar

- **`to_atom`'u "geçici" sanmak:** Geliştiriciler atomların da string gibi çöp toplandığını varsayar. Yanlış — kalıcıdır.
- **Dinamik fonksiyon/modül çağrısında atom üretmek:** `apply(String.to_atom(mod), ...)` gibi kalıplar hem atom sızdırır hem de rastgele kod çalıştırma (arbitrary function invocation) riski taşır.
- **Sadece rate limiting'e güvenmek:** Rate limit yavaşlatır ama engellemez. Saldırı birikimli olduğu için, düşük hızda uzun süre çalıştırılırsa yine tabloyu doldurur. Asıl çözüm atom üretimini kaynakta kesmektir.

---

## Bölüm 2: Dağıtık Node Güvenliği ve Cookie Zafiyeti

### Tanım: Erlang Distribution ve Node Kavramı

BEAM'in en güçlü özelliklerinden biri **dağıtık çalışma**dır. Birden fazla BEAM örneği (her biri bir **node**) ağ üzerinden birbirine bağlanıp tek bir mantıksal küme gibi davranabilir. Bir node'daki süreç, başka bir node'daki sürece **tıpkı yerel bir süreçmiş gibi** mesaj gönderebilir. `Node.connect/1`, uzak node'da fonksiyon çağırma (`:rpc.call`), süreçleri uzaktan spawn etme — hepsi dile gömülüdür. Bu "location transparency" (konum şeffaflığı), dağıtık sistem yazmayı olağanüstü kolaylaştırır.

Ama tam da bu güç, güvenlik açısından tehlikelidir: Uzak bir node'a bağlanabilen biri, o küme üzerinde pratikte **tam denetim** elde eder.

### Kök Neden: Magic Cookie Tabanlı Kimlik Doğrulama

Node'lar arasındaki kimlik doğrulama, **magic cookie** adı verilen basit bir paylaşılan sırra (shared secret) dayanır. Cookie, sadece bir atomdur — düz bir metin parolası gibi düşünün. İki node'un birbirine bağlanabilmesi için **aynı cookie'ye** sahip olması gerekir.

Cookie şu yollarla belirlenir:
- VM başlatılırken `-setcookie <değer>` bayrağıyla,
- Kullanıcının ana dizinindeki `~/.erlang.cookie` dosyasından (VM ilk açılışta yoksa bunu otomatik oluşturur),
- Çalışma zamanında `Node.set_cookie/1` ile.

Bağlanma anındaki doğrulama (handshake) şöyle işler kavramsal olarak: Bir node bağlanmak istediğinde, karşı taraf bir **challenge** (rastgele sayı) gönderir; bağlanan node bu sayıyı kendi cookie'siyle birleştirip bir hash (tarihsel olarak MD5) üretir ve geri gönderir. Karşı taraf aynı hesabı kendi cookie'siyle yapar; sonuçlar eşleşirse bağlantı kabul edilir. Bu, cookie'nin ağ üzerinden düz metin geçmesini engeller (challenge-response), ama **cookie'nin kendisi hâlâ tek faktörlü, paylaşılan, çoğu zaman zayıf bir sırdır.**

### Zafiyetin Kaynağı: Neden Bu Model Zayıf?

**1. Cookie çoğu zaman zayıf veya öngörülebilir.** Otomatik üretilen `~/.erlang.cookie` rastgeledir, ama pratikte pek çok kurulumda cookie ya kolay tahmin edilir bir değere set edilir (örneğin uygulama adı), ya deployment betiklerine sabit yazılır (hardcoded), ya da tüm sunuculara aynı dosya kopyalanır. Cookie ele geçirilirse tüm küme tehlikededir.

**2. Kimlik doğrulama sonrası HİÇBİR yetkilendirme yoktur.** BEAM distribution modelinde, cookie doğrulaması geçen bir node **güvenilir (trusted)** kabul edilir ve pratikte sınırsız yetki alır. Yetki seviyeleri, izin kapsamları yoktur — "içeri girdinsе her şeyi yapabilirsin" modeli. Bağlanan node, uzak node üzerinde `:os.cmd("...")` ile **kabuk komutu çalıştırabilir**, herhangi bir modülü yükleyebilir, süreçleri öldürebilir. Yani cookie'yi bilmek, doğrudan **uzaktan kod çalıştırma** (Remote Code Execution) demektir.

**3. Şifreleme varsayılan DEĞİLDİR.** Klasik Erlang distribution trafiği **varsayılan olarak şifrelenmez** (düz TCP). Yani ağ dinleyen (sniffing) veya araya giren (MITM) bir saldırgan trafiği görebilir. TLS ile şifreleme **mümkündür** (Erlang'ın "TLS distribution" desteği vardır ve `inet_tls_dist` gibi mekanizmalarla yapılandırılır), ama bunu açıkça yapılandırmak gerekir; kutudan çıktığı haliyle açık değildir.

**4. EPMD keşif servisi açık bilgi sızdırır.** **EPMD** (Erlang Port Mapper Daemon), varsayılan olarak **4369** portunda dinleyen bir servis olup, hangi node'ların hangi portta çalıştığını eşler. Kimlik doğrulaması olmadan sorgulanabilir; bir saldırgan EPMD'yi sorgulayarak node adlarını ve dağıtım portlarını öğrenebilir — keşif (reconnaissance) için değerli bilgi.

### Örnek Senaryo (Kavramsal)

Bir kuruluş, Elixir tabanlı bir kümesini bulut sunucularında çalıştırıyor ve distribution portlarını (EPMD 4369 ve dinamik dağıtım portları) yanlışlıkla internete açık bırakıyor. Cookie de deployment betiğinde `-setcookie myapp_prod` olarak sabit yazılmış. Bir saldırgan:

1. 4369 portunu bulur, EPMD'yi sorgular, node adını ve portunu öğrenir.
2. Cookie'yi tahmin eder veya kaynak kod sızıntısından öğrenir.
3. Kendi BEAM node'unu aynı cookie ile başlatıp kümeye `Node.connect` ile katılır.
4. `:rpc.call` ile hedef node üzerinde işletim sistemi komutu çalıştırır.

Sonuç: tek faktörlü zayıf sır + ağ erişimi = tam sistem ele geçirme. Bu, teorik değil, yanlış yapılandırılmış üretim sistemlerinde gerçekleşmiş bir sınıf zafiyettir.

### Doğru Kullanım ve Savunma

**1. Distribution portlarını asla internete açma.** En temel ve en etkili savunma budur. EPMD (4369) ve dağıtım portları yalnızca **güvenilir bir iç ağda** veya VPN/private subnet arkasında erişilebilir olmalıdır. Firewall/security group kurallarıyla bu portları dışarıya tamamen kapatın. Distribution asla bir "internet arayüzü" değildir; küme içi haberleşme kanalıdır.

**2. Güçlü, rastgele, gizli cookie kullan.** Cookie uzun, yüksek entropili ve rastgele olmalı; kaynak koda veya betiklere gömülmemeli, bir secret manager'dan (Vault, cloud secret store) enjekte edilmelidir. `~/.erlang.cookie` dosyasının izinleri kısıtlı olmalıdır (yalnızca sahibi okuyabilmeli — BEAM zaten aksi durumda uyarı verir).

**3. TLS distribution'ı etkinleştir.** Node'lar arası trafiği TLS ile şifreleyip **karşılıklı sertifika doğrulaması** (mutual TLS) ekleyerek hem gizlilik hem de cookie'den bağımsız güçlü bir kimlik doğrulama katmanı sağlayın. Bu, düz cookie modelinin en ciddi zayıflığını kapatır: artık sadece cookie'yi bilmek yetmez, geçerli bir istemci sertifikası da gerekir.

**4. Dağıtım portlarını sabitle ve daralt.** Dinamik dağıtım port aralığı `inet_dist_listen_min` / `inet_dist_listen_max` ayarlarıyla dar ve bilinen bir aralığa sabitlenebilir; bu, firewall kurallarını yazmayı ve denetlemeyi kolaylaştırır.

**5. Gerekmiyorsa distribution'ı hiç açma.** Tek bir node çalıştıran (dağıtık olmayan) uygulamalar için distribution'ı ve EPMD'yi tamamen kapatmak, tüm bu saldırı yüzeyini yok eder.

### Tespit (Detection)

- **Beklenmeyen node bağlantıları:** `Node.list/0` veya `:net_kernel` olaylarını izleyin. `:net_kernel.monitor_nodes(true)` ile node bağlanma/kopma olaylarına abone olup, beklenmeyen bir node adının kümeye katılmasını alarm koşulu yapabilirsiniz. Meşru node adlarınızı bir allowlist ile kontrol edin.
- **EPMD ve dağıtım portlarına dış erişim:** Ağ katmanında bu portlara gelen dış bağlantı denemelerini loglayın; 4369'a gelen beklenmedik trafik güçlü bir keşif/saldırı sinyalidir.
- **Başarısız handshake'ler:** Yanlış cookie ile bağlanma denemeleri BEAM loglarında görünür; tekrarlayan başarısız handshake'ler bir brute-force girişimine işaret edebilir.

### Yaygın Hatalar

- **"İç ağ zaten güvenli" varsayımı:** Zero-trust bakışıyla, iç ağa erişen bir saldırgan (yanal hareket, ele geçirilmiş bir başka servis) cookie'yi biliyorsa doğrudan RCE elde eder. Ağ izolasyonu tek başına yeterli değildir; TLS + güçlü cookie savunmayı derinlemesine yapar.
- **Cookie'yi kaynak kodda tutmak:** Git geçmişinde kalan, log'lara düşen cookie'ler klasik sızıntı kaynağıdır.
- **TLS'i "sonra ekleriz" diye ertelemek:** Distribution kurulduktan sonra TLS'e geçmek yapılandırma değişikliği ve node'ların koordineli yeniden başlatılmasını gerektirir; baştan planlamak çok daha ucuzdur.
- **EPMD'yi unutmak:** Distribution portlarını kapatıp EPMD'yi (4369) açık bırakmak, saldırgana keşif bilgisi sağlamaya devam eder.

---

## Sonuç: BEAM Güvenliğinin Zihniyeti

BEAM, bellek güvenliği ve süreç izolasyonu sayesinde klasik saldırıların çoğuna dayanıklıdır. Ama güvenliği "yok" değildir; sadece **başka bir yere kaymıştır.** İki temel ders:

1. **Kaynak tükenmesi, BEAM'de bellek bozmanın yerini alır.** Atom tablosu, süreç sayısı, ETS tabloları gibi global ve sınırlı kaynaklar, saldırganın hedefidir. Özellikle atom tablosu, geri döndürülemezliği (GC edilmemesi) nedeniyle en tehlikelisidir. Kural basit: **güvenilmeyen girdiyi asla dinamik olarak atoma çevirme;** `to_existing_atom` kullan ya da binary ile çalış.

2. **Location transparency, güçlü bir güvenlik sınırı gerektirir.** Node'lar arası şeffaf haberleşme, geliştirme kolaylığı sağlarken kimlik doğrulaması geçen herkese sınırsız yetki verir. Cookie modeli tek başına zayıftır; savunma **ağ izolasyonu + güçlü sır yönetimi + TLS distribution** katmanlarının birleşimidir.

Her iki konu da, bir dilin sözdizimini öğrenmenin ötesinde, o dilin **çalışma zamanı modelini ve varsayılanlarını** anlamanın neden kritik olduğunu gösterir. BEAM'de güvenlik, kod satırlarında değil, **çalışma zamanının davranışını ve dağıtım topolojisini** doğru yapılandırmakta gizlidir.
