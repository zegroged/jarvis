# AS-REP Roasting — Tespit

> Saha notu: Bu metin "4768'e bak, PreAuthType 0 ara" seviyesinin ötesini hedefler. O satırı zaten herkes biliyor. Değer, o satırın gerçek bir Active Directory ortamında neden tek başına işe yaramadığını ve kıdemli bir analistin gürültü denizinde gerçek ihlali nasıl ayıkladığını anlamakta.

## 1. Özet: saldırı + naif tespit

AS-REP Roasting, Kerberos ön kimlik doğrulamasının (pre-authentication) kapalı olduğu hesapları hedefleyen offline bir parola kırma saldırısıdır. Normal Kerberos akışında bir istemci, KDC'den TGT istemeden önce timestamp'ı kendi parola hash'iyle şifreleyip gönderir (PA-ENC-TIMESTAMP); KDC bunu çözemezse AS-REQ'i reddeder. Bu mekanizma, kimliği doğrulanmamış bir tarafın parola tahmini yapmasını engeller. Ancak `DONT_REQ_PREAUTH` bayrağı (userAccountControl'de `4194304`) set edilmiş hesaplarda bu adım atlanır. Saldırgan, bu hesaplar için doğrudan bir AS-REQ gönderir ve KDC ona, hesabın parola hash'iyle şifrelenmiş bir bölüm içeren AS-REP döner. İşte bu şifreli bölüm, ağdan hiçbir kimlik doğrulaması yapılmadan alınıp offline olarak Hashcat (mod 18200) ile kırılabilir. Kerberoasting'in (T1558.003) kardeşidir; MITRE'de kendi alt tekniği vardır: **T1558.004**.

Saldırının kritik ön koşulu şudur: saldırganın, ön kimlik doğrulaması kapalı hesapların listesine ihtiyacı vardır. Bunu genellikle LDAP sorgusuyla çıkarır — `userAccountControl` alanında `4194304` bitini `-band` ile arayan bir `Get-ADUser` sorgusu, ya da Rubeus'un `asreproast` modülünün kendi LDAP taramasıyla. Domain kullanıcısı yetkisi bile gerektirmeyebilir; bazı senaryolarda anonim/kimliksiz bir istemci sadece hesap adını bilerek AS-REP isteyebilir. Bu, saldırıyı özellikle sinsi yapan noktadır: kırma işlemi tamamen ağ dışıdır, KDC hiçbir "başarısız oturum" kaydı üretmez, çünkü teknik olarak başarısız bir şey olmamıştır — KDC istenen bileti nazikçe teslim etmiştir.

Naif tespit herkesin bildiği reçetedir: Windows Security log'unda **Event ID 4768** (A Kerberos authentication ticket TGT was requested) olaylarını izle, içlerinden `PreAuthType = 0` ve `TicketEncryptionType = 0x17` (RC4-HMAC) olanları filtrele, `ServiceName = krbtgt` koşulunu ekle. Referans Sigma kuralı tam olarak bunu yapar (`3e2f1b2c-4d5e-11ee...`): `EventID: 4768`, `PreAuthType: 0`, `TicketEncryptionType: '0x17'`, `ServiceName: 'krbtgt'`. Bir de araç tabanlı taraf var: Rubeus çalıştırıldığında `process_creation` üzerinden `Image|endswith: '\Rubeus.exe'` veya `CommandLine|contains: 'asreproast '` yakalanır (Florian Roth'un `7ec2c172...` kuralı). Ve enumerasyon tarafı: `Get-ADUser -Filter` içinde `useraccountcontrol` ve `4194304` geçen script block'lar (`96c982fe...`). Kağıt üzerinde üç katman: keşif, istek, araç. Sorun, bu üç katmanın her birinin gerçek ortamda ayrı ayrı bozulmasıdır.

## 2. Naif tespit neden yetmez

