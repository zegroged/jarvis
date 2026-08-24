# Kalite Kapısı / CI Yargısı (Lint, Coverage ve Ötesi)

## 1. Problem ve bağlam: kapı neyi çözer, ne zaman devreye girer

Kalite kapısı (quality gate), bir değişikliğin ana dala (main/trunk) veya bir sürüme
girmeden önce otomatik olarak geçmesi gereken eşiklerin toplamıdır. Lint, format
kontrolü, test coverage yüzdesi, statik analiz (SAST), tip kontrolü, bağımlılık
zafiyet taraması, build'in derlenmesi... hepsi birer "kapı çubuğu"dur. CI (Continuous
Integration) bu çubukları her push veya her pull request'te otomatik çalıştırır ve
"yeşil/kırmızı" bir yargıya bağlar.

Kapının çözdüğü asıl problem teknik değil, **sosyal**dir. On kişilik bir ekipte herkes
"iyi kod yazmaya çalışırım" dese bile, insanların dikkat seviyesi, uykusuzluğu, deadline
baskısı ve deneyimi farklıdır. Kapı, "insanın iyi niyetine" değil, "makinenin
tutarlılığına" dayanan bir alt sınır çizer. Cuma akşamı saat 19:00'da yorgun bir
geliştiricinin gözünden kaçan şeyi, kapı gözden kaçırmaz. Bu yüzden kapının gerçek
değeri, en iyi gününüzde değil, **en kötü gününüzde** ortaya çıkar.

Kapı ne zaman devreye girer? Klasik olarak üç noktada:
- **Pre-commit / pre-push (yerel):** Geliştiricinin makinesinde, commit'ten hemen önce.
  En hızlı geri bildirim, ama atlanabilir (`--no-verify`).
- **PR/CI (merkezi):** Pull request açıldığında sunucuda. Atlanamaz, ekibin gerçek kapısı.
- **Release / deploy öncesi:** Sürüm etiketlenmeden ya da prod'a çıkmadan önceki son savunma.

Acemi ekiplerde tek bir yer vardır (genelde CI) ve o da ya çok gevşek ya da çok
katıdır. Olgun ekiplerde kapı **katmanlıdır**: ucuz ve hızlı kontroller yerelde,
pahalı ve yavaş kontroller merkezde çalışır. Bu katmanlama, bu metnin en önemli
fikirlerinden biridir ve ilerledikçe açacağım.

## 2. Metodoloji ve karar ağacı (asıl değer)

### 2.1. Temel ilke: kapı bir "sinyal", ceza değildir

Kıdemsiz mühendis kapıyı bir polis gibi görür: "beni yakalayan, yolumu tıkayan şey".
Kıdemli mühendis kapıyı bir **sinyal kaynağı** olarak görür. Her kırmızı kapının sorduğu
soru şudur: "Bu sinyal gerçek bir riski mi gösteriyor, yoksa gürültü mü?" Kapı
tasarımının tüm sanatı **sinyal/gürültü oranını yükseltmektir**. Sürekli yanlış alarm
veren bir kapı, ekibin öğrenilmiş çaresizlikle her şeyi override etmesine yol açar; bu
da kapının hiç olmamasından beterdir, çünkü artık yeşil rengin anlamı kalmamıştır.

Bu yüzden ilk karar kuralım: **Bir kapı çubuğu eklemeden önce sor — bu kural ihlal
edildiğinde gerçekten bir şey mi patlar, yoksa sadece benim estetik tercihim mi?**
Estetik tercihler `warning` olur, gerçek riskler `error` olur. İkisini karıştırmak,
kapının güvenilirliğini yok eder.

### 2.2. Hız/katılık takası ve katman kararı

Bir kontrol ekleyeceğim. Nereye koyacağıma nasıl karar veririm? Karar ağacım:

