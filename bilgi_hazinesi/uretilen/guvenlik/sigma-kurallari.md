# Sigma ile Tespit Kuralı Yazma

## Tanım

Sigma, log verileri üzerinde tehdit tespiti (detection) yapmak için kullanılan, açık ve platform-bağımsız bir kural formatıdır. En yalın tanımıyla Sigma, "log dünyasının YARA'sıdır": nasıl ki YARA kuralları dosya ve bellek içeriğindeki desenleri tarif etmek için ortak bir dil sağlıyorsa, Sigma da log kayıtlarındaki şüpheli desenleri tarif etmek için ortak bir dil sağlar. Bir Sigma kuralı, insan tarafından okunabilir bir YAML dosyasıdır; belirli bir SIEM ürününün sorgu diline (Splunk SPL, Elastic'in KQL/EQL'i, Microsoft Sentinel'in KQL'i, QRadar AQL vb.) bağlı değildir.

Sigma'nın çözdüğü temel problem şudur: Tehdit istihbaratı ve tespit mantığı genellikle belirli bir üreticinin sorgu diline gömülü olarak paylaşılır. Bir kurumun Splunk için yazdığı bir korelasyon kuralı, Elastic kullanan başka bir kuruma doğrudan işe yaramaz. Herkes aynı tespit fikrini kendi diline yeniden çevirmek zorunda kalır; bu da hem emek israfıdır hem de hataya açıktır. Sigma, tespit mantığını *bir kez* soyut biçimde ifade etmenizi, ardından bir dönüştürücü (converter) aracılığıyla hedef platformun sorgu diline *otomatik* çevirmenizi sağlar. Böylece tespit bilgisi taşınabilir (portable) bir varlık haline gelir.

Sigma üç ana bileşenden oluşan bir ekosistemdir: (1) YAML tabanlı **kural formatı** (specification), (2) log alanlarını her platformda standart isimlere eşleyen **taxonomy ve alan eşlemeleri (field mappings)**, ve (3) kuralları hedef sorgulara çeviren **dönüştürme motoru**. Modern Sigma dünyasında bu dönüştürme işini büyük ölçüde `pySigma` kütüphanesi ve onun `sigma` komut satırı aracı yürütür; eski `sigmac` aracının yerini almıştır.

## Kök Neden / Çalışma Mantığı: Neden Böyle Bir Şeye İhtiyaç Var?

Sigma'nın var oluş nedenini anlamak için, tespit mühendisliğindeki (detection engineering) iki ayrık katmanı ayırt etmek gerekir: **mantık katmanı** ve **taşıma/dil katmanı**.

Bir tespit fikri aslında iki farklı bilgi içerir. Birincisi, *neyi* aradığınızdır: örneğin "PowerShell'in, encoded komut çalıştırmak için `-EncodedCommand` bayrağıyla başlatıldığı" durumu. Bu, saf tespit mantığıdır ve hangi SIEM'i kullanırsanız kullanın değişmez. İkincisi ise, *bu mantığı belirli bir üründe nasıl ifade edeceğinizdir*: Splunk'ta `index=windows EventCode=4688 New_Process_Name="*powershell*"`, Elastic'te ise tamamen farklı bir sözdizimi. İkinci katman tümüyle ürüne özgüdür ve tespit fikrinin özüyle ilgisizdir.

Geleneksel yaklaşımda bu iki katman iç içe geçmiştir. Sigma'nın temel içgörüsü, bu iki katmanı **ayrıştırmaktır** (decoupling). Kural yazarı yalnızca mantık katmanını, soyut ve okunabilir bir biçimde tanımlar; dil katmanı ise dönüştürme aşamasında makine tarafından üretilir. Bu ayrıştırma sayesinde:

- Aynı kural birden fazla platforma çevrilebilir (yaz-bir-kez, her-yerde-çalıştır).
- Kurallar sürüm kontrolünde (git) tutulabilir, incelenebilir ve topluluk halinde paylaşılabilir. SigmaHQ deposu, binlerce hazır kuralın topluca bakımının yapıldığı bir kamu malı hazinesidir.
- Tespit mantığı, belirli bir üreticiyle "kilitlenme" (vendor lock-in) olmadan taşınabilir. SIEM değiştirdiğinizde kurallarınızı sıfırdan yazmazsınız; yalnızca yeniden dönüştürürsünüz.

