# Hesap Manipülasyonu (Account Manipulation) — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin savunma ve tespit
> odaklıdır. Amaç, saldırganın hesap manipülasyonu davranışını **anlamak** ve
> ürettiği izleri **avlamaktır** — canlı bir saldırı reçetesi değil.

MITRE ATT&CK karşılığı: **T1098 (Account Manipulation)** ve yakın komşuları
**T1136 (Create Account)**, **T1087 (Account Discovery)**, **T1069 (Permission
Groups Discovery)**. Bu teknikler pratikte iç içe geçer: saldırgan önce keşif
yapar (kim admin?), sonra ya yeni bir hesap yaratır ya da mevcut bir hesabı
kalıcılık ve yetki için manipüle eder.

---

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Hesap manipülasyonu, saldırganın bir ortamda **zaten elde ettiği erişimi
kalıcı ve dayanıklı** hâle getirmek için kimlik ve yetki nesnelerini
değiştirmesidir. Buradaki kilit fikir şudur: saldırgan yeni bir zafiyet
sömürmez; ortamın **meşru kimlik yönetimi mekanizmalarını** kendi lehine
kullanır. Bu yüzden hesap manipülasyonu tespiti zordur — kullanılan araçlar
(`net.exe`, `net1.exe`, `dsadd`, PowerShell'in `ActiveDirectory` modülü,
`Set-ADUser`, LDAP çağrıları) tamamen meşru yönetim araçlarıdır.

Kavramsal olarak saldırganın hedefleri şunlardır:

- **Kalıcılık (persistence):** Ana giriş noktası kapansa bile geri dönebilmek.
  Bunun için ya yeni bir yerel/domain hesabı açar (T1136) ya da uykuda olan,
  devre dışı bir hesabı yeniden etkinleştirir, parolasını sıfırlar.
- **Yetki yükseltme ve yanal hareket için zemin:** Ele geçirdiği sıradan bir
  hesabı yüksek yetkili gruplara ekler (örneğin `Domain Admins`,
  `Enterprise Admins`, `Administrators`). Böylece düşük değerli bir kullanıcı
  bir anda "altın anahtar" hâline gelir.
- **Gizlenme (blend in):** Meşru görünen adlar seçer, hesabı normal kullanıcı
  isimlendirme şablonuna uydurur, "SafeMode", "backup", "svc-" gibi görünüşte
  masum önekler kullanır. DarkGate zararlısının `SafeMode` adında bir hesap
  yaratması buna tipik bir örnektir — ad, bir yöneticinin gözünden kaçacak
  kadar "sistemsel" görünür.
- **Kimlik doğrulama akışlarını sabote etme:** MFA aygıtını değiştirme,
  kurtarma e-postasını/telefonunu güncelleme, hesabın parola-süresiz olmasını
  sağlama, `AdminSDHolder`/ACL manipülasyonu ile hesaba gizli yetki bağlama.

Bu tekniğin savunmacı için en sinsi yanı, **"düşük gürültülü" olmasıdır.**
Bir exploit çoğu zaman çökme, anomalik bellek kullanımı, beklenmedik ağ
bağlantısı gibi gürültü üretir. Oysa `net user /add` komutu, ortamdaki
yüzlerce meşru yönetim işleminden birine bire bir benzer. Saldırgan tam da
bu benzerliği bir kalkan olarak kullanır: "meşru araç + meşru işlem +
meşru görünen ad" üçlüsü, kural tabanlı tespitin en zayıf noktasıdır. Bu
yüzden hesap manipülasyonu tespitinde başarı, tekil komutu görmekten değil,
**bağlamı ve zinciri** görmekten gelir — kim, hangi ana süreçle, hangi
hedefe, hangi keşiften hemen sonra bu işlemi yaptı?