1. **Bu kontrol milisaniye-saniye mi sürüyor, yoksa dakikalar mı?** Hızlıysa (format,
   lint, tip kontrolü) yerele **de** koy — geliştirici anında görsün. Yavaşsa
   (entegrasyon testleri, e2e, güvenlik taraması) sadece CI'da çalışsın.
2. **Deterministik mi?** Aynı girdiye her zaman aynı çıktıyı veriyor mu? Deterministik
   değilse (flaky test, ağ bağımlısı kontrol) bunu **bloke edici kapı yapma** — rapor
   et ama merge'ü durdurma, yoksa insanlar sebepsiz yere "retry" tuşuna basmayı öğrenir.
3. **False positive maliyeti mi yüksek, false negative maliyeti mi?** Güvenlik ve veri
   bütünlüğü konularında false negative (kaçırmak) pahalıdır, biraz gürültüye katlanırım.
   Stil konularında false positive (boşuna engellemek) pahalıdır, gevşek tutarım.

Belirti → yön eşlemem şöyle işler:
- **"CI 25 dakika sürüyor, kimse PR açmak istemiyor"** → Kapıyı katmanlara böl,
  paralelleştir, en olası hatayı en başa al (fail-fast). Lint 30 saniyede patlıyorsa,
  20 dakikalık e2e'yi beklemeden geliştiriciyi uyar.
- **"Coverage %80'in altına düştü diye acil bir hotfix'i merge edemiyoruz"** → Kapı,
  acil durumda esneyebilmeli. Ya patch-level coverage (sadece değişen satırlar) ölç,
  ya da denetlenebilir bir override mekanizması koy.
- **"Herkes lint'i geçiyor ama kod hâlâ berbat"** → Lint yanlış şeyi ölçüyor. Lint stili
  ölçer, tasarımı ölçmez. Buraya statik analiz/karmaşıklık metriği ekle, ama önce insan
  code review'ini güçlendir; lint code review'in yerini tutmaz.

### 2.3. Coverage konusundaki en kritik yargı: sayı yalan söyler

Kıdemli mühendisin en çok tekrarladığı gerçek: **coverage yüzdesi bir kalite ölçüsü
değil, bir kapsam ölçüsüdür.** %90 coverage, kodun %90'ının bir test tarafından
"çalıştırıldığını" söyler — o testin bir şeyi **doğruladığını** söylemez. `assert`
içermeyen, sadece fonksiyonu çağırıp sonucu görmezden gelen bir test coverage'ı
yükseltir ama sıfır güvence verir.

Bu yüzden coverage kapısıyla ilgili yargılarım:
- **Toplam coverage yüzdesine değil, patch/diff coverage'a bak.** "Bu PR'da eklediğin
  yeni satırların ne kadarı test edildi?" sorusu, "tüm kod tabanının ne kadarı test
  edildi?" sorusundan çok daha anlamlıdır ve adildir. Yeni gelen kişi, on yıllık test
  borcunu ödemek zorunda kalmaz; sadece kendi eklediğinden sorumludur.
- **Eşiği %100 yapma.** %100 coverage hedefi, insanları anlamsız testler yazmaya ve
  `// coverage:ignore` etiketleri serpiştirmeye iter. %70-85 bandı çoğu ürün kodu için
  sağlıklıdır; kritik ödeme/güvenlik modüllerinde daha yüksek tutulabilir.
- **Coverage düşüşünü engelle, mutlak sayıyı kovalama.** "Bu PR coverage'ı düşürüyorsa
  uyar" kuralı, "coverage %85 olmalı" kuralından daha yaşayabilirdir.

### 2.4. Kapının override edilebilirliği: denetlenebilir kaçış

Mutlak kural: **her kapının denetlenebilir bir kaçış yolu olmalı, ama kaçış iz
bırakmalı.** Prod yanıyorken coverage %0.5 düştü diye hotfix'i durduran bir kapı,
kapının kendisine olan güveni yok eder. Ama kaçış sessiz olmamalı: kim, ne zaman,
neden override etti — bu git geçmişinde ya da PR yorumunda kalmalı. "Break glass"
mekanizması: kırılır ama kırıldığı görülür.