Çalışma mantığının kalbinde **alan soyutlaması** yatar. Sigma kuralları, log alanlarını üreticinin gerçek alan adlarıyla değil, standartlaştırılmış mantıksal isimlerle anar. Örneğin bir sürecin komut satırı, Sigma'da genellikle `CommandLine` alanıdır. Windows olay günlüklerinde bu alan Sysmon'da `CommandLine`, güvenlik günlüğünde ise farklı bir isimle geçebilir; Elastic'te ECS (Elastic Common Schema) altında `process.command_line` olur. Dönüştürücü, kuraldaki mantıksal `CommandLine` alanını, hedef platformun **pipeline**'ında (dönüştürme boru hattı) tanımlı eşlemelere bakarak gerçek alan adına çevirir. İşte bu yüzden Sigma'yı sadece "YAML sözdizimi" olarak görmek eksiktir; asıl güç, sözdizimi + taxonomy + pipeline üçlüsündedir.

## Bir Sigma Kuralının Anatomisi

Somut bir örnekle ilerleyelim. Aşağıda, şüpheli bir PowerShell çalıştırmasını yakalamayı amaçlayan basit bir Sigma kuralı yer alıyor:

```yaml
title: Encoded Komutlu Suspicious PowerShell Calistirmasi
id: 6f3e2b14-0a7c-4d2e-9b1a-8c5f2d7e4a10
status: experimental
description: >
  PowerShell surecinin, gizlenmis (obfuscated) komut calistirmak icin
  kullanilan -EncodedCommand bayragiyla baslatilmasini tespit eder.
author: Ornek Yazar
date: 2026/07/05
references:
  - https://attack.mitre.org/techniques/T1059/001/
tags:
  - attack.execution
  - attack.t1059.001
logsource:
  category: process_creation
  product: windows
detection:
  selection:
    Image|endswith: '\powershell.exe'
    CommandLine|contains:
      - '-enc'
      - '-EncodedCommand'
  condition: selection
falsepositives:
  - Bazi mesru yonetim scriptleri encoded komut kullanabilir
level: medium
```

Bu kuralı katman katman inceleyelim çünkü her alanın bir işlevi vardır ve bu işlevleri anlamadan doğru kural yazılamaz.

### Meta veri (metadata) katmanı

`title`, `id`, `status`, `description`, `author`, `date`, `references`, `tags` alanları tespit mantığını değil, kuralın *yönetimini* ilgilendirir. Burada özellikle dikkat edilmesi gereken üç nokta var. **`id`**, kural için evrensel benzersiz bir tanımlayıcıdır (UUID). Bunun kritikliği şudur: kuralın başlığı zamanla değişebilir ama `id` sabit kalır; böylece bir kural, ismi ne olursa olsun, sistemler arasında tek ve aynı varlık olarak izlenebilir. Kuralı asla `id` olmadan üretime almayın.

**`status`** alanı kuralın olgunluğunu belirtir: `experimental` (deneme aşamasında, false positive üretebilir), `test` (test ediliyor), `stable` (üretime hazır) gibi değerler alır. Bu, kuralı hangi güvenle devreye alacağınızı belirleyen bir sinyaldir.

**`tags`** alanı, kuralı MITRE ATT&CK çerçevesindeki teknik ve taktiklere bağlar (`attack.t1059.001` gibi). Bunun değeri sadece dokümantasyon değildir; kapsam analizi (coverage analysis) yapmanızı sağlar. ATT&CK teknikleriyle etiketlenmiş kurallarınızı bir araya getirdiğinizde, hangi saldırgan davranışlarını gördüğünüzü ve hangilerine kör olduğunuzu bir haritada görebilirsiniz.

### Log kaynağı (logsource) katmanı

`logsource` bloğu, Sigma'nın en çok yanlış anlaşılan ama en kritik parçasıdır. Bu blok, kuralın *hangi tür log üzerinde* çalıştığını tanımlar. Üç anahtar taşır: `category`, `product` ve `service`.

- **`product`**: Logu üreten üst düzey ürün/işletim sistemi (`windows`, `linux`, `macos`, `aws`, `azure` gibi).
- **`category`**: Log kaydının davranışsal türü (`process_creation`, `network_connection`, `file_event`, `dns_query`, `registry_event` gibi). Bu, belirli bir üründen bağımsız, soyut bir kategori tanımıdır.
- **`service`**: Belirli bir günlük hizmeti veya kanal (`sysmon`, `security`, `sshd`, `cloudtrail` gibi).

