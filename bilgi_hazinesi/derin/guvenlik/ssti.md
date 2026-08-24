# Server-Side Template Injection (SSTI): Derin Dalış

Bu metin, SSTI'nin "ne olduğu"nu değil, bir sunucuda **nasıl** kod çalıştırmaya
dönüştüğünü, sahada **nasıl** göründüğünü ve savunmayı hangi mimari kararların
gerçekten kestiğini ele alır. Özet makale (`uretilen/guvenlik/ssti.md`) tanımı ve
katmanlı savunmayı verir; burada tek bir örneği baştan sona yürüyerek, gerçek CVE
kayıtlarına demirleyerek ve tasarım takaslarını tartışarak derinleşiyoruz.

---

## 1. Çözümlü yürüyüş: masum bir "kişiselleştirme" özelliğinden RCE'ye

Somut bir senaryo kuralım. Bir SaaS ürünü, kullanıcıların yorum/bildirim e-postalarına
kendi imza satırlarını "kişiselleştirilmiş" bir karşılama metniyle eklemesine izin
veriyor. Ürün ekibi "kullanıcı `Merhaba {isim}` yazabilsin, biz `{isim}` yerine gerçek
adı koyalım" istiyor. Geliştirici Flask + Jinja2 kullanıyor ve en kısa yolu seçiyor.

### Zafiyetli kod (gerçek, çalışır)

```python
# app.py  — ZAFIYETLI
from flask import Flask, request
from jinja2 import Environment

app = Flask(__name__)
env = Environment()  # sandbox YOK, autoescape kapalı

def render_greeting(user_template: str, name: str) -> str:
    # Hata tam burada: kullanıcı metni ŞABLONUN KAYNAĞI oluyor.
    full_source = "Sayin musteri,\n\n" + user_template + "\n\nSaygilarimizla."
    template = env.from_string(full_source)   # kullanıcı girdisi derleniyor
    return template.render(name=name)

@app.route("/preview")
def preview():
    # kullanıcı hem şablonu hem adını gönderiyor
    user_template = request.args.get("greeting", "Merhaba {{ name }}")
    name = request.args.get("name", "Mert")
    return render_greeting(user_template, name)

if __name__ == "__main__":
    app.run(debug=True)
```

Bakışta zararsız görünüyor: bir e-posta önizlemesi. Testte
`?greeting=Merhaba {{ name }}&name=Ayse` çağrısı `Merhaba Ayse` üretiyor, herkes mutlu.

### Sorun kavramsal olarak nasıl doğuyor?

Kritik satır `env.from_string(full_source)`. Burada `full_source` içinde **kullanıcının
gönderdiği metin** var ve `from_string` bu metni bir **şablon kaynağı** olarak derliyor.
Yani kullanıcı verisi, motorun "değer" olarak değil, "kod/söz dizimi" olarak okuduğu
katmana taşınıyor. Doğru desende kullanıcı verisi yalnızca `render(name=...)` içine bir
**değişken değeri** olarak akmalıydı; burada ise şablonun *iskeletini* oluşturuyor.

Saldırgan `greeting` parametresine `{{ 7*7 }}` koyunca yanıt `... 49 ...` dönüyor. Bu tek
gözlem her şeyi söyler: motor kullanıcı girdisini **ifade** olarak değerlendirdi. `49`
gördüğünüz an teşhis kesindir. Sonrası motorun (Python/Jinja2) nesne grafiğinde gezinip
tehlikeli yeteneklere ulaşmaktır:

```
{{ ''.__class__.__mro__[1].__subclasses__() }}
```

Bu ifade, boş string'in sınıfından `object`'e çıkar ve çalışma zamanında yüklü tüm
sınıfların listesini döker. Bu liste içinde bir yerde süreç başlatabilen bir sınıf
(`subprocess.Popen`) veya `os` modülüne erişim veren bir sınıf bulunur. Uzman yaklaşım,
listeyi **isimle** filtrelemektir — sabit indeks güvenmek amatörlüktür, çünkü indeks
Python sürümüne ve yüklü kütüphanelere göre kayar. Modern Flask ortamında en kısa yol
genellikle bağlamda hazır duran nesnelerdir:

