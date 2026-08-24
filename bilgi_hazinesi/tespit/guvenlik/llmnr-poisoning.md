# LLMNR/NBT-NS Poisoning — Tespit Odaklı Derinlemesine İnceleme

> "Hırsızı tanımadan mücevheri koruyamazsın." Önce saldırganın LLMNR/NBT-NS
> zehirlemesini kavramsal olarak nasıl istismar ettiğini anlayacağız; sonra bu
> davranışın bir Windows ortamında bıraktığı izleri, gerçek Sigma kurallarına
> demirlenmiş tespit mantığıyla avlayacağız. Bu metin savunma ve tespit amaçlıdır;
> adım adım canlı saldırı reçetesi değildir.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Bir Windows istemcisi bir isim çözmek istediğinde katı bir sıra izler. Önce
`hosts` dosyasına bakar, sonra DNS'e sorar. DNS bir yanıt döndüremezse — yani
istenen ad DNS'te yoksa — istemci **fallback (yedek) isim çözümleme**
protokollerine döner: **LLMNR (Link-Local Multicast Name Resolution, UDP 5355)**
ve onun daha eski akrabası **NBT-NS (NetBIOS Name Service, UDP 137)**. Bu iki
protokolün ortak zaafı şudur: sorgu, tek bir otoriteye sorulmaz; **yerel ağ
segmentine multicast/broadcast olarak yayılır** ve "bu adı kim tanıyor?" diye
herkese seslenir. Protokolde kimlik doğrulama yoktur; ilk cevap veren "doğru"
kabul edilir.

Saldırganın istismar ettiği kavramsal boşluk tam buradadır. Saldırgan, aynı ağ
segmentinde pasif olarak dinler. Bir kurban makine, var olmayan ya da yanlış
yazılmış bir ada (`\\fileserv01` yerine `\\fileserv0`, kapanmış bir paylaşım,
otomatik bağlanmaya çalışan bir yazıcı yolu, tarayıcı arama eki vb.) çözüm
ararken DNS başarısız olur ve makine çaresizce LLMNR/NBT-NS ile "bu adı bilen var
mı?" diye bağırır. Saldırgan bu çağrıya **"evet, o benim, IP adresim şu" diye
sahte bir yanıt** döndürür. Kurban, hiçbir doğrulama yapmadan saldırganın
makinesine bağlanmaya başlar.

Kritik nokta bir sonraki adımdadır. Kurban, sahte "sunucuya" bir SMB/HTTP
bağlantısı kurunca, Windows'un varsayılan davranışı olarak **kullanıcının
kimliğini otomatik olarak sunmaya** çalışır — yani NTLM kimlik doğrulama
el sıkışmasını başlatır. Saldırgan bu el sıkışmasında bir **challenge** gönderir,
kurban da kullanıcının parola karmasından türetilmiş bir **NetNTLMv1/v2 response**
üretip geri yollar. Saldırgan artık elinde bir **kimlik doğrulama karması**
tutmaktadır. Bu karma iki şekilde silahlandırılır:

- **Offline kırma (cracking):** NetNTLMv2 karması ele geçirilip çevrimdışı
  kaba-kuvvet/sözlük saldırısıyla kullanıcının açık parolasına dönüştürülmeye
  çalışılır.
- **NTLM Relay:** Karma hiç kırılmadan, canlı canlı başka bir hedefe (SMB imzası
  zorunlu olmayan bir sunucuya, LDAP'a, ADCS'ye) **yeniden iletilir (relay)** ve
  o hedefte kurbanın yetkileriyle oturum açılır. Bu, LLMNR zehirlemesinin
  privilege escalation ve lateral movement'a köprü kurduğu yoldur.

Özetle saldırgan yeni bir zafiyet sömürmez; **protokolün tasarımındaki güveni ve
istemcinin otomatik kimlik sunma davranışını** istismar eder. Savunma açısından
bu bize iki avlanma yüzeyi verir: (a) ağ üzerinde sahte isim yanıtlarının kendisi,
(b) saldırganın makinesinde çalışan **hacktool'lar** (Responder, Inveigh gibi) ve
relay sonrası oluşan izler.

