# Perl Güvenliği: Legacy CGI, Taint Mode ve Regex Injection

## Giriş: Neden Hâlâ Perl?

Perl, 1987'de doğmuş, 1990'ların ve 2000'lerin başında web'in tutkalı olmuş bir dildir. Bugün "yeni proje" olarak nadiren tercih edilir; ancak ölmemiştir. Ağ ekipmanı üreticilerinin yönetim arayüzleri, ISS'lerin (ISP) altyapı otomasyon script'leri, biyoinformatik pipeline'ları, sistem yönetimi araçları ve on yıllardır çalışan legacy CGI uygulamaları hâlâ Perl üzerinde koşar. Bu kod tabanları çoğunlukla "çalışıyor, dokunma" mantığıyla korunur ve modern güvenlik incelemesinden geçmemiştir.

Bu durum, Perl'ü güvenlik açısından ilginç bir konuma yerleştirir: dilin kendisi güçlü savunma mekanizmaları (özellikle **taint mode**) sunar, fakat bu mekanizmalar hem az bilinir hem de yanlış anlaşıldığında atlatılabilir. Bu makale, Perl'e özgü üç kritik alanı derinlemesine ele alır: legacy CGI'nin yapısal riskleri, taint mode'un çalışma mantığı ve atlatma yolları, ve regex/command injection'ın Perl'deki özgün biçimleri.

Amaç, bu mekanizmaları **anlamak** ve savunma/tespit kurmaktır; canlı saldırı reçetesi değil.

## Legacy CGI Mimarisi ve Kök Riskleri

### CGI Nedir, Neden Tehlikelidir?

CGI (Common Gateway Interface), web sunucusunun her HTTP isteği için ayrı bir process (genellikle bir Perl yorumlayıcısı) başlatıp, istek verilerini environment değişkenleri ve `STDIN` üzerinden bu process'e aktardığı bir protokoldür. `QUERY_STRING`, `PATH_INFO`, `HTTP_*` başlıkları gibi kullanıcı kontrollü veriler doğrudan environment'a düşer.

Kök risk şudur: CGI script'i, kullanıcı girdisini genellikle **shell veya dosya sistemi bağlamına** aktaran ince bir katmandır. Modern web framework'lerinin sağladığı otomatik output escaping, parametreli sorgu, ORM gibi soyutlamalar burada yoktur. Programcı, güvenliği elle kurmak zorundadır ve legacy kodda bu çoğunlukla eksiktir.

### Klasik Tehlikeli Kalıplar

Legacy CGI'de tekrar tekrar görülen tipik açık şudur: kullanıcı girdisinin string interpolation ile bir kabuk komutuna gömülmesi.

```perl
# TEHLİKELİ — sadece kavramı göstermek için
my $file = $cgi->param('file');
my @lines = `cat /var/data/$file`;   # backtick = shell çalıştırır
```

Buradaki `$file` değeri `rapor.txt` değil de `rapor.txt; rm -rf /` benzeri bir dize olursa, backtick operatörü bunu bir kabuğa (`/bin/sh -c`) verdiği için ikinci komut da çalışır. Bu klasik **command injection**'dır ve Perl'e özgü olmayan, ancak Perl'ün backtick, `system`, `open` gibi çok sayıda "shell'e giden kapı" sunması nedeniyle sık rastlanan bir sınıftır.

### `open`'ın İki Bıçaklı Doğası

Perl'ün en tarihsel tehlikeli özelliği, iki-argümanlı (2-arg) `open` fonksiyonudur:

```perl
# TEHLİKELİ 2-arg open
open(my $fh, $filename);          # mode ve dosya adı aynı string'de
```

2-arg `open`, dosya adı string'inin başındaki/sonundaki karakterleri **mode belirteci** olarak yorumlar. Eğer `$filename` kullanıcı kontrollüyse ve `"| komut"` ya da `"komut |"` biçimindeyse, Perl bunu bir dosya değil, bir **pipe**/komut olarak açar ve komutu çalıştırır. Yani salt "dosya okuyoruz" sanılan bir satır, aslında rastgele komut çalıştırmaya dönüşebilir. Ayrıca `"> /etc/..."` gibi bir değer dosyayı üzerine yazma modunda açabilir.