Bu üçlünün neden bu kadar önemli olduğunu anlamak lazım. `logsource`, dönüştürme aşamasında pipeline'ın hangi alan eşlemelerini ve hangi ek koşulları uygulayacağını belirleyen **anahtar**tır. Örneğin `category: process_creation` + `product: windows` kombinasyonu, dönüştürücüye "bu kuralı Sysmon Event ID 1 veya Windows Security Event ID 4688 üzerinde çalışan bir sorguya çevir ve `Image`, `CommandLine` gibi mantıksal alanları o kaynağın gerçek alanlarına eşle" der. `logsource`'u yanlış belirlerseniz, kural teknik olarak "geçerli" görünse bile dönüşümde yanlış veri kaynağına yönlendirilir ve hiçbir zaman ateşlenmez. Sigma'da sessizce çalışmayan kural, gürültülü kuraldan daha tehlikelidir çünkü size sahte bir güvenlik hissi verir.

### Tespit (detection) katmanı

`detection` bloğu, kuralın kalbidir. İki tür öğe içerir: bir veya daha fazla **search identifier** (arama tanımlayıcısı, örnekte `selection`) ve bir **`condition`** ifadesi.

Her search identifier, alan-değer eşleşmelerinden oluşan bir sözlük (map) ya da değerler listesidir. Örnekteki `selection` bloğunda iki koşul var:

```yaml
selection:
  Image|endswith: '\powershell.exe'
  CommandLine|contains:
    - '-enc'
    - '-EncodedCommand'
```

Burada **field modifier**'lar (alan değiştiricileri) devreye giriyor: `|endswith`, `|contains`, `|startswith`, `|re` (regex), `|base64`, `|base64offset`, `|all` gibi. Bu değiştiriciler, alan değerinin nasıl karşılaştırılacağını belirler. `Image|endswith: '\powershell.exe'` ifadesi, `Image` alanının `\powershell.exe` ile *bitmesini* arar; bu, `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` gibi tam yolları yakalarken, kötü niyetli birinin dosyayı başka bir dizine kopyalayıp adını değiştirmediği durumları kapsar.

Sigma'nın örtük mantık kuralları önemlidir ve çoğu hatanın kaynağıdır:

- Bir alanın altında **liste** verirseniz (örnekteki `-enc` ve `-EncodedCommand` gibi), bu **VEYA (OR)** anlamına gelir: değerlerden herhangi biri eşleşirse koşul sağlanır.
- Aynı search identifier içinde **birden fazla alan** verirseniz (örnekteki `Image` ve `CommandLine`), bunlar **VE (AND)** ile birleştirilir: tüm alanların eşleşmesi gerekir.

Bu iki kuralı karıştırmak, tespit mühendislerinin en sık yaptığı hatadır ve mantığın tam tersine dönmesine yol açabilir.

**`condition`** ifadesi ise search identifier'ları mantıksal olarak birleştirir. Basit bir kuralda `condition: selection` yeterlidir. Ancak gerçek dünyada koşullar daha karmaşıktır. Yaygın kalıp, bir "yakalama" bloğu ile bir "istisna" bloğunu birleştirmektir:

```yaml
detection:
  selection:
    Image|endswith: '\powershell.exe'
    CommandLine|contains: '-enc'
  filter:
    User|contains: 'ADMIN_SERVICE_ACCOUNT'
  condition: selection and not filter
```

Buradaki `condition: selection and not filter` mantığı şudur: PowerShell'i encoded komutla yakala, *ama* bilinen meşru bir servis hesabından geliyorsa hariç tut. `condition` içinde `and`, `or`, `not`, parantez, `1 of selection*`, `all of selection*` gibi ifadeler kullanılabilir. `1 of them` ve `all of them` kalıpları da sıkça görülür.

## Sömürü / İstismar Mantığı: Saldırgan Sigma'yı Nasıl Atlatır?

Sigma kuralı yazan bir savunmacı, aynı zamanda bir saldırganın bu kuralı nasıl atlatacağını (evasion) düşünmek zorundadır. Çünkü zayıf yazılmış bir Sigma kuralı, sadece işe yaramamakla kalmaz; savunmacıya kapsandığı yanılgısını vererek gerçek bir kör nokta yaratır. Saldırgan tarafındaki mantığı anlamak, sağlam kural yazmanın ön koşuludur.