```
{{ config.__class__.__init__.__globals__['os'].popen('id').read() }}
{{ request.application.__globals__.__builtins__.__import__('os').popen('id').read() }}
```

Bunlardan biri yanıt gövdesinde `uid=... gid=...` döndürdüğü an, "e-posta önizlemesi"
tam bir **Remote Code Execution** kanalıdır. `config` üzerinden `SECRET_KEY` sızdırmak
bile — komut çalıştırmaya hiç gerek kalmadan — oturum sahtekârlığına yeter.

### Düzeltilmiş kod (doğru desen)

Çözümün özü mimari: **kullanıcı metni asla `from_string`'e girmesin.** İki katmanlı
düzeltme veriyorum — hem sınırı doğru çiziyor hem de "kullanıcı gerçekten yer tutucu
istiyor" ihtiyacını güvenli karşılıyor.

```python
# app.py  — DÜZELTILMIS
from flask import Flask, request
from markupsafe import escape

app = Flask(__name__)

# 1) Şablon iskeleti SABIT ve geliştiriciye ait. Kullanıcı sadece "değer" verir.
GREETING_SKELETON = "Sayin musteri,\n\nMerhaba {name},\n{note}\n\nSaygilarimizla."

# 2) Kullanıcının serbest metni motora HIÇ girmez; düz string olarak yerleştirilir.
ALLOWED_PLACEHOLDERS = {"name"}  # kullanıcı yalnızca {name} kullanabilir

def render_greeting(user_note: str, name: str) -> str:
    # Kullanıcı notu bir DEĞER; str.format ile bile şablona koymuyoruz.
    # {name} dışındaki tüm süslü parantezleri kaçırıyoruz ki format string olmasın.
    safe_note = user_note.replace("{", "{{").replace("}", "}}")
    return GREETING_SKELETON.format(name=escape(name), note=safe_note)

@app.route("/preview")
def preview():
    user_note = request.args.get("note", "")
    name = request.args.get("name", "Mert")
    return render_greeting(user_note, name)
```

Burada `{{ 7*7 }}` gönderilse ne olur? `user_note.replace` süslü parantezleri iki
katına çıkarır, `str.format` bunları tek parantez olarak *edebî metin* basar ve hiçbir
motor değerlendirmesi olmaz. Çıktı `{{ 7*7 }}` (harfi harfine) olur — `49` **asla**
görünmez. Kullanıcının gerçekten seçmeli yer tutucu istediği durumda ise, motora değil,
**sizin kontrolünüzdeki bir allowlist'e** izin verirsiniz:

```python
def render_with_allowlist(user_note: str, ctx: dict) -> str:
    import re
    def repl(m):
        key = m.group(1)
        if key in ALLOWED_PLACEHOLDERS:
            return str(escape(ctx.get(key, "")))
        return m.group(0)  # bilinmeyen yer tutucu edebî kalır
    return re.sub(r"\{([a-zA-Z_]+)\}", repl, user_note)
```

Fark nettir: kullanıcı yalnızca **sizin izin verdiğiniz** anahtarları enterpole edebilir;
`__class__`, `subprocess`, ifade değerlendirme diye bir yüzey **yoktur**. Motorun ifade
gücünü kullanıcıya hiç açmadınız — RCE zincirinin ikinci ve üçüncü halkasını tasarımdan
kestiniz.

Eğer kullanıcının gerçekten döngü/koşul içeren zengin şablon yazması bir ürün gereksinimiyse,
doğru cevap "Jinja2'yi sandbox'la" değil, **logic-less bir motor** (Mustache gibi) ya da
whitelist tabanlı kısıtlı bir DSL'dir. Bunu 3. bölümde tartışıyoruz.

### Yürüyüşün savunma tarafı: bu açığı nasıl *yakalarsınız*?

