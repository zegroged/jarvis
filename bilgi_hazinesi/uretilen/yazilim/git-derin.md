# Git Derinlemesine: Nesne Modeli, Merge, Rebase, Branch Akışı ve Kurtarma

Git'i gündelik kullanan çoğu geliştirici, onu bir "komut ezberi" olarak öğrenir: `git add`, `git commit`, `git push`, tıkanınca da Stack Overflow. Bu yaklaşım bir yere kadar çalışır ama ilk ciddi çatışmada (conflict), ilk bozulan branch'te veya ilk yanlışlıkla silinen commit'te çöker. Bu makalenin amacı, Git'i komut düzeyinde değil **veri modeli** düzeyinde anlatmaktır. Çünkü Git'i gerçekten anlamanın tek yolu, alttaki nesne modelini kavramaktır. Nesne modelini anladığınızda, merge ile rebase arasındaki fark, "detached HEAD" uyarısı, `reflog` ile kurtarma gibi konular ezberlenmesi gereken kurallar olmaktan çıkıp, tek bir tutarlı sistemin doğal sonuçları haline gelir.

## Git Aslında Ne Depolar: Nesne Modeli

### Git bir içerik-adresli dosya sistemidir

Git'in kalbinde, kullanıcı arayüzünden bağımsız olarak çalışan küçük ve şaşırtıcı derecede sade bir **key-value deposu** vardır. Bu depoya herhangi bir içeriği verirsiniz, Git size o içeriğin **hash**'ini geri verir. Aynı içeriği daha sonra bu hash ile geri okuyabilirsiniz. Git tarihsel olarak bu hash için SHA-1 kullanmıştır; daha yeni sürümlerde SHA-256'ya geçiş için altyapı bulunur, ama pratikte hâlâ çok yaygın olan SHA-1'dir.

Buradaki kritik nokta şudur: hash, içeriğin **kendisinden** türetilir. Yani aynı içerik her zaman aynı hash'i verir. Bu özelliğe **content-addressable storage** (içerik-adresli depolama) denir ve Git'in neredeyse bütün güçlü davranışları bundan doğar. İki farklı branch'te birebir aynı dosya varsa, Git onu iki kez saklamaz; her ikisi de aynı nesneyi işaret eder. Bir commit'in içeriğini bir bit bile değiştirirseniz, hash'i tamamen değişir. Bu, Git tarihinin neden değiştirilemez (immutable) sayıldığının da temelidir: bir commit'i "düzenlediğinizde" aslında yeni bir hash'e sahip yepyeni bir commit yaratırsınız.

### Dört nesne türü

Git deposunun tamamı yalnızca dört nesne türünden oluşur. Bu dört türü anlarsanız, Git'in %90'ını anlamış olursunuz.

**blob (binary large object):** Bir dosyanın *içeriğini* tutar. Sadece içeriği; dosya adını, konumunu veya izinlerini değil. İki dosyanın içeriği aynıysa, tek bir blob'a işaret ederler. Bu yüzden blob, dosya değil, dosyanın gövdesidir.

**tree:** Bir dizini temsil eder. Bir tree, isimlerin (dosya/dizin adları), izinlerin ve bunların işaret ettiği nesnelerin (blob'lar veya alt tree'ler) bir listesidir. Yani tree, dosya adlarını içeriklere bağlayan katmandır. Bir tree başka tree'lere işaret ederek dizin hiyerarşisini kurar. Projenizin bir andaki tüm dosya yapısı, kök bir tree ile temsil edilir.

**commit:** Bir andaki proje durumunun (snapshot) fotoğrafıdır. Bir commit nesnesi şunları içerir: tek bir kök tree'ye işaret (yani o andaki tüm dosya durumu), bir veya daha fazla **parent** commit'e işaret, yazar (author) ve işleyen (committer) bilgisi, zaman damgası ve commit mesajı. Buradaki en önemli sözcük **parent**'tır: her commit, kendinden önceki commit'i işaret eder. Bu işaretler zinciri, projenin tarihini oluşturur.

**tag (annotated):** Belirli bir commit'e kalıcı, açıklamalı bir isim verir. Genellikle sürüm işaretlemek için kullanılır (`v1.0.0`), yazar ve mesaj bilgisi taşır.