## 3. Gerçek kod üzerinden yürüyüş: bozuk kapıdan sağlam kapıya

Somut bir senaryo kuralım. Bir ekip, coverage kapısını "hızlıca" kurmuş. İşte gerçekte
çok sık gördüğüm zafiyetli konfigürasyon (dil-bağımsız pseudocode olarak, ama gerçek
araçların davranışıyla birebir):

**Aşama 1 — Zafiyetli kurulum:**

```yaml
# CI pipeline (bozuk hali)
test-job:
  script:
    - run_tests --coverage
    - check_coverage --min 80   # toplam coverage %80 olmalı
  allow_failure: false
```

Ve test dosyasında şu tarz bir "test":

```
test("kullanıcı oluşturma çalışıyor", () => {
  createUser({ name: "Ali", email: "ali@x.com" })
  // assert yok! sadece çağırdık, patlamadıysa "geçti" sayılıyor
})
```

**Teşhis — ne yanlış?**

1. **Toplam coverage eşiği adaletsiz ve manipüle edilebilir.** Kod tabanı büyüdükçe,
   iyi test edilmiş kocaman bir çekirdek, yeni eklenen test edilmemiş kodu maskeler.
   Birisi 500 satır test edilmemiş kod ekler ama toplam yüzde sadece %79.6'ya düşer,
   %80'in altına inmezse kapı yeşil kalır. Risk tam da yeni koddadır ve kapı onu görmez.

2. **assert'siz test, coverage'ı şişirir ama hiçbir şey doğrulamaz.** `createUser`
   satırları "çalıştırıldı" sayılır, coverage yükselir, ama fonksiyon yanlış e-posta
   kaydetse bile test yeşil kalır. Bu, en tehlikeli yanlış güven kaynağıdır.

3. **`check_coverage` job'ı testlerden sonra, ayrı bir adımda.** Testler yavaşsa,
   geliştirici coverage sonucunu ancak 15 dakika sonra görür. Geri bildirim döngüsü
   çok uzun.

4. **Flaky testler bu kapıyı çürütür.** Zaman aşımına düşen tek bir ağ testi, tüm
   PR'ı kırmızıya boyar; ekip "retry" basmayı öğrenir; retry alışkanlığı gerçek
   hataları da görünmez kılar.

**Aşama 2 — Düzeltilmiş kurulum:**

```yaml
# CI pipeline (sağlam hali)
stages: [fast-checks, test, quality]

lint-and-types:          # saniyeler sürer, en başta patlar (fail-fast)
  stage: fast-checks
  script:
    - run_formatter --check      # format bozuksa hemen dur
    - run_linter --max-warnings 0
    - run_typecheck

unit-tests:
  stage: test
  script:
    - run_tests --coverage --coverage-report=diff
  # flaky testler ayrı işaretlenir, bloke etmez ama raporlanır
  retry:
    max: 1
    when: [runner_system_failure]   # sadece altyapı hatasında, test hatasında DEĞİL

diff-coverage-gate:
  stage: quality
  script:
    # SADECE bu PR'da değişen satırların coverage'ına bak
    - check_diff_coverage --min 85 --against origin/main
  # break-glass: etiketle override edilebilir, ama iz kalır
  allow_failure: false
```

Ve test artık gerçekten bir şey doğruluyor:

```
test("createUser geçerli e-postayı normalize edip kaydeder", () => {
  const user = createUser({ name: "Ali", email: "  ALI@X.COM " })
  assert(user.email === "ali@x.com")   // trim + lowercase doğrulandı
  assert(user.id != null)              // id atandı
  assert(db.find(user.id).name === "Ali")  // gerçekten kaydedildi
})

test("createUser geçersiz e-postayı reddeder", () => {
  assertThrows(() => createUser({ name: "Ali", email: "ali-at-x" }))
})
```

