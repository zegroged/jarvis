# Bash Scripting: Quoting, Güvenli Script Yazımı ve Injection'dan Kaçınma

## Giriş: Bash Neden Hem Güçlü Hem Tehlikeli

Bash, Unix ve Linux dünyasının tutkalıdır. Bir script bazen sadece birkaç komutu arka arkaya çalıştırmak için yazılır, sonra farkına varmadan üretim sunucularının bel kemiği hâline gelir. İşte tehlike de tam burada başlar: Bash'in tasarım felsefesi, "yazdığın her şey bir komut satırıdır" fikrine dayanır. Bu, onu inanılmaz esnek yapar; ama aynı zamanda, bir string'in ne zaman veri, ne zaman kod olduğu ayrımını sürekli bulanıklaştırır.

Çoğu güvenlik açığı ve garip hata, Bash'in bir metni "veri" olarak görmesini beklediğiniz yerde onu "çalıştırılacak kod" veya "bölünecek kelimeler" olarak yorumlamasından doğar. Bu makale, bu ayrımın nasıl çalıştığını kökten anlatır: quoting'in neden var olduğunu, word splitting ve globbing'in nasıl bir tuzak hâline geldiğini, komut injection'ın nasıl oluştuğunu ve güvenli script yazmanın somut disiplinlerini.

## Kök Neden: Shell Expansion ve Kelime Ayırma (Word Splitting)

Bash bir satırı çalıştırmadan önce, o satırı bir dizi dönüşümden (expansion) geçirir. Sıralama kabaca şöyledir: brace expansion, tilde expansion, parametre/değişken genişletme (`$var`), komut ikamesi (`$(...)`), aritmetik genişletme (`$((...))`), ardından **word splitting** ve en sonunda **filename expansion (globbing)**.

Buradaki kritik nokta şudur: değişken genişletme yapıldıktan **sonra**, ortaya çıkan sonuç `IFS` (Internal Field Separator) değişkenindeki karakterlere (varsayılan olarak boşluk, tab ve satır sonu) göre kelimelere bölünür. Yani `$var` içinde boşluk varsa, Bash o tek değeri birden fazla ayrı argümana böler.

Bir örnek bu tehlikeyi anlatmaya yeter:

```bash
dosya="benim raporum.txt"
rm $dosya        # TEHLİKE
```

Burada niyetiniz tek bir dosyayı silmekti. Ama Bash `$dosya` genişletmesinden sonra elde ettiği `benim raporum.txt` string'ini boşluktan böler ve komut şuna dönüşür:

```bash
rm benim raporum.txt
```

Yani `rm`'e iki ayrı argüman geçer: `benim` ve `raporum.txt`. İkisi de yoksa hata verir; ama daha kötüsü, ortamda `benim` adında başka bir dosya varsa onu silersiniz. Doğrusu:

```bash
rm "$dosya"
```

Çift tırnak, word splitting ve globbing'i devre dışı bırakır; `$dosya` tek bir argüman olarak `rm`'e ulaşır. **Bu, tüm makaledeki en önemli tek kuraldır: değişkenleri neredeyse her zaman çift tırnak içinde kullanın.**

### Neden `IFS` bu kadar merkezî?

Word splitting'in `IFS`'e bağlı olması, aslında bir güç kaynağıdır: CSV benzeri veriyi ayrıştırmak veya bir string'i parçalamak için `IFS`'i geçici olarak değiştirebilirsiniz. Ama bu güç, farkında olmadığınızda size karşı çalışır. Örneğin bir dosya adında satır sonu (`\n`) veya tab varsa, tırnaksız genişletme onu birden çok parçaya böler. Saldırgan kontrolündeki dosya adları bu yüzden tehlikelidir.

## Tırnakların Anatomisi: Tek Tırnak, Çift Tırnak ve Tırnaksız

Bash'te üç temel "quoting" durumu vardır ve aralarındaki fark, hata ve güvenlik açıklarının çoğunun kaynağıdır.

### Tek tırnak (`'...'`): Mutlak literal

