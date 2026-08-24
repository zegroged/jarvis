# Format String Zafiyeti

## Tanım

Format string (biçim dizesi) zafiyeti, bir programın kullanıcı tarafından kontrol edilen veriyi, `printf` ailesindeki fonksiyonlara *format parametresi* olarak doğrudan aktarmasından doğan bir bellek güvenliği açığıdır. Tehlikenin özü şudur: format dizesi aslında küçük bir yorumlanan dildir. İçindeki `%` yönergeleri (`%s`, `%x`, `%n` gibi) fonksiyona "yığından (stack) şu kadar argüman al, şu biçimde yorumla ve gerektiğinde belleğe yaz" talimatı verir. Programcı bu dizeyi bir sabit olarak verdiğinde her şey yolundadır; ancak saldırgan bu dizeyi belirleyebiliyorsa, programın kendi bellek okuma ve *yazma* yeteneğini saldırgana devretmiş olur.

Klasik hatalı kalıp şudur:

```c
printf(kullanici_girdisi);        // ZAFIYETLI
```

Olması gereken ise:

```c
printf("%s", kullanici_girdisi);  // DOGRU
```

İki satır arasındaki fark yüzeyde önemsiz görünür, ama güvenlik açısından uçurum kadar büyüktür. İlk satırda saldırgan `%x%x%x` yazarsa program bellek sızdırır; `%n` yazarsa program belleğe yazar. İkinci satırda ise kullanıcı girdisi yalnızca yazdırılacak *veri* olarak ele alınır, yönerge olarak yorumlanmaz.

Bu zafiyet C ve C++ gibi düşük seviyeli, manuel bellek yönetimli dillerde en yıkıcı biçimini alır; çünkü bu dillerde `printf` doğrudan `va_arg` mekanizmasıyla yığından argüman çeker ve bunun geçerli olup olmadığını denetlemez.

## Kök Neden: Neden Böyle Oluyor?

Format string zafiyetinin kökü, C'nin *variadic* (değişken argümanlı) fonksiyon çağrı sözleşmesinde yatar. `printf` prototipi kabaca şöyledir:

```c
int printf(const char *format, ...);
```

Buradaki `...` fonksiyonun kaç argüman aldığını derleme zamanında bilmediğini gösterir. Peki `printf` çalışırken kaç argüman olduğunu nasıl öğrenir? Öğrenmez. Yalnızca *format dizesini tarar* ve içinde kaç tane dönüşüm yönergesi (`%`) görürse o kadar argüman olduğunu **varsayar**. Her `%x` gördüğünde "sıradaki argümanı al" der ve çağrı sözleşmesinin belirlediği yerden (registerlar ve/veya yığın) bir sonraki değeri okur.

İşte kritik nokta: `printf` bu argümanların gerçekten sağlanıp sağlanmadığını doğrulayamaz. Format dizesinde beş tane `%x` varsa ama çağrıda hiç argüman verilmemişse, `printf` yine de gider yığından beş adet 32/64-bit değer okur. Bu değerler o an yığında ne varsa odur: fonksiyonun yerel değişkenleri, kaydedilmiş register değerleri, dönüş adresleri (return address), canary değerleri, işaretçiler. Böylece format dizesini kontrol eden saldırgan, aslında programın bellek düzenini keşfetme aracı elde etmiş olur.

Zafiyetin "yazma" boyutu ise `%n` yönergesinden gelir. `%n`, o ana kadar yazdırılmış karakter sayısını, argüman olarak verilen *işaretçinin gösterdiği adrese* yazar. Yani `%n` bir çıktı yönergesi değil, bir *bellek yazma* yönergesidir. Tasarımcıların amacı, biçimlendirme genişliğini programatik olarak öğrenmekti; ama saldırgan bağlamında bu, "istediğim adrese istediğim değeri yaz" primitifine dönüşür.