Aynı örneği savunmacı gözüyle tersten okuyalım, çünkü tespit yürüyüşün ayrılmaz yarısıdır.
Bu kodu bir güvenlik incelemesinde nasıl yakalarsınız? İz, `from_string`, `Template(...)`,
`env.from_string`, `str.format` ve f-string ile *kullanıcı verisi taşıyan bir değişkenin*
aynı ifadede buluştuğu her yerdir. Statik tarama kuralı kabaca şudur: "bir template derleme
çağrısının argümanı, kullanıcı girdisinden türeyen bir değişken içeriyor mu?" Bu soru
`grep`'lenebilir bir başlangıçtır ama veri akışını (taint) izlemek gerçek cevabı verir —
girdi birkaç fonksiyon öteden dolaşarak gelebilir.

Çalışma zamanı tespitinde ise sıra motor parmak izidir. `{{7*7}}` `49` verdiyse, sıradaki
ayırıcı test motoru daraltır: `{{7*'7'}}` `7777777` (yedi kez '7') üretiyorsa bu Python
string tekrar semantiğidir, yani **Jinja2** olası. `{{7*'7'}}` hata verip `${7*7}` çalışıyorsa
Java tabanlı bir motor (FreeMarker, Velocity) ya da bir Expression Language söz konusudur.
Smarty (CMS Made Simple'ın CVE-2017-16783'te düştüğü motor) `{$...}` sözdizimiyle ayrışır.
Doğru motoru bilmeden atılan zincir payload'ları çoğu zaman boşa gider; bu yüzden teşhis her
zaman parmak izinden sonra gelir.

---

## 2. Gerçek dünya: CVE kayıtlarıyla SSTI'nin sahadaki yüzü

Yukarıdaki oyuncak örnek, gerçek ürünlerde tam da bu şekillerde patlar. Verilen CVE
kayıtlarından üçünü, üç farklı SSTI arketipini göstermek için seçiyorum.

### Arketip 1 — "Kullanıcının düzenlediği şablon" tuzağı: CVE-2018-19907 (Crafter CMS)

**CVE-2018-19907**, Crafter CMS 3.0.18'de FreeMarker tabanlı bir SSTI'dir. Kayıt açıkça
şunu söyler: *developer* yetkisine sahip saldırganlar, bir `.ftl` şablon dosyası
oluşturup/düzenleyip içine `freemarker.template.utility.Execute` çağrısı gömdüklerinde,
sayfa render edilirken işletim sistemi komutları çalışır. Bu, 1. bölümdeki "kullanıcı
gerçekten şablon yazabiliyor" senaryosunun bir CMS'te gerçekleşmiş hâlidir. Buradaki
ders keskin: FreeMarker **varsayılan olarak** `Execute` gibi yardımcı sınıflara ve geniş
Java erişimine izin verir. Şablonu düzenleyebilen aktör (görünüşte "yetkili" bir
developer bile olsa) doğrudan RCE elde eder. Savunma, `TemplateClassResolver` ile sınıf
çözümlemesini kısıtlamak ve tehlikeli built-in'leri kapatmaktır; ama bu bilinçli bir
sıkılaştırma gerektirir, kutudan çıkmaz.

### Arketip 2 — "Zararsız parametre" tuzağı: CVE-2017-16783 & CVE-2017-1000454 (CMS Made Simple)

