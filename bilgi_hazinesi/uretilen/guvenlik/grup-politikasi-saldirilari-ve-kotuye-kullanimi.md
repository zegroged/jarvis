# Grup Politikası (GPO) Saldırıları ve Kötüye Kullanımı

## Tanım ve Kapsam

**Group Policy** (Grup Politikası), Active Directory (AD) ortamlarında yöneticilerin binlerce bilgisayar ve kullanıcı üzerinde ayarları merkezî olarak dağıtmasını sağlayan bir mekanizmadır. Bir **Group Policy Object (GPO)**, uygulanacak ayarların (güvenlik politikaları, kayıt defteri anahtarları, çalıştırılacak script'ler, kurulacak yazılımlar, zamanlanmış görevler vb.) taşıyıcısıdır. GPO'lar **Organizational Unit (OU)**, domain veya site düzeyine **link** edilir; bağlandıkları kapsamdaki nesneler politikayı otomatik olarak çeker ve uygular.

Bu merkezîlik, GPO'yu savunma açısından güçlü ama saldırgan açısından son derece cazip kılar: **Tek bir yazılabilir GPO üzerinde kontrol elde eden bir saldırgan, o GPO'nun bağlı olduğu tüm makinelerde kod çalıştırabilir.** Bu nedenle GPO kötüye kullanımı, AD ortamlarında en etkili **lateral movement** (yanal geçiş), **privilege escalation** (yetki yükseltme) ve **persistence** (kalıcılık) vektörlerinden biridir. Ayrıca GPO altyapısının depolandığı **SYSVOL** paylaşımı, tarihsel olarak (özellikle eski **Group Policy Preferences / GPP** parolaları nedeniyle) kimlik bilgisi sızıntısına yol açmıştır.

Bu makale mekanizmanın nasıl çalıştığını, hangi kötüye kullanım desenlerinin mümkün olduğunu ve en önemlisi **bunları nasıl tespit edip savunacağınızı** ele alır. Amaç kavramsal anlayış ve savunma inşasıdır.

## GPO'nun İki Parçalı Mimarisi (Kök Neden)

GPO kötüye kullanımını anlamak için önce bir GPO'nun fiziksel olarak nerede yaşadığını bilmek gerekir. Her GPO iki ayrı bileşenden oluşur:

- **Group Policy Container (GPC):** AD dizininde (`CN=Policies,CN=System,DC=...`) tutulan nesne. GPO'nun metadata'sını, sürüm numarasını ve hangi tarafların (Computer/User) etkin olduğunu içerir. GPO'nun benzersiz kimliği bir **GUID**'dir.
- **Group Policy Template (GPT):** Domain Controller'ların **SYSVOL** paylaşımında (`\\<domain>\SYSVOL\<domain>\Policies\{GUID}\`) tutulan dosya tabanlı kısım. Asıl ayar dosyaları burada yaşar: `GPT.ini`, `Registry.pol`, script'ler (`Scripts\Startup`, `Scripts\Logon`), tercih dosyaları (`Preferences\...\*.xml`), zamanlanmış görev tanımları vb.

Bu iki parçalı yapı iki temel güvenlik sonucunu doğurur:

1. **SYSVOL, domaindeki her authenticated user tarafından okunabilir.** Bir GPO'nun içeriğini görmek için özel yetki gerekmez; kimliği doğrulanmış herhangi bir kullanıcı `\\domain\SYSVOL` altındaki tüm politika dosyalarını okuyabilir. Bu, içine gömülmüş sırların (parolalar, script içerikleri) herkese açık olduğu anlamına gelir.
2. **GPO'ya yazma yetkisi, hem GPC (AD nesnesi) hem GPT (SYSVOL dosyaları) üzerinde değişiklik yapabilmeye açılır.** Saldırgan yeni bir startup script'i ekleyebilir, bir scheduled task tanımlayabilir veya kayıt defteri ayarını değiştirebilir; ardından GPC'deki **versionNumber** alanını artırarak istemcileri politikayı yeniden çekmeye zorlayabilir.

### Politika Nasıl Uygulanır?

İstemci makineler GPO'ları periyodik olarak (varsayılan yaklaşık 90 dakikada bir, rastgele bir kayma ile) ve yeniden başlatma/oturum açma anlarında yeniler. İstemci, bağlı olduğu her GPO'nun GUID'ini ve sürüm numarasını okur; sürüm arttıysa GPT'deki yeni ayarları indirip **Client-Side Extension (CSE)** modülleri aracılığıyla uygular. Örneğin script'ler bir CSE ile, kayıt defteri ayarları başka bir CSE ile, tercihler (Preferences) yine ayrı bir CSE ile işlenir.

**Kritik nokta:** Computer configuration (bilgisayar yapılandırması) altındaki ayarlar, o makinenin **SYSTEM** bağlamında çalışır. Yani bir saldırgan Computer tarafına zararlı bir startup script'i veya scheduled task eklerse, kodu hedef makinede **NT AUTHORITY\SYSTEM** olarak yürütür. Bu, GPO kötüye kullanımını neden bu kadar güçlü bir privilege escalation aracı yaptığının özüdür.

## Kötüye Kullanım Vektörleri

### 1. Yazılabilir GPO'ya Kod Enjeksiyonu

En yaygın senaryo, saldırganın **belirli bir GPO üzerinde yazma izni (write access)** elde etmesidir. Bu izin genellikle yanlış yapılandırılmış delegasyondan gelir: bir GPO'nun ACL'inde geniş bir gruba (örneğin bir yardım masası ekibine, hatta yanlışlıkla `Authenticated Users`'a) `WriteDacl`, `WriteOwner`, `GenericWrite` veya `GenericAll` gibi hakların verilmiş olması.

Saldırgan bu yazma iznine sahip olduğunda tipik olarak şunlardan birini yapar:

- **Immediate Scheduled Task ekleme:** GPO'nun Preferences kısmına, tetiklenir tetiklenmez çalışacak bir scheduled task tanımı (`ScheduledTasks.xml`) enjekte eder. Bu görev, saldırganın seçtiği bir komutu SYSTEM olarak çalıştırır.
- **Startup/Logon script ekleme:** GPT'nin `Scripts` klasörüne bir betik koyar ve `GPT.ini`/`scripts.ini` içinde onu referanslar.
- **Kayıt defteri veya kullanıcı ekleme:** Yerel bir yönetici hesabı ekleyen ya da güvenlik ayarını zayıflatan bir Preferences öğesi tanımlar.

Ardından GPC üzerindeki sürüm numarasını artırır. Bağlı tüm makineler bir sonraki yenileme döngüsünde (veya yeniden başlatmada) zararlı öğeyi çeker ve uygular. Bu tekniği kolaylaştıran açık kaynak araçlar (kavramsal olarak "GPO'ya immediate task ekleyip sürümü bump eden" yardımcılar) mevcuttur; savunmacı, bunların ürettiği **artefaktları** tanımaya odaklanmalıdır.

**Etki çarpanı:** Eğer bu GPO **Domain Controllers OU**'suna bağlı bir politikaysa veya çok sayıda sunucuya link'liyse, tek bir yazma izni domain çapında ele geçirmeye dönüşebilir. BloodHound gibi grafik analiz araçlarının "GPO -> OU -> Computers" ilişkisini haritalayıp saldırı yollarını göstermesinin nedeni budur.

### 2. GPO Link'i Üzerinden Kötüye Kullanım

GPO içeriğine yazma izni olmasa bile, bir saldırgan bir **OU üzerinde link yönetme yetkisine** (OU'nun `gPLink` özniteliğini yazma) sahipse, kendi kontrolündeki zararlı bir GPO'yu hedef OU'ya bağlayarak aynı sonucu elde edebilir. Yani saldırı iki farklı ACL zayıflığından beslenebilir: **GPO nesnesinin kendisi üzerinde yazma** veya **hedef OU üzerinde link ekleme** hakkı.

### 3. SYSVOL Üzerinden Kimlik Bilgisi Sızması (GPP Parolaları)

Bu, tarihsel olarak en meşhur GPO zafiyetidir. **Group Policy Preferences (GPP)**, yöneticilerin GPO aracılığıyla yerel kullanıcı hesapları oluşturmasına, yerel yönetici parolasını ayarlamasına, eşlenmiş sürücüler ve zamanlanmış görevler için kimlik bilgisi tanımlamasına olanak tanıyordu. Bu ayarlar SYSVOL'deki XML dosyalarına (`Groups.xml`, `Services.xml`, `ScheduledTasks.xml`, `DataSources.xml`, `Drives.xml` gibi) yazılır.

Sorun şuydu: Bu XML dosyalarındaki parola, `cpassword` adlı bir alanda **AES ile şifrelenmiş** olarak saklanıyordu — ancak şifreleme anahtarı Microsoft tarafından **kamuya açık olarak yayımlanmıştı**. Yani `cpassword` değerini elde eden herkes onu önemsiz biçimde çözebilir. SYSVOL her authenticated user tarafından okunabildiğinden, düşük yetkili bir saldırgan tüm SYSVOL'ü tarayıp `cpassword` içeren dosyaları bulabilir ve genellikle bir yerel yönetici parolası ele geçirebilir.

Microsoft bu özelliği **MS14-025** ile (2014) devre dışı bırakan bir yama yayımladı: yeni GPP parolası oluşturmayı engelledi. **Ancak** bu yama, önceden oluşturulmuş XML dosyalarındaki mevcut `cpassword` değerlerini **geriye dönük silmez**. Bu yüzden bugün bile yaşı ilerlemiş domainlerde SYSVOL taraması eski `cpassword` artıklarını ortaya çıkarabilir. Bu, "eski bir zafiyet ama hâlâ pratikte bol miktarda karşılaşılan" klasik bir örnektir.

> **Not (dürüstlük):** GPP `cpassword` çözümünün mümkün olduğu ve MS14-025'in yeni parola oluşturmayı engellediği doğrulanmış temel bilgilerdir. Belirli bir domaindeki artık dosyaların varlığı ise ancak tarama ile teyit edilir; varsaymak yerine denetlemek gerekir.

### 4. GPO Üzerinden Kalıcılık (Persistence)

Domain'de zaten yüksek yetki (örneğin Domain Admin) elde etmiş bir saldırgan, GPO'yu bir **kalıcılık** aracı olarak kullanabilir: geniş kapsamlı bir GPO'ya, düzenli aralıklarla bir C2 bağlantısı kuran bir scheduled task ya da yerel yönetici grubuna gizli bir hesap ekleyen bir Preferences öğesi yerleştirir. Bu, tek bir makineye backdoor koymaktan çok daha dayanıklıdır: politika kapsamındaki tüm makineler enfeksiyonu sürekli yeniden uygular, temizlenen bir makine bir sonraki yenilemede yeniden ele geçirilir. Bu yüzden IR (olay müdahale) ekipleri bir domain ihlalinde **GPO'ları da mutlaka denetlemelidir** — sadece uç noktaları temizlemek yetmez.

## Somut Örnek (Kavramsal Akış)

Aşağıdaki akış, savunmacının hangi olay zincirini beklemesi gerektiğini göstermek içindir (canlı saldırı reçetesi değil):

1. Saldırgan düşük yetkili bir domain hesabıyla oturum açar ve **BloodHound** ile grafiği toplar. Grafik, kontrol ettiği hesabın "HelpDesk" grubuna, o grubun da "Workstations-Policy" adlı GPO üzerinde `GenericWrite` hakkına sahip olduğunu gösterir. Bu GPO 400 iş istasyonuna bağlıdır.
2. Saldırgan bu GPO'ya, Computer configuration tarafına, tetiklendiğinde SYSTEM olarak çalışacak bir **immediate scheduled task** enjekte eder ve GPC sürüm numarasını artırır.
3. İş istasyonları bir sonraki yenileme döngüsünde politikayı çeker; scheduled task her makinede SYSTEM olarak çalışır ve saldırgana 400 makinede eşzamanlı erişim sağlar.
4. Saldırgan artefaktı GPO'dan siler; ancak SYSVOL değişikliği, GPC sürüm artışı ve makinelerdeki task oluşturma olayları geride iz bırakmıştır.

Bu akışın her adımı, doğru telemetri ile tespit edilebilir bir sinyal üretir.

## Tespit (Detection)

GPO kötüye kullanımının tespiti üç katmanda yürür: **AD nesne değişiklikleri**, **SYSVOL dosya değişiklikleri** ve **istemci tarafı yürütme artefaktları**.

### AD Katmanı — GPO Nesne Değişiklikleri

- **Dizin nesnesi değişikliği denetimi (directory service changes auditing)** ile GPC nesnelerinde (`CN=Policies` altında) yapılan değişiklikleri loglayın. Windows Security log'unda GPO ile ilişkili nesnelerde değişiklik olduğunda üretilen olaylara (tipik olarak **4662** — "An operation was performed on an object" ve dizin değişikliği olayları) odaklanın. Beklenmedik bir hesabın bir GPO'yu değiştirmesi güçlü bir sinyaldir.
- **ACL değişikliklerini** izleyin: bir GPO'nun DACL'inde yeni bir yazma hakkının belirmesi (özellikle geniş gruplara). Bu, hem saldırgan kurulum adımı hem de yanlış yapılandırma tespiti için kritiktir.
- **`gPLink` değişikliklerini** izleyin: bir OU'ya yeni bir GPO bağlanması, özellikle hassas OU'lara (Domain Controllers, sunucu OU'ları), incelenmelidir.

### SYSVOL Katmanı — Dosya Değişiklikleri

- **SYSVOL'de dosya bütünlüğü izleme (File Integrity Monitoring / FIM):** `\\domain\SYSVOL\...\Policies\` altında yeni script dosyaları, yeni/değişen `ScheduledTasks.xml`, `Registry.pol` değişiklikleri ve `GPT.ini` sürüm artışları izlenmelidir. Yetkili değişiklik pencereleri dışındaki değişiklikler alarm üretmelidir.
- **`cpassword` avı:** SYSVOL genelinde periyodik olarak `cpassword` string'ini içeren XML dosyalarını tarayın. Bulunan her örnek hem bir zafiyet (parolayı derhal değiştirin/kaldırın) hem de olası bir sızıntı işaretidir. Bu tarama, mavi takımın rutin higyeninin parçası olmalıdır.

### İstemci Katmanı — Yürütme Artefaktları

- **Scheduled task oluşturma olayları:** Task Scheduler operational log'undaki görev kayıt olayları (örneğin **4698** — "A scheduled task was created" güvenlik olayı ve TaskScheduler operational olayları) izlenmelidir. GPO kaynaklı, kısa ömürlü, SYSTEM bağlamında komut çalıştıran görevler şüphelidir.
- **Süreç oluşturma soyağacı:** GPO CSE'lerini işleyen süreçlerden (örneğin `gpscript.exe` startup/logon script'lerini yürütür) türeyen `cmd.exe`, `powershell.exe`, `wscript.exe` gibi süreçler dikkatle incelenmelidir. Bir startup script'inin ardından beklenmedik bir yorumlayıcı ve ağ bağlantısı gelmesi güçlü bir davranışsal sinyaldir. **Sysmon Event ID 1** (process create) ile bu soyağaçları yakalanabilir.
- **Yeni yerel yönetici hesabı:** GPP/Preferences ile eklenen yerel hesaplar için yerel hesap oluşturma olaylarını (örneğin **4720**) ve yerel yönetici grubu üyelik değişikliklerini (**4732**) izleyin.

### Yapısal (Proaktif) Tespit

Reaktif log takibine ek olarak, **BloodHound benzeri grafik analizi** düzenli olarak mavi takım tarafından da çalıştırılmalıdır. "Hangi düşük yetkili prensipaller hangi GPO'lara yazabiliyor ve o GPO'lar nereye bağlı?" sorusunun cevabı, saldırgan bulmadan önce bu yolları görmenizi sağlar. Bu, tespitin en değerli biçimidir: saldırı gerçekleşmeden önce **saldırı yüzeyini** kapatmak.

## Savunma (Hardening)

- **GPO delegasyonunu en az yetki ilkesiyle sıkılaştırın.** Bir GPO'yu kimin düzenleyebileceğini gözden geçirin; `Authenticated Users` veya geniş operasyonel gruplara verilmiş `WriteDacl`/`WriteOwner`/`GenericWrite`/`GenericAll` haklarını kaldırın. GPO düzenleme yetkisi, kimlik değeri açısından **Tier 0** (domain yönetimi) sınıfında ele alınmalıdır.
- **Tiering (katmanlama) modelini uygulayın.** Domain Controller ve Tier 0 sistemlerine bağlı GPO'ları yalnızca en yüksek güven düzeyindeki yöneticilerin değiştirebilmesini sağlayın. `gPLink` yazma yetkisini hassas OU'larda kısıtlayın.
- **Eski GPP `cpassword` artıklarını temizleyin.** MS14-025 yeni parola oluşturmayı engellese de eski XML'leri silmez. SYSVOL'ü tarayıp `cpassword` içeren tüm dosyaları bulun, ilgili parolaları rotasyona sokun ve dosyaları kaldırın. Yerel yönetici parolalarını GPP yerine **LAPS** (Local Administrator Password Solution) ile yönetin — LAPS her makineye benzersiz, otomatik rotasyonlu bir yerel yönetici parolası sağlar ve `cpassword` sınıfı sızıntıyı kökten ortadan kaldırır.
- **SYSVOL değişikliklerini merkezî olarak denetleyin.** FIM + SIEM entegrasyonu ile SYSVOL politikalarındaki her değişikliği yetkili bir change ticket'ına eşleyin. Eşleşmeyen değişiklikler soruşturulmalıdır.
- **GPO değişiklik yönetimi süreci kurun.** Kim, ne zaman, hangi gerekçeyle GPO değiştirdi kaydını tutan bir onay/değişiklik iş akışı, hem hesap verebilirlik hem de "beklenmedik değişiklik" tespiti için temeldir.
- **Client-Side Extension davranışını sınırlayın.** Bazı ortamlarda, startup script'lerinin veya belirli Preferences türlerinin kullanımına dair politikalar (ve bunların loglanması) uygulanabilir; ihtiyaç duyulmayan CSE davranışlarını asgariye indirmek saldırı yüzeyini daraltır.
- **İhlal sonrası GPO denetimi refleksi.** Bir domain ele geçirmesi şüphesinde, uç nokta temizliğinin yanı sıra tüm GPO'ları (özellikle scheduled task ve script içeren tercihleri) mutlaka gözden geçirin. GPO tabanlı kalıcılık atlanırsa temizlik eksik kalır.

## Yaygın Hatalar ve Yanlış Anlamalar

- **"SYSVOL zaten korumalı, oradaki dosyalar güvenli."** Yanlış. SYSVOL, tasarımı gereği tüm authenticated user'lar tarafından okunabilir; içine gömülen hiçbir sır gizli değildir. GPP `cpassword` felaketinin kökü tam olarak budur.
- **"MS14-025 yamasını uyguladık, GPP parola sorunu bitti."** Yama yalnızca **yeni** parola oluşturmayı engeller; **mevcut** `cpassword` artıklarını temizlemez. Yama sonrası da SYSVOL taraması gereklidir.
- **"GPO'yu sadece Domain Admin değiştirebilir."** Gerçekte delegasyon çok yaygındır ve zamanla birikmiş ACL'ler geniş gruplara yazma hakkı verebilir. Varsayım yerine ACL denetimi şarttır.
- **"GPO değişikliğini geri aldım, iş bitti."** Saldırgan zararlı öğeyi enjekte edip istemciler onu çektikten sonra artefaktı silse bile, kod hedef makinelerde çoktan çalışmış ve olası kalıcılık (yeni hesap, ayrı bir task) kurulmuş olabilir. GPO'yu temizlemek, uç noktaları temizlemenin yerini tutmaz.
- **Computer vs. User bağlamını karıştırmak.** Computer configuration ayarları makinede **SYSTEM** olarak çalışır — yetki yükseltme etkisi buradan gelir. Bu ayrımı gözden kaçırmak, tehdit modellemesinde ciddi bir eksikliğe yol açar.
- **Yalnızca reaktif log takibine güvenmek.** GPO saldırı yollarının çoğu, bir olay üretmeden önce yapısal olarak (yanlış delegasyon) zaten mevcuttur. Grafik tabanlı proaktif analiz olmadan, savunma her zaman bir adım geride kalır.

## Özet

GPO, AD'nin merkezî yönetim gücünün hem kaynağı hem de en keskin çift taraflı bıçağıdır. Tek bir yazılabilir GPO, çok sayıda makinede SYSTEM düzeyinde kod yürütmeye açılır; SYSVOL'ün açık okunabilirliği tarihsel `cpassword` sızıntılarını doğurmuştur; ve GPO tabanlı kalıcılık, domain ihlallerinde sıkça atlanan dayanıklı bir dayanaktır. Savunmanın özü üç ilkedir: **delegasyonu en az yetkiyle sıkılaştırmak** (özellikle Tier 0 GPO'ları), **SYSVOL ve GPO nesne değişikliklerini bütünlük izleme + denetim ile görünür kılmak**, ve **eski GPP artıklarını temizleyip LAPS'a geçmek**. Buna proaktif grafik analizi eklendiğinde, saldırgan yolu bulmadan önce kapatılabilir.