**Ne değişti ve neden önemli?**

- **Diff coverage:** Kapı artık "kod tabanının tamamı" değil, "senin dokunduğun
  satırlar" üzerinden yargılıyor. Bu hem adil (eski borç yeni geliştiriciye yıkılmıyor)
  hem de etkili (risk yeni kodda, kapı da oraya bakıyor).

- **Fail-fast sıralama:** Lint ve tip kontrolü ilk stage'de. Format hatası varsa,
  10 dakikalık testleri hiç çalıştırmadan geliştirici 20 saniyede uyarılıyor. CI
  dakikaları ve insan sabrı boşa harcanmıyor.

- **Anlamlı assert'ler:** Testler artık davranışı doğruluyor. Coverage sayısı artık
  "çalıştırıldı" değil, gerçekten "doğrulandı" anlamına yaklaşıyor. Mutation testing
  (bkz. bölüm 5) ile bunu daha da sertleştirebilirim.

- **Retry politikası cerrahi:** Sadece altyapı hatasında retry var; test mantık
  hatasında retry **yok**. Bu ayrım kritik: flaky altyapıyı tolere ediyoruz ama flaky
  test mantığını gizlemiyoruz, onu görünür kılıp düzeltmeye zorluyoruz.

### Bir başka gerçek tuzak: lint kuralının yanlış katmanda olması

Diyelim ekip "console.log/print production'a sızmasın" kuralını lint'e ekledi. Ama
kuralı `warning` yaptılar. Sonuç: uyarılar birikti, 400 tane oldu, kimse okumuyor,
gerçekten kritik bir uyarı 399 gürültünün arasında kayboldu. Düzeltme:
`--max-warnings 0` — ya uyarı yok, ya kapı kırmızı. Bir kural varsa uygulanır; yoksa
silinir. **"İzlenmeyen uyarı" en kötü durumdur**; ya error yap ya da tamamen kaldır.

## 4. Acemi vs pro: tuzaklar ve gözden kaçanlar

**Acemi: "Coverage %100 olsun, en güvenlisi bu."**
Pro: %100 coverage, testlerin kaliteli olduğunu değil, insanların ignore etiketi
serpiştirmekte ustalaştığını gösterir. %100 hedefi, `getter/setter` ve trivial kodu
test etmek için harcanan zamanı, gerçek edge-case'leri test etmekten çalar. Pro,
kritik yolları %95, gerisini %70 tutar ve enerjiyi doğru yere kanalize eder.

**Acemi: "CI yeşilse kod güvenli demektir."**
Pro: Yeşil CI, "bildiğimiz kontrollerin hiçbiri patlamadı" demektir — "kod doğru"
demek değil. CI, yazdığın testlerin kalitesi kadar iyidir. Boş assert'li testlerle
dolu yeşil bir CI, tehlikeli bir yalancı güvendir. Pro yeşile güvenir ama tapmaz.

**Acemi: bütün kontrolleri bloke edici (blocking) yapar.**
Pro: Bloke edici kapı ile bilgilendirici (informational) raporu ayırır. Deterministik,
yüksek sinyalli kontroller bloke eder (derleme, tip, kritik testler). Gürültülü,
olgunlaşmamış kontroller (yeni eklenen bir güvenlik tarayıcısı, kod karmaşıklığı
metriği) önce **rapor** olarak çalışır; ekip birkaç hafta sinyal kalitesini gözlemler,
sonra bloke ediciye terfi ettirir. Yeni bir kapıyı gün 1'de blocking yapmak, ekibin
ona olan güvenini daha doğmadan öldürür.