**CVE-2017-16783**, CMS Made Simple 2.1.6'da `cntnt01detailtemplate` parametresi
üzerinden Server-Side Template Injection'dır (Smarty motoru). Burada dikkat çeken nokta,
zafiyetin *bir HTTP parametresi* üzerinden gelmesidir — yani 1. bölümdeki oyuncak
`?greeting=` örneğinin birebir gerçek dünyadaki karşılığı. Aynı ürün ailesinde
**CVE-2017-1000454**, Smarty Template Injection'ın çekirdek bileşenlerde nasıl **local
file read** (2.2 öncesi) ve **local file inclusion** (2.2.1'den itibaren) etkisine
tırmandığını gösterir. Bu ikisi birlikte önemli bir gerçeği vurgular: SSTI her zaman
gösterişli bir RCE ile bitmez; motorun yeteneğine göre **dosya okuma / include** gibi
"daha sessiz" ama hâlâ kritik etkiler üretir. `49` görmeyen bir tester, "demek ki açık
yok" diye yanılabilir — oysa etki dosya sisteminde olabilir.

### Arketip 3 — "Kütüphane vs. uygulama sorumluluğu" tartışması: CVE-2018-13818 (Twig)

**CVE-2018-13818**, Twig'in 2.4.4 öncesi sürümlerinde `search_key` parametresi üzerinden
SSTI bildirir. Bu kaydın *notu* eğitici açıdan altın değerindedir: satıcı, Twig'in kendisinin
bir web uygulaması olmadığını, girdiyi uygun biçimde sarmalamanın **Twig'i kullanan
uygulamanın sorumluluğu** olduğunu belirtir. Bu, sahadaki en yaygın yanlış anlamayı ifşa
eder: "Modern Twig güvenli, o hâlde bende de güvenlidir." Motorun olgunlaşmış olması,
onu yanlış kullanan uygulamayı kurtarmaz. Aynı dersi ekosistem düzeyinde **CVE-2018-14716**
(Craft CMS SEOmatic plugin < 3.1.4) verir: hiçbir öğeyle eşleşmeyen istekler `canonicalUrl`'i
hatalı üretir ve Twig kodunun çalışmasına yol açar — yani zafiyet motorun içinde değil,
**motorun etrafındaki bütünleştirme kodundadır.**

### Arketip 4 — "Yetkili kullanıcı yine de saldırgandır": CVE-2018-11061 & CVE-2018-20465

**CVE-2018-11061** (RSA NetWitness / Security Analytics), CVSS 9.1 CRITICAL ile, template
motorunun **güvensiz yapılandırması** yüzünden Admin/Operator rolündeki kimliği doğrulanmış
bir kullanıcının **root yetkisiyle** komut çalıştırabildiğini gösterir. **CVE-2018-20465**
(Craft CMS ≤ 3.0.34) ise daha sessiz bir varyanttır: kimliği doğrulanmış adminler, Site
Settings'teki URI Format alanına `craft.app.config.DB.user` / `...DB.password` gibi ifadeler
koyarak veritabanı kullanıcı adı ve parolasını **açık metin** olarak sızdırabilir. İkisinin
ortak dersi: "kimlik doğrulaması gerekiyor" bir hafifletme değildir. İç tehdit, ele geçirilmiş
hesap veya yetki yükseltme, "authenticated" bariyerini rutin olarak geçer; SSTI'yi
"düşük risk" saymanın gerekçesi olamaz.

Bu altı kaydın panoraması: SSTI **her katmanda** çıkar — motorun kendisi (Twig), motorun
yapılandırması (RSA), motoru saran bütünleştirme (SEOmatic), kullanıcıya açılan şablon
düzenleme (Crafter), tek bir HTTP parametresi (CMS Made Simple) ve yetkili bir ayar alanı
(Craft CMS). Etki de RCE'den (root'a kadar) dosya okuma ve düz metin sır sızıntısına uzanır.

---

## 3. Karşılaştırma / karar: hangi savunma, ne zaman, neden

SSTI savunmasında birden çok geçerli seçenek vardır; mesele "en iyisi" değil, bağlama göre
**doğru takas**tır. Aşağıda kararı yönlendiren eksenleri karşılaştırıyorum.

### Seçenek A — Kullanıcıyı şablon yüzeyinden tamamen kesmek (statik şablon + değişken)

**Ne zaman:** Kullanıcının şablon *yazmadığı*, yalnızca veri sağladığı durumların ezici
çoğunluğu. Yani gerçek dünyanın %90'ı.
**Neden:** Kök nedeni (veri/kod sınırı ihlali) ortadan kaldırır. Zincirin ilk halkası olan
"değerlendirme kanıtı" bile oluşmaz; `{{7*7}}` edebî metin kalır.
**Takas:** Neredeyse takassız. Tek "maliyet", geliştiricinin `from_string`/string
birleştirme/f-string kolaylığından vazgeçmesidir. Bu bir maliyet değil, disiplindir.

### Seçenek B — Logic-less motor (Mustache benzeri)