Neden hem 32-bit hem 64-bit'te önemli? Çünkü çağrı sözleşmesi mimariden mimariye değişir. 32-bit x86'da tüm argümanlar yığına itilir, dolayısıyla `%x` dizisi doğrudan yığını taramaya başlar. 64-bit System V ABI'de (Linux x86-64) ilk altı tamsayı argümanı registerlarda (rdi, rsi, rdx, rcx, r8, r9) taşınır; `printf`'in format argümanı rdi'dedir, geri kalan "sahte" argümanlar önce registerlardan okunur, register argümanları tükendikten sonra yığına geçilir. Bu ayrım sömürü (istismar) tekniğini etkiler, ama zafiyetin varlığını değiştirmez.

## %x ile Bellek Sızıntısı (Information Disclosure)

`%x` yönergesi, format string zafiyetinin en zararsız görünen ama en çok işe yarayan yüzüdür: bellek sızıntısı. Saldırgan `%x` dizileri göndererek yığındaki ham değerleri onaltılık (hexadecimal) olarak okuyabilir.

Diyelim ki savunmasız program şu:

```c
char buf[256];
fgets(buf, sizeof buf, stdin);
printf(buf);   // ZAFIYETLI
```

Saldırgan girdi olarak `AAAA %x %x %x %x %x %x` gönderirse, çıktıda yığından okunmuş altı adet onaltılık değer görür. Belirli bir konumda `41414141` (yani "AAAA"nın ASCII kodu) görürse, bu, kendi girdisinin yığında nerede durduğunu tam olarak bulmuş demektir. Bu "ofset bulma" adımı sömürünün temelidir; çünkü sonraki adımlarda saldırgan kendi tampon (buffer) içindeki bir adresi argüman olarak kullandırmak isteyecektir.

