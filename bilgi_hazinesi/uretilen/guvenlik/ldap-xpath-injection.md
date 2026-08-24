# LDAP ve XPath Injection: Filtre Enjeksiyonu, Auth Bypass ve Parametreleme

## Giriş ve Kapsam

Injection zafiyetleri denince akla çoğunlukla SQL Injection gelir. Ancak "kullanıcıdan gelen veriyi bir sorgu diline karıştırmak" problemi tek bir teknolojiye özgü değildir; aynı kök neden farklı bir syntax'ta karşımıza çıkar. LDAP Injection ve XPath Injection, tam da bu ailenin daha az konuşulan ama en az SQL Injection kadar tehlikeli iki üyesidir.

Bu makale iki saldırı sınıfını da tek bir çatı altında ele alır çünkü sömürü mantıkları neredeyse birebir aynıdır: her ikisinde de saldırgan, sorgunun **veri** kısmına ait olması gereken girdiyi sorgunun **kod/mantık** kısmına sızdırır. LDAP tarafında bu, dizin filtresinin (directory filter) mantığını değiştirir; XPath tarafında ise XML belgesi üzerindeki seçim ifadesini (selection expression) değiştirir. Her ikisinin de en yıkıcı sonucu, kimlik doğrulama atlatma (authentication bypass) ve yetkisiz veri okumadır.

Odak noktalarımız: filtre enjeksiyonunun nasıl çalıştığı, auth bypass'ın mekaniği ve doğru savunmanın temeli olan parametreleme (parameterization) ile kaçış (escaping) stratejileri.

## LDAP Injection

### Tanım

LDAP (Lightweight Directory Access Protocol), kullanıcı, grup, cihaz gibi nesneleri hiyerarşik bir dizinde tutan ve sorgulayan bir protokoldür. Active Directory, OpenLDAP, 389 Directory Server gibi ürünler bu protokolü konuşur. Kurumsal ortamlarda uygulamalar, kullanıcı doğrulama ve yetki bilgisi için sıklıkla LDAP dizinine sorgu atar.

LDAP Injection, bir uygulamanın kullanıcıdan aldığı girdiyi bir LDAP arama filtresine (search filter) doğrudan, hiç kaçış uygulamadan yerleştirmesiyle oluşur. Saldırgan, filtre syntax'ına ait özel karakterleri girdisine ekleyerek sorgunun anlamını değiştirir.

### Kök Neden: LDAP Filtre Syntax'ı Neden Enjeksiyona Açık?

Meselenin kalbini anlamak için LDAP filtre gramerine bakmak gerekir. LDAP filtreleri, RFC 4515'te tanımlanan bir prefix (Polonya) notasyonu kullanır. Operatör önce gelir, operandlar sonra. Örnek bir filtre şöyledir:

```
(&(uid=jsmith)(userPassword=gizli123))
```

Burada:
- `&` mantıksal VE (AND) operatörüdür,
- `|` mantıksal VEYA (OR) operatörüdür,
- `!` mantıksal DEĞİL (NOT) operatörüdür,
- `=` eşitlik karşılaştırmasıdır,
- `*` joker karakter (wildcard), yani "herhangi bir değer" anlamına gelir,
- Parantezler ifadeleri gruplar.

Şimdi kök nedene gelelim. Uygulama bu filtreyi tipik olarak string birleştirme (concatenation) ile kurar:

```
filtre = "(&(uid=" + kullanici_adi + ")(userPassword=" + parola + "))"
```

Sorun şu: `kullanici_adi` ve `parola` değişkenlerinin içindeki karakterler ile filtre gramerinin kontrol karakterleri **aynı düzlemde** yaşar. LDAP kütüphanesi bu string'i aldığında, hangi parantezin veriden geldiğini hangisinin geliştiricinin niyeti olduğunu bilmez. Yorumlayıcı için ikisi de eşit derecede "filtre". İşte enjeksiyonun kök nedeni budur: **veri ile kod arasında syntax düzeyinde bir sınır yoktur.** Bu, tüm injection ailesinin ortak DNA'sıdır.

### Somut Örnek: Filtre Enjeksiyonu ve Auth Bypass

Diyelim ki giriş formu şu filtreyi üretiyor:

```
(&(uid=$user)(userPassword=$pass))
```

Saldırgan kullanıcı adı alanına şunu yazar:

```
*)(uid=*))(|(uid=*
```