**Ne zaman:** Kullanıcı **gerçekten** şablon yazmalı (e-posta şablonları, bildirim metinleri)
ama ifade/kod çalıştırmasına gerek yok.
**Neden:** Motor tasarımı gereği keyfi ifade yürütmez; yalnızca değişken yerleştirme ve basit
döngü/koşul sunar. RCE zincirinin 2. ve 3. halkasını *baştan* imkânsız kılar.
**Takas:** İfade gücü kaybı. Kullanıcı karmaşık mantık kuramaz; ama zaten kurmasını
istemiyordunuz. Bu bir özellik, kusur değil. Crafter CMS'in (CVE-2018-19907) FreeMarker
yerine logic-less bir motor kullanmış olması, o RCE sınıfını tümden silerdi.

### Seçenek C — Güçlü motor + sandbox (Jinja2 `SandboxedEnvironment`, Twig/Symfony sandbox, FreeMarker `TemplateClassResolver`)

**Ne zaman:** Güçlü motorun ifade gücü zorunlu ve girdinin bir kısmı yine de güvenilmez.
**Neden:** Tehlikeli attribute/metot erişimini (örn. `__class__`, `__subclasses__`) engellemeye
çalışır; saldırı yüzeyini daraltır.
**Takas:** **Sandbox birincil savunma değildir.** Tarih sandbox bypass'larıyla doludur;
filtreler, `attr`/`map` gibi dolaylı erişimler, string biçimlendirme nesneleri kaçış yolu
açmıştır. Sandbox'ı defense-in-depth'in *bir katmanı* olarak konumlandırın, tek duvar
olarak değil. RSA NetWitness (CVE-2018-11061) tam da "template motorunun güvensiz
yapılandırması" yüzünden düştü — sandbox/kısıtlama vardı denemez, **yoktu**; bu, C
seçeneğinin ancak *doğru yapılandırıldığında* değerli olduğunu gösterir.

### Seçenek D — Girdi allowlist + karakter engelleme (blacklist)

**Ne zaman:** Yalnızca ek bir gürültü azaltıcı olarak, A/B/C'nin üstüne.
**Neden (allowlist):** "Sadece alfanümerik isim" gibi bağlama sıkı bir beyaz liste anlamlı
daraltmadır.
**Neden olmasın (blacklist):** `{{`/`}}` engelleme neredeyse her zaman aşılır — kodlama,
alternatif sözdizimi (`{%...%}`, `${...}`), filtre zincirleri, string concat. Blacklist'i
tek savunma sanmak en yaygın ölümcül hatadır.
**Takas:** Tek başına asla güvenilmez; yanlış güven duygusu yaratma riski yüksek.

### Seçenek E — En az yetki + izolasyon + dışa giden trafik kısıtlama

**Ne zaman:** Her zaman, en dış katman olarak. Diğer seçeneklerin *yanında*.
**Neden:** Açığı kapatmaz; **etkiyi** sınırlar. RCE gerçekleşse bile root yerine düşük
yetkili kullanıcı, container izolasyonu, kısıtlı dosya sistemi ve engellenmiş outbound DNS
(blind SSTI'nin out-of-band kanalını kırar) hasarı daraltır.
**Takas:** Sömürüyü önlemez, sadece pahalılaştırır. CVE-2018-11061'in "root privileges"
detayı, bu katmanın yokluğunun etkiyi nasıl maksimize ettiğinin kanıtıdır.

### İki eksende bir örnekle karar

Somut bir kararı iki eksende görelim. Diyelim bir pazarlama ekibi "kullanıcılar kendi
kampanya e-postalarını, koşullu bloklarla (`abonelik türü premium ise şu metin`) tasarlasın"
istiyor. İki soru sorulur. Birincisi: kullanıcı gerçekten *mantık* mı yazacak, yoksa sadece
yer tutucu mu dolduracak? Sadece yer tutucuysa Seçenek A yeter, tartışma biter. Koşul/döngü
gerçekten gerekiyorsa ikinci soru: bu mantığın *ifade gücü* ne kadar geniş olmalı? "Sadece
eşitlik ve basit döngü" yetiyorsa Seçenek B (Mustache/Handlebars gibi logic-less veya
logic-limited motor) doğru cevaptır; keyfi Python/Java ifadesine hiç gerek yoktur. Ancak
"kullanıcı serbest hesaplama, filtre zinciri, biçimlendirme istiyor" deniyorsa — ki bu talep
çoğu zaman gereksinim değil *alışkanlıktır* — o zaman C'ye düşersiniz ve maliyeti kabul
edersiniz: sandbox'ı doğru kurmak, sürekli güncel tutmak, bypass'ları izlemek. Karar ağacının
özeti: **önce ihtiyacı daralt, sonra motoru seç.** Çoğu ekip tam tersini yapar — güçlü motoru
seçer, sonra onu zaptetmeye çalışır. Bu, RSA NetWitness (CVE-2018-11061) ve Crafter CMS
(CVE-2018-19907) gibi olayların ortak kalıbıdır: güçlü/geniş yetkili motor önce gelir,
kısıtlama sonradan (ve eksik) eklenir.