Sızıntı neden bu kadar tehlikeli? Modern savunmalar büyük ölçüde *gizliliğe* dayanır. ASLR (Address Space Layout Randomization) bellek düzenini rastgeleleştirir; stack canary rastgele bir değerle taşmayı tespit eder; PIE (Position Independent Executable) kod tabanını rastgele bir adrese koyar. `%x` (veya 64-bit'te daha pratik olan `%p` veya `%lx`) ile saldırgan tam da bu sırları sızdırabilir:

- Bir yığın işaretçisi sızdırarak stack tabanını hesaplar, ASLR'yi kısmen atlatır.
- Kaydedilmiş bir libc adresi sızdırarak libc taban adresini bulur; böylece `system` gibi fonksiyonların gerçek adresini hesaplar.
- Stack canary değerini doğrudan okuyarak, sonraki bir buffer overflow saldırısında canary'yi *aynen geri yazar* ve tespiti atlatır.

Pratik bir kısayol da doğrudan konumsal argümanlardır. `%7$x` yazımı, "yedinci argümanı onaltılık yazdır" demektir. Bu, `%x %x %x %x %x %x %x` yazmaya gerek kalmadan yığındaki belirli bir konumu tek hamlede okumayı sağlar; sömürü kodunu hem kısaltır hem güvenilir kılar. `%s` ise daha da güçlüdür ama daha risklidir: verilen argümanı bir *işaretçi* kabul edip gösterdiği adresteki dizeyi okumaya çalışır. Saldırgan geçerli bir adres yerleştirebilirse rastgele bellek okuyabilir; ama geçersiz bir adrese denk gelirse program çöker (segmentation fault).

## %n ile Bellek Yazma (Rastgele Yazma Primitifi)

Sızıntı ciddi bir sorundur, ama `%n` felaketin ta kendisidir. `%n`, "şimdiye kadar kaç karakter yazdırdıysam, o sayıyı argüman olarak verilen adrese yaz" anlamına gelir. Saldırgan format dizesini kontrol ettiği için:

1. Yazılacak **adresi** kendi girdisinin içine gömer (yığında görünür hale getirir).
2. Konumsal yönerge (`%k$n`) ile o adresi `%n`'in argümanı yapar.
3. Yazdırılan karakter sayısını, alan genişliği yönergeleriyle (`%100c`, `%65536x` gibi) istediği sayıya *ayarlar*.

Böylece "istediğim adrese, istediğim değeri yaz" (write-what-where) primitifi elde edilir. Bu primitif, bellek güvenliği dünyasının en güçlü saldırı yeteneğidir; çünkü onunla:

- Bir fonksiyon işaretçisini kendi shellcode adresine yönlendirebilir,
- GOT (Global Offset Table) girdisini değiştirip, sonraki bir libc çağrısını (`printf`, `exit` gibi) `system`'e yönlendirebilir,
- Bir dönüş adresini (return address) ROP zincirinin başlangıcına çevirebilirsiniz.

Büyük değerler yazmanın maliyeti ne olurdu? Örneğin 64-bit bir adres yazmak için doğrudan `%18446744073709551615c` gibi devasa bir genişlik kullanmak imkânsızdır (program milyarlarca karakter basmaya çalışır ve pratikte durur). Bu yüzden gerçek istismarda genellikle `%hn` (2 baytlık, `short`) veya `%hhn` (1 baytlık, `byte`) kullanılır. Saldırgan hedef adresi 2'şer bayt parçalara böler, her parçaya farklı bir küçük değer yazar ve yazma işlemini birkaç yönergeye dağıtır. Bu, klasik "byte-by-byte write" tekniğidir ve otomatik istismar araçları bu hesabı sizin yerinize yapar.

Somut bir örnek akışı şöyle görünür (kavramsal olarak):

```
[hedef_adres][hedef_adres+2] ... %.<deger1>x %k$hn %.<deger2>x %m$hn ...
```

Burada girdinin başına yazılmak istenen adresler dizilir, ardından her `%hn` için gereken karakter sayısı `%.<sayi>x` ile ayarlanır. Elle yazması zahmetlidir, ama bu tam da otomatik araçların çözdüğü bir denklemdir.

## Savunma: Zafiyeti Nasıl Önleriz?

Sömürü tarafını anlattıktan sonra asıl mesele savunmadır; çünkü bu zafiyet, doğru alışkanlıklarla **tamamen** önlenebilir bir sınıftır. Savunmayı katmanlar halinde düşünmek en sağlıklısıdır.

### 1. Kök çözüm: Format dizesini asla kullanıcıya bırakma

En temel ve en etkili kural: sabit, programcı tarafından yazılmış bir format dizesi kullan; değişken veriyi argüman olarak geçir.

```c
printf("%s", kullanici_girdisi);   // dogru
fprintf(log, "%s", mesaj);          // dogru
```

Bu tek disiplin, zafiyetin tüm türevlerini (hem `%x` sızıntısı hem `%n` yazması) kaynağında yok eder. Çünkü kullanıcı girdisi artık *yorumlanan* değil, *yazdırılan* konumdadır. Bu kural yalnızca `printf` için değil; `fprintf`, `sprintf`, `snprintf`, `vprintf`, `syslog`, `err`/`warn` aileleri, hatta bazı loglama kütüphaneleri için de geçerlidir. Özellikle `syslog(priority, kullanici_girdisi)` çok sık gözden kaçan bir tuzaktır.

### 2. Derleyici uyarılarını açık tut ve uyarıyı hataya çevir

Modern derleyiciler bu hatayı büyük ölçüde yakalayabilir. GCC ve Clang'de `-Wformat` ve özellikle `-Wformat-security`, sabit olmayan (non-literal) bir format dizesi argümansız kullanıldığında uyarı verir. `-Wformat-nonliteral` daha katıdır. Bu uyarıları `-Werror` ile hataya çevirmek, sorunlu kodun derlemeyi geçmesini engeller. Uyarı bayraklarının kesin adları sürümler arasında ufak farklılıklar gösterebildiğinden, projenizde bunları belgelemek ve CI'da zorunlu kılmak önemlidir.

Kendi variadic sarmalayıcı (wrapper) fonksiyonlarınızı yazarken, GCC/Clang'in `__attribute__((format(printf, N, M)))` özniteliğini kullanın. Bu öznitelik derleyiciye "bu fonksiyon printf gibi davranır, N'inci argüman format dizesidir" der ve derleyici sizin fonksiyonunuz için de format denetimlerini uygular. Bu, ev yapımı loglama katmanlarındaki sessiz zafiyetleri yakalamanın en pratik yoludur.

### 3. `%n`'i devre dışı bırakma imkânlarından yararlan

Bazı platformlarda ve C kütüphanelerinde `%n`'in kötüye kullanımına karşı ek koruma vardır. Örneğin bazı çalışma zamanları, yazılabilir olmayan bellekte bulunan format dizelerinde `%n`'e izin verirken, yazılabilir bir bölgeden gelen format dizesinde `%n` görüldüğünde işlemi sonlandırır (FORTIFY tarzı korumalar). Ayrıca bazı sistemler `%n` desteğini tümüyle kaldırma seçeneği sunar. Bu korumalar platforma özgüdür ve sürüm bağımlıdır; bu yüzden "her yerde `%n` engellidir" varsayımına güvenmeyin. Bunlar yardımcı katmanlardır, kök çözümün yerine geçmez.

### 4. Genel bellek sertleştirmeleri (hardening) yardımcı olur ama yetmez

ASLR, PIE, stack canary, RELRO (özellikle "full RELRO" ile GOT'un salt-okunur yapılması) ve `_FORTIFY_SOURCE` gibi mekanizmalar, format string sömürüsünü *zorlaştırır*:

- **Full RELRO**, GOT girdilerini salt-okunur yapar; böylece `%n` ile GOT üzerinden kontrol ele geçirme yolunu kapatır.
- **Stack canary**, format string ile birleşen yığın taşmalarını zorlaştırır (ama `%x` ile canary sızdırılabildiği için mutlak değildir).
- **ASLR/PIE**, saldırganın adres bilmesini engeller (ama `%x`/`%p` sızıntısı tam da bunu delmek içindir).

Buradaki ders nettir: bu sertleştirmeler *sızıntı* zafiyetiyle birlikte çalışamaz. Format string açığı hem okuma hem yazma sağladığı için, bu savunmaların bir kısmını kendi başına atlatabilir. Dolayısıyla sertleştirme, kaynak koddaki kök çözümün yerine değil, yanına konur.

### 5. Statik ve dinamik analiz

Statik analiz araçları (derleyici uyarıları, lint araçları, güvenlik odaklı SAST çözümleri) `printf(x)` kalıbını taramada oldukça başarılıdır. Dinamik tarafta fuzzing, format yönergesi içeren girdilerle programı zorlayarak çökme ya da beklenmedik davranışları ortaya çıkarabilir. `%s`, `%n`, `%x` içeren girdiler fuzzing sözlüğünde standart olarak bulunmalıdır. Kod inceleme (code review) sırasında, `printf` ailesindeki her çağrıda ilk argümanın sabit bir dize literali olup olmadığını mekanik olarak kontrol etmek çok etkilidir.

## Yaygın Hatalar

Deneyimli geliştiriciler bile aşağıdaki tuzaklara düşer; bu yüzden her birini ayrı ayrı bilinçte tutmak gerekir.

**Loglama fonksiyonlarını unutmak.** En sık hata, `printf`'e dikkat edip `syslog`, `fprintf`, kendi `LOG(...)` makronuzu veya hata mesajı fonksiyonlarını gözden kaçırmaktır. `syslog(LOG_ERR, mesaj)` çağrısında `mesaj` kullanıcı kontrolündeyse zafiyet aynen oradadır. Kural, format string kabul eden *tüm* fonksiyonları kapsamalıdır.

**"Kullanıcı buraya `%` koyamaz" varsayımı.** Girdinin dolaylı yollardan (dosya adı, HTTP başlığı, ortam değişkeni, veritabanı alanı, hata mesajına gömülen bir değer) formata sızabileceğini gözden kaçırmak yaygındır. Girdi kaynağını "güvenilir" saymak, çoğu ihlalin başlangıcıdır.

**`sprintf`/`snprintf`'te format argümanını karıştırmak.** `snprintf(buf, n, kullanici_girdisi)` da tıpkı `printf(kullanici_girdisi)` kadar zafiyetlidir. Boyut sınırlaması yalnızca klasik buffer overflow'a karşı korur, format string yorumlamasını engellemez.

**Uyarıları görmezden gelmek.** `-Wformat-security` uyarısını "gürültü" sayıp bastırmak, tam da yakalanmak istenen zafiyeti serbest bırakır. Uyarı çıktısı temiz tutulmalı ve bu sınıftaki uyarılar asla susturulmamalıdır.

**"Sadece okuma, zararsız" yanılgısı.** `%x` sızıntısını "yalnızca birkaç hex değer, ne olacak" diye küçümsemek büyük hatadır. O birkaç değer canary, libc tabanı veya stack adresi olabilir; yani başka bir açığın sömürülmesini mümkün kılan anahtardır.

**64-bit'te güvende sanmak.** 64-bit mimaride ilk argümanların registerlarda taşınması sömürüyü biraz değiştirir, ama zafiyeti ortadan kaldırmaz. `%p` ve konumsal yönergelerle 64-bit'te de sızıntı ve yazma gayet mümkündür.

## En İyi Pratikler

Bir güvenlik uzmanı gözüyle önceliklendirilmiş özet şudur:

1. **Format dizesi daima sabit bir literal olsun.** Değişken veriyi `%s` gibi bir yönergeyle argüman olarak geçir. Bu tek kural, zafiyet sınıfının neredeyse tamamını ortadan kaldırır. Kuralı bir kod standardı olarak yazıya dökün ve inceleme kontrol listesine ekleyin.

2. **Derleyici format denetimlerini zorunlu kılın.** `-Wformat`, `-Wformat-security` gibi uyarıları açın, `-Werror` ile hataya çevirin, CI hattında bu bayrakları zorlayın. Kendi variadic sarmalayıcılarınıza `format` özniteliğini ekleyin ki denetim onlara da uygulansın.

3. **Sertleştirmeleri katman olarak açın.** Full RELRO, ASLR/PIE, stack canary ve FORTIFY korumalarını derleme ve dağıtımda etkinleştirin. Bunlar tek başına yeterli değildir ama sömürü maliyetini yükseltir ve savunma derinliği (defense in depth) sağlar.

4. **Girdi kaynaklarını haritalayın.** Kullanıcı verisinin format string'e ulaşabileceği tüm yolları (doğrudan girdi, dosya adları, ağ başlıkları, log mesajları, çeviri/i18n dizeleri) belirleyin. Özellikle yerelleştirme (localization) dosyalarından gelen çeviri dizeleri, gözden kaçan bir format string kaynağıdır; çünkü çeviri metni kullanıcı ya da üçüncü taraf kontrolünde olabilir.

5. **Statik analiz ve fuzzing'i sürece gömün.** SAST araçlarını CI'ya bağlayın, `%s`/`%n`/`%x` içeren girdileri fuzzing korpusunuza ekleyin, kod incelemesinde `printf` ailesindeki her çağrının ilk argümanını mekanik olarak denetleyin.

6. **Mümkünse daha güvenli soyutlamalar kullanın.** C++'ta tip-güvenli biçimlendirme (örneğin modern `std::format` benzeri arayüzler veya akış tabanlı çıktı), format dizesi/argüman uyuşmazlıklarını derleme zamanında yakalayabilir ve `%n` gibi tehlikeli yönergeleri baştan dışarıda bırakabilir. Diğer dillerde de biçimlendirmeyi tip sistemine bağlayan API'ler tercih edilmelidir.

## Kapanış

Format string zafiyeti, tek bir eksik `"%s"` yüzünden bir programın kendi bellek okuma-yazma yeteneğini saldırgana teslim ettiği, öğretici ölçüde net bir açıktır. `%x` ile saldırgan yığını tarayıp canary, libc tabanı ve stack adresleri gibi sırları sızdırır; `%n` ile bu okumayı, "istediğim adrese istediğim değeri yaz" primitifine dönüştürür ve GOT'tan dönüş adreslerine kadar kritik işaretçileri ele geçirir. İyi haber şudur: bu, savunulması en kolay zafiyet sınıflarından biridir. Format dizesini asla kullanıcıya bırakmamak, derleyici uyarılarını hataya çevirmek ve sertleştirmeleri katman katman açmak birleştiğinde, açık pratikte kaynağında kapanır. Uzman refleksi tek cümleye sığar: format dizesi programcının, veri kullanıcınındır; ikisi asla yer değiştirmez.
