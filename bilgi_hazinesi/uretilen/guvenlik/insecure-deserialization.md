# Güvensiz Deserialization (Insecure Deserialization)

## Tanım

Serialization (serileştirme), bellekteki bir nesnenin (object) — alanları, tipi ve iç durumuyla birlikte — diske yazılabilir veya ağ üzerinden gönderilebilir bir bayt dizisine ya da metne dönüştürülmesidir. Deserialization (geri serileştirme) ise bunun tersidir: alınan bayt dizisinden nesneyi yeniden inşa etme işlemidir. Bu mekanizma başlı başına zararlı değildir; oturum durumunu (session state) saklamak, RPC/API çağrılarında nesne taşımak, cache doldurmak veya dağıtık sistemlerde mesaj iletmek için gündelik olarak kullanılır.

**Güvensiz deserialization**, uygulamanın *güvenilmeyen bir kaynaktan* (kullanıcı, ağ, cookie, mesaj kuyruğu) gelen serialized veriyi, içeriğinin gerçekten beklenen tipte ve zararsız olduğunu doğrulamadan geri serileştirmesi durumunda ortaya çıkar. Saldırgan, bu veriyi öyle biçimlendirir ki geri inşa süreci sırasında saldırganın seçtiği kod çalışır ya da uygulamanın mantığı çarpıtılır. Sonuç genellikle en ağır sınıftan bir açıktır: **Remote Code Execution (RCE)**. Yan etkiler arasında yetki yükseltme, denial of service, authentication bypass ve dosya işlemleri yer alır.

OWASP bu zafiyeti uzun süre kendi "Top 10" listesinde ayrı bir madde olarak tuttu; sonraki sürümlerde "Software and Data Integrity Failures" başlığı altında ele alındı. Popülerlik kazanmasının nedeni tekil bir hata olması değil, birçok dilin *tasarım gereği* güçlü ama tehlikeli deserialization mekanizmaları sunmasıdır.

## Kök Neden: Neden Bu Kadar Tehlikeli?