**Kör nokta 1: PreAuthType = 0 tek başına "ihlal" demek değildir.** En büyük yanılgı burada. Ön kimlik doğrulaması kapalı hesaplar bir saldırı sonucu değil, çoğu ortamda **kalıtsal bir yapılandırma gerçeğidir**. Eski UNIX/Linux entegrasyonları, bazı Java tabanlı uygulamalar, MIT Kerberos istemcileri, eski NAS/appliance servis hesapları — bunların bir kısmı Windows pre-auth ile uyumsuz olduğu için `DONT_REQ_PREAUTH` ile açılmıştır. Bu hesaplar **her meşru oturum açışlarında** `PreAuthType = 0` ile 4768 üretir. Yani kuralınız "0 gördüm, alarm" derse, bu hesapların normal günlük trafiği sizi alarm seline boğar. Kural, olayın **anormal mi yoksa hesabın normal davranışı mı** olduğunu ayırt edemez, çünkü tek bir event'e bakar.

**Kör nokta 2: RC4 (0x17) filtresi hem çok gevşek hem çok dar.** Detection tasarımcıları `0x17` filtresini koyar çünkü saldırgan RC4 ister — RC4 hash'i AES'e göre çok daha hızlı kırılır. Ama iki problem var. Birincisi, `0x17` sadece saldırıya değil, **eski/yanlış yapılandırılmış** ortamlara da işaret eder; Server 2008 öncesi kalıntıları, `msDS-SupportedEncryptionTypes` set edilmemiş hesaplar rutin olarak RC4 üretir. False positive kaynağı. İkincisi ve daha tehlikelisi: modern saldırganlar AES istemeyi de bilir. Rubeus `asreproast` çağrısında hesabın desteklediği en güçlü şifreyle AS-REP alabilir; hesap AES destekliyorsa `0x12` (AES256) döner. Kırma yavaşlar ama saldırı devam eder — ve sizin `0x17` filtreniz bunu **tamamen ıskalar**. Yani filtre, gürültüyü içeri alırken gerçek AES varyantını dışarıda bırakır: iki yönlü başarısızlık.

**Kör nokta 3: 4768 varsayılan olarak yeterli detayda loglanmaz — ve DC dışında hiç yoktur.** Kerberos TGT istekleri **yalnızca Domain Controller'larda** kaydedilir, üye sunucularda değil. Eğer "Audit Kerberos Authentication Service" alt kategorisi Success için açık değilse (birçok ortamda Advanced Audit Policy elle sıkılaştırılmamıştır), 4768 hiç üretilmez. Kural mükemmel yazılmış olabilir; besleyen log yoksa kör kalır. Ayrıca çok-DC'li ortamlarda saldırgan hangi DC'ye giderse olay orada kalır — SIEM'e tüm DC'lerden toplama yapılmıyorsa görünürlük deliği açılır.

**Kör nokta 4: Rubeus imzası kırılgan bir tuzaktır.** `Image|endswith: '\Rubeus.exe'` veya `OriginalFileName: 'Rubeus.exe'` yakalaması, saldırganın aracı ismini değiştirmediğini varsayar. Gerçekte Rubeus derleme aşamasında yeniden adlandırılır, PE metadata'sı temizlenir, ya da tamamen bellek içinde (Cobalt Strike `execute-assembly`, PowerShell reflection) çalıştırılır — bu durumda diskte hiçbir zaman `Rubeus.exe` olmaz, `process_creation` olayı bile doğmaz. CommandLine imzası (`asreproast `) da ancak süreç ayrı bir işlem olarak başlarsa işe yarar; in-memory .NET assembly yüklemesinde komut satırı görünmez. Araç imzasına dayanan tespit, en kolay atlatılan katmandır ve tek başına yanlış bir güven verir.

Özetle: naif kural üç ayrı yerden sızdırır — meşru pre-auth-off hesaplar FP üretir, AES varyantı ve renamed/in-memory araçlar FN üretir, ve loglama açık değilse hiçbiri fark etmez. Değer, bu boşlukları kapatan korelasyonda başlar.

## 3. Korelasyon zinciri (asıl değer)