**1. Sözdizimsel varyasyon (obfuscation) ile atlatma.** Örnek kuralımız `CommandLine|contains: '-enc'` arıyordu. PowerShell'in komut satırı ayrıştırıcısı, bayrakları kısaltmaya izin verir; `-EncodedCommand` bayrağı `-e`, `-en`, `-enc`, `-encod` gibi çok sayıda biçimde yazılabilir. Ayrıca büyük/küçük harf duyarsızdır: `-EnC`, `-ENC` de geçerlidir. Saldırgan `-ec` yazarsa, `-enc` arayan kuralınız ateşlenmez. Bu yüzden zayıf bir string eşleşmesi, saldırganın en küçük varyasyonuyla delinir.

**2. Boşluk ve dolgu (padding) enjeksiyonu.** Komut satırına fazladan boşluklar, tırnak işaretleri (`p^ower^shell`, `"powershell"`) veya çevre değişkeni genişletmeleri (`%COMSPEC%`) sokarak, birebir string eşleşen kurallar atlatılabilir. Windows komut yorumlayıcısı bu karakterleri temizleyip komutu yine de çalıştırır, ama loga düşen ham string kuralın aradığı desenle uyuşmaz.

**3. Living-off-the-land (LOLBin) ikamesi.** Kural belirli bir ikili dosyayı (`powershell.exe`) hedefliyorsa, saldırgan aynı işi yapan başka bir meşru sistem aracına (`pwsh.exe`, `cmd.exe`, `mshta.exe`, `rundll32.exe`) geçebilir. `Image|endswith` ile tek bir ikiliye kilitlenmek, bu ikame saldırılarına karşı kırılgandır.

**4. Log kaynağının kendisini devre dışı bırakma.** En temel atlatma, olayın *hiç loglanmamasını* sağlamaktır. Sysmon yapılandırması saldırgan tarafından değiştirilir, Windows olay günlüğü servisi durdurulur ya da denetim (audit) politikası kapatılırsa, kuralınız ne kadar iyi yazılmış olursa olsun besleneceği veri gelmez. Bu yüzden "log tamperingi" (`4688`/`1102` olay günlüğü temizleme, Sysmon config değişikliği) tespiti başlı başına önemli bir kural sınıfıdır.

### Savunma: Sağlam ve atlatmaya dayanıklı kural yazmak

Yukarıdaki atlatma yöntemlerinin her birine karşı savunmacının elinde araçlar var:

- **Varyasyona karşı normalize et.** Bayrak kısaltmalarını tek tek listelemek yerine, davranışsal desenler arayın. Encoded PowerShell için tek başına `-enc` yerine, base64 payload'ın kendisini yakalamaya çalışın; Sigma'nın `|base64offset|contains` değiştiricisi tam da bunun için vardır: aradığınız düz metni base64'e kodlayıp komut satırındaki kodlanmış halini arar. Böylece saldırganın nasıl kodladığından bağımsız hale gelirsiniz.
- **Tek göstergeye değil, davranış zincirine bak.** Sağlam tespit, tek bir string yerine bir davranış bileşimidir: "encoded PowerShell" + "ağ bağlantısı kuruyor" + "ana süreci Office uygulaması" gibi. Sigma **correlation** kuralları (birden fazla olayı zaman penceresinde ilişkilendiren) tam olarak bu çok-adımlı tespit için tasarlanmıştır.
- **LOLBin ikamesini kategoriyle karşıla.** Tek bir ikiliye kilitlenmek yerine, davranış kategorisine (script yorumlayıcısı başlatma, şüpheli ana-alt süreç ilişkisi) odaklanın.
- **Loglama bütünlüğünü izle.** Güvenlik günlüğü temizleme, Sysmon servisinin durması, audit policy değişikliği için ayrı tespit kuralları yazın. Savunmanın kör edilmesi, saldırının kendisi kadar önemli bir sinyaldir.

Buradaki temel felsefe şudur: **kırılgan, birebir (brittle, exact-match) göstergeler yerine dayanıklı, davranışsal (robust, behavioral) göstergeler** arayın. Bu, "Pyramid of Pain" fikriyle örtüşür: hash veya IP gibi kolayca değiştirilebilen göstergeler saldırganı az acıtır; TTP (taktik, teknik, prosedür) düzeyindeki davranışsal tespit ise saldırganı gerçekten zorlar.

## Dönüştürme (Conversion): Sigma'dan Çalışan Sorguya

Sigma kuralı tek başına hiçbir şey tespit etmez; bir SIEM'de çalışabilecek somut bir sorguya *dönüştürülmesi* gerekir. Bu dönüşümü modern araç zincirinde `pySigma` ve komut satırı aracı `sigma` yürütür (eski `sigmac` yerine geçmiştir).