Saldırının doğal akışı genellikle **önce keşif, sonra manipülasyon**
şeklindedir. Saldırgan hangi hesabı hedefleyeceğini bilmek için ortamı sorgular:
"kimler domain admin?", "yerel yönetici kim?" Bu keşif fazı, ilk sağlanan Sigma
kuralının ("Reconnaissance Activity") yakaladığı davranıştır. Manipülasyon fazı
ise hesabın açılması/değiştirilmesidir — ikinci Sigma kuralının ("DarkGate -
User Created Via Net.EXE") yakaladığı davranıştır. Bu iki fazı birlikte görmek,
tespit mühendisi için altın değerindedir: tekil olayları "gürültü" sanabilirsin,
ama **keşif → hesap oluşturma → gruba ekleme** zinciri neredeyse hiçbir zaman
masum değildir.

---

## 2. Bıraktığı izler / artefaktlar

Hesap manipülasyonu, doğası gereği kimlik altyapısında iz bırakır. Önemli olan,
doğru **log kaynaklarının** açık ve toplanıyor olmasıdır. Aksi hâlde en kritik
olaylar hiç üretilmez.

### 2.1 Windows Security (kimlik olayları)

Domain Controller ve üye sunucuların Security log'u en zengin kaynaktır:

- **4720** — Bir kullanıcı hesabı oluşturuldu (A user account was created).
- **4722** — Bir hesap etkinleştirildi (devre dışı hesabın yeniden açılması).
- **4724** — Parola sıfırlama girişimi (bir yönetici başka bir hesabın
  parolasını sıfırladı).
- **4738** — Bir kullanıcı hesabı değiştirildi (bayrak/attribute değişiklikleri;
  örn. `Password never expires` açılması, `UserAccountControl` değişimi).
- **4732 / 4728 / 4756** — Bir üye, yerel güvenlik grubuna / global gruba /
  evrensel gruba eklendi. `Domain Admins`, `Enterprise Admins`,
  `Administrators` hedef alındığında bu olaylar kritik alarm kaynağıdır.
- **4767** — Bir hesabın kilidi açıldı.
- **4741 / 4743** — Bilgisayar hesabı oluşturuldu/değiştirildi (makine
  hesaplarının kötüye kullanımı için).

Keşif (discovery) tarafında, ilk Sigma kuralının demirlendiği olay:

- **4661** — Bir nesneye erişim için handle talep edildi (A handle to an object
  was requested). Bu olay, `Audit SAM` ve `Audit Kernel Object` ileri denetim
  politikaları açık olduğunda SAM veritabanındaki kullanıcı/grup nesnelerine
  yapılan doğrudan sorguları görünür kılar. `net user administrator /domain`
  veya `net group "domain admins" /domain` gibi komutlar, DC üzerinde bu tür
  SAM nesne erişimleri üretir.

### 2.2 Process creation (komut satırı desenleri)

Sysmon **Event ID 1** veya Windows Security **4688** (komut satırı denetimi
açıkken) davranışsal en güçlü kaynaktır. Aranan desenler:

- `net.exe` / `net1.exe` ile `user ... /add` (yeni yerel kullanıcı),
  `user <ad> <parola>` (parola set/sıfırlama), `localgroup administrators <ad>
  /add`, `group "domain admins" <ad> /add /domain`.
- Keşif: `net user <ad> /domain`, `net group "domain admins" /domain`,
  `net localgroup administrators`.
- PowerShell: `New-LocalUser`, `Add-LocalGroupMember`, `New-ADUser`,
  `Set-ADUser -PasswordNeverExpires`, `Add-ADGroupMember "Domain Admins"`.
- `dsadd user`, `wmic useraccount`, `Add-ADGroupMember` LDAP çağrıları.

Komut satırındaki **parent process** de önemlidir: `net.exe`'yi başlatan şey
`cmd.exe /c` ve onun da parent'ı bir Office ürünü, `wscript`/`cscript`,
`rundll32`, ya da bir zararlı loader ise şüphe katsayısı çok yükselir. DarkGate
örneğinde tam olarak `/c net user /add SafeMode DarkGate0!` tarzı bir komut
satırı görülür.

### 2.3 Registry ve dosya izleri

- Yerel hesaplar SAM hive'ında (`HKLM\SAM`) tutulur; yeni hesap oluşumu bu
  hive'da değişiklik yaratır (doğrudan okumak zordur, ama offline analizde
  görünür).
- `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SpecialAccounts\UserList`
  altında bir hesabı **giriş ekranından gizleme** (değer = 0) klasik bir kaçış
  artefaktıdır: saldırgan yeni hesabı buraya ekleyerek logon ekranında
  görünmez kılar.