AS-REP Roasting tek bir event olarak zayıf sinyaldir. Onu yüksek güvenli tespite çeviren şey, saldırının **doğal yaşam döngüsünü** birden fazla sinyalle örmektir. Saldırının gerçek şekli üç fazlıdır: **keşif → toplu istek → offline kırma sonrası kullanım**. Her fazın kendi zayıf izi var; asıl güç bunları zamansal ve bağlamsal olarak birbirine bağlamakta.

**Zincir A — Keşif + toplu istek korelasyonu (en güçlü sinyal):**

Gerçek AS-REP Roasting neredeyse hiçbir zaman tek bir 4768 değildir. Saldırgan önce hedef listesini çıkarır (LDAP `userAccountControl -band 4194304` sorgusu), sonra o listedeki **tüm** hesaplar için kısa bir zaman penceresinde AS-REP ister. Yani gerçek desen şudur:

> **A:** Bir hosttan, kısa süre önce (dakikalar içinde) `DONT_REQ_PREAUTH` bayrağını sorgulayan bir LDAP/PowerShell keşfi (`96c982fe` kuralının `ScriptBlockText` deseni, ya da 5136/4662 dizin erişim olayları)
> **+ B:** Aynı kaynak IP'den, **çok sayıda farklı hesap** için kısa pencerede (örn. 60 saniyede 5+) `PreAuthType = 0`, `ServiceName = krbtgt` 4768 olayı
> **= yüksek güvenli AS-REP Roasting**

Burada kritik sezgi şudur: **tek hesap için 0** normaldir (kalıtsal yapılandırma), ama **kısa pencerede birçok farklı hesap için 0**, hele bir keşif olayının hemen ardından geliyorsa, meşru bir açıklaması yoktur. Meşru pre-auth-off hesaplar birbirinden bağımsız zamanlarda, kendi iş yüklerine göre oturum açar; hepsi aynı 30 saniyede aynı client IP'den istenmez. Korelasyonun kalbi **"tekilin normalliği vs. kümenin anormalliği"** ayrımıdır.

**Zincir B — Client IP / hesap davranış temeli (baseline sapması):**

4768 olayında `Client Address` alanı vardır. Meşru bir pre-auth-off servis hesabı her zaman kendi sabit sunucusundan (aynı IP) TGT ister. Eğer aynı hesap için 4768 aniden **farklı, alışılmadık bir workstation IP'sinden** gelirse — özellikle bir kullanıcı iş istasyonundan bir servis hesabı için — bu bariz bir sapmadır. Buradaki korelasyon: `(hesap adı) → (tarihsel client IP seti)` temelini tut, yeni IP'yi flag et. AS-REP Roasting'de saldırgan kendi foothold hostundan istek yapar, dolayısıyla IP hedeflenen hesabın normal kaynağıyla eşleşmez.

**Zincir C — Kırma sonrası kullanım (ihlalin kapanışı):**

Saldırganın nihai amacı hash'i kırıp o hesapla oturum açmaktır. Yani AS-REP Roasting bir **öncü göstergedir**; asıl ihlal, kırılan parolayla gelen erişimdir. Güçlü korelasyon şudur:

> **A:** Hesap X için anormal AS-REP isteği (yukarıdaki desen) — diyelim saat 14:00
> **+ C:** Aynı hesap X için **saatler/gün sonra**, farklı bir hosttan başarılı interaktif/network oturum açma (4624, LogonType 3 veya 10), ya da o hesabın daha önce hiç dokunmadığı sistemlere erişim
> **= AS-REP Roasting başarılı oldu, parola kırıldı, lateral hareket başladı**

Bu zincir, "roast → offline kırma → kullanım" arasındaki zaman boşluğunu köprüler ve tek başına ne 4768'in ne de 4624'ün veremeyeceği yargıyı verir: **saldırı sadece denenmedi, başarılı oldu.** SOC'de asıl kovalanan budur.

Pratikte ben bu üçünü tek bir "AS-REP kampanyası" risk skoruna bağlarım: keşif olayı +2, çoklu-hesap 0 kümesi +3, anormal client IP +2, kırma-sonrası oturum +4. Tek sinyal alarm üretmez (gürültü); toplam eşiği aşınca yüksek öncelikli olay açılır. Böylece kalıtsal pre-auth-off hesabın günlük 4768'i asla tetiklemez, ama gerçek kampanya birkaç dakika içinde eşiği patlatır.

