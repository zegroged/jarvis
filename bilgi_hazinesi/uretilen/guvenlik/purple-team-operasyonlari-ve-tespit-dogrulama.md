# Purple Team Operasyonları ve Tespit Doğrulama

## Giriş ve Tanım

Klasik güvenlik testi ikiye ayrılır: **Red Team** (saldırgan taklidi yapan taraf) ve **Blue Team** (savunmayı işleten, tespit ve müdahale eden taraf). Bu iki takım geleneksel olarak birbirinden habersiz, hatta rekabet halinde çalışır. Red Team bir kaleyi delip "içeri girdik, sizi yakalayamadınız" raporu yazar; Blue Team ise savunmasının nerede kör olduğunu ancak aylar sonra, uzun bir rapor üzerinden öğrenir. Bu model bir gerçeği ölçer ama bir şeyi **iyileştirmez**: aradaki geri besleme döngüsü çok yavaş ve çok kayıplıdır.

**Purple Team**, bu iki rengin karışımıdır ve bir takımdan çok bir **çalışma biçimidir**. Temel fikri şudur: saldıran taraf bir teknik uygular, savunan taraf o anda telemetrisine bakar, "bu saldırıyı gördük mü, alarm üretti mi, üretmediyse neden?" sorusunu **gerçek zamanlı** ve **iş birliği içinde** yanıtlar. Purple team'in ürettiği asıl değer, bir "hacklendiniz" raporu değil; ölçülebilir, tekrarlanabilir bir **tespit kapsama (detection coverage)** haritasıdır.

Bu makalenin merkezindeki soru şudur: *"Yazdığım Sigma/EDR/SIEM kuralı gerçekten çalışıyor mu?"* Bir tespit kuralı yazmak kolaydır. O kuralın, saldırının gerçek varyantları karşısında ateşlediğini **kanıtlamak** ise ayrı bir disiplindir. İşte bu kanıtlama döngüsünü kuran metodoloji purple team operasyonlarıdır.

---

## Kök Neden: Neden "Kural Yazdım" Yeterli Değildir

Bir savunmacı bir MITRE ATT&CK tekniği (örneğin T1053 Scheduled Task, T1003 Credential Dumping) için bir kural yazdığında üç ayrı yanılsamaya düşebilir:

1. **Var olma yanılsaması (coverage on paper):** ATT&CK matrisinde ilgili hücrenin "yeşil" olması, o tekniğin *tüm* uygulama varyantlarının yakalandığı anlamına gelmez. LSASS bellek dökümü yapmanın onlarca yolu vardır (comsvcs.dll MiniDump, doğrudan syscall, handle duplication, register dumping). Tek bir yöntemi yakalayan kural, hücreyi yeşile boyar ama gerçekte kapsamın küçük bir dilimini kaplar.

2. **Ateşleme yanılsaması (rule fires ≠ rule is good):** Kural loglarda görünür ama ya çok gürültülüdür (binlerce false positive, kimse bakmaz), ya çok dardır (tek bir komut satırı imzasına bağlıdır ve saldırgan bir boşluk/argüman değiştirince kaçar), ya da alarm hiçbir yere akmaz (SIEM'de kural aktif ama alerting pipeline'ı kopuk).

3. **Telemetri yanılsaması (blind spot):** Kural mantığı doğrudur ama beslendiği ham log **hiç toplanmıyordur.** Sysmon Event ID 10 (process access) kapalıysa, LSASS erişimini yakalayan kuralınız asla veri görmez. Kural mükemmeldir; gözü kördür.

Purple team, bu üç yanılsamayı da tek bir mekanizmayla kırar: **kontrollü, bilinen bir saldırıyı çalıştırıp beklenen telemetrinin ve alarmın gerçekten üretilip üretilmediğini gözlemlemek.** Bilinen girdi → beklenen çıktı. Bu, mühendislikte "unit test" ne ise güvenlik tespiti için de odur.

---

## Atomic Testing ve Tespit Kapsama Testi

### Atomic test nedir

**Atomic test**, tek bir ATT&CK tekniğini (veya alt tekniğini) izole biçimde, mümkün olan en küçük ve tekrarlanabilir eylemle çalıştıran test parçasıdır. "Atomic" (atomik) kelimesi buradan gelir: test bölünemez, tek bir davranışa odaklıdır. Bu alandaki en bilinen açık kaynak proje **Atomic Red Team**'dir; testleri MITRE ATT&CK tekniklerine göre indekslenmiş, YAML formatında tanımlanmış küçük eylemler halinde tutar. Yürütme motoru olarak **Invoke-AtomicRedTeam** (PowerShell) sıkça kullanılır.