### En büyük kavram yanılgısı: Git "diff" saklamaz, "snapshot" saklar

Çoğu insan Git'i, her commit'te "değişiklikleri" (diff) saklayan bir sistem olarak hayal eder. Bu **yanlıştır** ve bu yanılgı, ileride merge/rebase davranışlarını kafa karıştırıcı kılar. Git, her commit'te projenin **tam bir anlık görüntüsünü** (tam tree'yi) saklar. Değişmeyen dosyalar için yeni blob yaratmaz, önceki blob'u yeniden işaret eder; ama kavramsal olarak her commit, o andaki dünyanın tam halidir.

Peki `git diff` veya `git log -p` nasıl değişiklik gösteriyor? Git, iki snapshot arasındaki farkı **istendiğinde, o an** hesaplar. Yani diff, saklanan bir veri değil, iki tam durumun karşılaştırılmasından türetilen bir çıktıdır. Bu ayrım hayati: Git tarihini, "yamalar zinciri" değil, "snapshot'lar zinciri" olarak düşünmelisiniz. Cherry-pick, rebase ve merge'ün nasıl çalıştığı ancak bu zihinsel modelle netleşir.

### Referanslar: branch, HEAD ve etiketler

Yukarıdaki dört nesne "değişmez" dünyadır. Ama biz her gün branch'lerde çalışıp ilerliyoruz. İşte burada **ref** (referans) kavramı devreye girer. Bir branch, aslında **bir commit hash'ini işaret eden basit bir metin dosyasından** ibarettir. `.git/refs/heads/main` dosyasını açarsanız, içinde sadece 40 karakterlik bir hash görürsünüz. Yani "main branch'i" dediğimiz şey, bir commit'e işaret eden hareketli bir işaretçidir.

`HEAD` ise "şu an neredeyim" sorusunun cevabıdır. Normalde HEAD, bir branch'i işaret eder (`.git/HEAD` içinde `ref: refs/heads/main` yazar). Yeni bir commit attığınızda olan biten şudur: yeni commit nesnesi yaratılır, parent'ı eski commit olur, ve HEAD'in işaret ettiği branch **ileri kaydırılır** (yeni commit'i işaret eder). Yani commit atmak, "branch işaretçisini bir sonraki snapshot'a ilerletmektir".

Bu model, **detached HEAD** durumunu da açıklar. Eğer HEAD bir branch yerine doğrudan bir commit hash'ini işaret ederse, "detached" (kopmuş) haldesinizdir. Burada commit atabilirsiniz ama hiçbir branch ilerlemediği için, başka bir branch'e geçtiğinizde bu commit'ler "sahipsiz" kalır. Bu tehlikeli görünür ama aslında kaybolmazlar; bunu kurtarma bölümünde göreceğiz.

## Merge ve Rebase: İki Farklı Tarih Felsefesi

Branch'leri birleştirmenin iki temel yolu vardır ve aralarındaki fark, teknik olmaktan çok **felsefidir**: "Tarih gerçekte ne oldu?" mu yoksa "Tarih okunması kolay bir hikâye mi olmalı?"

### Merge nasıl çalışır

`git merge`, iki branch'in tarihini **birleştiren yeni bir commit** yaratır. Bu birleştirme commit'inin özelliği, **iki parent'ının** olmasıdır: birleştirdiğiniz her iki branch'in de son commit'i. Böylece tarih bir grafik (DAG - directed acyclic graph) olarak, çatallanıp tekrar birleşen bir yapıya kavuşur.

Git birleştirmeyi yaparken genellikle **three-way merge** (üç yönlü birleştirme) kullanır. Sadece iki branch'in son hallerine bakmaz; ayrıca ikisinin **ortak atası** olan commit'i (merge base) de bulur. Neden üç nokta? Çünkü bir dosya iki tarafta da farklıysa, "hangi taraf değiştirdi?" sorusunun cevabı ortak ataya bakmadan verilemez. Ortak ata "A" diyorsa, bir taraf "B" yaptıysa ama diğer taraf hiç dokunmadıysa (hâlâ "A"), Git güvenle "B"yi seçer. Ama iki taraf da ortak atadan farklı, birbirinden de farklı bir şey yaptıysa, işte o zaman **conflict** (çatışma) oluşur ve insan kararı gerekir.