Bir noktayı vurgulamak, tespit stratejisini şekillendirir: saldırganın en büyük
avantajı **pasifliktir**. Zehirleme çoğu zaman "aktif" bir tarama gerektirmez;
saldırgan sadece dinler ve ağın kendisinin ürettiği hatalı isim sorgularının
kapıya gelmesini bekler. Bu, geleneksel port taraması / brute-force temelli
tespitlerin bu tekniği kaçırdığı anlamına gelir. Bu yüzden savunmacı, saldırganın
**yanıt verme** anındaki davranışına ve toplanan karmayı silahlandırdığı sonraki
aşamalara odaklanmalıdır. Bir başka deyişle: zehirlemenin "dinleme" kısmı
neredeyse görünmezdir; ama "yanıt verme" ve "karmayı kullanma" kısımları bol iz
bırakır. Tespit mühendisliği bu iki gürültülü halkaya kurulur.

Zamanlama boyutu da önemlidir. Zehirleme fırsatı, kurbanın DNS'in başarısız
olduğu ve fallback'e düştüğü **milisaniyelik pencerede** doğar. Kurumsal ağlarda
bu pencereleri tetikleyen tipik senaryolar şunlardır: kullanıcının yanlış
yazdığı UNC yolları, kapatılmış ama GPO/kısayolda kalmış eski sunucu adları,
otomatik bağlanmaya çalışan haritalanmış sürücüler, web proxy auto-discovery
(WPAD) sorguları ve yazıcı bulma trafiği. Saldırgan için her başarısız DNS
çözümü bir hasat fırsatıdır; savunmacı için ise her tutarlı LLMNR/NBT-NS yanıtı
bir av işaretidir.

---

## 2. Bıraktığı izler / artefaktlar

Teknik "sessiz" görünse de, hem ağ hem endpoint tarafında bol iz bırakır. Tespiti
bu izlere yaslayacağımız için somut olarak sıralayalım.

### Ağ düzeyi izler
- **UDP 5355 (LLMNR)** ve **UDP 137 (NBT-NS)** üzerinde anormal yoğunlukta yanıt
  trafiği. Normal ortamda istemciler çokça *sorgu* yayınlar; ancak tek bir
  makinenin sürekli ve tutarlı biçimde **yanıt** vermesi anomalidir.
- Aynı isim sorgusuna hem meşru bir kaynaktan hem de beklenmedik bir host'tan
  yanıt gelmesi (yarış/çakışma).
- **Multicast 224.0.0.252** (LLMNR) trafiğine bir host'un sürekli cevap üretmesi.
- Zehirlemenin ardından kurban → saldırgan yönünde beklenmedik **SMB (TCP 445)**
  ve/veya **HTTP (TCP 80)** kimlik doğrulama oturumları.

### Windows Event Log izleri
- **Security 4624 / 4625** (logon başarılı/başarısız): Relay ya da kırma denemesi
  sonrası, kaynağı olmayan/beklenmedik makinelerden gelen **NTLM (Package Name:
  NTLM V1/V2)** logon olayları. Özellikle `LogonType 3` (network) ve
  `Authentication Package: NTLM` alanları.
- **Security 4648** (explicit credential kullanımı): Relay senaryolarında
  belirebilir.
- Kurban tarafında **başarısız isim çözümü** sonrası fallback'e düşüşü gösteren
  DNS Client (`Microsoft-Windows-DNS-Client/Operational`) olayları — DNS
  çözemedi, ardından LLMNR/NBT-NS devreye girdi deseni.
- **Sysmon** varsa en zengin kaynak:
  - **Event ID 1 (process_creation):** Saldırganın makinesinde `Responder.py`,
    `Responder.exe`, `Inveigh` gibi araçların çalıştırılması; ya da relay
    araçlarının süreç adı/komut satırı.
  - **Event ID 3 (network_connection):** UDP 5355/137 dinleme, 224.0.0.252
    multicast bağlantıları, beklenmedik 445/80 bağlantıları.
  - **Event ID 8 (create_remote_thread):** Relay sonrası enjeksiyon/exec
    zincirlerinde alışılmadık kaynak süreçlerin uzak thread oluşturması.
  - **Event ID 11 (file_create):** Toplanan karmaların dökümü, log/çıktı
    dosyaları.