### 2.4 Ağ / dizin izleri

- Domain ortamında LDAP yazma işlemleri (grup üyeliği, attribute değişimi) DC
  üzerinde iz bırakır; DC replikasyon trafiği ve `4662` (dizin nesnesine
  operasyon) olayları da izlenebilir.
- Bulut/Hibrit (Azure AD / Entra ID) tarafında Azure AD Audit Logs: "Add member
  to role", "Reset user password", "Update user", "Add owner to application"
  gibi işlemler analog artefaktlardır. Bu metin Windows odaklı olsa da, aynı
  tespit mantığı buluta taşınır.

---

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Elimizdeki iki gerçek Sigma kuralı, hesap manipülasyonunun iki farklı fazını
temsil ediyor. Her ikisinin mantığını Türkçe açıklayıp, aynı çizgide 1-2 basit
tespit mantığı örneği türeteceğim.

### 3.1 Kural A — Keşif: SAM üzerinden yüksek değerli hesap sorgusu

**id:** `968eef52-9cff-4454-8992-1e74b9cbad6c`

- **logsource:** `product: windows`, `service: security`. Yani bu, DC'lerin
  Windows Security log'undan beslenir.
- **detection.selection:**
  - `EventID: 4661` — SAM nesnesine handle talebi.
  - `AccessMask: '0x2d'` — talep edilen erişim maskesi; okuma/enumerate tarzı
    hakları temsil eden spesifik bir değer.
  - `ObjectType: SAM_USER` **veya** `SAM_GROUP` — sorgulanan nesnenin türü.
  - `ObjectName|startswith: 'S-1-5-21-'` — domain SID öneki; yani yerel değil,
    domain kimlik nesnesi.
  - `ObjectName|endswith: '-500'` **veya** `'-512'` — bu son ekler kritiktir:
    **-500** yerleşik **Administrator** hesabının RID'i, **-512** ise
    **Domain Admins** grubunun RID'idir.
- **condition:** `selection` — yani yukarıdaki tüm koşullar aynı olayda
  sağlanırsa alarm.

**Mantığın özü:** Bu kural, "birisi domain'in en değerli iki kimlik nesnesine
(yerleşik Administrator ve Domain Admins) doğrudan SAM seviyesinde erişim
talep ediyor" davranışını yakalar. `net user administrator /domain` veya
`net group "domain admins" /domain` komutları tam olarak bunu üretir. Buradaki
zekâ, jenerik "birisi bir hesabı sorguladı" gürültüsüne bakmak yerine, **sadece
en yüksek değerli hedeflere** (-500, -512) odaklanmasıdır. Bu, sinyal/gürültü
oranını dramatik biçimde iyileştirir.

**Önemli önkoşul:** Kuralın `definition` alanı uyarıyor — `Audit SAM` ve
`Audit Kernel Object` ileri denetim politikaları sunucu tavsiyelerinde varsayılan
kapalıdır ve 4661 hacmi DC'lerde yüksektir. Yani bu kuralı çalıştırmak için
önce denetimi bilinçli açman ve hacmi kaldırabilecek bir toplama/depolama
kapasiten olmalı. Tespit mühendisliğinin gerçeği budur: kural ancak besleyen
log varsa çalışır.

### 3.2 Kural B — Manipülasyon: net.exe ile hesap oluşturma (DarkGate)

**id:** `bf906d7b-7070-4642-8383-e404cf26eba5`

- **logsource:** `category: process_creation`, `product: windows`. Yani Sysmon
  EID 1 veya Security 4688 gibi süreç oluşturma kaynağı.
- **detection.selection:**
  - `Image|endswith: '\net.exe'` **veya** `'\net1.exe'` — çalıştırılan ikili.
  - `CommandLine|contains|all:` → `'user'`, `'add'`, `'DarkGate'`, `'SafeMode'`
    — komut satırının **hepsini birden** içermesi gerekir.
- **condition:** `selection`. **level: high.**

**Mantığın özü:** Bu kural çok spesifiktir; DarkGate'in imza davranışı olan
`net user /add SafeMode DarkGate0!` komutunu, hem `SafeMode` hem `DarkGate`
dizgilerini birlikte arayarak yakalar. `contains|all` mantığı önemlidir:
tek başına `user`+`add` görmek false positive üretir (yöneticiler meşru hesap
açar), ama `DarkGate` dizgisi eklendiğinde neredeyse sıfır meşru kullanım kalır.
Bu yüzden `falsepositives: Unlikely` ve `level: high` denmiştir.