Doğru savunma, **üç-argümanlı (3-arg) `open`** kullanmaktır; burada mode ayrı bir argüman olarak verildiği için dosya adı asla mode olarak yorumlanamaz:

```perl
# DOĞRU — mode ayrı argüman, dosya adı asla komut olamaz
open(my $fh, '<', $filename) or die "açılamadı: $!";
```

3-arg `open`, magic pipe/mode enjeksiyonunu yapısal olarak imkânsız kılar. Bu, legacy Perl kodunu sertleştirirken taranması gereken ilk kalıplardan biridir.

## Taint Mode: Perl'ün Yerleşik Kirlilik Takibi

### Tanım ve Çalışma Mantığı

Taint mode, Perl'ün en özgün ve güçlü güvenlik mekanizmasıdır. Fikir basit ama derindir: **program dışından gelen her veri "kirli" (tainted) kabul edilir**, ve kirli veri, sistemi etkileyen "tehlikeli" işlemlerde (komut çalıştırma, dosya işlemi, `eval` vb.) kullanılamaz — kullanılmaya çalışılırsa program çalışma zamanında ölür (die).

Taint mode `-T` bayrağıyla etkinleşir:

```perl
#!/usr/bin/perl -T
```

Perl setuid/setgid çalıştığında taint mode **otomatik olarak** devreye girer. Bu, tarihsel olarak setuid Perl script'lerini korumak için tasarlanmıştır.

### Neyin Kirli Sayıldığı

Kirlilik kaynakları, "programın kontrol etmediği dünya" olarak düşünülebilir:

- Komut satırı argümanları (`@ARGV`)
- Environment değişkenleri (`%ENV`) — CGI'de `QUERY_STRING` vb.
- Dosyalardan, socket'lerden, `STDIN`'den okunan veriler
- `readdir`, `readlink`, `getpwent` gibi çağrıların dönüşleri
- Locale bilgisi ve benzeri dış kaynaklar

Kritik nokta: **kirlilik bulaşıcıdır (taint propagation)**. Kirli bir değişkenden türetilen her yeni değer de kirlidir. `$b = $tainted . "sabit"` ifadesinde `$b` de kirlidir. Bu, veri akışını izleyen bir kirlilik grafiği oluşturur.

### "Tehlikeli" Sayılan İşlemler

Kirli veri şu işlemlerde kullanılırsa Perl ölür: `system`, `exec` (tek argümanlı/list olmayan biçimlerinde), backtick, `open` (pipe modunda), `eval` (string eval), `unlink`, kabuğa giden `glob`, ve dış kaynağı etkileyen benzeri çağrılar. Ayrıca `%ENV`'in `PATH`, `IFS`, `CDPATH`, `ENV`, `BASH_ENV` gibi tehlikeli girdileri güvenli hale getirilmeden alt process çalıştırma da engellenir; bu yüzden taint mode altında genellikle `$ENV{PATH}` elle temiz bir değere set edilir.

### Untainting: Kirliliği Temizlemenin TEK Yolu

İşte taint mode'un en önemli — ve en çok yanlış anlaşılan — kuralı: kirli bir değeri temizlemenin (untaint) yerleşik ve tek meşru yolu, onu bir **regex ile yakalayıp (capture group) çıkarmaktır**.

```perl
# Untainting: capture group'tan gelen değer temiz sayılır
if ($input =~ /^([\w.-]+)$/) {
    my $clean = $1;   # $1 artık TEMİZ (untainted)
} else {
    die "geçersiz girdi";
}
```

Buradaki felsefe şudur: Perl, kirli veriyi bir regex'in yakalama grubundan geçirdiğinizde, programcının o veriyi **bilinçli olarak doğruladığını** varsayar. Yani untaint, "bu veriyi gördüm, deseni onayladım" beyanıdır. Perl, deseni sizin adınıza yorumlamaz — sadece "bir capture yaptınız" gerçeğine güvenir.

## Taint Mode'un Atlatılması ve Yanlış Kullanımı

### Kök Zafiyet: Zayıf Untaint Deseni