Dönüştürme kavramsal olarak üç girdiye dayanır:

1. **Kural(lar)ın kendisi** — yazdığınız YAML dosyası.
2. **Backend (arka uç)** — hedef platformun sorgu dilini üreten eklenti. Splunk, Elasticsearch (ES|QL / Lucene / EQL), Microsoft 365 Defender / Sentinel (KQL), QRadar gibi hedefler için ayrı backend'ler vardır. Bir backend, soyut Sigma AST'sini (soyut söz dizim ağacı) o platformun sorgu sözdizimine çeviren mantığı içerir.
3. **Pipeline (işleme boru hattı)** — alan eşlemelerini ve log kaynağı çözümlemesini yapan katman. Örneğin bir Windows/Sysmon pipeline'ı, kuraldaki soyut `Image` ve `CommandLine` alanlarını, hedef veride gerçekte hangi alan adlarına karşılık geldiklerine çevirir; ayrıca `logsource` bilgisine bakarak doğru olay kimliği (Event ID) filtresini ekler.

Bu üç parçanın ayrımı çok önemlidir. **Backend, "hangi dile" çevirileceğini; pipeline ise "alanların nasıl eşleneceğini" belirler.** Aynı kural, aynı backend'le ama farklı pipeline'larla, farklı log şemalarına (örneğin ham Sysmon vs. ECS-normalize Elastic verisi) çevrilebilir. Bu yüzden "dönüşüm başarısız oldu" ya da "kural ateşlenmiyor" sorunlarının büyük çoğunluğu, backend seçiminde değil, **yanlış veya eksik pipeline** seçiminde saklıdır.

Kavramsal bir dönüştürme çağrısı şuna benzer (kesin bayrak adları sürüme göre değişebileceğinden burada kavramı veriyorum, birebir komut yerine): `sigma convert` komutuna hedef backend'i (örneğin Splunk), uygun pipeline'ı (örneğin windows-sysmon) ve kural dosyasını verirsiniz; araç size o platformda çalıştırılabilir bir sorgu döndürür. Örnek PowerShell kuralımız Splunk backend'iyle, kabaca `Image` alanının `\powershell.exe` ile bittiği ve `CommandLine`'ın `-enc` veya `-EncodedCommand` içerdiği kayıtları arayan bir SPL sorgusuna dönüşür.

Dönüşümün bir de "kaçınılmaz kayıp" (lossy) tarafı vardır ve bunu dürüstçe bilmek gerekir. Her Sigma özelliği her backend tarafından birebir desteklenmez. Bir platform belirli bir regex yeteneğini ya da bir field modifier'ı desteklemiyorsa, dönüştürücü ya bir yaklaşım (approximation) üretir ya da hata verir. Bu yüzden "kural SigmaHQ'da var, bende çalışıyor demektir" varsayımı yanlıştır; her kuralı kendi platformunuzda dönüştürüp, ürettiği sorguyu gözden geçirip, gerçek veride test etmeniz gerekir.

## Yaygın Hatalar

Tespit mühendislerinin Sigma ile en sık düştüğü tuzaklar, çoğunlukla mantık ile sözdizimi arasındaki incelikleri gözden kaçırmaktan kaynaklanır.