**Acemi: flaky testi "retry" ile geçiştirir.**
Pro: Flaky test, kapının kanserdir. Her retry, ekibi kırmızı rengin "muhtemelen
yalandır, tekrar bas" demek olduğuna alıştırır. Bir kez bu alışkanlık yerleşince,
**gerçek** bir regresyon da retry'la geçiştirilir ve prod'a sızar. Pro, flaky testi
ya derhal quarantine (karantina) eder — bloke etmeyen ayrı bir kovaya alır ve bilet
açar — ya da siler. Flaky test, testin yokluğundan daha tehlikelidir çünkü sinyali
zehirler.

**Acemi: lint kurallarını maksimuma açar, "ne kadar çok o kadar iyi".**
Pro: Aşırı katı lint, geliştiricileri `// eslint-disable` / `# noqa` / `//nolint`
serpiştirmeye iter. Her disable yorumu, kapının etrafından dolanan bir tüneldir. Pro,
az sayıda ama gerçekten önemli kuralı **istisnasız** uygular; bir kuralı sürekli
disable ediyorsak, ya kural yanlıştır ya da bir tasarım sorununu maskeliyoruzdur —
ikisi de araştırılmalıdır.

**"İşe yarar gibi görünüp prod'da patlayan" klasik tuzak:**
Lokal makinede geçen, CI'da geçen ama prod'da patlayan kod. Neden? Çünkü kapı
**ortam farkını** ölçmüyordu. CI, testleri temiz bir veritabanı ve seed data ile
çalıştırıyordu; prod'da ise migration sırası farklıydı ve bir kolon henüz yoktu.
Kapı "kod doğru mu" sorusunu yanıtladı ama "bu kod bu ortama güvenle gider mi"
sorusunu yanıtlamadı. Pro, kapıya migration/şema uyumluluk kontrolü ve
staging'de smoke test ekler; birim test coverage'ı bu boşluğu asla kapatmaz.

**Gözden kaçan: test süresi kapının kendisini çürütür.**
15+ dakikalık CI, geliştiricileri PR'ları büyük ve seyrek yapmaya iter (çünkü her PR
pahalı). Büyük PR'lar da review'i zorlaştırır, hata riskini artırır. Yani yavaş kapı,
dolaylı yoldan kalitesizliği besler. Pro, CI süresini bir kalite metriği olarak izler;
"p95 CI süresi 10 dakikayı geçince optimize et" gibi bir bütçe koyar.

**Gözden kaçan: bağımlılık ve tedarik zinciri kapısı.**
Acemi coverage ve lint'e odaklanır, ama modern sistemlerde en büyük risk çoğu zaman
üçüncü parti bağımlılıklardır. Bilinen zafiyetli bir kütüphane sürümü, senin
%95 coverage'ının hiç dokunmadığı bir yerden sistemi çökertebilir. Pro, kapıya
bağımlılık zafiyet taraması (dependency audit) ve lockfile bütünlük kontrolü ekler.

## 5. Araçlar ve saha notları

**Format ve lint:**
Format kontrolünü (prettier, gofmt, black, rustfmt gibi deterministik formatlayıcılar)
lint'ten **ayrı** tut ve her zaman `--check` modunda çalıştır. Formatı tartışma
konusu olmaktan çıkarır — makine karar verir, code review'de kimse boşluk/girinti
tartışmaz. Lint (eslint, ruff, golangci-lint, clippy) ise mantıksal/stilistik kuralları
uygular; `--max-warnings 0` ile çalıştır ki "uyarı çöplüğü" oluşmasın.

**Coverage araçları:**
Coverage üreten aracın (dilin standart coverage aracı) çıktısını, bir **diff coverage**
katmanıyla birleştir. Diff coverage, PR'da değişen satırları git diff'ten okuyup sadece
onları raporlar — kapının adil ve etkili olmasının anahtarı budur. Toplam coverage'ı
bir dashboard'da **trend** olarak izle (zamanla düşüyor mu?), ama merge kapısı olarak
diff coverage kullan.