Parola alanı önemsiz. Ortaya çıkan filtre şuna dönüşür:

```
(&(uid=*)(uid=*))(|(uid=*)(userPassword=$pass))
```

Burada olan şudur: saldırgan `*` joker karakteriyle `uid=*` yaparak "herhangi bir kullanıcı" koşulu enjekte etti ve fazladan parantezlerle sorgunun mantıksal yapısını yeniden şekillendirdi. Parola kontrolünü içeren alt ifade artık bir `|` (OR) dalının içinde kaldığı için, ilk dal doğru olduğunda tüm filtre eşleşir. Sonuç: parola hiç doğrulanmadan bir kullanıcı bulunur ve sunucu "eşleşme var" der.

Daha basit ve klasik bir auth bypass örneği: uygulama sadece kullanıcı adını sorguya koyup dönen kayıt varsa girişi kabul ediyorsa (parola başka yerde kontrol ediliyor veya hiç kontrol edilmiyorsa), saldırgan kullanıcı adına şunu yazar:

```
*
```

Filtre `(uid=*)` olur, bu da dizindeki **her** nesneyle eşleşir. Uygulamanın "en az bir sonuç döndü mü?" mantığı bozulur.

### Bilgi Sızdırma (Blind LDAP Injection)

Auth bypass tek risk değildir. Filtreyi kontrol edebilen saldırgan, dizinden veri de sızdırabilir. Uygulama doğrudan çıktı vermese bile, "sonuç döndü / dönmedi" gibi ikili (boolean) bir davranış farkı gözlemlenebiliyorsa, bu bir **blind injection** kanalıdır.

Saldırgan, joker karakterlerle karakter karakter tahmin yürütür. Örneğin bir kullanıcının bir özniteliğini (attribute) çıkarmak için:

```
(&(uid=admin)(departman=a*))
(&(uid=admin)(departman=b*))
...
```