**Fast-forward** özel bir durumdur. Eğer hedef branch, sizin branch'inizin doğrudan atasıysa (arada çatallanma yoksa), Git yeni bir merge commit'i yaratmaya gerek duymaz; sadece branch işaretçisini ileri kaydırır. Tarihte hiçbir çatal görünmez. Bu bazen istediğiniz şeydir, bazen değil; `--no-ff` ile fast-forward'ı engelleyip her zaman bir merge commit'i yaratmaya zorlayabilirsiniz; böylece "burada bir branch birleşti" bilgisi tarihte kalıcı olur.

### Rebase nasıl çalışır

`git rebase`, bambaşka bir şey yapar. Branch'inizdeki commit'leri alır, sanki **başka bir noktadan dallanmışlar gibi yeniden oynatır** (replay eder). "Rebase" kelimesi tam olarak bunu anlatır: branch'inizin *temelini* (base) değiştirmek.

Somut olarak: `feature` branch'inizde 3 commit var ve `main` bu sırada ilerledi. `git rebase main` dediğinizde Git şunu yapar: sizin 3 commit'inizin her birini birer birer alır, `main`'in yeni ucuna **sırayla yeniden uygular**. Kritik nokta şudur: bu yeni commit'ler, orijinallerin **birebir kopyası değildir**. Parent'ları değişti, dolayısıyla içerikleri değişti, dolayısıyla **hash'leri değişti**. Yani rebase, eski commit'lerinizi atıp, aynı değişikliği içeren *yepyeni* commit'ler yaratır. Eski commit'ler bir süre `reflog`'da yaşamaya devam eder ama tarih artık onları işaret etmez.

Sonuç: rebase sonrası tarih **düz bir çizgidir**. Çatal yoktur, merge commit'i yoktur. Sanki siz baştan beri `main`'in en güncel halinin üzerinde çalışmışsınız gibi görünür.

### Hangisi ne zaman, ve tehlikeli tuzak

Fark şuraya iner:

**Merge** gerçeği korur. "Bu iki branch şu tarihte, şu noktada gerçekten birleşti" bilgisini tarihe yazar. Dezavantajı, çok sayıda branch ve merge ile tarihin "spagetti"ye dönüp okunmasının zorlaşmasıdır.

**Rebase** hikâyeyi güzelleştirir. Tarihi lineer, okunabilir, `git bisect` ile hata avlamaya uygun bir hale getirir. Dezavantajı, tarihi **yeniden yazmasıdır**.

Buradaki **altın kural**, Git'in en önemli emniyet kurallarından biridir: **Başkalarıyla paylaştığınız (push ettiğiniz) commit'leri asla rebase etmeyin.** Neden? Çünkü rebase yeni hash'ler yaratır. Siz eski commit'leri yeni hash'lerle değiştirdiğinizde, o eski commit'lere sahip olan meslektaşınızın deposu ile sizinki çelişir. Herkes aynı değişikliğin iki farklı versiyonuna sahip olur; birleştirmeye çalışıldığında tarih çift görünür, çatışmalar birikir ve büyük bir karmaşa doğar. Rebase, **kendi lokal, henüz paylaşılmamış** çalışmanızı temizlemek için mükemmeldir; ortak tarihi değiştirmek için felakettir.

### Interactive rebase: tarihinizi düzenlemek

`git rebase -i` (interactive), rebase'in en güçlü biçimidir. Commit'lerinizi paylaşmadan önce: birleştirebilir (squash), yeniden sıralayabilir, mesajlarını düzeltebilir (reword), silebilir (drop) veya bölebilirsiniz. "10 tane deneme-yanılma commit'ini tek anlamlı commit'e indirgemek" tam olarak bunun işidir. Yine aynı kural geçerlidir: sadece henüz kimseyle paylaşmadığınız commit'lerde yapın.

## Branch Akışı: Dallanma Stratejileri

Branch'in "ucuz bir işaretçi" olduğunu anladıysak, dallanmanın neden bu kadar teşvik edildiği de netleşir: Git'te branch yaratmak, birkaç bayt yazmaktan ibarettir. Asıl mesele, **ekip olarak hangi akışı benimsediğinizdir**.