Sıradan bir veri formatı (örneğin JSON'ın düz kullanımı) yalnızca *veri* taşır: sayılar, string'ler, listeler. Buna karşılık dillerin native serialization biçimleri *veriyi değil, nesneleri* taşır. Nesne ise sadece durum değildir; bir **tip** ile ilişkilidir ve o tipin davranışları (metotları) vardır. İşte kök neden buradadır:

> Güvensiz deserialization, saldırganın **hangi tipte** nesnenin inşa edileceğini ve o nesnenin alanlarının **hangi değerlerle** doldurulacağını kontrol edebilmesinden doğar. Nesne inşa edilirken bazı diller belli metotları *otomatik olarak* tetikler. Saldırgan, çalışması istenmeyen ama yan etkisi tehlikeli olan bir tipi seçerek bu otomatik tetikleyicileri kendi lehine kullanır.

Bunu üç aşamada düşünmek faydalıdır:

1. **Tip seçimi:** Native format, akışın içine "bu bir X tipidir" bilgisini gömer. Deserializer bu bilgiye güvenerek X tipini örnekler. Saldırgan X'i istediği gibi değiştirebiliyorsa, uygulamanın hiç beklemediği ama classpath/ortamda mevcut olan tehlikeli bir sınıfı seçebilir.
2. **Otomatik geri çağırma (magic methods / callbacks):** Birçok dilde nesne yeniden kurulurken çalışan özel metotlar vardır. Örneğin PHP'de `__wakeup` ve `__destruct`, Python pickle'da `__reduce__`, Java'da `readObject`. Bunlar tam olarak deserialization anında, saldırganın kontrolündeki alanlarla çalışır.
3. **Gadget chain:** Tek bir sınıfın magic metodu genellikle doğrudan komut çalıştırmaz. Ama bu metot başka bir nesnenin bir metodunu çağırır, o da bir başkasını... Zincirin sonunda `Runtime.exec`, `system()`, `os.system` gibi bir "sink" (varış noktası) bulunur. Bu birbirini besleyen çağrı halkalarına **gadget chain** denir. Saldırganın kendi kodunu enjekte etmesi *gerekmez*; hedef uygulamada zaten var olan sınıfları lego parçaları gibi birleştirerek istediği etkiyi üretir.

Kritik nokta şudur: Zafiyet çoğu zaman deserializer'ın kendisinde bir "bug" değildir. Deserializer tam da tasarlandığı işi yapar — keyfi tipleri, keyfi alanlarla yeniden kurar. Sorun, bu güçlü yeteneğin güvenilmeyen girdiye açılmasıdır. Bu yüzden yama tek bir satır değil, çoğu zaman *mimari* bir karardır.

## Dile Göre Çalışma Mantığı ve Örnekler

### Java

Java'da `ObjectOutputStream.writeObject` bir nesneyi, `ObjectInputStream.readObject` ise onu geri üretir. `Serializable` arayüzünü uygulayan sınıflar, isteğe bağlı olarak özel bir `private void readObject(ObjectInputStream in)` metodu tanımlayabilir; bu metot deserialization sırasında çağrılır ve sınıf yazarına özel kurulum imkânı verir. İşte gadget'ların dayanağı budur.

Serialized Java verisi, hex olarak `AC ED 00 05` (Base64'te genellikle `rO0AB...` ile başlayan) sabit bir "magic number" ile başlar; bir trafikte bu imzayı görmek güçlü bir sinyaldir.

Gadget chain kavramını meşhur eden şey, **ysoserial** aracı ve popüler kütüphanelerdeki gadget'lardır. Klasik örnek, `InvokerTransformer` benzeri sınıflar içeren eski Apache Commons Collections sürümleridir. Bu sınıf, reflection (yansıma) yoluyla verilen bir nesne üzerinde adı sonradan belirlenen bir metodu çağırabilir. Bir `Map`/`Set` inşası tetiklendiğinde bu transformer zinciri çalışır ve sonunda `Runtime.getRuntime().exec(...)` çağrılır. Yani saldırgan hiçbir yeni sınıf yüklemeden, sadece classpath'te bu kütüphane olduğu için komut çalıştırabilir.

Java tarafında dikkat edilmesi gereken bir başka nokta: yalnızca `readObject` değil, `readResolve`, `validateObject` ve bazı framework'lerin (örneğin XML/JSON tabanlı deserializer'ların — XStream, Jackson'ın polymorphic tip çözümlemesi, bazı RMI/JMX yolları) da benzer tip-güdümlü inşa yapmasıdır. "Sadece binary serialization tehlikelidir" varsayımı yanlıştır; tip bilgisini girdiden alan her mekanizma risk taşır.

### PHP

PHP'de `serialize()` ve `unserialize()` fonksiyonları kullanılır. Serialized biçim insan tarafından okunabilir; örneğin:

```
O:4:"User":2:{s:4:"name";s:5:"admin";s:7:"isAdmin";b:1;}
```

Burada `O:4:"User"` "4 karakterlik ada sahip User sınıfının bir nesnesi", ardından alan sayısı ve alanlar gelir. Saldırgan bu metni elle üretebildiği için hem alan değerlerini (örneğin `isAdmin` bayrağını) hem de **hangi sınıfın** örnekleneceğini serbestçe belirleyebilir.

PHP'de magic metotlar zincirin kalbidir:
- `__wakeup()`: nesne unserialize edilirken çalışır.
- `__destruct()`: nesne yok edilirken çalışır; script sonunda tetiklendiği için saldırganın en sevdiği tetikleyicilerdendir.
- `__toString()`: nesne string bağlamında kullanıldığında çalışır.

Bir POP chain (Property-Oriented Programming zinciri), bu magic metotlardan birinin, saldırganın doldurduğu bir alanı başka bir nesnenin tehlikeli metoduna aktarmasıyla kurulur. Örneğin `__destruct` içinde bir dosya silme, log yazma veya `call_user_func` gibi bir işlem varsa ve o işlemin parametresi saldırganın kontrolündeki bir alandan geliyorsa, zincir başlatılabilir.

PHP'ye özgü tehlikeli bir varyant, **phar:// deserialization**tır. Bazı dosya sistemi fonksiyonları (`file_exists`, `fopen`, `getimagesize` gibi) `phar://` sarmalayıcısıyla bir yola eriştiğinde, phar arşivinin metadata'sını *otomatik olarak* unserialize eder. Yani doğrudan `unserialize()` çağrısı görünmese bile, saldırgan kontrol ettiği bir yolu bir dosya fonksiyonuna geçirtebilirse deserialization tetiklenebilir. Bu, "kodda `unserialize` aramak yeterli" varsayımını çürüten önemli bir örnektir.

### Python (pickle)

Python'un `pickle` modülü, neredeyse tanımı gereği güvensizdir ve bunu resmi dokümantasyon açıkça belirtir: **pickle, güvenilmeyen veriye karşı güvenli değildir.** Sebep, pickle formatının aslında küçük bir yığın tabanlı sanal makine (stack-based VM) için opcode'lar içermesidir. Bu opcode'lar arasında nesne inşa etmek için callable'ları çağıran talimatlar da vardır.

İşin merkezinde `__reduce__` metodu bulunur. Bir nesne pickle'lanırken, sınıf `__reduce__` ile "beni geri kurmak için şu callable'ı şu argümanlarla çağır" diyebilir. Saldırgan, kötü niyetli bir sınıf yazıp `__reduce__`'ın `(os.system, ("komut",))` gibi bir tuple döndürmesini sağlarsa, unpickle anında `os.system("komut")` çalışır. Kavramsal iskelet:

```python
import pickle, os

class Kotucul:
    def __reduce__(self):
        return (os.system, ("id",))

payload = pickle.dumps(Kotucul())
# Kurban tarafında:
pickle.loads(payload)   # burada "id" komutu calisir
```

Bu, gadget chain aramaya bile gerek kalmadan doğrudan RCE demektir; çünkü format, callable çağırmayı birinci sınıf bir yetenek olarak sunar. Aynı risk `pickle`'ı zemin alan modülleri de kapsar: birçok cache, kuyruk ve ML model serialization yolu (özellikle eğitilmiş modellerin `pickle` ile kaydedilip yüklenmesi) aynı tehlikeyi taşır. Python ekosisteminde `yaml.load`'un (güvensiz loader ile) ve bazı `jsonpickle` kullanımlarının da tip inşasına izin vererek benzer riskler yarattığını unutmamak gerekir.

### .NET

.NET tarafında tarihsel olarak `BinaryFormatter`, ayrıca `SoapFormatter`, `NetDataContractSerializer`, `LosFormatter` (ViewState ile ilişkili) ve `ObjectStateFormatter` gibi tip-güdümlü serializer'lar risk taşımıştır. `BinaryFormatter` bu kadar tehlikelidir ki Microsoft onu resmen güvensiz ilan etmiş ve yeni sürümlerde kullanımını kısıtlama/kaldırma yoluna gitmiştir.

.NET'te gadget chain kavramını **ysoserial.net** aracı popülerleştirdi. `TypeConfuseDelegate`, `ObjectDataProvider` gibi gadget'lar, deserialization sırasında bir delegate/metot çağrısını tetikleyerek keyfi komut çalıştırmaya kadar giden zincirler kurar. Özellikle web dünyasında meşhur bir yüzey **ViewState**tir: ASP.NET ViewState, sunucu tarafı durumunu istemciye taşır ve bütünlüğü `MachineKey` ile korunur. Eğer bu anahtar sızarsa veya bütünlük doğrulaması devre dışıysa/zayıfsa, saldırgan geçerli imzalı bir kötü ViewState üretip deserialization yoluyla RCE elde edebilir. Buradaki ders: deserialization açığı çoğu zaman *ayrı bir sırrın* (imzalama anahtarı) ele geçirilmesiyle iç içedir.

Tip çözümlemesini girdiye bırakan JSON serializer'ları da (örneğin `TypeNameHandling` gibi bir ayarın gevşek kullanıldığı durumlar) aynı sınıfa girer: veri, "şu tipi kur" diyebiliyorsa, gadget yüzeyi açılır.

## Sömürü/İstismar Mantığı

Bir saldırganın tipik iş akışı, açığın *tespitinden* silahlandırmaya doğru ilerler:

1. **Giriş noktasını bulma:** Cookie'ler, gizli form alanları, HTTP header'ları, API gövdeleri, mesaj kuyruğu payload'ları, cache girdileri. Base64 ile kodlanmış, `rO0` (Java), `O:` ile başlayan (PHP), belirli byte imzaları taşıyan (pickle protokol byte'ları) veya `__VIEWSTATE` gibi alanlar güçlü ipuçlarıdır.

2. **Teknolojiyi ve gadget yüzeyini teşhis etme:** Hangi dil/framework? Classpath'te veya bağımlılıklarda hangi kütüphaneler var? Saldırgan çoğu zaman uygulamanın bağımlılık listesini (açık kaynak ise doğrudan, değilse hata mesajları/versiyon sızıntılarıyla) çıkarıp o bağımlılıklara uygun bir gadget seçer. Gadget chain'in var olması, o kütüphanenin ortamda bulunmasına bağlıdır.

3. **Payload üretme:** ysoserial (Java), ysoserial.net (.NET), PHPGGC (PHP POP chain kataloğu) gibi araçlar, bilinen kütüphaneler için hazır zincirler üretir. Python pickle'da genellikle özel araca bile gerek yoktur; birkaç satırlık `__reduce__` yeter.

4. **Doğrulama ve genişletme:** İlk hedef çoğu zaman "out-of-band" bir sinyaldir — örneğin saldırganın kontrol ettiği bir sunucuya DNS/HTTP isteği attırmak (blind exploitation). Komut çalıştığı doğrulandıktan sonra reverse shell, kalıcılık ve yatay hareket gelir.

İstismarın "sinsi" yanı, exploitasyonun **uygulamanın normal iş mantığından tamamen bağımsız** olabilmesidir. Saldırgan uygulamanın ne yaptığını umursamaz; yalnızca deserializer'a kötü bir nesne ulaştırıp gadget zincirinin tetiklenmesini bekler. Bu yüzden "biz o sınıfı hiç kullanmıyoruz ki" savunması yetersizdir — önemli olan sınıfın *çağrılması* değil, ortamda *var olması* ve deserializer'ın onu inşa edebilmesidir.

## Savunma: Katmanlı Yaklaşım

Deserialization'a karşı tek bir sihirli çözüm yoktur; savunma katmanlıdır ve öncelik sırası şöyledir:

**1. En etkili savunma: Güvenilmeyen veriyi hiç native deserialize etmemek.** Mümkünse dilin native/binary serialization'ını kullanıcıya açık yollarda tamamen bırakın. Yerine yalnızca *veri* taşıyan formatlar kullanın: düz JSON, Protocol Buffers gibi şemaya bağlı formatlar. Bunlar tip inşasına ve otomatik callback'lere izin vermediği için gadget yüzeyini kökten kapatır. Python için: pickle yerine JSON; PHP için: `unserialize` yerine `json_decode`; .NET için: `BinaryFormatter` yerine `System.Text.Json`; Java için: `ObjectInputStream` yerine JSON/DTO tabanlı bir yaklaşım.

**2. Bütünlük doğrulaması (integrity).** Native serialization gerçekten şartsa, veriyi istemciye salt-güvenli halde göndermeyin. Sunucu tarafında saklayın (session store) ve istemciye sadece opak bir referans (rastgele session id) verin. Zorunlu olarak istemciye taşınacaksa, veriyi bir gizli anahtarla **HMAC** ile imzalayın ve deserialize etmeden *önce* imzayı doğrulayın. Ancak dikkat: imzalama, anahtar sızarsa çöker (ViewState örneği). İmza doğrulaması, girdiyi *filtrelemenin* yerini tutmaz; onu tamamlar.

**3. Tip beyaz listesi (allow-list) / look-ahead deserialization.** Native deserialization kaçınılmazsa, hangi sınıfların inşa edilebileceğini sıkı bir beyaz listeyle sınırlayın. "Şu kara listedeki tehlikeli sınıfları engelle" yaklaşımı (deny-list) yetersizdir çünkü yeni gadget'lar sürekli keşfedilir; kara liste her zaman geriden gelir. Bunun yerine "yalnızca şu birkaç bilinen, güvenli DTO tipine izin ver" (allow-list) yaklaşımı doğrudur.
   - **Java:** `ObjectInputFilter` (JEP 290 ile gelen serialization filtreleme mekanizması) ile hem sınıf allow-list'i hem derinlik/nesne sayısı limitleri koyabilirsiniz. Uygulama-genelinde bir filtre + endpoint bazında dar filtreler idealdir.
   - **Python:** Zorunlu pickle kullanımında, `pickle.Unpickler`'ı türeterek `find_class` metodunu override edin ve yalnızca izin verdiğiniz modül/sınıf çiftlerine izin verin; gerisini reddedin. Yine de en sağlıklısı pickle'dan tamamen kaçmaktır.
   - **PHP:** `unserialize($data, ['allowed_classes' => false])` ile hiçbir nesnenin örneklenmemesini (sadece skaler/dizi) veya `['allowed_classes' => ['Sadece', 'Bunlar']]` ile dar bir listeyi zorlayabilirsiniz.
   - **.NET:** Tip çözümlemesini girdiye bırakan ayarları kapatın (`TypeNameHandling.None`), zorunluysa `SerializationBinder` ile tipleri sıkıca sınırlayın.

**4. Kaynak limitleri (DoS savunması).** Deserialization DoS'a da yol açabilir ("billion laughs" benzeri iç içe yapılar, aşırı büyük koleksiyonlar, derin nesne grafikleri). Nesne sayısı, derinlik, dizi boyutu ve toplam byte için limitler koyun. Java'nın `ObjectInputFilter`'ı bu limitleri de destekler.

**5. Bağımlılık hijyeni ve en az ayrıcalık.** Gadget'lar bağımlılıklarda yaşadığı için, kullanılmayan kütüphaneleri classpath'ten çıkarmak saldırı yüzeyini daraltır. Bilinen gadget içeren kütüphane sürümlerini güncel tutun (SCA/dependency scanning). Uygulamayı düşük ayrıcalıkla, mümkünse container/sandbox içinde ve dışarı giden ağ trafiği kısıtlanmış (egress filtering) şekilde çalıştırın — böylece RCE olsa bile blind exploitation ve dışa veri sızması zorlaşır.

**6. Ağ/uygulama katmanı tespiti.** Trafikte deserialization imzalarını (Java magic number, PHP `O:` desenleri, pickle opcode'ları) tespit eden WAF kuralları ek bir katmandır — ama kolayca atlatılabildiği için *birincil* savunma sayılmamalıdır.

## Yaygın Hatalar

- **"JSON kullanıyoruz, güvendeyiz" yanılgısı.** Tehlike formatın kendisinde değil, *tip inşasına izin verip vermediğindedir*. Polymorphic tip çözümlemesi açık bir JSON deserializer (Jackson'da gevşek yapılandırma, .NET'te `TypeNameHandling`, Python'da `yaml.load` güvensiz loader) düz JSON kadar tehlikeli olabilir.
- **Sadece `unserialize`/`readObject` çağrısını aramak.** phar:// (PHP) ve framework içindeki dolaylı deserialization yolları, kodda görünür bir çağrı olmadan tetiklenebilir. Statik arama tek başına yetmez.
- **Deny-list'e güvenmek.** Bilinen tehlikeli sınıfları engellemek, yeni keşfedilen gadget'lara karşı korumasızdır. Allow-list şarttır.
- **İmzalamayı filtrelemeyle karıştırmak.** HMAC ile imzalamak, veriyi *değiştirilemez* yapar ama anahtar sızarsa hiçbir işe yaramaz ve zaten girdi doğrulamasının yerine geçmez. İkisi farklı problemleri çözer.
- **"Bu sınıfı kullanmıyoruz" savunması.** Sınıfın uygulama tarafından *çağrılması* gerekmez; classpath/ortamda *var olması* saldırgan için yeterlidir.
- **Şifreleme ile bütünlüğü karıştırmak.** Veriyi şifrelemek gizliliği sağlar ama saldırgan içeriği görmese bile bazı senaryolarda değiştirebilir. Deserialization güvenliği için gereken şey öncelikle *bütünlük ve tip kısıtlamasıdır*, gizlilik değil.
- **Cache/kuyruk/model dosyalarını "iç kaynak" sanmak.** Redis, mesaj kuyrukları veya diskteki pickle'lanmış ML modelleri saldırgan tarafından zehirlenebilirse, bunlar da güvenilmeyen kaynaktır. "İç ağ = güvenli" varsayımı yanlıştır.

## En İyi Pratikler (Özet)

1. **Varsayılanı tersine çevirin:** Güvenilmeyen girdiyi native deserialize etmeyin; yalnızca veri taşıyan, şemaya bağlı formatları tercih edin.
2. **Durumu sunucuda tutun:** İstemciye serialized nesne yerine opak referans verin.
3. **Zorunluysa allow-list uygulayın:** Java `ObjectInputFilter`, Python `find_class` override, PHP `allowed_classes`, .NET `SerializationBinder`.
4. **Bütünlüğü koruyun ama tek başına yeterli sanmayın:** HMAC imzalama + anahtar yönetimi + rotasyon.
5. **Kaynak limitleri koyun:** derinlik, nesne sayısı, boyut — DoS'a karşı.
6. **Bağımlılıkları temizleyin ve güncel tutun:** kullanılmayan kütüphaneleri kaldırın, SCA tarayın.
7. **En az ayrıcalıkla çalıştırın:** sandbox, düşük yetki, egress filtering ile RCE'nin etkisini sınırlayın.
8. **Derinlemesine tehdit modelleyin:** dolaylı yolları (phar, framework auto-deserialize, cache/kuyruk zehirlenmesi) unutmayın.

Sonuç olarak güvensiz deserialization, "bir input doğrulama hatası" olmaktan çok, güçlü ama tehlikeli bir dil özelliğinin yanlış yerde açık bırakılmasıdır. En kalıcı çözüm, güvenilmeyen veriyi hiçbir zaman keyfi nesnelere dönüştürmemek; buna mecbursanız, hangi tiplerin inşa edilebileceğini sıkı sıkıya sınırlamaktır. Yama uygulamaktan çok mimari disiplin gerektiren bir konudur.