### Endpoint / araç imzaları ve komut satırı desenleri
- **Antivirüs alarmları:** Responder, Inveigh, ntlmrelayx (Impacket), PetitPotam,
  Potato ailesi gibi araçlar birçok AV motorunda **hacktool** olarak sınıflanır
  (`HKTL/`, `HTOOL/`, `ATK/`, `PWS.` gibi imza önekleri).
- Komut satırında `-I <iface>`, `--lm`, `--disable-ess`, `relay`, `-t
  ldap://`, `-smb2support` gibi araç parametrelerinin izleri.
- **Credential dumping** izleri (zehirleme başarılı olup lateral movement'a
  dönerse ikincil aşama): `lsass` süreci üzerinde `Get-Process`, `esentutl.exe`
  ile hassas dosya kopyalama, `ntds.dit`/SAM erişimi.
- Registry: LLMNR/NBT-NS'nin ortamda **açık** kalmış olması zafiyet göstergesidir
  (`HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient` altında
  `EnableMulticast` ayarının olmaması/1 olması). Bu bir saldırı izi değil ama
  saldırı yüzeyi göstergesidir ve tespit hijyeninin parçasıdır.

### İzlerin okunma sırası (triage mantığı)
Bir analistin bu izleri hangi sırayla okuması gerektiği tespitin kalitesini
belirler. Pratik bir triage sırası şöyledir:
1. **Endpoint hacktool imzası mı var?** AV alarmı ya da Sysmon Event ID 1'de
   Responder/Inveigh/relay araç adı — en yüksek güven, en hızlı doğrulama.
2. **Ağda tutarlı yanıtlayıcı var mı?** UDP 5355/137 üzerinde tek bir host'un
   sürekli yanıt üretmesi — zehirleyicinin konumunu ifşa eder.
3. **NTLM logon anomalisi var mı?** Security 4624/4625'te beklenmedik kaynaktan,
   kısa pencerede çok hesaplı NTLM network logon — relay/kırma göstergesi.
4. **İkincil aşama başladı mı?** LSASS erişimi, `esentutl` ile hassas dosya
   kopyalama, `ntds.dit`/SAM dokunuşu — zehirlemenin lateral movement'a
   dönüştüğünün kanıtı.
Bu sıra, "en somut kanıttan en bağlamsala" doğru ilerler ve her adım bir sonraki
için kapsam daraltır.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Şimdi elimizdeki **gerçek Sigma kurallarına** yaslanarak neye, hangi logsource'ta,
hangi field ve koşullarla alarm vereceğimizi kuralım. LLMNR/NBT-NS zehirlemesinin
tespiti tek bir sihirli kurala sığmaz; **kill-chain'in farklı halkalarını** ayrı
ayrı yakalayan kuralların birleşimidir. Aşağıdaki dört gerçek kural bu tekniğin
tespit iskeletini oluşturur.

### 3.1 Araç imzası — AV katmanı
`title: Antivirus - Hacktool Signature` (id: `fa0c05b6-8ad3-468d-8231-c1cbccb64fba`)
kuralı, en dıştaki savunma halkasıdır. Bu kuralın `logsource.category: antivirus`
üzerinde çalıştığına ve **`Signature`** field'ına baktığına dikkat edin.

- **Mantık:** `Signature|startswith` ile `'ATK/'` (Sophos), `'HKTL'`, `'HTOOL'`,
  `'PWS.'`, `'PWSX'`, `'SecurityTool'` gibi hacktool önekleri; `Signature|contains`
  ile `'Adfind'`, `'BloodH'`, `'BloodyAD'`, `'BruteR'` gibi araç adları yakalanır.
  Responder/Inveigh gibi zehirleme araçları AV tarafından bu ailelerden biriyle
  imzalandığında alarm üretilir.
- **Kritik uyarı — kuralın açıklamasındaki cümle:** AV aracı *blokladı* diye olayı
  görmezden gelme; **"o araç oraya en başta nasıl geldi?"** sorusunu araştır.
  LLMNR zehirlemesinde bu soru altın değerindedir: bir endpoint'te Responder
  imzası patladıysa, o makine büyük olasılıkla saldırganın konumudur ya da
  ele geçirilmiş bir dayanak noktasıdır.
- **Seviye:** Bu kuralın kendisi `stable` statüde; hacktool imzası tek başına
  yüksek güvenilirlikli bir sinyaldir.