### Neden dallanma stratejisine ihtiyaç var

Teknik olarak istediğiniz gibi dallanabilirsiniz. Ama bir ekipte tutarlı bir strateji olmazsa: hangi branch'in "canlıda çalışan kod" olduğu belirsizleşir, sürüm çıkarmak kâbusa döner, ve "acil düzeltmeyi (hotfix) nereye atacağız?" sorusu her seferinde tartışma konusu olur. Strateji, bu soruların cevabını önceden vererek kaosu önler.

### Yaygın modeller ve mantıkları

**Trunk-based development (tek gövde odaklı):** Herkes `main` (trunk) üzerinde çalışır veya çok kısa ömürlü branch'ler açıp hızlıca birleştirir. Amaç, branch'lerin günlerce/haftalarca uzaklaşıp devasa çatışmalar yaratmasını önlemektir. Continuous integration (sürekli entegrasyon) ve güçlü otomatik test kültürü olan ekipler için idealdir; çünkü küçük ve sık birleştirme, "integration hell" (birleştirme cehennemi) denen ertelenmiş çatışma yığınını ortadan kaldırır.

**GitHub Flow (basit feature-branch):** `main` her zaman dağıtılabilir (deployable) kabul edilir. Her iş için `main`'den bir feature branch açılır, iş bitince pull request ile gözden geçirilip `main`'e birleştirilir ve dağıtılır. Sadeliği ve modern CI/CD ile uyumu nedeniyle en yaygın modellerden biridir.

**Git Flow:** `main` ve `develop` gibi kalıcı branch'ler, ayrıca `feature/`, `release/`, `hotfix/` gibi geçici branch'ler içeren, daha yapılandırılmış bir modeldir. Belirli sürümler halinde çıkan (ör. masaüstü uygulaması, gömülü yazılım) ürünler için düzen sağlar. Ancak sürekli dağıtım yapan web servisleri için genellikle **gereğinden fazla karmaşıktır**; sürekli teslimat çağında birçok ekip bunu bilinçli olarak terk etmiştir. "Popüler diye" seçmek yerine, ürününüzün sürüm ritmine bakmalısınız.

Önemli bir dürüstlük notu: "En iyi model" diye evrensel bir cevap yoktur. Doğru seçim, ekibin büyüklüğüne, dağıtım sıklığına ve test otomasyonu olgunluğuna bağlıdır. Sürekli dağıtan, güçlü testleri olan bir ekip için trunk-based; ayrık sürümler çıkaran bir ürün için Git Flow türü bir yapı daha mantıklı olabilir.

## Kurtarma: "Her Şey Mahvoldu" Anları

Git'in en az anlaşılan ama en rahatlatıcı yönü şudur: **Git'te bir şeyi gerçekten kaybetmek şaşırtıcı derecede zordur.** Nesne modelini hatırlayın: commit'ler içerik-adresli nesnelerdir ve bir kez yaratıldıklarında, bir yerden işaret edildikleri sürece (veya son işaretlenmelerinin üzerinden garbage collection süresi geçmediği sürece) veritabanında dururlar. Sizin "sildiğiniz" şey genellikle commit'in kendisi değil, ona giden **işaretçidir**.

### reflog: gizli güvenlik ağı

`git reflog`, kurtarmanın en güçlü aracıdır ve çoğu geliştirici varlığından habersizdir. Reflog, **HEAD'inizin ve branch'lerinizin zaman içinde nereleri işaret ettiğinin lokal bir günlüğüdür.** Her checkout, commit, merge, rebase, reset işlemi buraya bir satır düşer.

Kritik olan şudur: Bir commit'i "kaybettiğinizde" (yanlış bir `reset --hard`, kötü bir rebase, silinen bir branch), o commit'in hash'i hâlâ reflog'da durur. `git reflog` çalıştırıp o hash'i bulur, ardından o hash'e bir branch yaratarak (`git branch kurtarma <hash>`) veya `git reset` ile geri dönerek çalışmanızı geri alırsınız. Detached HEAD'de attığınız "sahipsiz" commit'ler de bu şekilde geri gelir. Reflog, "geri alınamaz" sandığınız pek çok işlemi geri alınabilir kılar.