Bu kuralın dersi şudur: **yüksek özgüllük = düşük yanlış pozitif, ama düşük
kapsama.** DarkGate imzasını bilmeyen bir saldırgan `SafeMode`/`DarkGate`
kelimelerini kullanmaz ve bu kural sessiz kalır. Bu yüzden onu daha geniş,
davranışsal bir kuralla tamamlaman gerekir (aşağıda).

### 3.3 Türetilmiş tespit mantığı örnekleri

**Örnek 1 — Genişletilmiş "net.exe ile hesap oluşturma" (davranışsal).**
Kural B'nin dar imzasını, DarkGate'e bağlı olmayan genel bir davranışa
genişletiyoruz. Fikir: `net user ... /add` görüldüğünde, ancak `SafeMode`/
`DarkGate` gibi imza dizgilerine bağlı kalmadan alarm ver; gürültüyü meşru
yönetim ana süreçlerini eleyerek düşür.

```yaml
title: Suspicious Local/Domain Account Creation via net.exe
status: experimental
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith:
            - '\net.exe'
            - '\net1.exe'
        CommandLine|contains|all:
            - 'user'
            - '/add'
    filter_legit:
        ParentImage|endswith:
            - '\SCNotification.exe'   # örnek: bilinen yönetim aracı
    condition: selection and not filter_legit
falsepositives:
    - Meşru yönetici/otomasyon hesap açılışları (allowlist ile ayıklanmalı)
level: medium
```

Bu kural bilinçli olarak `medium` seviyesindedir çünkü tek başına `user`+`/add`
meşru olabilir. Değeri, **korelasyonla** artar (bkz. Örnek 2).

**Örnek 2 — Keşif ardından ayrıcalıklı gruba ekleme (korelasyon).**
En güçlü sinyal, tekil olay değil **zincirdir**. Kural A'nın yakaladığı keşif
(4661, -512) ile bir grup-ekleme olayının (4728/4732) kısa bir zaman
penceresinde aynı hesaptan gelmesi, neredeyse kesin kötü niyettir.

```yaml
title: Recon of Domain Admins Followed by Privileged Group Change
status: experimental
logsource:
    product: windows
    service: security
detection:
    recon:
        EventID: 4661
        ObjectName|endswith: '-512'      # Domain Admins RID
    priv_add:
        EventID:
            - 4728   # global gruba üye eklendi
            - 4732   # yerel gruba üye eklendi
        TargetUserName|contains: 'Admins'
    timeframe: 30m
    condition: recon and priv_add
level: high
```

Buradaki `timeframe` ve iki koşulun birlikteliği, tek tek bakıldığında
"normal yönetim" görünebilecek olayları, bir **saldırı anlatısına** dönüştürür.
Tespit mühendisliğinde altın kural: yüksek değerli hedefe (Domain Admins,
-500/-512) yönelik keşif + değişiklik = düşük gürültü, yüksek güven.

---

## 4. Kaçınma ve karşı-tespit + false positive

### 4.1 Saldırgan bu tespiti nasıl atlatmaya çalışır

- **İmza dizgilerinden kaçınma:** Kural B `DarkGate`/`SafeMode` dizgilerine
  bağlıdır. Saldırgan hesap adını değiştirdiği anda (örneğin `svc-backup`)
  kural sessiz kalır. **Karşı-tedbir:** dizgi imzalarına değil, davranışa
  (net.exe + user + /add + şüpheli parent) dayan; Örnek 1 gibi genel kuralla
  kapsamı genişlet.
- **Aracı değiştirme (LOLBin/API kayması):** `net.exe` yerine doğrudan
  PowerShell `New-LocalUser`/`New-ADUser`, `dsadd`, `wmic useraccount call
  create`, ya da doğrudan LDAP/Win32 API çağrıları kullanmak. **Karşı-tedbir:**
  tespiti tek ikiliye (`net.exe`) bağlama; Security 4720/4726/4732 gibi
  **sonuç olaylarını** izle. 4720 ("hesap oluşturuldu"), hangi araçla
  yapıldığından bağımsız olarak üretilir — bu yüzden araç-agnostik ve daha
  dayanıklıdır.