Taint mode kusursuz değildir; asıl zayıflık, **untaint deseninin kendisinin güvenliğidir**. Perl, `$1`'i temiz sayar ama desenin gerçekten güvenli olup olmadığını denetleyemez. Programcı gevşek bir desen yazarsa, tehlikeli içeriği "temiz" olarak işaretlemiş olur.

```perl
# YANLIŞ — desen çok gevşek, taint'i anlamsız kılar
if ($input =~ /^(.*)$/) {     # her şeyi yakalar!
    my $clean = $1;            # "temiz" ama aslında hâlâ tehlikeli
}
```

`(.*)` her girdiyi yakalar; `; rm -rf /` dâhil. Perl artık bu değeri temiz sayar ve `system($clean)` çalışır. Taint mode teknik olarak açık, ama pratikte devre dışıdır. Bu, "untaint yaptım, güvendeyim" yanılgısının somut biçimidir. **Untaint, allow-list (izin listesi) mantığıyla, mümkün olan en dar desenle yapılmalıdır** — örn. yalnızca beklenen karakter sınıfını (`[\w.-]`, `[0-9]+`, sabit enum değerleri) kabul eden anchor'lı (`^...$`) desenler.

### Anchor Eksikliği ve Çok Satırlılık Tuzağı

Bir başka ince hata, `^` ve `$` anchor'larının çok satırlı girdide beklenenden farklı davranmasıdır. `$` desende son satırdaki bir newline'dan hemen öncesini de eşleyebilir; `\n`'den önceki kısımla eşleşen bir desen, satır sonrasındaki kötü niyetli yükü göz ardı edebilir. Kesin uç sınırlama için `\z` (string'in mutlak sonu) kullanmak, `$`'a göre daha güvenlidir:

```perl
# Daha güvenli anchor: \A ve \z string'in kesin başı/sonu
if ($input =~ /\A([\w.-]+)\z/) {
    my $clean = $1;
}
```

`\A` string başı, `\z` string sonudur ve `/m` bayrağından etkilenmezler; bu yüzden untaint desenlerinde `^`/`$` yerine `\A`/`\z` tercih edilmelidir.

### Taint Mode Neyi KAPSAMAZ

Taint mode, SQL injection'ı **doğrudan engellemez**. Kirli veri bir `DBI` sorgusuna string olarak gömülürse, taint mode bunu tehlikeli bir "sistem işlemi" olarak görmez — veritabanı çağrısı Perl'ün taint denetimindeki listede değildir. Yani taint mode açık olsa bile, string birleştirmeyle kurulan SQL sorgusu hâlâ injection'a açıktır. Savunma ayrıdır: **placeholder (parametreli sorgu)** kullanmak.

```perl
# DOĞRU — placeholder, SQL injection'ı yapısal olarak engeller
my $sth = $dbh->prepare('SELECT * FROM users WHERE name = ?');
$sth->execute($name);   # $name kirli olsa da güvenli, ayrıca aktarılır
```

Benzer şekilde taint mode, XSS gibi output-tarafı açıkları da kapsamaz; o, HTML encoding'in görevidir. Taint mode'un kapsamı **input → tehlikeli sistem çağrısı** akışıdır; her açık sınıfını değil.

### `system` ve `exec`'in List Biçimi

Command injection'a karşı en sağlam savunma, taint mode'dan bağımsız olarak, `system`/`exec`'i **list (çok argümanlı) biçimde** çağırmaktır:

```perl
# TEHLİKELİ — tek string, shell'e gider
system("ls -l $dir");

# DOĞRU — list biçimi, shell devreye GİRMEZ
system('ls', '-l', $dir);
```