### 3.2 Relay araçlarının çalıştırılması — process_creation
`title: Potential SMB Relay Attack Tool Execution`
(id: `5589ab4f-a767-433c-961d-c91f3f704db1`) kuralı doğrudan
**T1557.001 (LLMNR/NBT-NS Poisoning and SMB Relay)** MITRE tekniğine etiketlenmiştir
ve bu konunun kalbindeki kuraldır.

- **Logsource:** `category: process_creation`, `product: windows`.
- **Mantık:** `selection_pe` bloğu `Image|contains` ile relay ve potato ailesi
  araç adlarını arar: `'PetitPotam'`, `'RottenPotato'`, `'HotPotato'`,
  `'JuicyPotato'`, `'\just_dce_'` gibi. Bir süreç yürütülebilir yolunda bu
  desenlerden biri geçiyorsa, ortamda aktif bir relay/privilege escalation
  denemesi olduğu varsayılır.
- **Neden önemli:** LLMNR zehirlemesiyle toplanan karma sıklıkla bu araçlar
  aracılığıyla relay'lenir. Yani bu kural, zehirlemenin "silahlandırma"
  aşamasını yakalar. `attack.credential-access` ve `attack.t1557.001`
  etiketleri bunu doğrular.

### 3.3 İkincil aşama — credential access sinyalleri
Zehirleme başarılı olup saldırgan lateral movement'a döndüğünde iki gerçek kural
devreye girer:

**a) LSASS'a dokunma —** `title: PowerShell Get-Process LSASS`
(id: `b2815d0d-7481-4bf0-9b6c-a4c48a94b349`):
- **Logsource:** `category: process_creation`.
- **Mantık:** `CommandLine|contains` ile `'Get-Process lsas'`, `'ps lsas'`,
  `'gps lsas'` (Get-Process aliasları) yakalanır. LSASS süreci üzerinde
  Get-Process çalıştırmak neredeyse her zaman kötücül bir işaretttir; çünkü
  bellek dump'ı için LSASS handle'ı aranıyordur. `level: high`,
  `attack.t1552.004`.

**b) Hassas dosya kopyalama —** `title: Copying Sensitive Files with Credential Data`
(id: `e7be6119-fc37-43f0-ad4f-1f3f99be2f9f`):
- **Logsource:** `category: process_creation`, `product: windows`.
- **Mantık:** `selection_esent_img` bloğu `Image|endswith: '\esentutl.exe'` ya da
  `OriginalFileName: '\esentutl.exe'` ile başlar; komut satırında hassas dosya
  (ör. `ntds.dit`, SAM, shadow copy) kopyalama desenlerini arar. Relay sonrası
  DC'ye erişim sağlandıysa `ntds.dit` çekme girişimi bu kuralla yakalanır.
  Etiketler: `attack.t1003.002/.003` (credential access).

### 3.4 Uzak thread anomalisi — create_remote_thread
`title: Rare Remote Thread Creation By Uncommon Source Image`
(id: `02d1d718-dd13-41af-989d-ea85c7fab93f`):
- **Logsource:** `product: windows`, `category: create_remote_thread` (Sysmon
  Event ID 8).
- **Mantık:** `selection` bloğu `SourceImage|endswith` ile alışılmadık kaynak
  süreçleri listeler (`\findstr.exe`, `\gpupdate.exe`, `\esentutl.exe`,
  `\expand.exe`, `\hh.exe`, `\installutil.exe` vb.). Bu LOLBAS ikililerinin
  uzak thread oluşturması istatistiksel olarak nadirdir; relay sonrası kod
  enjeksiyon zincirlerinde ortaya çıkabilir. `attack.t1055` (process injection).

### 3.5 Basit Sigma-benzeri tespit mantığı örnekleri

Aşağıdaki iki örnek, yukarıdaki gerçek kuralların mantığını izleyerek yazılmış
sadeleştirilmiş tespit fikirleridir (yalnızca gerçek field/event adlarına dayanır):