**Mutation testing — coverage'ın yalanını yakalayan araç:**
Coverage "satır çalıştırıldı mı" der; mutation testing "test bu satırdaki bir hatayı
yakalar mı" diye sorar. Kodda küçük değişiklikler (mutasyonlar) yapar — `>` yerine
`>=`, `+` yerine `-` — ve testlerin bu bozulmayı yakalayıp yakalamadığını ölçer.
Testleriniz bu mutasyonu "öldüremiyorsa", o test aslında bir şeyi doğrulamıyordur.
Mutation testing yavaştır, bu yüzden onu her PR kapısı yapma; kritik modüllerde
haftalık/nightly çalıştır. Bir modülün "sahte %90 coverage" mı yoksa "gerçek %90 mı"
olduğunu ölçmenin en dürüst yolu budur.

**Statik analiz / SAST:**
Güvenlik odaklı statik analiz araçları (kod içi zafiyet paternlerini arayanlar) yüksek
sinyal verir ama başta çok gürültülüdür. Saha taktiği: aracı önce tüm kod tabanına
çalıştırıp mevcut bulguları bir "baseline" olarak dondur; kapı sadece **yeni** bulguları
bloke etsin. Böylece on yıllık teknik borcu bir günde ödemek zorunda kalmadan, yeni
zafiyetlerin girmesini engellersin.

**CI orchestration ve saha tüyoları:**
- **Paralelleştir ve önbelleğe al.** Bağımlılık kurulumunu, derleme çıktısını cache'le.
  Test paketini n parçaya bölüp paralel çalıştır. CI süresi kalitenin dolaylı düşmanıdır.
- **Fail-fast sıralaması.** En ucuz ve en olası patlayan kontrolü en başa koy. Kimse
  format hatası için e2e'yi beklememeli.
- **Required checks'i branch protection ile zorunlu kıl.** Kapı, ana dalda "önerilen"
  değil "zorunlu" olmalı; aksi halde deadline gecesinde biri kestirmeden geçer.
- **`git bisect` dostu ol.** Ana dal her zaman yeşil kalırsa, bir regresyon girdiğinde
  `git bisect` ile hangi commit'in bozduğunu ikili aramayla dakikalar içinde bulursun.
  Yeşil kalmayan bir ana dal, bisect'i işe yaramaz hâle getirir. "Ana dal her zaman
  yeşil" kuralı, sadece disiplin değil, bir debugging aracıdır.

**Gözlemlenebilirlik — kapının kendisini izle:**
Olgun ekip, kapının metriklerini toplar: kaç PR ilk denemede geçiyor, kapı hangi
kontrolde en çok patlıyor, hangi kontrol en çok override ediliyor, flaky test oranı ne.
Sürekli override edilen bir kontrol ya yanlış ayarlıdır ya gereksizdir. Hiç patlamayan
bir kontrol ise ya mükemmel ya da ölü olabilir — ikisini karıştırma. Kapı da bakım
isteyen canlı bir sistemdir; kur ve unut değildir.

**Pratik son not — kapı felsefesi:**
En iyi kapı, geliştiricinin "düşmanı" değil "çift gözü" gibi hissettirir. Hızlı geri
bildirim verir, adil yargılar (diff üzerinden), gerçek riskleri yakalar, gürültüyü
susturur ve acil durumda denetlenebilir şekilde esner. Kötü kapı ise yavaş, adaletsiz,
gürültülü ve katıdır; ekip ondan nefret eder, etrafından dolanmayı öğrenir ve kapının
tüm koruyucu değeri buharlaşır. Kapı bir teknoloji değil, bir **güven mühendisliği**
problemidir: makinenin verdiği yeşil rengin gerçekten bir şey ifade etmesini sağlamak.
Yeşilin anlamı korunduğu sürece kapı çalışır; anlamı aşındığı an, ne kadar sofistike
olursa olsun sadece bir tören haline gelir.