### Karar özeti

Öncelik sırası nettir ve mimariden dışa doğru gider: **A > B > C > (D, E ek katman).**
Kullanıcı şablon yazmıyorsa A yeter ve en ucuzdur. Yazıyorsa B'yi seç. B mümkün değilse
(ifade gücü zorunlu) C'yi *doğru yapılandırarak* kullan ama asla ona yaslanma. D ve E her
zaman en dıştaki güvenlik ağlarıdır, çekirdek çözüm değil. En pahalı hata, D'yi (blacklist)
çekirdek çözüm sanıp A'yı atlamaktır. İkinci en pahalı hata, ihtiyaç B iken C'yi seçip
gereksiz bir sandbox bakım yükü altına girmektir — az yetenekli motor, bakımı yapılamayan
güçlü motordan güvenlidir.

---

## 4. Hata-modu kataloğu: geliştirici ve savunmacıların tipik yanılgıları

1. **Kullanıcı girdisini `from_string`/string birleştirme/f-string ile şablona gömmek.**
   Kök hata budur: veri, motorun "kod" olarak okuduğu katmana taşınır. `render(context)`
   yerine şablon *kaynağını* kullanıcıyla inşa etmek zincirin ilk halkasını yaratır.

2. **`{{`/`}}` kara listesine güvenmek.** Template dilleri esnektir; kodlama, alternatif
   sözdizimi ve filtre zincirleriyle blacklist neredeyse her zaman aşılır. En fazla gürültü
   azaltır, güvenlik sağlamaz.

3. **SSTI'yi XSS ile karıştırıp auto-escape'i yeterli sanmak.** Auto-escaping çıktının HTML
   anlamını nötralize eder; şablonun **sunucuda çalışmasını** engellemez. Motor `{{7*7}}`'yi
   zaten çalıştırmıştır; çıktının kaçışlanması `49`'u geri almaz.

4. **Sandbox'ı aşılamaz bir duvar sanmak.** `SandboxedEnvironment` ve Symfony/Twig sandbox'ı
   faydalıdır ama tarih bypass'larla doludur (`attr`, `map`, filtre ve biçimlendirme yolları).
   Tek savunma olarak yaslanmak yanlış güven üretir.

5. **Sabit `__subclasses__()` indeksi kullanmak (ve savunmayı buna göre kurmak).** İndeks
   Python sürümüne ve yüklü kütüphanelere göre kayar; internetten kopyalanan sabit indeksli
   payload'lar ortam değişince kırılır. Savunmacı da "o indeks bizde yok, güvendeyiz" diye
   yanılır — saldırgan isimle enumerate eder.

6. **"Kullanıcı sadece isim/parametre giriyor, ne olabilir ki" varsayımı.** CVE-2017-16783'te
   olduğu gibi tek bir HTTP parametresi (`cntnt01detailtemplate`) tam SSTI taşıyabilir.
   Etkiyi belirleyen girdinin masumluğu değil, girdinin **nereye aktığı**dır.

7. **"Authenticated gerekiyor, o hâlde düşük risk" demek.** CVE-2018-11061 (Admin/Operator →
   root) ve CVE-2018-20465 (admin → DB parolası açık metin) tam tersini kanıtlar. İç tehdit,
   ele geçirilmiş hesap ve yetki yükseltme bu bariyeri rutin geçer.