Tek tırnak içinde **hiçbir** genişletme yapılmaz. `$`, `` ` ``, `\`, `*` — hepsi düz metin olarak kalır. Tek tırnağın içinde tek tırnak bile kullanamazsınız (kaçış yoktur). Sabit metinler, regex desenleri, `awk`/`sed` programları ve şifre gibi içinde özel karakter olan sabitler için idealdir.

```bash
echo 'Fiyat: $5 ve yol: /home/*'   # Aynen basılır, hiçbir şey genişlemez
```

### Çift tırnak (`"..."`): Kontrollü genişletme

Çift tırnak içinde değişken genişletme (`$var`), komut ikamesi (`$(...)`) ve aritmetik genişletme **yapılır**, ama word splitting ve globbing **yapılmaz**. Bu, en sık ihtiyaç duyduğunuz moddur: değeri kullanmak istersiniz ama tek argüman olarak kalmasını da istersiniz.

```bash
mesaj="Merhaba $USER, bugün $(date +%A)"
echo "$mesaj"
```

### Tırnaksız: Tehlikeli varsayılan

Tırnaksız genişletme, hem word splitting'i hem globbing'i açar. Nadiren gerçekten istediğiniz budur. İstediğiniz bilinçli durumlar (örneğin bir string'i kasıtlı olarak kelimelere bölmek) dışında, tırnaksız `$var` bir hatadır.

### Kaba kural

- Sabit metin, hiçbir şey genişlemesin: **tek tırnak**.
- Değer lazım ama tek parça kalsın (neredeyse her zaman): **çift tırnak**.
- Kasıtlı word splitting veya globbing (bilinçli ve nadir): tırnaksız.

## `$@` ve `$*` Tuzağı: Neden `"$@"` Her Zaman Kazanır

Script'lere geçen argümanları başka bir komuta iletmek çok yaygındır. Burada dört varyant vardır ve üçü hatalıdır:

- `$*` — tüm argümanları tek string'e birleştirir, sonra word splitting'e uğrar. Boşluklu argümanlar parçalanır.
- `$@` — tırnaksız, argümanları ayrı verir ama yine word splitting'e ve globbing'e maruz bırakır.
- `"$*"` — hepsini `IFS`'in ilk karakteriyle birleştirip **tek** argüman yapar. Nadiren istenir.
- `"$@"` — **her argümanı ayrı ve olduğu gibi** korur. Boşluklar, özel karakterler bozulmaz.

```bash
# Doğru: argümanları başka komuta olduğu gibi ilet
yedek_al() {
    tar czf yedek.tgz "$@"
}
yedek_al "aylık rapor.txt" "gizli notlar.txt"
```

`"$@"` neden özeldir? Çünkü Bash bunu, gerçek argüman sınırlarını koruyan tek genişletme olarak özel kabul eder. Argüman diziniz üç elemanlıysa, `"$@"` tam olarak üç argüman üretir; içlerinde boşluk olsa bile. Bir script argüman iletiyorsa ve `"$@"` kullanmıyorsa, orada gizli bir bug vardır.

## Command Injection: Verinin Koda Dönüştüğü An

Injection'ın kökü şudur: kullanıcıdan (veya dış kaynaktan) gelen **veri**, shell tarafından **kod** olarak yorumlanır. Bu, iki yolla olur.

### 1. `eval` ve dolaylı çalıştırma

`eval`, kendisine verilen string'i **tekrar** shell komutu olarak yorumlar. Kullanıcı girdisi bir `eval`'e ulaşırsa, saldırgan istediği komutu çalıştırabilir:

```bash
girdi='dosya.txt; rm -rf ~'
eval "cat $girdi"     # FELAKET: rm -rf ~ da çalışır
```

Buradaki `;` shell için komut ayırıcıdır. `eval`, string'i çalıştırmadan önce genişlettiği için `;` sonrası ayrı bir komut olur. Kural nettir: **`eval`'den mümkün olduğunca kaçının.** Değişkenler arası dolaylı erişim (indirection) gerekiyorsa, Bash 4+ için `${!ref}` veya `declare -n` (nameref) gibi güvenli alternatifler vardır.

### 2. Kullanıcı verisinin komut yapısına gömülmesi

Aynı problem tırnaksız genişletmede de gizlice yaşanır. Bir değeri `sh -c` içine, bir SSH komutuna veya bir SQL client'ının komut satırına string birleştirerek koyarsanız, o katmanın kendi ayrıştırıcısı devreye girer:

```bash
kullanici="ali; DROP TABLE users"
mysql -e "SELECT * FROM t WHERE u='$kullanici'"   # TEHLİKE
```

Burada tehlike Bash'ten çok hedef sistemin (SQL) ayrıştırıcısındadır, ama tetikleyen şey aynı hatadır: veriyi güvenli biçimde ayırt etmeden bir komut string'ine gömmek. Doğru yaklaşım, veriyi argüman olarak (string birleştirmeden) geçirmek veya hedef sistemin parametreli/escape'li mekanizmasını kullanmaktır.

### 3. `printf %q` ile güvenli hâle getirme

Bir değeri başka bir shell bağlamına (örneğin `ssh host "..."` veya `bash -c "..."`) güvenle iletmeniz gerçekten gerekiyorsa, `printf '%q'` o değeri shell için yeniden tırnaklanmış, güvenli bir forma çevirir:

```bash
guvenli=$(printf '%q' "$kullanici_girdisi")
ssh sunucu "grep -- $guvenli /var/log/uygulama.log"
```

`%q`, değerin içindeki her özel karakteri hedef shell'in aynen veri olarak göreceği şekilde kaçışlar. Yine de, mümkün olan her yerde uzak tarafta string birleştirmek yerine argüman dizisi kullanmak (`ssh sunucu komut "$arg1" "$arg2"` yerine yapıyı sabit tutup veriyi ayrı geçirmek) daha güvenlidir.

## Sessiz Felaketler: Boş Değişken ve Silme Komutları

Bir güvenlik açığı kadar yıkıcı olan bir sınıf hata da vardır: tanımsız veya boş değişkenlerin genişlemesi. Klasik örnek:

```bash
rm -rf "$HEDEF_DIZIN/"      # $HEDEF_DIZIN tanımsızsa: rm -rf /
```

Eğer `$HEDEF_DIZIN` bir yerde tanımlanmadıysa (yazım hatası, atlanmış bir adım), genişleme boş string üretir ve komut `rm -rf /` hâline gelir. Bu tür facialar gerçek dünyada üretim sistemlerini silmiştir.

Kök neden, Bash'in varsayılan olarak tanımsız değişkeni **boş string** olarak kabul edip sessizce devam etmesidir. Bunu iki katmanla önlersiniz:

1. `set -u` ile tanımsız değişkende hata verilmesini sağlayın (aşağıda).
2. Kritik yerlerde varsayılan değer veya zorunluluk operatörü kullanın: `"${HEDEF_DIZIN:?Hedef dizin tanımlı degil}"` — bu, değişken boş veya tanımsızsa script'i mesajla durdurur.

## Güvenli Script'in Temeli: `set` Bayrakları ve `IFS`

Neredeyse her ciddi Bash script'inin başında şu satır (veya bir varyantı) bulunur:

```bash
set -euo pipefail
IFS=$'\n\t'
```

Her parçanın **neden** orada olduğunu anlamak önemlidir, çünkü bunlar sihir değil, bilinçli davranış değişiklikleridir.

### `set -e` (errexit): Hatada dur

Varsayılan Bash, bir komut başarısız olsa (sıfırdan farklı çıkış kodu) bile bir sonrakine geçer. `set -e`, çoğu durumda ilk hatada script'i durdurur. Bu, "bir adım başarısız oldu ama script devam edip yanlış varsayımlarla çalışmaya devam etti" felaketini önler.

Ancak `set -e`'nin tuzakları vardır ve bunları bilmezseniz yanlış güven duyarsınız: bir komut `if`, `while`, `&&`, `||` gibi bir test bağlamında ise başarısızlığı script'i durdurmaz (bu kasıtlıdır). Ayrıca bir fonksiyonun içindeki başarısızlıkların yayılması ve pipe davranışı bazı köşe durumlarda beklenmedik olabilir. Bu yüzden `set -e` bir güvenlik ağıdır, mutlak bir garanti değil; kritik komutların çıkış kodunu yine de açıkça kontrol etmek gerekir.

### `set -u` (nounset): Tanımsız değişkende hata

Yukarıda anlattığımız boş değişken felaketini önleyen ana savunmadır. Tanımsız bir değişkene erişince script hata verip durur. Bilinçli olarak "olabilir de olmayabilir de" bir değişken kullanacaksanız, `"${VAR:-varsayilan}"` ile açıkça varsayılan verin.

### `set -o pipefail`: Pipe'ın gerçek çıkış kodu

Varsayılan olarak bir pipe'ın (`a | b | c`) çıkış kodu, **son** komutun kodudur. Yani `a` başarısız olsa bile `c` başarılıysa, pipe başarılı sayılır. `pipefail`, pipe'taki **herhangi bir** komut başarısız olursa pipe'ı başarısız sayar. `set -e` ile birlikte, `cat gizli.txt | grep desen` gibi bir zincirde `cat`'in başarısızlığını yakalamanızı sağlar.

### `IFS=$'\n\t'`: Kaza eseri bölünmeyi azalt

`IFS`'ten boşluğu çıkarıp yalnızca satır sonu ve tab bırakmak, boşluk içeren dosya adlarının kaza eseri bölünme riskini azaltır. Bu bir "kemer ve pantolon askısı" önlemidir; yine de değişkenleri tırnaklama disiplininin yerini **tutmaz**, onu tamamlar.

## Yaygın Tuzaklar ve Hatalar

### Globbing'in sessizce genişlemesi

Tırnaksız bir `*`, bulunduğu dizindeki dosya adlarına genişler. Bir değişken içinde `*` varsa ve tırnaksız kullanırsanız, beklenmedik dosyalar işleme girer:

```bash
desen="*.log"
ls $desen     # dizindeki .log dosyalarına genişler (bazen istenir)
echo "$desen" # "*.log" olarak kalır (literal)
```

Niyetiniz literal metinse tırnaklayın; kasıtlı glob istiyorsanız tırnaksız bırakın ama bunu bilinçli yapın. Dahası, hiç eşleşme yoksa Bash varsayılan olarak deseni **olduğu gibi** bırakır (örneğin `*.log`), bu da alt komutlara garip argümanlar geçmesine yol açar. `shopt -s nullglob` ile eşleşme yoksa deseni boşa indirebilir, `failglob` ile eşleşme yoksa hata verdirebilirsiniz.

### `[ ]` ile boş değişken karşılaştırması

Eski test `[ $var = "x" ]`, `$var` boşsa `[ = "x" ]` hâline gelir ve söz dizimi hatası verir. Çözümler: değişkeni tırnaklayın (`[ "$var" = "x" ]`) veya Bash'in `[[ ]]` yapısını kullanın. `[[ ]]`, word splitting ve globbing uygulamaz, bu yüzden karşılaştırmalar için daha güvenlidir. Yalnız `[[ ]]` içinde sağ tarafta tırnaksız string, pattern matching olarak yorumlanabilir; sabit eşitlik istiyorsanız sağ tarafı da tırnaklayın.

### `for dosya in $(ls)` — çifte hata

Bu deyim iki hatayı birleştirir: `ls` çıktısını ayrıştırmak (dosya adlarındaki boşluk/özel karakter bozulur) ve gereksiz bir alt süreç. Doğrusu glob ile döngü kurmaktır:

```bash
for dosya in *.txt; do
    [ -e "$dosya" ] || continue   # nullglob yoksa eşleşme kontrolü
    echo "İşleniyor: $dosya"