Her denemede uygulamanın davranışına bakarak (giriş başarılı mı, sayfa farklı mı) özniteliğin ilk harfini bulur, sonra ikinciye geçer. Bu, LDAP dizininde saklanan hassas verilerin (roller, grup üyelikleri, hatta zayıf şemalarda parola hash'leri) yavaş ama kesin biçimde sızdırılmasını sağlar.

### LDAP Injection'a Karşı Savunma

**1. Girdi kaçışı (input escaping) — RFC 4515'e uygun.**
Doğrudan string birleştirmeden kaçınamıyorsanız, kullanıcı girdisindeki her özel karakter LDAP filtre kaçış kuralına göre kaçırılmalıdır. RFC 4515, filtrede özel anlam taşıyan karakterlerin ters bölü (`\`) ve iki haneli onaltılık (hex) koduyla temsil edilmesini gerektirir. Kaçırılması gereken temel karakterler şunlardır:

- `*` → `\2a`
- `(` → `\28`
- `)` → `\29`
- `\` → `\5c`
- NUL karakteri → `\00`

Böylece saldırganın yazdığı `*` artık joker olarak değil, "yıldız harfi" olarak yorumlanır ve mantık bozulmaz.

**2. Doğru mühendislik çözümü: kütüphanenin filtre kurucusunu kullanmak.**
Kaçışı elle yapmak hataya açıktır. Olgun LDAP kütüphaneleri, filtreyi güvenli biçimde inşa eden yapılar sunar. Java tarafında JNDI/LDAP ortamında `SearchControls` ile birlikte filtreyi `{0}`, `{1}` gibi yer tutucularla (placeholder) verip argümanları ayrı parametre olarak geçmek mümkündür; bu yaklaşımda kütüphane değerleri kendisi kaçırır. .NET tarafında `System.DirectoryServices` katmanı ve OWASP ESAPI'nin `encodeForLDAP` / `encodeForDN` fonksiyonları bu işi üstlenir. Buradaki fikir SQL'deki parametreli sorgunun (prepared statement) LDAP karşılığıdır: değeri sorgu string'ine gömmek yerine, ayrı bir kanaldan, "bu bir veri" etiketiyle iletmek.

**3. DN (Distinguished Name) enjeksiyonunu ayrı ele almak.**
Filtre kaçışı ile DN kaçışı **farklı kurallara** tabidir. Bir kullanıcı girdisi bir DN içine (`cn=...,ou=...` gibi) konacaksa, orada özel olan karakterler farklıdır (`,`, `+`, `"`, `\`, `<`, `>`, `;`, satır başı ve sondaki boşluklar). Yanlış tablo ile kaçış yapmak sahte güvenlik yaratır. Girdinin nereye gittiğine göre doğru kaçış bağlamını (context) seçmek şarttır.

**4. En az yetki ve girdi doğrulama.**
Uygulamanın LDAP'a bağlanırken kullandığı servis hesabı yalnızca ihtiyacı olan alt ağacı (subtree) okuyabilmeli. Ayrıca kullanıcı adı gibi alanlarda beklenen karakter kümesini beyaz liste (allowlist) ile kısıtlamak (örneğin sadece harf, rakam, alt çizgi) saldırı yüzeyini daralttır. Beyaz liste kaçışın yerine geçmez, onu tamamlar.

## XPath Injection

### Tanım

XPath (XML Path Language), bir XML belgesindeki düğümleri (node) seçmek için kullanılan bir sorgu dilidir. Bazı uygulamalar kullanıcı bilgilerini, yapılandırmayı veya küçük veri kümelerini bir veritabanı yerine XML dosyasında tutar ve doğrulamayı XPath sorgusuyla yapar. XPath Injection, kullanıcı girdisinin bir XPath ifadesine kaçış uygulanmadan yerleştirilmesiyle oluşur.

### Kök Neden: Neden SQL Injection'a Bu Kadar Benziyor?

XPath'in tipik bir kimlik doğrulama sorgusu şuna benzer:

```
/kullanicilar/kullanici[isim/text()='$user' and parola/text()='$pass']
```

Köşeli parantez içindeki kısım bir yüklemdir (predicate); bir koşuldur. `and`, `or`, `=`, tek tırnak ile string sınırları ve fonksiyonlar bu dilin kontrol yapılarını oluşturur. Uygulama yine string birleştirme ile bu ifadeyi kurar:

```
"/kullanicilar/kullanici[isim/text()='" + user + "' and parola/text()='" + pass + "']"
```

Kök neden LDAP'takiyle aynıdır: kullanıcı girdisindeki tek tırnak, XPath yorumlayıcısı için string'i **sonlandıran** bir kontrol karakteridir; ama uygulama onu sıradan veri sanır. SQL Injection'a benzerliği tesadüf değil: her ikisi de string tabanlı sorgu dilleridir ve her ikisinde de tırnak, mantığı kırmanın anahtarıdır.

XPath'in SQL'e göre bir "avantajı" (saldırgan için) vardır: standart XPath 1.0'da yorum sözdizimi ve çok ifadeli batch çalıştırma yoktur, ama buna karşılık **erişim kontrolü kavramı da yoktur.** SQL'de tablo/kolon izinleri olabilir; XPath'te belge yüklendiyse, saldırgan prensipte belgenin **tamamını** okuyabilir. Bu, veri sızdırmayı SQL'den bazen daha tehlikeli kılar.

### Somut Örnek: Klasik Auth Bypass

Saldırgan kullanıcı adı alanına şunu yazar:

```
' or '1'='1
```

Ortaya çıkan sorgu:

```
/kullanicilar/kullanici[isim/text()='' or '1'='1' and parola/text()='...']
```

`or '1'='1'` her zaman doğru olduğu için yüklem tüm kullanıcı düğümleriyle eşleşir; uygulama genellikle ilk kullanıcıyı (çoğu zaman yönetici) alır ve girişi kabul eder. Bu, en klasik ve en yaygın XPath auth bypass'tır ve pratikte SQL'deki `' OR '1'='1` ile birebir aynı mantığı taşır.

Operatör önceliğine dikkat etmek gerekir: `and` operatörü `or`'dan daha yüksek önceliğe sahip olduğundan, saldırgan bunu hesaba katarak yükünü (payload) `or` ile en dışta bir "her zaman doğru" koşulu yaratacak biçimde kurar.

### Blind XPath Injection ile Tüm Belgeyi Sızdırmak

XPath Injection'ın gerçek gücü blind sömürüde ortaya çıkar. Uygulama sadece "giriş başarılı/başarısız" gibi ikili bir yanıt verse bile, saldırgan XPath fonksiyonlarıyla belgenin tamamını harf harf çıkarabilir. Kullanılan tipik fonksiyonlar:

- `string-length()` — bir değerin uzunluğunu bulmak için,
- `substring()` — belirli bir karakteri izole etmek için,
- `count()` — bir yol altındaki düğüm sayısını bulmak (belgenin yapısını haritalamak) için,
- `name()` — düğümün adını öğrenmek için.

Saldırgan önce `count(/*)` benzeri sorgularla kök yapıyı sayar, sonra `substring(.../text(),1,1)='a'` gibi koşulları doğru/yanlış tepkisine bakarak dener. Bu ikili arama (binary search) ile hızlandırılabilir. Sonuçta, hiçbir doğrudan çıktı olmasa bile XML'deki her kullanıcı, her parola, her düğüm sızdırılabilir. Belgede erişim kontrolü olmadığı için "bu düğümü okuyamazsın" diyen bir katman yoktur.

### XPath Injection'a Karşı Savunma

**1. Parametreli XPath (precompiled / variable binding).**
En sağlam savunma, girdiyi ifadeye gömmemektir. XPath'i derleyip (compile) değerleri değişken olarak bağlamak (bind) gerekir. Java'da `javax.xml.xpath.XPath` API'si `XPathVariableResolver` ile değişken çözümü sağlar; ifadede `$user` gibi bir değişken tanımlar, gerçek değeri ayrı bir kanaldan verirsiniz. Bu, prepared statement'ın XML dünyasındaki tam karşılığıdır: yorumlayıcı `$user`'ı her zaman tek bir string değeri olarak görür, asla XPath kodu olarak yorumlamaz. Böylece tek tırnak enjekte etmenin hiçbir anlamı kalmaz çünkü girdi zaten ifade metnine hiç dokunmaz.

**2. Kaçış (parametreleme mümkün değilse ikinci savunma).**
Mecburen birleştirme yapılıyorsa, string sınırlayıcı olan tırnaklar özenle işlenmelidir. Ancak XPath 1.0'da tırnak kaçışı SQL'deki gibi basit "tırnağı ikiye katlama" değildir; tek tırnaklı bir string içine tek tırnak gömmek doğrudan mümkün olmayabilir ve `concat()` gibi çözümler gerekebilir. Bu kırılganlık, tam olarak **kaçışa güvenmek yerine parametrelemeyi tercih etmek gerektiğinin** kanıtıdır. Elle kaçış her zaman gözden kaçan bir bağlam bırakır.

**3. Girdi doğrulama ve tip zorlaması.**
Beklenen veri tipini zorlamak (sayı bekleniyorsa sayıya çevirmek, kullanıcı adında sadece belirli karakterlere izin vermek) saldırı yüzeyini azaltır. Yine, bu tek başına yeterli bir savunma değildir; parametrelemeyi tamamlayan bir katmandır.

**4. Mimari düzeltme: kimlik doğrulamayı XML'den çıkarmak.**
Daha derin bir çözüm, hassas kimlik doğrulama verisini düz bir XML dosyasında XPath ile sorgulamayı tamamen bırakmaktır. Parolaların salt (salt) + yavaş hash (bcrypt, Argon2 gibi) ile saklandığı uygun bir kimlik altyapısına taşımak, hem enjeksiyon riskini hem de düz metin parola sızıntısı riskini birlikte ortadan kaldırır.

## İki Saldırının Ortak Deseni ve Doğru Zihinsel Model

LDAP ve XPath Injection'ı yan yana koyunca ortak ders netleşir. Her ikisinde de:

- **Kök neden aynıdır:** veri ile sorgu kodu, aynı string düzleminde karışır.
- **Sömürü mantığı aynıdır:** kontrol karakterlerini (LDAP'ta `*`, `(`, `)`, `&`, `|`; XPath'te `'`, `or`, `and`) enjekte ederek sorgunun boolean mantığını "her zaman doğru" hale getirmek.
- **En yıkıcı sonuç aynıdır:** auth bypass ve blind veri sızdırma.
- **Doğru savunma aynıdır:** veriyi koddan ayıran parametreleme.

Bu yüzden bu zafiyetleri "SQL Injection'ın kuzenleri" olarak düşünmek doğrudur, ama tehlikeli bir hataya da düşmemek gerekir: **SQL Injection savunmanız bunları kapsamaz.** WAF kuralınız `UNION SELECT` arıyorsa, `*)(uid=*)` veya `' or '1'='1` yükünü tanımayabilir. LDAP ve XPath'in kendi bağlamına özel kaçış/parametreleme uygulanmalıdır.

## Yaygın Hatalar

**1. "Kaçış yaptım, güvendeyim" yanılgısı.**
Elle kaçış yapan geliştiriciler sıklıkla yanlış karakter kümesini veya yanlış bağlamı kaçırır. LDAP'ta filtre kaçışı ile DN kaçışını karıştırmak; XPath'te tek tırnağı doğru işleyip fonksiyon bağlamını unutmak tipik hatalardır. Kaçış, doğru bağlamda yapılmadıkça sahte bir güven verir.

**2. SQL savunmasını her yere kopyalamak.**
Girdiyi SQL için kaçıran bir yardımcı fonksiyonu LDAP veya XPath'e de uygulamak işe yaramaz; her dilin özel karakter tablosu farklıdır. SQL'de `'` tehlikeli iken LDAP filtresinde `(` ve `*` tehlikelidir.

**3. Blind kanalları küçümsemek.**
"Uygulama zaten dizinden/XML'den veri basmıyor, o yüzden sızdırma olmaz" düşüncesi yanlıştır. Giriş başarılı/başarısız gibi tek bitlik bir davranış farkı bile, sabırla tüm dizini veya XML belgesini sızdırmaya yeter.

**4. Girdi doğrulamayı tek savunma sanmak.**
Beyaz liste doğrulama değerli ama kırılgandır; iş gereksinimi geniş karakter kümesi gerektirdiğinde (örneğin isimlerde tırnak, boşluk) doğrulama gevşer. Parametreleme olmadan doğrulamaya tek başına güvenmek risklidir.

**5. Hata mesajlarıyla sızdırma yüzeyini büyütmek.**
Ayrıntılı LDAP/XPath hata mesajlarını kullanıcıya döndürmek, saldırgana filtre/ifade yapısı hakkında ipucu vererek blind sömürüyü kör olmaktan çıkarıp yarı-görünür hale getirir.

## En İyi Pratikler

1. **Önce parametreleme.** Mümkün olan her yerde LDAP filtre kurucularını ve XPath değişken bağlamayı (variable binding) kullanın. Girdiyi asla sorgu string'ine elle birleştirmeyin. Bu tek karar, riskin büyük kısmını yok eder.

2. **Kaçış, yalnızca ikinci savunma ve doğru bağlamda.** Parametreleme mümkün değilse, olgun bir kütüphanenin (OWASP ESAPI `encodeForLDAP`/`encodeForDN` gibi) bağlam-farkında kaçış fonksiyonlarını kullanın; elle regex ile kaçış yazmayın.

3. **Girdiyi beyaz liste ile doğrulayın.** Beklenen karakter kümesini ve uzunluğu zorlayın. Bunu parametrelemenin yerine değil, üstüne koyun (defense in depth).

4. **En az yetki uygulayın.** LDAP servis hesabına yalnızca gereken okuma iznini verin; XPath ile sorgulanan XML'de hassas veriyi düz tutmayın.

5. **Hata mesajlarını dışarı sızdırmayın.** Kullanıcıya genel hata gösterin; ayrıntıyı yalnızca sunucu loglarına yazın.

6. **Test edin.** Statik analiz (SAST) araçları string birleştirmeli filtre/XPath çağrılarını yakalayabilir; dinamik testte klasik yükleri (`*`, `*)(uid=*)`, `' or '1'='1`) ve blind boolean farklarını deneyin.

7. **Mümkünse mimariyi düzeltin.** Kimlik doğrulamayı düz XML/LDAP filtre mantığından, salt+yavaş hash kullanan uygun bir kimlik katmanına taşımak, hem enjeksiyonu hem de veri sızıntısını kökten azaltır.

## Sonuç

LDAP ve XPath Injection, farklı sorgu dillerinde ortaya çıkan aynı temel kusurun iki yüzüdür: kullanıcı verisini sorgu kodundan ayırmamak. Filtre veya ifade syntax'ının kontrol karakterlerini enjekte edebilen bir saldırgan, kimlik doğrulamayı atlatabilir ve blind tekniklerle tüm dizini ya da XML belgesini sızdırabilir. Doğru savunmanın çekirdeği tek bir ilkedir ve SQL Injection ile aynıdır: **veriyi asla kod olarak yorumlatma.** Bunun pratikteki adı parametrelemedir; kaçış, doğrulama ve en az yetki ise onu tamamlayan katmanlardır. Bu ilkeyi bağlama doğru uygulayan bir uygulama, bu saldırı sınıfına karşı büyük ölçüde bağışık hale gelir.