Önemli sınır: reflog **lokaldir ve süreye tabidir**. Sizin bilgisayarınızdaki hikâyedir; başka birinin deposunda yoktur. Ayrıca ulaşılamaz hale gelen nesneler, garbage collection sonrasında (varsayılan olarak epeyce bir süre sonra) gerçekten temizlenebilir. Yani kaza fark edilir edilmez kurtarmaya girişmek en güvenlisidir.

### reset türlerini anlamak

`git reset`, en çok kafa karıştıran ama kurtarmada en kritik komuttur. Üç modu, üç farklı "katmanı" etkiler:

- **`--soft`:** Sadece branch işaretçisini geriye taşır. Değişiklikleriniz staging area'da (index) durmaya devam eder. Commit'i "geri açıp" yeniden düzenlemek için idealdir.
- **`--mixed` (varsayılan):** İşaretçiyi geriye taşır ve staging'i temizler, ama çalışma dizinindeki (working directory) dosyalarınıza dokunmaz. Değişiklikleriniz "unstaged" hale gelir ama kaybolmaz.
- **`--hard`:** İşaretçiyi geriye taşır **ve** staging'i **ve** çalışma dizinini o noktaya zorlar. İşte veri kaybı riski buradadır: henüz commit'lenmemiş çalışmanız bu modda gerçekten gider (çünkü hiçbir nesneye bağlanmamıştı). Commit'lenmiş olanlar reflog'da bulunabilir, ama commit'lenmemiş olanlar bulunamaz. Bu yüzden `--hard`'ı her zaman iki kez düşünerek kullanın.

### revert ve reset arasındaki felsefi fark

`git revert`, `git reset`in **paylaşılan tarih için güvenli** karşılığıdır ve ikisini karıştırmak yaygın bir hatadır. `reset` tarihi geriye alır (işaretçiyi geri taşır, tarihi yeniden yazar). `revert` ise tarihi geriye almaz; bunun yerine, istenmeyen commit'in **etkisini tersine çeviren yeni bir commit** yaratır. Yani tarihte "hatalı commit" de, "onu geri alan commit" de birlikte görünür.

Neden bu fark önemli? Çünkü zaten push edilmiş, herkesin sahip olduğu bir commit'i `reset` ile silmeye çalışmak, rebase'deki aynı felakettir: yeni hash'ler, çelişen depolar. Ama `revert` yeni bir commit eklediği için hiçbir tarihi yeniden yazmaz; herkes onu sorunsuz çeker. **Kural:** Henüz paylaşılmamış lokal hatalarda `reset`, halihazırda paylaşılmış hatalarda `revert`.

### Diğer kurtarma araçları

**`git stash`:** Yarım kalmış çalışmanızı geçici olarak bir kenara koyar; branch değiştirmeniz gerektiğinde ama commit atmaya hazır olmadığınızda kullanışlıdır. Ancak stash'lerin uzun süre birikmesi ve unutulması yaygın bir tuzaktır; kalıcı bir depolama yeri değildir.

**`git cherry-pick`:** Belirli bir commit'i (veya birkaçını), bulunduğu branch'ten alıp, bulunduğunuz branch'e "aynı değişikliği yeni bir commit olarak uygulayarak" taşır. Bir hotfix'i sadece belirli bir sürüm branch'ine taşımak için idealdir. Rebase gibi, o da yeni hash'li yeni commit yaratır.

**`git fsck` ve dangling nesneler:** Reflog bile bir commit'i göstermiyorsa, `git fsck` ile veritabanındaki "dangling" (hiçbir yerden işaret edilmeyen) nesneleri tarayabilirsiniz. Bu, son çare niteliğinde derin bir kurtarma yoludur.

## Yaygın Hatalar ve En İyi Pratikler

**Hata: Force push'u körlemesine kullanmak.** `git push --force`, uzaktaki branch'i sizinkiyle zorla değiştirir ve bu sırada meslektaşınızın push ettiği ama sizde olmayan commit'leri **yok edebilir**. Bunun yerine `--force-with-lease` kullanın; bu bayrak, "uzaktaki branch hâlâ benim beklediğim yerde mi?" diye kontrol eder, birileri araya girmişse push'u reddeder. Force gerektiğinde bile "kira ile" yapmak, körlemesine ezmekten çok daha güvenlidir.