- **`net1.exe` ikamesi:** `net.exe` bazı çağrıları sessizce `net1.exe`'ye
  devreder. Sadece `net.exe` izleyen bir kural atlatılır. Sigma kuralları zaten
  ikisini de kapsıyor — bu iyi bir örnek, sen de her iki ikiliyi listele.
- **Denetimi kör etme:** Saldırgan `Audit SAM`/`Audit Kernel Object`
  politikasını kapatmaya, log toplamayı durdurmaya, ya da event log'u
  temizlemeye (Security **1102** — log temizlendi) çalışabilir. **Karşı-tedbir:**
  logları merkezî bir SIEM'e **anında** ilet (yerelde silinse bile kopya kalsın),
  1102 ve denetim politikası değişikliklerini (`4719`) yüksek öncelikli izle.
- **Gizleme:** Yeni hesabı `SpecialAccounts\UserList` registry'sine ekleyerek
  logon ekranından saklamak. **Karşı-tedbir:** bu registry yoluna yazımları
  (Sysmon EID 13) izle — meşru kullanımı neredeyse yoktur.
- **Yavaşlatma (low-and-slow):** Keşif ile manipülasyonu günlere yayarak
  korelasyon penceresinden kaçmak. **Karşı-tedbir:** korelasyon penceresini
  makul tut ama tekil yüksek-değerli olayları (Domain Admins'e ekleme) tek
  başına da alarm yap; -500/-512 hedefli olayları uzun süreli baseline'a karşı
  değerlendir.

### 4.2 Tipik false positive kaynakları ve ayıklama

- **Meşru IT yönetimi:** Yardım masası parola sıfırlar (4724), yeni çalışan için
  hesap açar (4720), kullanıcıyı gruba ekler (4728/4732). Bunlar Örnek 1 gibi
  davranışsal kuralları tetikler. **Ayıklama:** onaylı yönetim hesaplarını,
  IPAM/otomasyon servis hesaplarını ve bilinen jump-host'ları allowlist'e al;
  bilet sistemi (ITSM) ile eşleştir — değişiklik bir talebe bağlı mı?
- **Yönetim araçları ve script'ler:** SCCM, provisioning script'leri, yedekleme
  ve dizin senkron araçları `net`/PowerShell ile hesap işlemleri yapabilir.
  **Ayıklama:** `ParentImage` ve çalıştıran kullanıcıya göre filtrele; bilinen
  otomasyon ana süreçlerini `filter` bloğuna koy.
- **4661 hacmi:** DC'lerde SAM erişim olayları çok yoğundur; `Audit SAM` açıksa
  kör 4661 kuralı SIEM'i boğar. Kural A'nın zekâsı burada: `AccessMask 0x2d` ve
  `-500/-512` filtreleriyle hacmi yönetilebilir tutar. **Ayıklama:** asla ham
  4661 alarmlama; her zaman AccessMask + yüksek-değerli RID kısıtı uygula.
- **Golden/known-good adlandırma çakışması:** `admin`, `backup`, `svc-`
  önekleri hem meşru hem kötü niyetli kullanılabilir. **Ayıklama:** ada değil,
  **davranış zincirine** (keşif → oluşturma → ayrıcalıklı gruba ekleme) güven;
  yeni açılan bir hesabın kısa sürede Domain Admins'e girmesi meşru IT
  akışında nadirdir.

### 4.3 Savunmacı için pratik öncelik sırası

1. **Sonuç olaylarını topla:** 4720, 4722, 4724, 4738, 4728/4732/4756. Bunlar
   araç-agnostiktir; saldırgan hangi LOLBin'i seçerse seçsin üretilir.
2. **Yüksek-değerli hedeflere odaklan:** -500 (Administrator) ve -512
   (Domain Admins) içeren her olayı ayrı, yüksek öncelikli bir tenant gibi izle.
3. **Zincirle korele et:** Kural A (keşif) + grup değişikliği (4728/4732) kısa
   pencere korelasyonu, en yüksek güvenli sinyaldir.
4. **Denetim bütünlüğünü koru:** 1102 (log temizleme) ve 4719 (denetim
   politikası değişimi) senin "tespit sistemine saldırı" alarmlarındır.
5. **Baseline kur:** "Normalde kim, hangi ana süreçle, hangi saatte hesap açar?"
   sorusuna cevabın olsun; sapma bu baseline'a karşı anlam kazanır.

### 4.4 Tespit olgunluğu: katmanlı yaklaşım

Tek bir kurala güvenmek kırılgandır. Olgun bir tespit programı hesap
manipülasyonunu **katmanlı** ele alır ve her katman farklı bir kaçış yöntemine
karşı dayanıklıdır:

- **Katman 1 — İmza (dar, yüksek güven):** DarkGate örneğindeki gibi bilinen
  zararlı davranış imzaları. Yanlış pozitifi neredeyse sıfır, ama sadece
  bilinen tehditleri yakalar. `level: high` ile anında müdahale hattına gider.
- **Katman 2 — Davranış (orta genişlik):** "net.exe/PowerShell ile hesap
  oluşturma/gruba ekleme" gibi araç-davranış kalıpları. İmzayı bilmeyen
  saldırganı da yakalar, ama allowlist bakımı ister. Genellikle `level: medium`.
- **Katman 3 — Sonuç olayları (araç-agnostik):** 4720/4728/4732/4738 gibi
  Windows'un kendi ürettiği kimlik olayları. Saldırgan hangi aracı seçerse
  seçsin bu katman üretilir; bu yüzden en dayanıklı ama en gürültülü katmandır.
  Değeri, yüksek-değerli hedef filtreleri (-500/-512) ve korelasyonla artar.
- **Katman 4 — Korelasyon ve anomali:** Keşif → oluşturma → yetkilendirme
  zinciri, olağandışı saat, olağandışı kaynak host, yeni açılan hesabın
  saniyeler içinde Domain Admins'e girmesi. En yüksek bağlamsal güven buradadır.

Bu katmanlar birbirini tamamlar: Katman 1 hızlı ve kesindir ama dardır;
Katman 3 geniştir ama gürültülüdür. Saldırgan Katman 1'i atlatmak için aracını
değiştirdiğinde Katman 3 devreye girer; Katman 3'ü boğmak için düşük-yavaş
gittiğinde ise yüksek-değerli hedef filtreleri ve Katman 4 korelasyonu onu
görünür kılar. Savunmanın gücü tek bir mükemmel kuralda değil, bu katmanların
**örtüşmesinde** yatar.

### 4.5 Doğrulama ve sürekli test

Yazdığın kuralın gerçekten çalıştığını varsayma; **doğrula.** Kontrollü bir
lab ortamında (üretim değil) `net user test /add`, `net group "domain admins"
/domain` gibi meşru-görünen komutları çalıştırıp beklenen olayların
(4720, 4661, Sysmon EID 1) gerçekten üretildiğini ve kuralının tetiklendiğini
teyit et. Denetim politikası kapalıysa hiçbir olay üretilmez ve kuralın
"sessiz başarısız" olur — bu en tehlikeli durumdur, çünkü koruma olduğunu
sanırsın ama yoktur. Purple team tatbikatları ve düzenli detection validation,
kuralların zaman içinde (yeni Windows sürümü, değişen field adı, kapatılan
denetim) körelmediğinden emin olmanın tek yoludur.

**Özet:** Hesap manipülasyonu, meşru araçlarla yapılan gayrimeşru bir iştir.
Bu yüzden tespit, "aracı yakalamak"tan çok "**davranış zincirini ve yüksek
değerli hedefi**" yakalamaya dayanır. Gerçek Sigma kurallarının bize öğrettiği
iki ders nettir: (1) gürültüyü kırmak için en değerli kimlik nesnelerine
(-500, -512) daral; (2) dar imzaları (DarkGate/SafeMode) davranışsal, sonuç
odaklı kurallarla (4720/4728/4732) tamamla ki saldırgan aracını değiştirdiğinde
kör kalmayasın. Hırsızın önce mücevherin nerede olduğunu sorduğunu (keşif),
sonra kasayı açtığını (manipülasyon) birlikte görürsen, onu iş üstünde
yakalarsın.