Bir atomic testin kavramsal anatomisi şudur:
- **Teknik referansı:** hangi ATT&CK tekniğini simüle ediyor (ör. T1218 signed binary proxy execution).
- **Ön koşullar (prerequisites):** testin çalışması için gereken dosya/araç/ayar.
- **Yürütme adımı:** çalıştırılacak eylem (bir komut, bir script bloğu).
- **Temizlik (cleanup):** testin ortamda bıraktığı izleri geri alma komutları.

Atomic testin amacı sistemi *ele geçirmek değildir*; amacı **bilinen bir davranışın telemetride nasıl göründüğünü tetiklemektir.** Örneğin `mshta` ile uzak script çalıştırma davranışını simüle eden bir test, gerçekte zararlı bir yük indirmez; sadece o davranış zincirinin log ayak izini üretir ki savunmacı "bu görünüyor mu?" diye bakabilsin.

### Kapsama testi döngüsü

Tespit kapsama testinin temel döngüsü ("detection validation loop") şöyledir:

1. **Seç:** Bir ATT&CK tekniği ve onu temsil eden bir atomic test seçilir.
2. **Çalıştır:** Test kontrollü bir uç noktada (izole lab veya işaretlenmiş test hostu) çalıştırılır. Çalıştırma zamanı ve host **kesin olarak kaydedilir** — sonraki adımda "bu alarm bizim testimizden mi, gerçek bir olaydan mı?" ayrımını yapabilmek için.
3. **Gözle:** Beklenen üç şey aranır — (a) **ham telemetri** üretildi mi (log geldi mi), (b) **tespit kuralı** bu telemetriyle eşleşti mi, (c) **alarm** operatöre/SIEM'e ulaştı mı.
4. **Sınıfla:** Sonuç dört durumdan birine düşer (aşağıdaki matris).
5. **Onar:** Boşluk varsa telemetri açılır, kural yazılır/genişletilir, alerting düzeltilir.
6. **Yeniden çalıştır (regression):** Aynı test tekrar koşulur; artık yakalanıyorsa döngü kapanır.

### Tespit kapsama matrisi

Purple team'in en değerli çıktısı, tekniklerin bu dört durumdan hangisine düştüğünü gösteren bir tablodur. Kavramsal sınıflar:

| Durum | Anlamı | Örnek yorum |
|---|---|---|
| **Detected (Prevented/Alerted)** | Saldırı engellendi veya güvenilir alarm üretti | İdeal durum; regression testi için sabitlenir |
| **Logged (Telemetry only)** | Ham log var ama kural/alarm yok | En hızlı kazanç: veri elde, sadece kural yazılacak |
| **No Telemetry (Blind)** | İlgili log hiç toplanmıyor | Kör nokta: kural yazmadan önce loglama açılmalı |
| **Missed / Bypassed** | Kural var ama saldırı kaçtı | En tehlikeli yanılsama: kapsam "yeşil" sanılıyordu |

Bu matris, ham "yeşil/kırmızı" ATT&CK Navigator boyamasından daha zengindir çünkü **neden** yakalanamadığını da söyler. "Kör nokta"yı "kötü kural"dan ayırmak, düzeltme çabasını doğru yere yönlendirir: birinde loglama mühendisliği (Sysmon config, EDR politikası), diğerinde detection engineering (kural mantığı) gerekir.

---

## Tespit Boşluk Analizi (Detection Gap Analysis)

Boşluk analizi, "neyi yakalamadığımızı **sistematik** olarak bulma" sürecidir. İki farklı boşluk türü karıştırılmamalıdır:

**Yatay boşluk (breadth gap):** ATT&CK matrisinin hangi taktik/tekniklerine hiç dokunmadığınız. Örneğin Credential Access sütununda güçlüsünüz ama Defense Evasion sütunu neredeyse boş. Bu boşluk, tehdit istihbaratıyla önceliklendirilir: sizi hedefleyen tehdit gruplarının (threat actor) fiilen kullandığı teknikler öne alınır. Herkesin her tekniği kapsaması ne mümkün ne gereklidir; **tehdide dayalı önceliklendirme (threat-informed defense)** esastır.

**Dikey boşluk (depth gap):** Kapsadığınızı sandığınız bir teknik içindeki varyant boşluğu. T1003.001 (LSASS memory) için bir kuralınız var ama sadece `procdump.exe` argümanını yakalıyor; comsvcs MiniDump, taskmgr üzerinden dump, ya da doğrudan bellek okuma varyantları kaçıyor. Dikey boşluk, "prosedür çeşitliliği" (procedure variation) ile test edilir: aynı teknik için birden çok atomic varyant çalıştırılır ve kaçının yakalandığına bakılır.

