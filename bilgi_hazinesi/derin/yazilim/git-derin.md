# Git Derinlemesine: Çözümlü Yürüyüş, Gerçek Vakalar, Kararlar ve Hata Modları

Bu metin bir özet değil; Git'i gerçek kod ve gerçek kaza senaryoları üzerinden çalıştıran, uygulamalı bir derin-dalıştır. Nesne modelini (blob/tree/commit/tag), hareketli işaretçileri (branch/HEAD) ve içerik-adresli değişmezliği zaten kavradığınızı varsayar. Buradan sonrası, o modelin gerçek terminalde nasıl "elinizde patladığını" ve nasıl kurtardığınızı gösterir.

---

## 1. Çözümlü yürüyüş: Bir `git reset --hard`'ın yuttuğu sabahın kurtarılması

Somut bir senaryo üzerinden gidelim. Bir CI temizlik script'i düşünün: geliştirici, "çalışma dizinini uzaktaki `main` ile birebir aynı hale getir" demek istiyor. Ekipte dolaşan, kopyala-yapıştır ile çoğalmış bir betik var.

### Önce: zafiyetli/hatalı kod

```bash
#!/usr/bin/env bash
# temizle-ve-guncelle.sh  --  "depoyu main'e sıfırla"
set -e

git fetch origin
git checkout main
git reset --hard origin/main    # (1) her şeyi origin/main'e zorla
git clean -fd                   # (2) izlenmeyen dosyaları da sil
git branch | grep -v '^\*' | xargs git branch -D   # (3) diğer branch'leri sil
```

Bu betik "temiz depo" isteyen bir CI ortamında masumdur. Ama bir geliştirici bunu **kendi lokal makinesinde**, üzerinde henüz commit'lememiş 2 saatlik çalışması varken çalıştırdığında sabahı biter. Somut olarak şu olur: geliştiricinin `feature/rapor` branch'inde henüz push edilmemiş 3 commit'i ve staging'de bekleyen değişiklikleri vardı.

### Sorun neden oluşuyor

Üç ayrı yıkım birbirini besliyor:

1. **`git reset --hard origin/main`** işaretçiyi geri/ileri zorlarken staging'i **ve** working directory'yi ezer. Henüz hiçbir nesneye bağlanmamış (commit'lenmemiş) 2 saatlik çalışma, hiçbir hash'e ait olmadığı için gerçekten yok olur — reflog bile onu göstermez, çünkü reflog commit işaretçilerini takip eder, commit'lenmemiş working-tree değişikliklerini değil.
2. **`git clean -fd`** izlenmeyen (untracked) yeni dosyaları siler. Yeni yazdığınız ama henüz `git add` etmediğiniz dosyalar buhar olur.
3. **`git branch -D`** ile branch'lerin *işaretçileri* silinir. İyi haber: buradaki commit'ler nesne veritabanında hâlâ durur ve reflog'da izleri kalır — yani (3) geri alınabilir. Kötü haber: (1) ve (2)'nin yuttukları geri alınamaz.

Kritik ayrım: **commit'lenmiş her şey kurtarılabilir, commit'lenmemiş hiçbir şey kurtarılamaz.** `--hard` bu iki dünyanın tam sınırında durur.

### Kurtarma: reflog ile branch işaretçilerini geri getirme

Silinen `feature/rapor` branch'inin commit'leri (push edilmemiş olsa da commit'lenmişlerdi) reflog'dadır:

```bash
$ git reflog --date=iso
a1b2c3d HEAD@{0}: reset: moving to origin/main
9f8e7d6 HEAD@{1}: commit: rapor: PDF export ekle
5c4b3a2 HEAD@{2}: commit: rapor: tablo başlıkları
1a2b3c4 HEAD@{3}: commit: rapor: iskelet

# 9f8e7d6, silinen branch'in son commit'iydi. Geri getir:
$ git branch feature/rapor-kurtarma 9f8e7d6
$ git log --oneline feature/rapor-kurtarma
9f8e7d6 rapor: PDF export ekle
5c4b3a2 rapor: tablo başlıkları
1a2b3c4 rapor: iskelet
```

Üç commit de geri geldi. Ama staging'deki commit'lenmemiş değişiklikler gitmiştir — onlar için tek kaynak, IDE'nin lokal geçmişi (local history) veya editör swap dosyalarıdır.

### Sonra: düzeltilmiş/doğru kod

Doğru betik iki şey yapar: **yıkıcı olmadan önce iş kaybını tespit eder** ve niyeti CI ile lokali ayırır.

```bash
#!/usr/bin/env bash
# temizle-ve-guncelle.sh  --  güvenli sürüm
set -euo pipefail

# 1. Commit'lenmemiş iş var mı? Varsa DURDUR (CI dışında).
if [[ "${CI:-false}" != "true" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "HATA: commit'lenmemiş değişiklikler var. Önce commit veya stash et." >&2
    git status --short >&2
    exit 1
  fi
  # Untracked dosyaları da uyar (silmeden önce).
  if [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    echo "UYARI: izlenmeyen dosyalar mevcut, clean çalıştırılmayacak." >&2
    exit 1
  fi
fi

git fetch origin

# 2. reset yerine, güvenli fast-forward dene; sapma varsa insana bırak.
current="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current" != "main" ]]; then
  git switch main
fi

# --ff-only: sadece ilerleme mümkünse güncelle, tarihi ezme.
if ! git merge --ff-only origin/main; then
  echo "HATA: main ile origin/main sapmış. Manuel inceleme gerekli." >&2
  exit 1
fi

# 3. Branch silme: sadece origin'e tam olarak birleşmiş (merged) olanları sil.
git branch --merged main | grep -vE '^\*|main|develop' | xargs -r git branch -d
#                                                                        ^^ küçük d:
#   sadece güvenle silinebilenler; -D (büyük) körü körüne silerdi.
```

Fark üç noktada: (a) `--hard reset` yerine `merge --ff-only` — tarihi asla ezmez, sapma varsa reddeder; (b) commit'lenmemiş iş varken durur, yani geri alınamaz kaybı en baştan önler; (c) branch silmede `-D` yerine `-d` — birleşmemiş bir branch'i yanlışlıkla silmeyi imkânsız kılar.

### Bir adım öteye: `git reflog`'un neden çalıştığını nesne modeliyle görmek

Kurtarmanın işe yaramasının sebebini yüzeysel bilmek ("reflog var işte") ile derinlemesine bilmek arasında pratik bir fark vardır: ne zaman kurtaramayacağınızı da bilmek. Şu deneyi yapın:

```bash
mkdir gc-lab && cd gc-lab && git init -q
git config user.email a@b.c && git config user.name X
echo v1 > f.txt && git add f.txt && git commit -qm c1
lost=$(git rev-parse HEAD)        # commit'in hash'ini yakala
echo v2 > f.txt && git commit -qam c2
git reset --hard HEAD~1           # c2'yi "sil"

# c2 hâlâ nesne veritabanında mı? Doğrudan hash ile sor:
git cat-file -t "$(git rev-parse 'HEAD@{1}')"   # -> commit
git show "$(git rev-parse 'HEAD@{1}')" --stat    # c2'nin içeriği hâlâ burada
```

`reset --hard` yalnızca `main` işaretçisini `c1`'e çekti; `c2` commit nesnesi ve onun blob/tree'leri silinmedi, sadece hiçbir branch onları göstermiyor. Reflog, `HEAD@{1}` üzerinden hâlâ o hash'i tutuyor. İşaretçi gitti, nesne durdu — kurtarmanın tamamı bu tek cümledir.

Şimdi sınırı görün: eğer `c2` hiç commit'lenmemiş olsaydı (sadece working directory'de kalsaydı), ne reflog'da ne nesne veritabanında hiçbir izi olmazdı, çünkü hiçbir zaman bir nesneye dönüşmemişti. "Commit et, sonra düşün" refleksinin teknik gerekçesi budur: commit, çalışmanızı içerik-adresli, kalıcı bir nesneye çevirerek onu Git'in koruma şemsiyesi altına alır.

---

## 2. Gerçek sistem örneği: Merge/rebase davranışını "elle" doğrulamak

Merge ve rebase'in tarihi nasıl farklı yazdığını anlatmak kolay; **görmek** ikna edicidir. Aşağıdaki, gerçekten çalışan, sıfırdan kurulan bir laboratuvardır. Kopyalayıp çalıştırın; her adımda hangi işaretçinin nereye gittiğini gözlemleyin.

```bash
# Sıfırdan izole bir depo kur
mkdir git-lab && cd git-lab && git init -q
git config user.email lab@example.com
git config user.name Lab

# Ortak taban
printf 'satir1\n' > dosya.txt
git add dosya.txt && git commit -qm "C0: taban"

# feature branch'i ayır ve iki commit at
git switch -qc feature
printf 'satir1\nfeature-A\n' > dosya.txt && git commit -qam "C1: feature-A"
printf 'satir1\nfeature-A\nfeature-B\n' > dosya.txt && git commit -qam "C2: feature-B"

# main bu sırada ilerlesin (çatallanma yaratmak için)
git switch -q main
printf 'satir1\nmain-X\n' > baska.txt && git add baska.txt && git commit -qm "M1: main-X"
```

Şu an tarih çatallı: `C0`'dan hem `feature` (C1→C2) hem `main` (M1) ayrılıyor. Şimdi aynı durumu iki kez, iki yöntemle birleştirelim ve hash'lere bakalım.

**Yöntem A — merge:**

```bash
git switch -q main
git merge --no-edit feature
git log --oneline --graph --all
# *   7d3f9a1 Merge branch 'feature'   <- İKİ parent'lı yeni commit
# |\
# | * 2b1c8e4 C2: feature-B
# | * 9a4d2f0 C1: feature-A
# * | 5e6f7a8 M1: main-X
# |/
# * c0d1e2f C0: taban
```

`C1` ve `C2`'nin hash'leri (`9a4d2f0`, `2b1c8e4`) **değişmedi**. Tarih çataldı ve tekrar birleşti; grafikte bunu net görüyorsunuz.

**Yöntem B — rebase (aynı başlangıçtan tekrar kurup):**

```bash
# ... aynı laboratuvarı yeniden kurun (git-lab2) ...
git switch -q feature
git rebase main
git log --oneline --graph --all
# * f11a22b C2: feature-B    <- YENİ hash (eskiden 2b1c8e4 idi)
# * c99d88e C1: feature-A    <- YENİ hash (eskiden 9a4d2f0 idi)
# * 5e6f7a8 M1: main-X
# * c0d1e2f C0: taban
```

İşte kanıt: aynı değişiklikleri taşıyan `C1`/`C2` artık **farklı hash'lere** sahip (`c99d88e`, `f11a22b`). Parent değişti → içerik değişti → hash değişti. Tarih düz bir çizgi oldu, merge commit'i yok. Bölüm 3'teki "paylaşılan commit'i rebase etme" kuralının somut sebebi tam olarak budur: dünyadaki başka bir depo hâlâ `9a4d2f0`'ı tutuyorsa, sizin `c99d88e`'niz onunla çelişir.

Bu laboratuvarı bir kez elle çalıştıran biri, "rebase yeni hash yaratır" cümlesini bir daha asla ezber olarak görmez.

### Vaka: Paylaşılmış branch'i rebase etmenin ekipte açtığı yara

Yukarıdaki mekanizmanın gerçek bir ekipte nasıl felakete döndüğünü canlandıralım. İki geliştirici, Ayşe ve Bora, aynı `feature/odeme` branch'i üzerinde çalışıyor. Branch push edilmiş; her ikisinin deposunda da `C1 (9a4d2f0)` ve `C2 (2b1c8e4)` var.

```bash
# Ayşe, "tarihi temizlemek" için paylaşılmış branch'i rebase edip force push'lar:
git switch feature/odeme
git rebase -i main            # C1, C2 yeniden yazıldı -> c99d88e, f11a22b
git push --force origin feature/odeme
```

Ayşe'nin gözünde her şey temiz. Ama Bora, bu sırada aynı branch üzerine kendi `C3`'ünü eklemiş ve `pull` yapıyor:

```bash
# Bora'nın makinesinde:
git pull
# Uzakta artık c99d88e/f11a22b var, Bora'da hâlâ 9a4d2f0/2b1c8e4 + C3.
# Git, "aynı" değişikliği iki farklı hash'te görür ve BİRLEŞTİRMEYE çalışır:
#   -> aynı satırlar için üst üste conflict,
#   -> C1/C2'nin içeriği tarihte İKİ kez belirir,
#   -> Bora yanlışlıkla merge'lerse, ödeme kodu çift uygulanmış commit'lerle kirlenir.
```

Kök sebep bölüm 2'deki kanıtın birebir sonucudur: rebase `9a4d2f0`'ı yok edip `c99d88e`'yi yarattı, ama Bora'nın deposu hâlâ `9a4d2f0`'ı gerçek sanıyordu. İki depo, "aynı iş"in iki ayrı hash'li kopyasına sahip oldu.

Doğru yol iki seçenekten biriydi: (a) branch paylaşıldıysa rebase'i hiç yapmamak, güncellemeyi `merge` ile almak; ya da (b) rebase mutlaka gerekliyse, önce ekipçe "kimse dokunmuyor" diye anlaşıp, sonra herkesin `git pull --rebase` veya `git reset --hard origin/feature/odeme` ile yeni tarihe hizalanması. Kurtarma pratiği: Bora, kendi `C3`'ünü kaybetmemek için onu yeni tarihe cherry-pick'ler:

```bash
git fetch origin
c3=$(git rev-parse feature/odeme@{1})    # kendi C3'ünün eski hash'i (reflog'dan)
git reset --hard origin/feature/odeme    # Ayşe'nin temiz tarihine hizala
git cherry-pick "$c3"                    # C3'ü yeni tabanın üstüne taşı
```

Ders: rebase bir "tarih düzenleme" aracıdır ve düzenlenen tarih paylaşılmışsa, düzeltmesi her zaman elle, ağrılı ve hataya açıktır. Kuralın "asla" kadar kesin olması bu yüzdendir.

---

## 3. Karşılaştırma / karar: Yaygın Git kararları ve takasları

Git'te "doğru cevap" nadiren tek bir komuttur; genellikle bir takas seçimidir. En sık karşılaşılan dört karar:

### 3.1 `merge` mi `rebase` mi (branch güncellerken)

| Boyut | `git merge origin/main` | `git rebase origin/main` |
|---|---|---|
| Tarih şekli | Çatal + merge commit'i korunur | Lineer, düz çizgi |
| Hash'ler | Korunur (değişmez) | Yeniden yazılır (yeni hash) |
| Paylaşılmış commit'te güvenlik | Güvenli | **Tehlikeli** |
| `git bisect` kolaylığı | Merge commit'leri gürültü yapar | İdeal (lineer) |
| Conflict çözümü | Bir kez, merge sırasında | Commit başına tekrarlanabilir |

**Karar:** Henüz push etmediğiniz lokal feature branch'inizi güncel tutmak için `rebase` (temiz tarih, kolay review). Paylaşılan/uzun ömürlü branch'leri birleştirirken `merge` (gerçeği koru, kimseyi kırma). Rebase sırasında aynı conflict'i defalarca çözmek can sıkarsa `git rerere`'yi (reuse recorded resolution) açın; Git çözümünüzü hatırlar. Ölçek notu: rebase, N commit'i tek tek yeniden uygularken her adımda conflict çıkabilir; merge tek seferde çözülür. Bu yüzden çok sayıda commit içeren, uzaklaşmış bir branch'te rebase "conflict maratonu"na dönebilir — böyle durumlarda tek seferlik bir merge pratikte daha az emek ister.

### 3.2 `reset` mi `revert` mi (bir commit'i geri almak)

`reset` işaretçiyi geriye taşır — **tarihi yeniden yazar**. `revert` istenmeyen commit'in etkisini tersine çeviren **yeni bir commit ekler** — tarihi korur.

**Karar:** Commit henüz **push edilmemişse** `reset` (temiz, iz bırakmaz). Commit **zaten paylaşılmışsa** kesinlikle `revert` — çünkü paylaşılan bir commit'i `reset`'lemek, herkesin deposuyla çelişen bir tarih yaratır. Basit kural: *"Başkası bu commit'i çekti mi? Öyleyse `revert`."*

### 3.3 `merge --squash` mi normal `merge` mi (PR birleştirirken)

- **Normal merge:** Feature branch'in tüm ara commit'leri tarihe girer. "Nasıl geliştirildi" görünür ama gürültülü.
- **Squash merge:** Feature'ın tüm commit'leri tek bir commit'e ezilir. `main` tertemiz olur; ama ara adımlar ve gerçek yazarlık ayrıntısı kaybolur, `git bisect` granülaritesi düşer.
- **Rebase merge:** Ara commit'ler korunur ama lineer eklenir.

**Karar:** `main`'in her satırının anlamlı olmasını isteyen, "bir PR = bir mantıksal değişiklik" kültürü olan ekipler için **squash** yaygın ve iyi bir seçimdir. Uzun, çok-yazarlı feature branch'lerinde bireysel katkı ve granüler bisect önemliyse normal/rebase merge tercih edin.

### 3.4 `--force` mü `--force-with-lease` mi

`--force` uzaktaki branch'i körü körüne ezer; araya giren meslektaşınızın commit'ini yok edebilir. `--force-with-lease` önce "uzak hâlâ benim beklediğim yerde mi?" diye bakar, biri araya girdiyse reddeder.

**Karar:** Neredeyse her zaman `--force-with-lease`. Düz `--force`'u yalnızca gerçekten neyi ezdiğinizi bildiğiniz, tek kişilik, kesin durumlarda kullanın. Daha da iyisi `--force-with-lease=<ref>:<beklenen-hash>` ile beklentiyi açıkça yazın; CI'ın araya fetch'lemesi gibi durumlarda lease'in yanlış "güvenli" sinyali vermesini de engeller.

---

## 4. Hata-modu kataloğu: Geliştiricilerin tipik tökezlemeleri

Aşağıdaki her madde, gerçekte sık yaşanan bir Git kazasını ve refleks düzeltmesini içerir.

**1. `git reset --hard`'ı commit'lenmemiş iş varken çalıştırmak.** `--hard` staging'i ve working directory'yi ezer; hiçbir hash'e bağlanmamış çalışma reflog'da bile olmadığından gerçekten kaybolur. Yıkıcı komutlardan önce daima `git status` bakın veya `git stash` ile emniyete alın.

**2. Push edilmiş commit'leri rebase etmek.** Rebase yeni hash yaratır; başkalarının deposundaki eski hash'lerle çelişir, tarih çift görünür ve conflict yığılır. Rebase yalnızca henüz paylaşmadığınız lokal commit'ler içindir.

**3. `--force` ile `--force-with-lease`'i karıştırmak.** Düz `--force`, siz fetch'lemeden önce push eden meslektaşınızın commit'ini sessizce siler. Varsayılan refleksiniz `--force-with-lease` olmalı.

**4. Bir sırrı (API key, parola) commit'leyip sonraki commit'te silmekle "temizlediğini" sanmak.** Sır tarihte hâlâ durur ve depoyu çekebilen herkes görebilir. Doğru refleks: anahtarı derhal iptal edip yenile (rotate); tarih temizliği (`git filter-repo` veya BFG) ayrı ve zahmetli, ikincil bir iştir.

**5. Detached HEAD'de commit atıp branch oluşturmadan başka yere geçmek.** Commit'ler "sahipsiz" kalır; tarih onları göstermez. Kaybolmazlar (reflog'dadırlar) ama fark edilmezse garbage collection sonrası gerçekten gidebilir. Detached HEAD'de iş yaptıysanız hemen `git branch <isim>` ile sabitleyin.

**6. Conflict marker'larını (`<<<<<<<`, `=======`, `>>>>>>>`) anlamadan bir tarafı rastgele silip kapatmak.** Bu, derlense bile sessiz mantık hatası üretir. Conflict "Git iki niyeti uzlaştıramadı, insan kararı istiyor" demektir; iki tarafın niyetini anlayıp birleştirin, sonra mutlaka test edin.

**7. `.gitignore`'a eklemenin, zaten izlenen (tracked) dosyayı takipten çıkardığını sanmak.** `.gitignore` yalnızca henüz izlenmeyen dosyalara etki eder. Daha önce commit'lenmiş bir dosyayı takipten çıkarmak için ayrıca `git rm --cached <dosya>` gerekir.

**8. Devasa, çok-amaçlı commit'ler atmak.** "Bir sürü şey düzeltildi" diyen tek dev commit; `git bisect` ile hata avlamayı, `git revert` ile seçici geri almayı ve code review'u neredeyse imkânsız kılar. Her commit tek bir mantıksal değişikliği kapsasın.

**9. `git pull`'un varsayılan merge davranışıyla lokal tarihi küçük merge commit'leriyle kirletmek.** Sürekli senkronda çalışan ekiplerde bu "merge bubble"lar tarihi çöp haline getirir. Lokal branch'i güncellerken `git pull --rebase` (veya `pull.rebase=true` konfigürasyonu) lineer tarih verir — yine yalnızca paylaşılmamış commit'lerde güvenli.

**10. `git stash`'i kalıcı depo gibi kullanmak.** Stash'ler birikir, isimsizdir ve unutulur; bir süre sonra hangisinin ne olduğu bilinmez. Stash geçici bir raftır; işi ya kısa sürede geri alın (`stash pop`) ya da anlamlı bir commit/branch'e dönüştürün.

**11. `git clean -fd`'yi düşünmeden çalıştırmak.** İzlenmeyen dosyaları geri dönüşsüz siler — henüz `add` etmediğiniz yeni dosyalar dahil. Önce `git clean -nd` (dry-run) ile neyin silineceğini görün.

**12. `git commit --amend`'i push edilmiş commit üzerinde yapmak.** Amend yeni bir hash üretir; push edilmiş bir commit'i amend'lemek, rebase gibi paylaşılan tarihi bozar ve karşı tarafta çakışma yaratır. Amend yalnızca henüz push etmediğiniz son commit için güvenlidir.

**13. `git checkout <dosya>` ile working-tree değişikliğini geri almanın kalıcı olduğunu fark etmemek.** `git checkout -- dosya.txt` (yeni sözdiziminde `git restore dosya.txt`) dosyayı son commit'lenmiş haline döndürür; aradaki commit'lenmemiş düzenlemeleriniz hiçbir yere kaydedilmeden silinir. Reset --hard gibi, bu da commit'lenmemiş işi geri dönüşsüz yok eder.

**14. `.git/hooks` içindeki hook'ların klonla gelmediğini bilmemek.** Hook'lar depoya dahil değildir; başka bir makinede otomatik çalışmazlar. "Bende pre-commit çalışıyordu" diyen bir kod, meslektaşta hiç çalışmayabilir. Paylaşılan hook'lar için `core.hooksPath` veya `pre-commit` gibi bir araçla hook'ları versiyonlanabilir bir dizine taşıyın.

**15. `git bisect`'i kirli working directory ile başlatmak.** Bisect her adımda farklı commit'lere checkout yapar; commit'lenmemiş değişiklikleriniz varsa ya checkout başarısız olur ya da sonuçları kirletir. Bisect'e girmeden önce mutlaka temiz bir working directory (commit veya stash edilmiş) ile başlayın.

---

## Kapanış

Bu metindeki her kaza ve her karar tek bir çekirdek gerçeğe iniyor: **Git commit'lenmiş nesneleri kaybetmez, yalnızca işaretçileri oynatır.** `reset --hard`'ın yıkıcılığı, rebase'in yeni hash'leri, force-push'un tehlikesi, detached HEAD'in "sahipsiz" commit'leri — hepsi "hangi işaretçi nereye gitti ve bu değişiklik daha önce commit'lenmiş miydi?" sorusunun cevabıdır. Bir komut sizi şaşırttığında terminale değil, önce bu soruya bakın; Git o an ezberlenen bir araç olmaktan çıkıp anlaşılan bir sisteme döner.