List biçiminde Perl komutu doğrudan `execvp` benzeri bir çağrıyla çalıştırır; araya `/bin/sh` girmez. Dolayısıyla `$dir` içindeki `;`, `|`, `&&`, `$(...)` gibi metakarakterler kabuk tarafından yorumlanmaz — sadece tek bir argüman olarak `ls`'e geçer. Bu, "shell metacharacter" temelli command injection'ı kökten kapatır. Legacy kodu sertleştirirken tek-string `system`/`exec`/backtick çağrılarını list biçimine (veya boru için `open`'ın 3+ argümanlı list biçimine) çevirmek önceliklidir.

## Regex Injection: Perl'e Özgü Bir Tehlike Sınıfı

### Tanım

Regex injection, kullanıcı girdisinin **derlenen bir düzenli ifadenin içine** girmesiyle oluşur. Perl, regex'i dilin çekirdeğine gömdüğü ve regex desenlerinde kod çalıştırma yeteneği sunduğu için bu sınıf Perl'de özellikle keskindir. İki alt biçim vardır: desen mantığının bozulması (ReDoS dâhil) ve — çok daha vahim olanı — regex içinde kod yürütülmesi.

### En Tehlikeli Biçim: `(?{ ... })` ve `(??{ ... })`

Perl regex'i, desen içinde Perl kodu çalıştırmaya izin veren `(?{ CODE })` ve `(??{ CODE })` yapıları sunar. Bu, güçlü bir özelliktir ama kullanıcı girdisi ham olarak bir desene interpolate edilirse felakete dönüşür:

```perl
# TEHLİKELİ — kullanıcı deseni doğrudan interpolate ediliyor
my $pattern = $cgi->param('search');
if ($text =~ /$pattern/) { ... }
```

Kullanıcı `$pattern` olarak `(?{ system("...") })` benzeri bir dize gönderirse, regex derlenirken bu kod çalışabilir — bu, arbitrary code execution'a giden bir yoldur.

Perl'ün modern sürümleri burada önemli bir savunma ekler: `(?{...})` ve `(??{...})` yapıları, **interpolate edilmiş (dışarıdan gelen) desen parçalarında varsayılan olarak yasaktır**. Yani `$pattern` bir değişkenden gelip içinde `(?{...})` varsa, Perl bunu güvenlik gerekçesiyle reddeder (`use re 'eval'` pragma'sı açıkça verilmedikçe). Bu yüzden `use re 'eval'`'i asla kullanıcı girdisiyle birlikte açmayın. Yine de bu savunmaya kör güvenmek yanlıştır: eski Perl sürümleri, kod bloğu olmayan ama yine de yıkıcı desenler ve `use re 'eval'` içeren legacy kod hâlâ risklidir.

### Doğru Savunma: `\Q...\E` ve `quotemeta`

Kullanıcı girdisini regex'te bir **literal string** olarak aramak istiyorsanız (çoğu "arama" özelliğinin gerçek amacı budur), girdiyi `quotemeta` ile veya desen içinde `\Q...\E` ile kaçışlamalısınız. Bu, tüm regex metakarakterlerini (`.`, `*`, `(`, `?` vb.) sıradan karakterlere çevirir:

```perl
# DOĞRU — kullanıcı girdisi literal olarak aranır, metakarakter etkisiz
my $needle = $cgi->param('search');
if ($text =~ /\Q$needle\E/) { ... }
# veya:
my $quoted = quotemeta($needle);
```

`\Q$needle\E` içindeki `(?{...})`, `.*`, `(` gibi her şey artık literal karakterdir; ne kod çalışır ne de desen mantığı bozulur.

### ReDoS: Catastrophic Backtracking

Regex injection'ın kod çalıştırmayan ama yine de tehlikeli biçimi **ReDoS** (Regular Expression Denial of Service) tir. Belirli desenler — özellikle iç içe nicelik belirteçleri (nested quantifier) içerenler, örn. `(a+)+$` kalıbı — belirli girdilerde üstel (exponential) backtracking'e girer ve CPU'yu kilitler. Saldırgan ya deseni kontrol ediyorsa (regex injection) ya da sabit ama kırılgan bir desene eşleşmeyecek uzun bir girdi gönderiyorsa, tek bir istekle process'i saatlerce meşgul edebilir.

Savunma çok yönlüdür: kullanıcı girdisini asla ham desen olarak kabul etmemek; sabit desenleri nested quantifier'dan arındırmak; girdi uzunluğunu sınırlamak; mümkünse "atomik gruplar" `(?>...)` veya possessive quantifier'lar (`a++`, `a*+`) kullanarak backtracking'i kesmek; ve modern Perl'ün belirli regex türlerinde sunduğu ReDoS'a dirençli eşleme motorundan yararlanmak.

## Yaygın Hatalar ve Kontrol Listesi

Legacy Perl kodunu incelerken tekrar tekrar karşılaşılan hatalar:

- **2-arg `open` kullanmak.** Her `open(FH, $x)` çağrısı magic pipe injection adayıdır. 3-arg biçime çevir.
- **Tek-string `system`/`exec`/backtick.** Kullanıcı girdisi içeriyorsa list biçimine geç; shell'i devre dışı bırak.
- **Taint mode'u kapalı bırakmak veya `-T`'yi unutmak.** CGI ve setuid bağlamında `-T` neredeyse zorunludur.
- **Gevşek untaint deseni (`(.*)`, geniş karakter sınıfları).** Untaint'i allow-list mantığıyla, dar ve anchor'lı (`\A...\z`) yaz.
- **`use re 'eval'`'i kullanıcı girdisiyle açmak.** Bu, regex-tabanlı kod çalıştırmaya kapı açar; kaçın.
- **Kullanıcı girdisini `\Q...\E` olmadan desene interpolate etmek.** Literal arama için mutlaka `quotemeta`/`\Q\E`.
- **Taint mode'u SQL/XSS için yeterli sanmak.** DBI placeholder ve HTML encoding ayrı savunmalardır; taint bunları kapsamaz.
- **String `eval`'e kullanıcı verisi vermek.** `eval "$user_code"` arbitrary code execution'dır; `eval { ... }` (blok, hata yakalama için) ile karıştırma.
- **`use strict` ve `use warnings` yokluğu.** Bunlar güvenlik değil ama bütün hata sınıflarını (tanımsız değişken, tipografik hata) erken yakalar; legacy kodda çoğu eksiktir.
- **Eski, güncellenmemiş CPAN modülleri ve Perl sürümü.** Bilinen zafiyetler için sürüm ve bağımlılıkları denetle.

## Tespit ve Sertleştirme Yaklaşımı

Bir Perl kod tabanını güvenlik açısından değerlendirirken pratik akış şudur. Önce **statik tarama**: kod tabanında `system`, `exec`, backtick (`` ` ``), 2-arg `open`, `eval "` (string eval), `qx`, `use re 'eval'` ve değişken-interpolate edilmiş regex (`=~ /$...`) kalıplarını arayın; bunların her biri incelenmesi gereken bir düğümdür. `Perl::Critic` gibi bir statik analiz aracı, bu kalıpların çoğunu güvenlik politikalarıyla işaretleyebilir.

Sonra **taint mode'u zorunlu kılın**: `-T` ile çalıştırıp kırıldığı yerleri düzeltmek, aslında güvenlik açığı olan noktaları görünür kılar (Perl orada ölür). Bu, taint mode'un çift işlevidir: hem çalışma zamanı savunması hem de bir denetim aracı.

Son olarak **veri akışını düşünün**: her dış girdinin (CGI param, `%ENV`, dosya, socket) hangi tehlikeli çağrıya (`sink`) ulaştığını izleyin ve her yol için doğru savunmayı yerleştirin — komut için list biçimi, dosya için 3-arg `open` + path doğrulama, SQL için placeholder, regex için `\Q\E`, output için encoding.

## Sonuç

Perl, güvenlik açısından paradoksal bir dildir: taint mode gibi çağının ötesinde, veri akışı temelli bir savunma sunar; ama aynı zamanda backtick, 2-arg `open`, string `eval` ve regex-içi kod gibi çok sayıda "ayağa sıkma" mekanizmasını da barındırır. Legacy CGI bağlamında bu ikilik, gerçek ve düşük görünürlüklü bir risk oluşturur — çünkü bu kod hem kritik altyapıda çalışır hem de nadiren incelenir.

Ana çıkarım net: taint mode değerli bir katmandır ama **sihirli değildir** — gücü, untaint desenlerinizin darlığı kadardır ve SQL/XSS gibi sınıfları kapsamaz. Gerçek güvenlik, her tehlikeli sink için doğru, yapısal savunmayı (shell'i devre dışı bırakan list çağrıları, parametreli sorgular, `\Q\E` ile literal regex, 3-arg `open`) katmanlı biçimde uygulamaktan gelir. Perl'ün mekanizmalarını anlamak, bu eski ama hâlâ yaşayan kodu güvenli hale getirmenin ilk şartıdır.