Sağlam bir boşluk analizi ayrıca **brittleness (kırılganlık)** ölçer: bir kural ne kadar "dar imzaya" bağlı? Sabit bir dosya adına, tam bir komut satırı stringine, ya da belirli bir kullanıcı adına bağlı kurallar kırılgandır — saldırgan trivial bir değişiklikle (yeniden adlandırma, boşluk ekleme, encoding) kaçar. Dayanıklı (robust) kurallar davranışa bağlanır: "process X, parent Y altında, şu handle erişimini yaptı." Purple team, atomic testin argümanlarını kasıtlı olarak değiştirerek (fuzzing benzeri) kuralın ne kadar kolay atlatıldığını ölçer.

---

## Adversary Emulation Planlaması

Atomic testler tek teknikleri ölçer; ama gerçek bir saldırı bir **zincirdir** (kill chain). **Adversary emulation** (düşman taklidi), bilinen bir tehdit grubunun gerçek TTP'lerini (Tactics, Techniques, Procedures) **sıralı ve tutarlı bir senaryo** olarak, o grubun davranışına sadık kalacak şekilde yeniden canlandırmaktır.

Buradaki kritik ayrım:
- **Atomic testing:** izole tekniklerin nokta testi ("bu tuğla sağlam mı?").
- **Adversary emulation:** uçtan uca senaryo ("bu duvar, bu saldırı deseni karşısında ayakta mı?").

Emulation, izole testlerin gözden kaçırdığı bir şeyi yakalar: **korelasyon tespiti.** Tek başına "PowerShell çalıştı" alarmı gürültülüdür; ama "phishing eki açıldı → PowerShell → dış bağlantı → scheduled task → LSASS erişimi" zinciri, tek tek zayıf sinyalleri birleştirince güçlü bir tespit oluşturur. Emulation, bu korelasyon kurallarının ("bu sıra, bu zaman penceresinde görülürse alarm ver") çalışıp çalışmadığını test eder.

Emulation planlaması adımları (kavramsal):
1. **Tehdit seçimi:** Sektörünüzü/coğrafyanızı fiilen hedefleyen bir grup seçilir (cyber threat intelligence çıktısına dayalı).
2. **TTP çıkarımı:** Grubun bilinen davranışları ATT&CK teknik listesine dökülür. MITRE'nin **Adversary Emulation Plans** kütüphanesi (ör. CTID/Center for Threat-Informed Defense çıktıları) bu haritalamayı hazır sunabilir.
3. **Senaryo kurgusu:** Teknikler gerçekçi bir sıraya dizilir; initial access'ten actions-on-objective'e kadar bir anlatı kurulur.
4. **Kapsam ve güvenlik sınırları:** Hangi hostlar, hangi veri, hangi yıkıcı olmayan (non-destructive) eylemler — mutlaka yazılı rules of engagement (RoE).
5. **Yürütme ve gözlem:** Her adımda, o adımın karşılık gelmesi beklenen tespitin ateşlenip ateşlenmediği kaydedilir.

Önemli bir dürüstlük notu: emulation "grubu birebir taklit" iddiası taşıdığında, kullanılan TTP'lerin gerçekten o gruba ait olduğunun istihbarat kaynağıyla doğrulanması gerekir. Kaynağı belirsiz "şu grup şunu yapar" iddialarını senaryoya koymak, yanlış bir güvenlik hissi üretir. Emin olunmayan atıflar, "bu teknik genel olarak gözlenir" diye genel dille ifade edilmeli, uydurma atıf yapılmamalıdır.

---

## Breach-and-Attack Simulation (BAS)

**BAS** araçları, purple team döngüsünü **otomatikleştiren ve sürekli hale getiren** platformlardır. Manuel purple team egzersizi değerli ama pahalı ve seyrektir (çeyrekte bir). BAS, aynı doğrulama mantığını **planlı, tekrarlı, otomatik** biçimde koşarak "tespit yeteneğim bugün de dünkü kadar iyi mi?" sorusunu sürekli yanıtlar.