## 4. False positive gerçeği ve triage yargısı

Gerçek ortamlarda `PreAuthType = 0` alarmını meşru üreten şeyler — ve bunlar azınlık değil, çoğunluktur:

- **Kalıtsal servis/uygulama hesapları:** Eski Linux/UNIX entegrasyonları, MIT Kerberos istemcileri, Java (bazı JDK Kerberos yapılandırmaları), eski NAS/SAN appliance hesapları, bazı VPN/SSO köprüleri. Bunlar `DONT_REQ_PREAUTH` ile kasıtlı açılmıştır ve her oturumda 0 üretir.
- **Yanlış yapılandırılmış "geçici" hesaplar:** Bir zamanlar bir sorunu çözmek için pre-auth kapatılıp sonra unutulan hesaplar. Ortam ne kadar eskiyse o kadar çok vardır.
- **Vuln scanner ve güvenlik araçları:** Tenable/Nessus, Qualys, ve özellikle **BloodHound/SharpHound** koleksiyonu dizin enumerasyonu yapar; bu, keşif fazının (`4194304` sorgusu) meşru — ya da en azından "yetkili kırmızı takım" — kaynaklı olabileceği anlamına gelir. SharpHound'un LDAP sorguları gerçek saldırganınkiyle neredeyse aynıdır.
- **Kırmızı takım / pentest pencereleri:** Onaylı bir angajman sırasında Rubeus/Impacket `GetNPUsers.py` tam da bu deseni üretir. Triage'ın ilk sorusu her zaman: "onaylı bir test penceresi açık mı?"
- **SCCM / yedekleme / envanter yazılımları:** Bunlar tipik olarak pre-auth-off üretmez ama geniş hesap erişim desenleriyle korelasyon kurallarını tetikleyebilir; asıl AS-REP FP'sinden çok "çoklu hesap erişimi" kurallarında karışırlar.

**Kıdemli analistin triage yargısı — sırayla neye bakarım:**

1. **Tekil mi, küme mi?** İlk bakışım event sayısına ve dağılımına. Tek hesap, tek IP, tekrarlayan/periyodik 0 → neredeyse kesin kalıtsal yapılandırma, düşük öncelik, hesabı "bilinen pre-auth-off" allowlist'ine al. Kısa pencerede çok sayıda farklı hesap → yüksek şüphe.

2. **Client IP kimin?** 4768'in `Client Address`'ine bakarım. Bilinen bir uygulama sunucusu mu (servis hesabının normal evi), yoksa bir kullanıcı iş istasyonu / alışılmadık subnet mi? Servis hesabı için isteğin bir workstation'dan gelmesi tek başına kırmızı bayraktır.

3. **Önünde keşif var mı?** İstek kümesinden hemen önce aynı hosttan bir LDAP/`Get-ADUser` `4194304` sorgusu ya da SharpHound imzası var mı? Varsa keşif→istek zinciri kapanıyor demektir. Yoksa, belki gürültü.

4. **Hedef hesapların değeri.** İstenen hesaplar rastgele mi yoksa yüksek değerli mi (admin, servis hesabı)? Saldırgan `DONT_REQ_PREAUTH` olan **her** hesabı roast eder; meşru trafik böyle toplu davranmaz.

5. **Onaylı test var mı?** Change/pentest takvimini kontrol ederim. Kırmızı takım penceresi açıksa olayı oraya iliştirir, kapatırım — ama IP ve zamanı doğrularım.

6. **Kapanış: kullanım oldu mu?** En önemlisi — o hesaplarda takip eden anormal 4624 var mı? Varsa artık FP tartışması biter, incident'e döner.