**Hata: Devasa, çok amaçlı commit'ler.** "Bir sürü şeyi düzelttim" diyen tek bir dev commit; `git bisect` ile hata avlamayı, `git revert` ile seçici geri almayı ve kod incelemesini neredeyse imkânsız kılar. **Pratik:** Her commit tek bir mantıksal değişikliği kapsasın; tarihi, iyi yazılmış bir hikâye gibi düşünün.

**Hata: Anlamsız commit mesajları.** "fix", "asdf", "son deneme" gibi mesajlar, altı ay sonra tarihi okunamaz kılar. **Pratik:** Kısa ve emir kipinde bir özet satırı (ör. "Login formunda null kontrolü ekle"), gerekiyorsa boş satır ve ardından *neden* yaptığınızı açıklayan bir gövde. "Ne yaptığın" zaten diff'te var; asıl değerli olan "neden"dir.

**Hata: Conflict'i anlamadan kapatmak.** Çatışma işaretlerini (`<<<<<<<`, `=======`, `>>>>>>>`) gördüğünde panikleyip bir tarafı rastgele silmek, sessiz hatalara yol açar. **Pratik:** Çatışma, "Git iki niyeti otomatik uzlaştıramadı, insan kararı istiyor" demektir. İki tarafın da ne yapmaya çalıştığını anlayıp bilinçli birleştirin; sonra mutlaka test edin.

**Hata: Sırları (secret) commit'lemek.** Bir API anahtarını yanlışlıkla commit'leyip push ettiğinizde, onu sonraki bir commit'te silmek **yeterli değildir**; anahtar tarihte hâlâ durur ve çekebilen herkes görebilir. **Pratik:** Anahtarı derhal geçersiz kılıp (rotate) yenisini üretin; tarihi temizlemek ise ayrı ve zahmetli bir iştir. En iyisi, `.gitignore` ve sır tarama araçlarıyla bunu en baştan önlemektir.

**Pratik: `.gitignore`'u ciddiye alın.** Derleme çıktıları, bağımlılık klasörleri, IDE ayarları ve ortam dosyaları tarihe girmemelidir. Bir kez izlenmeye başlamış (tracked) bir dosyayı `.gitignore`'a eklemek onu takipten çıkarmaz; ayrıca `git rm --cached` gerekir.

**Pratik: Pull ederken merge mi rebase mi?** `git pull` varsayılan olarak fetch + merge yapar ve bu, yerel tarihinize sık sık küçük merge commit'leri ekleyerek onu kirletebilir. Birçok ekip, lokal branch'i güncellerken lineer tarih için `pull --rebase` tercih eder. Yine de kural aynı: rebase yalnızca henüz paylaşmadığınız lokal commit'lerde güvenlidir.

## Kapanış: Tek Bir Zihinsel Model

Bu makale boyunca dört nesne (blob, tree, commit, tag), hareketli işaretçiler (branch, HEAD) ve içerik-adresli değişmezlik temasına tekrar tekrar döndük. Bunun sebebi şudur: Git'in görünürdeki bütün karmaşıklığı, bu tek modelden türer.

Merge, iki işaretçiyi iki parent'lı yeni bir snapshot'ta birleştirmektir. Rebase, commit'leri yeni bir temel üzerinde yeni hash'lerle yeniden yaratmaktır. Detached HEAD, işaretçinin branch yerine doğrudan bir commit'e bakmasıdır. Kurtarma, "silinen commit aslında hâlâ orada, sadece işaretçisi gitti" gerçeğinden ibarettir. `reset` işaretçiyi oynatır, `revert` yeni commit ekler, `reflog` işaretçilerin geçmişini hatırlar.

Bir sonraki sefer Git sizi şaşırttığında, komut aramadan önce şunu sorun: "Şu an hangi nesneler var, hangi işaretçi nereyi gösteriyor, ve bu komut hangi işaretçiyi nasıl oynatacak?" Bu soruyu cevaplayabildiğiniz anda, Git artık ezberlenen bir araç değil, anlaşılan bir sistem olur.