BAS'ın kavramsal çalışma mantığı:
- Bir **ajan** (agent) veya ajansız (agentless) mekanizma, hedef ortamda güvenli/simüle edilmiş saldırı eylemlerini çalıştırır.
- Eylemler bir **kütüphaneden** seçilir (ATT&CK'e eşlenmiş teknikler, tam senaryolar).
- Platform, eylemin engellenip engellenmediğini (prevention) ve/veya loglanıp alarm üretip üretmediğini (detection) **kendisi ölçer** ve bir skor kartı üretir.
- Sonuçlar zaman içinde izlenir: bir EDR güncellemesi bir tespiti bozduğunda (regression), BAS bunu bir sonraki koşuda yakalar.

BAS'ın atomic testing'e göre farkı, otomasyonun yanı sıra **ölçüm entegrasyonudur**: iyi bir BAS, sadece saldırıyı çalıştırmakla kalmaz, savunma yığınına (SIEM/EDR API) bağlanıp "bu alarm üretildi mi?" sorusunu programatik olarak doğrular. Bu, insan gözlemcinin "sanırım gördük" belirsizliğini ortadan kaldırır.

BAS'ın sınırları da dürüstçe belirtilmelidir:
- BAS eylemleri genellikle **güvenli/dişleri sökülmüş** (defanged) sürümlerdir; gerçek zararlının tüm ayak izini üretmeyebilir. Bir tespit BAS testini geçtiği halde gerçek malware'i kaçırabilir.
- BAS kütüphanesi ne kadar iyiyse doğrulama o kadar iyidir; kütüphanede olmayan teknik test edilmez (kapsamın kapsamı sorunu).
- BAS "yeşil skor" üretmeye teşvik ederse, kolay geçen testler eklenip skor şişirilebilir. Skor, kapsamın **derinliğiyle** birlikte okunmalıdır.

---

## Somut Örnek: Bir Kuralı Doğrulama Döngüsü

Diyelim ki savunmacısınız ve T1003.001 (LSASS Memory) için bir Sigma kuralı yazdınız. Kural, `lsass` sürecine `procdump` benzeri erişimi yakalıyor. Purple team döngüsü şöyle işler:

1. **İlk çalıştırma:** LSASS dump davranışını simüle eden bir atomic test çalıştırırsınız (kontrollü lab hostunda, işaretli). Beklenti: Sysmon EID 10 (process access, GrantedAccess bayrağı LSASS'a şüpheli erişim gösteren) → kural eşleşir → alarm.
2. **Gözlem:** Alarm geldi. İyi. Ama tek varyant test edildi.
3. **Varyant genişletme:** Aynı tekniğin farklı prosedürleriyle tekrar çalıştırırsınız — comsvcs MiniDump çağrısı, task manager üzerinden dump gibi. Bunlardan biri **alarm üretmez.** Dikey boşluk bulundu.
4. **Kök neden:** Kural, komut satırında `procdump` stringine bağlıymış (kırılgan imza). comsvcs yolu farklı bir process ve komut satırı ürettiği için kaçtı.
5. **Onarım:** Kuralı davranışa taşırsınız — komut satırı imzası yerine "lsass sürecine şu erişim maskesiyle handle açılması" davranışını yakalar hale getirirsiniz. Böylece prosedürden bağımsızlaşır.
6. **Regression:** Her iki varyantı da tekrar çalıştırırsınız; ikisi de artık yakalanıyor. Bu iki test, sürekli koşan test setine (BAS pipeline) eklenir.

Bu örnekte kritik ders: **"kural ateşledi" ilk çalıştırmada doğruydu ama kapsam sığdı.** Purple team olmadan bu boşluk, gerçek bir olayda comsvcs yolunu kullanan bir saldırganla karşılaşana kadar görünmez kalırdı.

---

## Tespit ve Savunma Perspektifi

Purple team'in kendisi zaten bir savunma faaliyeti olduğundan, buradaki "savunma" bölümü iki katmanlıdır: (a) purple team döngüsünün savunmayı nasıl güçlendirdiği, (b) purple team faaliyetinin **kendisinin** güvenli yürütülmesi.

**Savunmayı güçlendiren pratikler:**
- **Detection-as-code:** Tespit kuralları versiyon kontrolünde (Git) tutulur, her kural bir atomic test ile eşleştirilir. Kural değiştikçe test otomatik koşar (CI benzeri). Bu, "kural bozuldu ama kimse fark etmedi" regresyonlarını engeller.
- **Telemetri temelinin doğrulanması:** Kural yazmadan önce ilgili loglama kaynağının (Sysmon, EDR, cloud audit log) fiilen aktığı doğrulanır. "No Telemetry" durumu her zaman kural sorunundan önce çözülmelidir.
- **Kapsamı derinlikle ölçmek:** ATT&CK Navigator'da hücreyi yeşile boyamadan önce, o teknik için **kaç prosedür varyantının** yakalandığı not edilir. Tek varyant = "sığ yeşil."
- **Korelasyon tespitleri:** Emulation senaryolarından çıkan zincir tespitleri, tek teknik alarmlarının gürültüsünü azaltır ve gerçek saldırı desenlerini yakalar.

**Purple team faaliyetinin kendini koruması (operasyonel güvenlik):**
- **İşaretleme (deconfliction):** Her test eylemi, gerçek olaydan ayrılabilecek şekilde işaretlenir (bilinen kaynak IP, test kullanıcı, zaman damgası logu). Aksi halde SOC ekibi purple team testini gerçek ihlal sanıp panik müdahale başlatır, ya da tersine gerçek bir saldırıyı "herhalde purple team'dir" diye görmezden gelir. İkincisi felakettir.
- **Non-destructive kısıt:** Test eylemleri geri alınabilir ve zarar vermez olmalı; cleanup adımları çalıştırılıp doğrulanmalı.
- **İzole ortam tercihi:** Yeni/riskli testler önce lab veya sandbox'ta koşulur; üretim ortamına ancak etkisi bilindiğinde geçirilir.
- **Yetki ve kapsam yazılı olmalı (RoE):** Hangi sistem, hangi zaman, hangi eylem — yazılı onaya bağlanmalı.

---

## Yaygın Hatalar

- **"Yeşil hücre = kapsandı" yanılgısı:** ATT&CK Navigator'ı tek varyara dayanarak boyamak. Kapsam derinliğini ölçmeden yeşile boyanan matris, gerçekte kırmızı olan boşlukları gizler.
- **Telemetriyi doğrulamadan kural yazmak:** Beslendiği log gelmeyen mükemmel kural, sessiz bir kör noktadır. Önce veri, sonra kural.
- **Kırılgan imzalara güvenmek:** Sabit dosya adı/komut satırı stringine bağlı kurallar, saldırganın en küçük değişikliğiyle kaçar. Davranış temelli tespit tercih edilmelidir.
- **Deconfliction atlanması:** Test eylemlerini işaretlememek, hem yanlış paniğe hem de gerçek saldırının gözden kaçmasına yol açar. Bu, purple team'in en tehlikeli operasyonel hatasıdır.
- **BAS skorunu mutlak gerçek sanmak:** "Skor %92, savunmam mükemmel" demek. BAS defanged eylemler kullanır ve kütüphanesiyle sınırlıdır; skor bir gösterge, kanıt değildir.
- **Cleanup'ı ihmal etmek:** Test artıklarının (dosya, kayıt defteri anahtarı, kullanıcı) ortamda kalması, hem gelecekteki testleri kirletir hem de yanlış alarmlar üretir.
- **Emulation'da uydurma atıf:** "Bu grup şunu yapar" iddialarını doğrulanmamış istihbaratla senaryoya koymak, yanlış güvenlik hissi üretir. Atıf belirsizse teknik genel dille test edilmeli.
- **Regression'ı unutmak:** Bir kuralı düzeltip bir daha hiç test etmemek. EDR/OS güncellemeleri tespitleri sessizce bozabilir; sürekli koşan test seti şarttır.
- **Tek seferlik egzersiz zihniyeti:** Purple team'i yılda bir "olay" gibi görmek. Değer, döngünün **sürekliliğinden** gelir; tek atış bir anlık fotoğraftır, tehdit ortamı ise sürekli değişir.

---

## Özet

Purple team operasyonları, "saldırı" ile "savunma"yı bir ölçüm döngüsü içinde birleştirir. Atomic testing tek teknikleri nokta atışı doğrular; adversary emulation bunları gerçekçi zincirlere dizip korelasyon tespitlerini sınar; tespit kapsama matrisi neyin yakalandığını ve **neden yakalanmadığını** (kör nokta mı, kötü kural mı) ayırır; boşluk analizi hem yatay (hangi teknikler) hem dikey (hangi varyantlar) eksikleri sistematik bulur; BAS araçları tüm bu döngüyü sürekli ve otomatik hale getirir. Merkezi soru hep aynıdır: *"Yazdığım kural gerçekten çalışıyor mu?"* — ve bu soru ancak bilinen bir saldırıyı çalıştırıp beklenen telemetriyi ve alarmı **gözlemleyerek** yanıtlanır. İyi bir purple team programı bir rapor değil, sürekli koşan, dürüstçe ölçen ve düzeltmeyi geri besleyen yaşayan bir sistemdir.