done
```

### `cd` başarısızlığını yok saymak

```bash
cd "$dizin"
rm -rf *          # cd başarısızsa yanlış dizinde silersiniz!
```

`cd` başarısız olursa (dizin yok, izin yok) script mevcut dizinde kalır ve bir sonraki `rm -rf *` yanlış yerde çalışır. `cd "$dizin" || exit 1` veya `set -e` ile bunu yakalayın.

### Kaçışsız kullanıcı verisinin dosya yollarına gömülmesi

Kullanıcının verdiği bir ad `-` ile başlıyorsa (`-rf` gibi), komut onu bayrak sanabilir. Bunu `--` ile (seçenek sonu işareti) önlersiniz:

```bash
rm -- "$kullanici_dosyasi"
```

`--`, "bundan sonrası argümandır, bayrak değildir" der. Kullanıcı kontrolündeki değerleri komutlara geçirirken `--` alışkanlığı önemlidir.

### Geçici dosyalarda race condition

Sabit adlı geçici dosyalar (`/tmp/benim_dosyam`) hem çakışmaya hem güvenlik açığına yol açar (predictable temp file / symlink saldırıları). `mktemp` ile öngörülemez, size özel bir dosya/dizin oluşturun:

```bash
tmp=$(mktemp) || exit 1
trap 'rm -f "$tmp"' EXIT
```

`trap ... EXIT` script hangi yolla çıkarsa çıksın temizlik yapılmasını sağlar.

## Fonksiyonlar, `local` ve Kapsam Tuzakları

Bash'te değişkenler varsayılan olarak **global**'dir. Bir fonksiyon içinde `local` kullanmazsanız, oradaki atama tüm script'i etkiler ve uzaktan çalışan başka bir fonksiyonu bozabilir. Bu, büyük script'lerde teşhisi zor hatalara yol açar.

```bash
islem() {
    local sayac=0        # 'local' olmadan global'i ezerdi
    local -a liste=()     # yerel dizi
    # ...
}
```

Ayrıca `local x=$(komut)` yazımının bir inceliği vardır: `local`'in kendisi bir komut olduğu için, `$(komut)`'un çıkış kodu `local`'in başarısı tarafından maskelenebilir ve `set -e` bunu yakalayamaz. Kritik durumlarda önce `local x` bildirip sonra ayrı satırda `x=$(komut)` atamak daha güvenlidir.

## Doğru Kullanım: Uçtan Uca Güvenli Bir İskelet

Aşağıdaki iskelet, yukarıdaki ilkeleri tek bir yapıda toplar:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Geçici alan ve garantili temizlik
tmp_dir=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp_dir"' EXIT

kullan() {
    printf 'Kullanim: %s <girdi-dosyasi> <hedef-dizin>\n' "$0" >&2
    exit 2
}

main() {
    # Argüman doğrulama
    [ "$#" -eq 2 ] || kullan
    local girdi="$1"
    local hedef="${2:?Hedef dizin zorunlu}"

    [ -f "$girdi" ]  || { printf 'Hata: girdi yok: %s\n' "$girdi" >&2; exit 1; }
    [ -d "$hedef" ]  || { printf 'Hata: dizin yok: %s\n' "$hedef" >&2; exit 1; }

    # Tüm değişken kullanımları tırnaklı, -- ile bayrak koruması
    while IFS= read -r satir; do
        printf '%s\n' "$satir"
    done < "$girdi" > "$tmp_dir/islenmis.txt"

    cp -- "$tmp_dir/islenmis.txt" "$hedef/"
}

main "$@"
```