- **`logsource` uyumsuzluğu.** Kuralı `category: process_creation` ile yazıp, dönüşümde bu kategoriyi karşılamayan bir pipeline seçmek. Sonuç: teknik olarak geçerli ama hiçbir zaman ateşlenmeyen bir kural. Bu, en sinsi hatadır çünkü sessizce başarısız olur.
- **AND/OR mantığını karıştırmak.** Aynı search identifier altındaki farklı alanların AND, bir alan altındaki liste değerlerinin ise OR olduğunu unutmak. Beklediğiniz "her ikisi de" mantığı yerine "herhangi biri" mantığı kurup false positive selinde boğulmak (ya da tam tersi).
- **Aşırı dar (brittle) eşleşme.** `CommandLine: 'powershell.exe -EncodedCommand ...'` gibi tam string eşleşmesi kullanmak. Komut satırındaki en ufak varyasyon (fazladan boşluk, farklı bayrak sırası) kuralı devre dışı bırakır. `|contains`, `|endswith` gibi değiştiricileri doğru kullanmamak bu hataya yol açar.
- **Aşırı geniş (noisy) eşleşme.** Bunun tersi: `CommandLine|contains: 'powershell'` gibi çok genel bir desen, meşru yönetim faaliyetlerini de yakalayıp analistleri alarm yorgunluğuna (alert fatigue) sürükler. İyi bir kural, sinyal/gürültü oranını dengeler.
- **`falsepositives` ve `level` alanlarını atlamak.** Bu alanlar sadece dokümantasyon değildir; kuralı devreye alacak analiste, neyi bekleyeceğini ve alarmı hangi ciddiyetle ele alacağını söyler. Bunları boş bırakmak, kuralı bir "kara kutu"ya çevirir.
- **Base64/encoding körlüğü.** Encoded payload arayan bir kuralı düz metin string'iyle yazmak. `|base64offset|contains` gibi değiştiricileri bilmemek, en yaygın gizleme (obfuscation) tekniğine kör kalmak demektir.
- **Kuralı gerçek veride test etmeden üretime almak.** Dönüşümün lossy olabileceğini görmezden gelip, ürettiği sorguyu incelemeden ve tarihsel veride çalıştırıp doğrulamadan devreye almak. Kural, hem gerçek saldırı örneğinde ateşlenmeli (true positive doğrulaması) hem de normal veride sessiz kalmalıdır (false positive kontrolü).

## En İyi Pratikler

- **Önce mantığı, sonra sözdizimini düşün.** Bir kural yazmadan önce şu soruyu net cevaplayın: "Hangi saldırgan davranışını, hangi log kaynağında, hangi ayırt edici gözlemle yakalayacağım?" Sözdizimi bu cevabın ifadesidir, tersi değil.

- **Davranışsal göstergeleri tercih et.** Kolayca değiştirilebilen göstergeler (tek bir hash, tek bir IP, tek bir tam string) yerine, saldırganın değiştirmesi zor olan davranış kalıplarını hedefle. Bu, kuralın ömrünü uzatır ve atlatmaya karşı direncini artırır.

- **`logsource`'u titizlikle seç ve pipeline'la eşleştir.** Kuralın hangi veri kaynağında çalışacağını netleştir; dönüştürürken de o kaynağa uygun pipeline'ı kullan. Bu ikisinin uyumu, kuralın hayatta kalıp kalmamasını belirler.

- **MITRE ATT&CK ile etiketle.** Her kuralı ilgili teknik ve taktiklerle etiketlemek, hem dokümantasyon sağlar hem de kapsam (coverage) analizini mümkün kılar. Hangi saldırgan davranışlarına kör olduğunuzu görmenin tek yolu budur.

- **Kuralları sürüm kontrolünde tut ve gözden geçirmeden geçir.** Sigma kuralları koddur; git'te tutun, pull request süreciyle inceleyin, `sigma` aracının test/lint özellikleriyle sözdizimini doğrulayın. Bir kuralı üretime almadan önce en az bir başka mühendisin gözünden geçmesini sağlayın.

- **False positive ayarlamasını (tuning) kuralın parçası say.** Mükemmel bir kural yoktur; her kural, kendi ortamınızın gürültüsüne göre ayarlanır. `filter`/`not` blokları ile bilinen meşru davranışları hariç tutarak sinyal/gürültü oranını iyileştirin. Bu ayarlamayı kuralın içine, izlenebilir biçimde (yorumlarla) yazın.

- **Hem pozitif hem negatif test yap.** Kuralı, gerçek bir saldırı örneğinde (örneğin bir atak simülasyon aracının ürettiği olayda) çalıştırıp ateşlendiğini doğrulayın; ardından normal üretim verisinde çalıştırıp makul bir false positive oranı verdiğini onaylayın. Test edilmemiş kural, umuttan ibarettir.

- **Topluluktan yararlan ama körü körüne güvenme.** SigmaHQ deposundaki hazır kurallar mükemmel bir başlangıç noktasıdır, ama her kuralı kendi log şemanıza, kendi pipeline'ınıza ve kendi gürültü profilinize göre uyarlayın. Başkasının ortamında `stable` olan bir kural, sizin ortamınızda `experimental` olabilir.

Özetle Sigma, tespit mantığını taşınabilir bir varlığa dönüştüren güçlü bir soyutlamadır; ama gücü, onu sözdizimi + taxonomy + pipeline bütünü olarak kavrayan ve kuralı saldırganın gözünden test eden mühendisin elinde ortaya çıkar. Sigma yazmak, YAML doldurmak değil; savunmayı düşünmenin disiplinli bir biçimidir.