Kritik operasyonel nokta: bu tespitin sağlığı **allowlist hijyenine** bağlıdır. Ortamdaki tüm meşru pre-auth-off hesaplarını bir kez envanterle (`Get-ADUser -Filter {useraccountcontrol -band 4194304}` ile çıkar), bunları bilinen-iyi listesine koy, ve **listede olmayan** bir hesap için 0 gördüğünde önceliği yükselt. Bu tek adım, FP hacminin çoğunu keser ve gerçek anomaliyi (yeni açılmış ya da beklenmeyen pre-auth-off hesap) öne çıkarır. Bonus: bir hesabın pre-auth'ının **yeni kapatılması** (4738 — User Account Management, `msDS-SupportedEncryptionTypes`/UAC değişikliği; `f6de9536` kuralının mantığı) başlı başına bir tespit fırsatıdır — saldırgan bazen kendi kontrol ettiği bir hesabın pre-auth'ını kapatıp onu roast eder (persistence/privilege abuse).

## 5. Kaçınma → karşı-tespit (derin kedi-fare)

**Kaçınma 1 — AES iste, RC4'ten kaç.** Saldırgan `TicketEncryptionType = 0x17` filtresini bildiği için, AES destekleyen hesapları AES ile roast eder; AS-REP `0x12` döner ve `0x17` kuralınız susar. Kırma yavaşlar ama saldırı çalışır.
**Karşı-tespit:** Şifre türü filtresini kaldırın ya da genişletin. `ServiceName = krbtgt` + `PreAuthType = 0` deseni **şifre türünden bağımsız** anomalidir. RC4'e özel filtre bir "hızlı kırma" göstergesidir, tespitin temeli olmamalı. Ben `PreAuthType = 0`'ı ana sinyal, şifre türünü sadece **önceliklendirme** faktörü olarak kullanırım (0x17 = daha acil çünkü kırma hızlı).

**Kaçınma 2 — Yavaş ve dağıtık istek (low-and-slow).** Saldırgan çoklu-hesap kümesini tespit ettiğinizi bilir; istekleri saatlere yayar, farklı hesaplara farklı zamanlarda, hatta farklı DC'lere dağıtarak "kısa pencere" korelasyonunuzu kırar.
**Karşı-tespit:** Korelasyon penceresini genişlet ve **kaynak-merkezli** say. Tek bir hosttan/kullanıcı bağlamından zaman içinde (24 saat gibi) toplam kaç **farklı** pre-auth-off hesap için istek geldiğini biriktir. Meşru bir foothold host, günde 15 farklı servis hesabı için TGT istemez. Ayrıca tüm DC'lerden merkezi toplama şart — dağıtım ancak loglar tek yerde birleşmezse işe yarar.

**Kaçınma 3 — Rubeus'u yeniden adlandır / bellekte çalıştır.** `\Rubeus.exe` ve `OriginalFileName` imzaları rename ile ölür; `execute-assembly` / reflection ile disk ve komut satırı imzası hiç doğmaz.
**Karşı-tespit:** Araç imzasına değil, **davranışa** dayan. İn-memory .NET yüklemesi bile CLR'ı sürece yükler; Sysmon **Event ID 7** (Image/DLL Loaded) ile `clr.dll`/`mscoree.dll`'in beklenmedik bir sürece (örn. bir Office ya da beklenmeyen bir binary) yüklenmesi + ardından KDC trafiği korelasyonu iz bırakır. Daha da güçlüsü: araç ne olursa olsun **KDC tarafındaki 4768 deseni değişmez** — Rubeus, Impacket `GetNPUsers.py`, ya da elle yazılmış bir istemci, hepsi aynı `PreAuthType = 0` çoklu-hesap izini üretir. Bu yüzden ben tespitin ağırlığını **her zaman istemci tarafı imzasına değil, KDC tarafındaki olay desenine** koyarım. İstemci imzası bonus'tur, temel değil.

**Kaçınma 4 — Impacket ile Windows host'u hiç kullanma.** `GetNPUsers.py` bir Linux saldırgan hostundan doğrudan LDAP + Kerberos konuşur; Windows `process_creation`/Sysmon telemetrisi olan hiçbir kurumsal hosta dokunmaz.
**Karşı-tespit:** Yine KDC tarafı kurtarır — olay DC'de doğar, saldırganın host telemetrisine ihtiyaç yoktur. Ek olarak `Client Address` alanı, isteğin bilinen bir Windows istemcisi yerine alışılmadık/Linux bir kaynaktan geldiğini gösterebilir (özellikle kurumsal ağda o subnet'te normalde iş istasyonu yoksa).