8. **SSTI'yi hep "RCE veya hiçbir şey" sanmak.** CVE-2017-1000454 gösterir ki etki **local
   file read / local file inclusion** ya da (CVE-2018-20465) **düz metin sır sızıntısı** de
   olabilir. `49` görmeyen tester "açık yok" diye erken kapatır; oysa etki dosya sisteminde
   veya ayar alanında olabilir.

9. **Motoru tespit etmeden RCE payload'ı savurmak.** `49` "açık var" der ama zincir motora
   bağımlıdır (Jinja2 ≠ FreeMarker ≠ Twig ≠ Smarty). Motor parmak izi atlanınca payload'lar
   hem başarısız olur hem gereksiz iz bırakır. Önce ayırıcı testler (`{{7*'7'}}` vs `${7*7}`),
   sonra motora özgü zincir.

10. **"Modern framework güvenlidir" diye motorun olgunluğuna güvenmek.** CVE-2018-13818'in
    satıcı notu nettir: girdiyi sarmalamak **uygulamanın** sorumluluğudur. Olgun Twig bile
    yanlış bütünleştirmeyle (CVE-2018-14716, SEOmatic'in `canonicalUrl` hatası) SSTI'ye açılır.
    Güvenlik motorda değil, **kullanım ve bütünleştirme** şeklindedir.

11. **FreeMarker'ı varsayılan yapılandırmayla güvenilmez girdiye maruz bırakmak.**
    CVE-2018-19907'de `freemarker.template.utility.Execute` doğrudan komut çalıştırdı.
    FreeMarker tasarımı gereği geniş Java erişimi verir; `TemplateClassResolver` ile
    kısıtlamak ve tehlikeli built-in'leri kapatmak **bilinçli** bir adımdır, otomatik değil.

12. **Blind SSTI'yi görmezden gelmek.** Girdi bir e-posta/PDF/rapor motoruna gidip yansımayınca
    "test temiz" sanılır. Oysa zaman tabanlı ispat (gecikme) ve out-of-band etkileşim (motorun
    DNS/HTTP isteği yapması) zafiyeti hâlâ kanıtlar. Outbound trafiği kısıtlamamak bu kanalı
    açık bırakır.

13. **Şablonu güvenlik incelemesinin kapsamı dışında tutmak.** Kod gözden geçirmede `render`
    çağrıları taranırken şablon dosyalarının **nereden yüklendiği** (statik mi, kullanıcı DB'sinden
    mi, parametreden mi) çoğu zaman atlanır. Zafiyet tam da bu "veri kaynağı" ayrımında yaşar.

14. **Bağımlılıkları güncellememek.** Motorların sandbox bypass ve SSTI düzeltmeleri sürümlerle
    gelir (örn. Twig'in 2.4.4 düzeltmesi, SEOmatic'in 3.1.4'ü, CMS Made Simple'ın 2.2.2'si).
    Eski sürümde "kapalı sandığın" yol açık olabilir; sürüm sabitlemek sessiz bir risktir.

---

## Kapanış

SSTI'nin çekirdeği tek cümledir: **veriyi kod olarak yorumlatmak.** Motor Jinja2, FreeMarker,
Twig ya da Smarty olsun, mekanizma aynıdır — motorun iç nesne modelinden host dilin tehlikeli
yeteneklerine bir köprü kurulur ve bu köprü çoğu zaman RCE'ye, bazen dosya okumaya ya da düz
metin sır sızıntısına çıkar. Verilen CVE'ler bu köprünün her katmanda kurulabildiğini gösterir:
motorda, yapılandırmada, bütünleştirmede, kullanıcıya açılan şablonda, tek bir parametrede.
En sağlam savunma bir payload filtresi değil, bir **mimari karardır**: kullanıcı verisini
şablonun *içine* değil, şablona aktarılan bir değişkenin *değerine* koymak. Geri kalan her şey —
logic-less motor, sandbox, allowlist, en az yetki, izolasyon — bu temel kararın etrafına örülen
ve gerçek dünyanın belirsizliğine karşı derinlik sağlayan katmanlardır.