**Örnek 1 — Relay aracı çalıştırma (3.2'nin özü):**
```
title: LLMNR/SMB Relay Tool Process Execution (basitleştirilmiş)
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|contains:
            - 'PetitPotam'
            - 'RottenPotato'
            - 'JuicyPotato'
            - 'HotPotato'
    condition: selection
level: high
```
Mantık: `process_creation` logsource'unda `Image` field'ında relay/potato araç
adı geçen her süreç başlangıcı alarm üretir. False positive'i düşüktür çünkü bu
adlar meşru yazılımda pratikte hiç geçmez.

**Örnek 2 — NTLM network logon anomalisi (izlerin korelasyonu):**
```
title: Suspicious NTLM Network Logon After Name Resolution Failure
logsource:
    product: windows
    service: security
detection:
    selection:
        EventID: 4624
        LogonType: 3
        AuthenticationPackageName: 'NTLM'
    filter_known:
        WorkstationName:
            - 'BILINEN-SUNUCU01'
    condition: selection and not filter_known
level: medium
```
Mantık: `Security` logunda `EventID 4624`, `LogonType 3` (network) ve
`AuthenticationPackageName` NTLM olan; ancak bilinen/beyaz-listeli iş
istasyonlarından gelmeyen logon'ları işaretler. Tek başına gürültülüdür; bu
yüzden 3.2'deki relay araç tespiti ya da ağ üzerindeki UDP 5355/137 yanıt
anomalisiyle **korele edildiğinde** güçlenir. Eşik olarak: kısa zaman
penceresinde aynı kaynaktan çok sayıda farklı hesabın NTLM network logon'u
güçlü bir relay/zehirleme sinyalidir.

**Tespit felsefesi:** LLMNR zehirlemesini tek kuralla değil, **katmanlı** yakalarız
— (1) AV hacktool imzası, (2) relay araç yürütme, (3) NTLM logon anomalisi,
(4) ikincil credential-access ve create_remote_thread sinyalleri. Bu halkalardan
birden fazlası aynı host/zaman penceresinde tetiklendiğinde güven skoru yükselir.

---

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan tespiti nasıl atlatmaya çalışır
- **Araç adını/imzasını değiştirme:** Responder/Inveigh yeniden derlenip yeniden
  adlandırılarak `Image|contains` ve AV imza tespitlerinden (`fa0c05b6...`,
  `5589ab4f...`) kaçmaya çalışılır. Karşı önlem: statik ada değil **davranışa**
  yaslanmak — ağ katmanında UDP 5355/137 yanıt anomalisi ve NTLM network logon
  korelasyonu ada bağlı değildir.
- **Analiz/selektif zehirleme:** Saldırgan yalnızca belirli, değerli isim
  sorgularına yanıt vererek (örn. sadece belirli bir dosya sunucusu adı) trafik
  gürültüsünü azaltır, böylece "sürekli yanıt veren host" anomalisini bastırır.
  Karşı önlem: baseline'a göre **yeni bir yanıtlayıcı** çıkışını izlemek; ortamda
  daha önce hiç LLMNR yanıtı üretmeyen bir host'un yanıt üretmeye başlaması
  düşük hacimde bile şüphelidir.
- **Relay yerine sadece kırma:** Saldırgan karmayı canlı relay'lemek yerine
  offline kırmaya götürürse, 3.3/3.4'teki endpoint izleri oluşmaz. Bu durumda
  tek görünür halka ağ katmanı ve varsa AV/araç yürütme kalır — bu yüzden
  ağ görünürlüğü kritiktir.
- **Meşru araçlarla karışma (living-off-the-land):** `esentutl.exe` gibi imzalı
  LOLBAS ikililerini kullanarak `Copying Sensitive Files` (e7be6119...) ve
  `create_remote_thread` (02d1d718...) kurallarının nadir-kaynak mantığından
  kaçmaya çalışır. Karşı önlem: kuralların dayandığı **komut satırı bağlamı**
  (hedef dosya `ntds.dit`/SAM mı, kaynak süreç anormal mi) ile ayıklama.

### Savunmacının karşı hamleleri
- **Kökten kapatma (en etkili tespit + önleme):** LLMNR ve NBT-NS'yi Group Policy
  ile devre dışı bırakmak (LLMNR için `EnableMulticast=0`, NetBIOS over TCP/IP'yi
  kapatma). Kapatıldıktan sonra ağda görülen **her** LLMNR/NBT-NS yanıtı,
  meşru gürültü olmadığı için yüksek güvenilirlikli bir alarma dönüşür —
  yani kapatma hem saldırı yüzeyini yok eder hem tespiti keskinleştirir.
- **SMB imzalama zorunluluğu (SMB signing):** Relay'i etkisiz kılar; karma
  iletilse bile hedef sunucu imzasız oturumu reddeder. Bu, 3.2'deki relay
  araçlarının başarısını düşürür.
- **Honeypot / canary isimler:** Ağa hiçbir zaman meşru olarak çözülmemesi
  gereken sahte isimler yerleştirmek; bu adlara gelen LLMNR yanıtı doğrudan
  zehirleyiciyi ifşa eder (sıfıra yakın false positive).
- **Korelasyon eşiği:** Tek bir NTLM 4624/4625'e değil, **kısa pencerede çok
  hesap + tek kaynak** desenine alarm vermek gürültüyü düşürür.

### Tipik false positive kaynakları ve nasıl ayıklanır
- **Meşru LLMNR/NBT-NS gürültüsü:** LLMNR henüz kapatılmamış ortamlarda yazıcılar,
  eski uygulamalar ve yanlış yazılmış paylaşım yolları normal olarak fallback
  üretir. Ayıklama: *sorgu* ile *yanıt* trafiğini ayırmak — sorgu normaldir,
  tutarlı **yanıt** anormaldir; ayrıca baseline dışı yeni yanıtlayıcıya odaklan.
- **Güvenlik araçlarının kendisi:** Vulnerability scanner'lar, red-team
  egzersizleri ve pentest araçları hacktool imzalarını (`fa0c05b6...`) ve relay
  araç adlarını (`5589ab4f...`) meşru olarak tetikleyebilir. Ayıklama: bilinen
  tarama sunucularını ve onaylı test pencerelerini beyaz-listeye almak; ancak
  kuralın uyarısını unutma — imza görüldüyse "araç oraya nasıl geldi?" sorusu
  yine de yanıtlanmalı.
- **NTLM network logon (4624 LogonType 3):** Eski uygulamalar, NAS cihazları ve
  Kerberos yerine NTLM'e düşen bağlantılar meşru NTLM logon üretir. Ayıklama:
  bilinen legacy sistemleri `filter_known` ile dışlamak; alarmı yalnızca çoklu
  hesap/tek kaynak desenine daraltmak.
- **`esentutl.exe` meşru kullanımı:** Yedekleme, veritabanı bakımı ve Exchange
  yönetimi `esentutl` kullanır. Ayıklama: `Copying Sensitive Files` kuralında
  hedef dosyanın gerçekten credential içeren bir dosya (`ntds.dit`, SAM,
  shadow copy) olup olmadığına bakmak; sıradan `.edb` bakımını dışlamak.
- **`create_remote_thread` nadir-kaynak listesi:** Bazı yönetim/dağıtım araçları
  `gpupdate.exe`, `installutil.exe` gibi ikilileri meşru olarak kullanabilir.
  Ayıklama: kaynak sürecin ebeveynini, imzasını ve hedef süreci bağlamla
  incelemek; tek başına değil diğer halkalarla korele etmek.

---

### Kapanış

LLMNR/NBT-NS zehirlemesi yeni bir zafiyet değil, **protokolün doğuştan gelen
güvenini ve Windows'un otomatik kimlik sunma alışkanlığını** istismar eden bir
tekniktir. Bu yüzden tespiti de tek bir noktaya değil, kill-chain boyunca dağılmış
izlere yaslanır: ağda sahte isim yanıtları, endpoint'te hacktool imzaları
(`fa0c05b6...`), relay araç yürütmeleri (`5589ab4f...`, `T1557.001`), ve zehirleme
başarılıysa ikincil credential-access sinyalleri (`b2815d0d...`, `e7be6119...`) ile
uzak thread anomalileri (`02d1d718...`). En güçlü savunma ise tespitle önlemenin
birleştiği yerdedir: LLMNR/NBT-NS'yi kapatmak ve SMB imzalamayı zorunlu kılmak,
hem saldırı yüzeyini yok eder hem de geriye kalan her sinyali neredeyse
gürültüsüz, yüksek güvenilirlikli bir alarma dönüştürür. Hırsızın nasıl
girdiğini anladığımızda, mücevheri korumak artık bir tahmin değil, korelasyon
meselesidir.