**Kaçınma 5 — Tek hesap, düşük gürültü.** Saldırgan tüm listeyi roast etmek yerine sadece bir yüksek değerli, zayıf parolalı hesabı hedefler. Çoklu-hesap korelasyonunuz tetiklenmez çünkü küme yoktur.
**Karşı-tespit:** Burada tek savunma **allowlist + client IP baseline**'dır. Hesap bilinen pre-auth-off listesinde değilse, ya da istek hesabın normal kaynağından gelmiyorsa, tekil olay bile flag edilir. Bu senaryo, allowlist hijyeninin neden pazarlık konusu olmadığını gösterir — çoklu-hesap sezgisi çöktüğünde geriye kalan tek şey "bu hesap için 0 normal mi?" sorusudur ve buna ancak envanterli bir baseline cevap verebilir.

**Kaçınma 6 — Kendi hesabının pre-auth'ını kapat.** Yetki kazanmış saldırgan, kontrol ettiği bir hesabın UAC'sini değiştirip pre-auth'ı kapatır, roast eder, sonra geri açar.
**Karşı-tespit:** **4738** (User Account Management) üzerinden UAC/`DONT_REQ_PREAUTH` değişikliğini izle. Bir hesabın pre-auth'ının runtime'da kapatılması nadir ve yüksek şüphelidir; hemen ardından o hesap için 4768 `PreAuthType = 0` gelmesi neredeyse imza kalitesinde bir zincirdir. `f6de9536` kuralının izlediği 4738 sinyalinin gerçek değeri buradadır — statik bir "zayıf şifre açıldı" alarmı değil, bir saldırı zincirinin ilk halkası olarak.

## 6. SIEM / saha gerçeği

**Field mapping tuzakları.** En sık yenilen kaza `PreAuthType` alanının kaynağa göre farklı isimlenmesidir. Ham Windows Security XML'inde alan `PreAuthType`'tır ama değer bir string olarak `"0"` gelebilir; bazı forwarder/parser'lar bunu integer'a çevirir, bazıları çevirmez. `EventID: 4768; PreAuthType: 0` kuralınız, alan `"0"` (string) olarak indekslenmişse integer `0` ile eşleşmeyebilir. **Splunk**'ta Windows TA (`Splunk_TA_windows`) alanı `Pre_Authentication_Type` ya da `PreAuthType` olarak çıkarabilir ve değer çoğu zaman insan-okunur metinle gelir. **Sentinel**'de `SecurityEvent` tablosunda alan `PreAuthType`'tır ama string'tir; KQL'de `PreAuthType == "0"` yazmalısın, `== 0` değil — bu klasik sessiz başarısızlıktır (kural çalışır, hiç eşleşmez, kimse fark etmez). **Elastic/ECS**'te 4768 `winlog.event_data.PreAuthType` altına düşer ve normalize edilmez; ham event_data'ya inmen gerekir. Kuralı devreye almadan önce **mutlaka bilinen bir pre-auth-off hesapla test et** ve alanın gerçekten eşleştiğini gör; yoksa "kural var, alarm yok" güvenli sanılıp aslında kör kalırsın.

Aynı tuzak `TicketEncryptionType`'ta da var: değer bazen `0x17` (hex string), bazen `23` (decimal integer), bazen `RC4-HMAC` (çözülmüş metin) olarak gelir. `TicketEncryptionType: '0x17'` yazan bir kural, kaynağın `23` ürettiği bir ortamda hiç tetiklenmez. Her üç formu da kapsayan bir eşleme (`0x17` OR `23`) kullan, ya da parser'ın hangisini ürettiğini kesin doğrula. `ServiceName` de dikkat ister: `krbtgt` mi yoksa `krbtgt/DOMAIN` mi olarak geliyor? `equals` yerine `contains` gerekebilir.