Bu iskeletteki her seçim bilinçlidir: `while IFS= read -r satir`, satırları olduğu gibi (baştaki/sondaki boşluğu kırpmadan, ters bölü kaçışlarını yorumlamadan) okur — dosya işlemenin altın kuralı. `printf '%s\n' "$satir"` yerine `echo "$satir"` kullanmamanın nedeni, `echo`'nun `-e`, `-n` gibi girdilerde ve ters bölü davranışında taşınabilir olmamasıdır; **veri basarken `printf` her zaman daha güvenlidir.**

## En İyi Pratikler: Özet Disiplin

- **Her değişkeni tırnakla.** İstisna, kasıtlı word splitting/globbing istediğiniz nadir, bilinçli durumlardır. Şüpheye düşünce tırnakla.
- **`"$@"` kullan**, `$*` veya tırnaksız `$@` değil, argüman iletirken.
- **`set -euo pipefail`** ile başla; ama sınırlarını bil — bu bir güvenlik ağı, mutlak garanti değil.
- **`eval`'den kaçın.** Dolaylı erişim için nameref (`declare -n`) veya `${!var}` kullan.
- **Kullanıcı verisini asla komut string'ine gömme.** Argüman olarak geçir; uzak bağlam gerekiyorsa `printf %q` ile güvenli hâle getir.
- **`--` kullan** ki kullanıcı verisi bayrak sanılmasın.
- **`mktemp` + `trap ... EXIT`** ile geçici dosyaları güvenli ve temiz tut.
- **Dosya okurken `while IFS= read -r`**, veri basarken `printf` kullan; `echo` ve `for ... in $(ls)`'ten kaçın.
- **Fonksiyonlarda `local`** kullan; global sızıntısını önle.
- **`shellcheck` çalıştır.** Bu statik analiz aracı, bu makaledeki tuzakların çoğunu otomatik yakalar; her ciddi script boru hattının parçası olmalıdır.

## Sonuç

Bash güvenliğinin tamamı tek bir kavramsal ayrıma dayanır: **veri ile kodu ayırmak.** Word splitting, globbing, `eval` ve tırnaksız genişletme — hepsi, verinin kod veya çoklu argüman olarak yeniden yorumlandığı yerlerdir. Tırnak disiplini, `set` bayrakları, `--`, `printf %q` ve `shellcheck` bir araya geldiğinde, bu yeniden yorumlanmayı kontrol altına alırsınız. Bash'i tehlikeli yapan esnekliği, aynı zamanda onu güçlü yapar; fark, o esnekliğin bilinçli mi yoksa kaza eseri mi kullanıldığındadır.