**Varsayılan loglanmayanlar.** 4768 ve 4769 **yalnızca DC'lerde** ve **yalnızca** "Audit Kerberos Authentication Service" (4768) ve "Audit Kerberos Service Ticket Operations" (4769) Success denetimi açıksa üretilir. Bunlar Advanced Audit Policy'de yer alır ve birçok ortamda default GPO ile açık değildir. Şart: tüm DC'lere uygulanan bir GPO ile bu iki alt kategoriyi Success (gerekirse Failure) için etkinleştir. Ayrıca **hacim uyarısı**: 4768/4769 büyük ortamlarda devasa hacim üretir; SIEM lisans/ingest maliyeti gerçektir. Pratik yaklaşım: DC loglarını topla ama `PreAuthType = 0` gibi dar bir filtreyi mümkünse toplama/indeksleme aşamasında değil, arama/korelasyon aşamasında uygula ki nadir ama kritik olayı kaybetme.

Keşif fazı için **Script Block Logging** (PowerShell EID 4104) şarttır — `96c982fe` kuralının dayandığı `ScriptBlockText` bu olmadan yoktur. LDAP tabanlı enumerasyonu (SharpHound, ADSI) yakalamak istiyorsan DC'de **Directory Service Access** denetimi (4662) ya da 5136 gerekir; bunlar da default kapalıdır ve açıldığında yüksek hacimlidir. Sysmon tarafında in-memory araç tespiti için **Config'in Image Load (EID 7) olayını CLR DLL'leri için loglaması** gerekir — çoğu Sysmon config'i (SwiftOnSecurity dahil) performans için Image Load'u dar tutar; `clr.dll`/`clrjit.dll` yüklemelerini beklenmedik süreçler için loglayacak şekilde genişletmen gerekebilir.

**Platform farkları — tuning gerçeği.**
- **Splunk:** Korelasyonu `stats` ile kur. Örn. `Client_Address` ve `_time` üzerinde `bin span=10m` yapıp `dc(user)` (farklı hesap sayısı) hesapla; eşiği geçen kaynağı alarma bağla. Tekil FP'yi `lookup` tabanlı allowlist ile ele. `tstats` ile data model üzerinden hızlandır ama accelerated model'de `PreAuthType` alanının constraint'te olduğundan emin ol.
- **Sentinel:** KQL'de zaman-pencereli çoklu-hesap için `summarize dcount(TargetUserName) by ClientIPAddress, bin(TimeGenerated, 10m)` deseni. String karşılaştırma tuzağına dikkat (`PreAuthType == "0"`). Kırma-sonrası korelasyon için `SecurityEvent` (4768) ile takip eden 4624'ü `join` ile aynı `TargetUserName` üzerinden birleştir — bu, Zincir C'yi doğrudan verir.
- **Elastic:** EQL `sequence` bu iş için biçilmiş kaftandır. `sequence by user.name` ile keşif olayını, çoklu 4768'i ve takip eden logon'u zamansal sırayla bağlayabilirsin — üç fazlı zinciri tek kuralda ifade etmenin en temiz yolu. `maxspan` ile pencereyi ayarla.

**Son tuning gerçeği.** Bu tespit "yaz ve unut" değildir. İlk hafta allowlist'i dolduracaksın (envanterdeki her meşru pre-auth-off hesap), çünkü onlarsız kural gürültüden kullanılamaz. Sonra client IP baseline'ını oturtacaksın. Kırmızı takım penceresi geldiğinde kural patlayacak — bu iyi, çalıştığını gösterir; ama o pencereyi bastırma mekanizman (change ticket'a bağlı geçici mute) olmalı ki analistleri yormasın. Ve şifre türü / araç imzası gibi kırılgan katmanlara asla tek başına güvenme: bu tespitin bel kemiği her zaman **DC tarafındaki `PreAuthType = 0` desenidir**, gerisi önceliklendirme ve zenginleştirmedir. Araç değişir, şifre türü değişir, host değişir — KDC'nin ön kimlik doğrulamasız bilet vermek zorunda kalması değişmez. Tespiti oraya demirle.
