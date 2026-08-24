# Run Key Persistence — Tespiti

> "Hırsızı tanımadan mücevheri koruyamazsın." Bu metin bir saldırı reçetesi değil; bir tespit mühendisliği (detection engineering) çalışmasıdır. Önce tekniğin mantığını anlıyoruz, sonra bıraktığı izleri okuyup gerçek Sigma kurallarına demirlenmiş alarm mantığı kuruyoruz.

## 1. Teknik nasıl çalışır (saldırgan gözüyle, kavramsal)

Windows, kullanıcı oturum açtığında veya sistem başladığında belirli registry anahtarlarında listelenen programları otomatik olarak çalıştırır. Bu anahtarlar "autostart extensibility point" (ASEP) olarak adlandırılır ve en bilineni **Run** / **RunOnce** anahtarlarıdır. Meşru amacı bellidir: güncelleyiciler, senkronizasyon araçları, yazıcı yardımcıları oturum açar açmaz kendilerini ayağa kaldırmak ister. Microsoft'un kendi dokümantasyonu (Run and RunOnce Registry Keys) bu mekanizmanın normal işletim davranışı olduğunu tarif eder.

Saldırganın istismar ettiği şey tam da bu güvendir. Bir kez sisteme kod çalıştırma yeteneği elde eden saldırgan, kalıcılık (persistence) ister: makine yeniden başladığında ya da kullanıcı tekrar oturum açtığında zararlısının otomatik olarak yeniden yükleneceğinden emin olmak. Bunun için kendi çalıştırılabilir dosyasının yolunu bir Run anahtarına bir değer olarak yazar. MITRE ATT&CK bu davranışı **T1547.001 (Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder)** olarak sınıflandırır.

Kavramsal olarak saldırganın önünde üç temel değişken vardır:

1. **Hangi kovan (hive)?** `HKEY_CURRENT_USER` (HKCU) altındaki Run anahtarı yalnızca o kullanıcının haklarıyla yazılabilir ve yönetici gerektirmez; sadece o kullanıcı oturum açtığında tetiklenir. `HKEY_LOCAL_MACHINE` (HKLM) altındaki Run anahtarı ise tüm kullanıcıları etkiler ama yazmak için yükseltilmiş (elevated) haklar ister. Saldırgan sahip olduğu ayrıcalık düzeyine göre seçim yapar.

2. **Kalıcı mı, tek seferlik mi?** `Run` her oturum açılışında yeniden tetiklenir. `RunOnce` bir kez çalışır ve değeri silinir — genellikle bir sonraki aşamaya geçiş (staging) veya yeniden başlatma sonrası tek bir eylem için kullanılır.

3. **Anahtara nasıl yazılır?** İşte tespit açısından kritik nokta budur. Saldırgan registry'yi doğrudan Windows API'siyle (`RegSetValueEx`) sessizce değiştirebileceği gibi, çoğu zaman "living off the land" yaklaşımıyla sistemde zaten var olan araçları kullanır: en yaygını `reg.exe add ...`, ayrıca PowerShell'in `New-ItemProperty` / `Set-ItemProperty` komutları veya `wmic process call create` üzerinden dolaylı olarak `reg.exe` çağrısı. Bu araç seçimi, komut satırında (command line) çok belirgin izler bırakır — ki tespit mühendisliğinin ana tutamağı budur.

Özetle: teknik yeni bir zafiyet sömürmez; işletim sisteminin meşru bir otomatik başlatma özelliğini kötüye kullanır. Bu yüzden tespit, "zafiyet imzası" aramaz; **davranış anomalisi ve bağlam** arar.

Saldırganın Run key'i neden bu kadar sık seçtiğini de anlamak gerekir; çünkü tespit mühendisi "neyi ne sıklıkta görürüm" sorusunun cevabını buradan kurar. Run key kalıcılığı ucuzdur (tek bir registry yazımı), güvenilirdir (Microsoft'un desteklediği resmî mekanizma, kırılma riski düşük), ayrıcalık gerektirmez (HKCU varyantı standart kullanıcıyla çalışır) ve gürültünün içinde saklanabilir (meşru yazılımlar da aynı anahtarı kullanır). Bu dört özellik onu düşük-yetenekli commodity zararlısından APT'ye kadar geniş bir yelpazenin favorisi yapar. Savunmacı açısından sonuç şudur: bu tekniği kör noktada bırakmak lüks değildir; çünkü tehdit yelpazesinin neredeyse tamamı bir noktada bu kapıyı dener. Ama aynı yaygınlık, tespiti "reg.exe gördüm, alarm ver" kabalığında kuran ekibi false positive altında boğar. İşte bu gerilim — yüksek yaygınlık ile yüksek meşru-kullanım — Run key tespitinin neden bağlam mühendisliği gerektirdiğini açıklar.

## 2. Bıraktığı izler / artefaktlar

Bir Run anahtarı manipülasyonu, hangi yöntemle yapıldığına bağlı olarak farklı katmanlarda iz bırakır. Tespit mühendisi bu katmanları bilerek görünürlük (visibility) planlar.

### Süreç oluşturma izleri (process creation)

Saldırgan `reg.exe`, `powershell.exe` veya `wmic.exe` gibi bir aracı çalıştırdığında bir süreç oluşur. Bu, en zengin ve en güvenilir izdir:

- **Sysmon Event ID 1** (Process Creation) — `provider: Microsoft-Windows-Sysmon`. Yukarıdaki gerçek Sigma kuralının regresyon testi de tam olarak bu sağlayıcıdan üretilmiş bir `.evtx` ile doğrulanmıştır.
- **Windows Security Event ID 4688** (A new process has been created) — komut satırı loglaması (`Include command line in process creation events`) etkinse `CommandLine` alanını da taşır.

İlgili alanlar ve tipik desenler:

- `Image` alanı `\reg.exe`, `\powershell.exe`, `\wmic.exe` ile biter.
- `OriginalFileName` alanı (Sysmon, PE metadata'sından okur) `reg.exe` veya `wmic.exe` olur — bu, dosyanın adı değiştirilse (renamed binary) bile gerçek kimliği yakalar.
- `CommandLine` alanı `reg add ... Software\Microsoft\Windows\CurrentVersion\Run ...` gibi bir desen taşır.
- `ParentImage` / ebeveyn süreç bağlamı: `reg.exe`'yi başlatan sürecin `winword.exe`, `wscript.exe`, `mshta.exe`, `cmd.exe` (bir makro veya indirilmiş script zincirinden) olması alarmı ciddi biçimde güçlendirir.

### Registry değişikliği izleri

Doğrudan API ile yazıldığında süreç izi zayıf olabilir; bu durumda registry katmanına bakılır:

- **Sysmon Event ID 13** (Registry value set) — `TargetObject` alanı `HKU\<SID>\Software\Microsoft\Windows\CurrentVersion\Run\<değer_adı>` veya `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\...` yolunu içerir; `Details` alanı yazılan veriyi (çoğu zaman bir dosya yolu) taşır. Sysmon Event ID 12 ise anahtar oluşturma/silme olayını verir.
- **Windows Security Event ID 4657** (A registry value was modified) — SACL denetimi ilgili anahtar üzerinde etkinleştirilmişse üretilir.

### Kalıcı artefaktlar (disk üzerinde, olay sonrası)

- Registry hive dosyalarının kendisi: `NTUSER.DAT` (HKCU başına) ve `SOFTWARE` hive (HKLM). Adli inceleme (forensics) bu anahtarların **LastWriteTime** zaman damgasını taşır — hangi kaydın ne zaman değiştiğini gösterir.
- Run değerinin işaret ettiği çalıştırılabilir dosyanın kendisi: sıklıkla `%AppData%\Roaming`, `%LocalAppData%`, `%ProgramData%`, `%Temp%` gibi kullanıcı-yazılabilir ve şüpheli konumlarda yer alır. Gerçek Sigma kuralındaki (WMI üzerinden autorun) örnek komut satırı da tam olarak `C:\Users\user\AppData\Roaming\...` altına işaret eder.
- Autoruns benzeri araçların numaralandırdığı ASEP listesi: Run/RunOnce anahtarlarının tam envanteri.

### Komut satırı desenleri (özet)

Tespit için en değerli metinsel imzalar şunlardır:
- `Software\Microsoft\Windows\CurrentVersion\Run` (ana anahtar yolu)
- `reg` + ` add ` birlikteliği (reg.exe kullanımında)
- `RunOnce`, `RunServices`, `RunServicesOnce`, `RunOnceEx` gibi kardeş ASEP anahtarları
- `wmic ... process call create ... reg.exe add ...` (dolaylı çağrı)
- PowerShell'de `New-ItemProperty`, `Set-ItemProperty` ile `-Path ...\Run` birlikteliği

### Görünürlük planlaması (ne olmadan hiçbiri işe yaramaz)

Yukarıdaki izlerin hiçbiri kendiliğinden toplanmaz; bunları görebilmek için önkoşullar vardır ve tespit mühendisinin ilk işi bu boşlukları kapatmaktır:

- **Süreç komut satırı loglaması** açık olmalı. Security EID 4688 varsayılan olarak `CommandLine` alanını içermez; bunun için "Include command line in process creation events" GPO ayarı etkinleştirilmelidir. Bu ayar olmadan Kural 1, 2 ve 3'ün dayandığı `CommandLine` koşulları boşta kalır. Sysmon kullanılıyorsa EID 1 komut satırını doğrudan taşır ve `OriginalFileName` gibi ek zenginleştirme sağlar — bu yüzden birçok kurum Sysmon'u tercih eder.
- **Sysmon registry olayları** (EID 12/13) yalnızca Sysmon konfigürasyonu ilgili anahtarları kapsıyorsa üretilir. Tipik bir Sysmon config'i `RegistryEvent` bloğunda `CurrentVersion\Run` yollarını dahil eder; edilmezse API-temelli yazımlar tamamen görünmez kalır.
- **PowerShell Script Block Logging (EID 4104)** ve **Module Logging** ayrı ayrı etkinleştirilir; obfuscation'a karşı en değerli katman budur ama varsayılan kapalıdır.
- Logların merkezî bir SIEM'e (veya EDR'a) iletilmesi ve saklama süresinin, kalıcılığın haftalar sonra keşfedilebileceği gerçeğini karşılayacak kadar uzun olması gerekir.

Bu önkoşullar sağlanmadan yazılan bir Sigma kuralı "çalışıyor" görünür ama sessizce kördür — bu, tespit mühendisliğinin en sık yaptığı hatalardan biridir.

## 3. Tespit mantığı (gerçek Sigma kurallarına demirli)

Aşağıdaki tespit mantığı, göreve eklenen dört gerçek SigmaHQ kuralına dayanır. Hepsinin ortak paydası `logsource: category: process_creation, product: windows` olmasıdır — yani süreç oluşturma logları (Sysmon EID 1 veya Security EID 4688) üzerinde çalışırlar.

### Kural 1 — reg.exe ile Run anahtarı ekleme (de587dce-915e-4218-aac4-835ca6af6f70)

Bu kural, tekniğin en klasik biçimini yakalar: `reg.exe` aracıyla Run anahtarına değer eklenmesi. Mantığı üç koşulun **VE** ile birleşmesidir:

- `Image` alanı `\reg.exe` ile bitmeli — yani çalıştırılan araç reg.exe.
- `CommandLine` hem `reg` hem de ` add ` alt dizgelerini **birlikte** içermeli (`contains|all`). Bu, "reg add" eyleminin — okuma/sorgulama değil, yazma — gerçekleştiğini belirtir.
- `CommandLine`, hedef anahtar yolunu — `Software\Microsoft\Windows\CurrentVersion\Run` — içermeli.

Buradaki tespit felsefesi nettir: reg.exe'nin varlığı tek başına şüpheli değildir; ama reg.exe + `add` fiili + Run anahtarı yolu üçlüsü, bir kalıcılık girişiminin oldukça yüksek olasılıklı imzasıdır. Kuralın SigmaHQ tarafındaki metadata'sı (e60e5322... altında referanslanan de587dce...) bu kuralın Sysmon `.evtx` verisiyle "Positive Detection Test" geçtiğini, yani `match_count: 1` ile doğrulandığını gösterir.

### Kural 2 — Doğrudan ASEP değişikliği (24357373-078f-44ed-9ac4-6d334a668a11)

Bu kural bir öncekini genelleştirir. `Image` alanı `\reg.exe` ile bitmeli **veya** `OriginalFileName` `reg.exe` olmalı — bu ikinci koşul, dosyanın adı değiştirilerek (örneğin `r.exe`) tespitten kaçmaya çalışılmasını da yakalar; çünkü PE metadata'sındaki orijinal ad değişmez. Ardından `CommandLine` `add` içermeli (yazma fiili). Kural, sadece Run değil; birden çok ASEP anahtarını hedefler ve — kural içindeki yorumun belirttiği gibi — sorgulama/keşif (discovery) amaçlı `reg query` çağrılarıyla kesişmemek için `add` koşulunu şart koşar. Yani tasarım kararı: "yazma niyeti olmayan reg kullanımını dışarıda bırak, false positive'i azalt."

### Kural 3 — WMI üzerinden dolaylı autorun (c80e66d8-1780-48a9-b412-46663fd21ac0)

Bu kural, saldırganın `reg.exe` çağrısını doğrudan değil, `wmic process call create` aracılığıyla dolaylı olarak yapması senaryosunu hedefler. Mantığı: `Image` alanı `\wmic.exe` ile bitmeli **veya** `OriginalFileName` `wmic.exe` olmalı. Kuralın tarif ettiği tipik komut, WMIC'in bir alt süreç olarak `reg.exe add HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run ...` çalıştırması ve verinin `AppData\Roaming` altındaki bir dosyaya işaret etmesidir. Etiketleri hem `t1547.001` (Run key) hem de `t1047` (WMI) taşır — yani iki tekniğin birleşimini yakalar. Bu, "araç dolaylandırması" (indirection) yoluyla kaçınmaya karşı bir tespit katmanıdır.

### Kural 4 — Kötücül PowerShell komutları (02030f2f-6199-49ec-b258-ea71b07e03dc)

Bu kural doğrudan Run anahtarına odaklanmaz; iyi bilinen PowerShell istismar çerçevelerine (Empire, PowerSharpPack vb.) ait cmdlet adlarını süreç oluşturmada arar. Run key bağlamındaki değeri şudur: kalıcılık genellikle daha büyük bir saldırı zincirinin parçasıdır. PowerShell tabanlı bir yükleyici Run anahtarını `Set-ItemProperty` ile yazarken, aynı oturumda bu tür kötücül cmdlet'ler de görülebilir. Bu kural, Run-key alarmını **zenginleştiren** bir korelasyon sinyali olarak kullanılır — tek başına değil, bağlam olarak.

### Basit Sigma-benzeri tespit mantığı örnekleri

**Örnek A — Kullanıcı-yazılabilir konuma işaret eden Run kaydı (reg.exe):**

```yaml
title: reg.exe ile suphelı konuma Run kaydı
logsource:
    category: process_creation
    product: windows
detection:
    selection_tool:
        - Image|endswith: '\reg.exe'
        - OriginalFileName: 'reg.exe'
    selection_action:
        CommandLine|contains|all:
            - ' add '
            - '\CurrentVersion\Run'
    selection_path:
        CommandLine|contains:
            - '\AppData\'
            - '\ProgramData\'
            - '\Temp\'
    condition: selection_tool and selection_action and selection_path
```

Mantık: araç reg.exe (ya adıyla ya orijinal adıyla), fiil `add`, hedef Run anahtarı ve üstüne yazılan verinin kullanıcı-yazılabilir/geçici bir dizine işaret etmesi. Üç koşulun birleşimi false positive'i belirgin şekilde düşürür.

**Örnek B — Ofis/script ebeveyninden Run kaydı (davranışsal korelasyon):**

```yaml
detection:
    selection_action:
        Image|endswith: '\reg.exe'
        CommandLine|contains|all:
            - ' add '
            - '\CurrentVersion\Run'
    selection_parent:
        ParentImage|endswith:
            - '\winword.exe'
            - '\excel.exe'
            - '\wscript.exe'
            - '\mshta.exe'
            - '\powershell.exe'
    condition: all of selection_*
```

Mantık: reg.exe + Run yazımının, bir belge/script sürecinin çocuğu olarak ortaya çıkması neredeyse hiçbir zaman meşru değildir. Bu ebeveyn-çocuk (parent-child) bağlamı, tekil komut satırından çok daha yüksek güven sağlar. Eşik olarak bu tür bir eşleşme genellikle tekil olayda bile "high severity" alarm hak eder.

### Şiddet (severity) ve eşik kararı nasıl verilir?

Gerçek Sigma kurallarının `level` alanına doğrudan bakmak yerine, bu tekniğe özgü bir şiddet mantığı kurmak daha sağlıklıdır; çünkü aynı imza farklı bağlamlarda çok farklı risk taşır. Pratik bir yaklaşım şu eksenleri puanlayıp toplamaktır:

- **Araç + eylem imzası tek başına** (reg.exe + `add` + Run yolu): düşük-orta şiddet, tek başına genellikle triage kuyruğuna. Çünkü meşru installer'lar da bunu üretir.
- **+ Hedef yol kullanıcı-yazılabilir/geçici dizinde** (`AppData`, `Temp`, `ProgramData`): şiddeti orta-yükseğe çeker. Meşru yazılım tipik olarak `Program Files` altını gösterir.
- **+ Şüpheli ebeveyn süreç** (Office, script host, `mshta`, imzasız süreç): tek başına bile yüksek şiddet. Bu, gerçek bir saldırı zincirinin en güçlü işaretidir.
- **+ Aynı zaman penceresinde korele sinyal** (Kural 4'teki kötücül cmdlet, aynı host'ta yeni indirilen imzasız binary, C2 benzeri ağ bağlantısı): kritik şiddet, otomatik izolasyon veya acil müdahale.

Bu katmanlı puanlama, "reg.exe = alarm" ikili mantığından kaçınmanın ve analistin zamanını gerçekten önemli olaylara ayırmanın yoludur. Eşik burada sabit bir sayı değil, bağlam sinyallerinin birikimidir.

## 4. Kaçınma ve karşı-tespit + false positive

### Saldırgan tespiti nasıl atlatmaya çalışır?

- **Aracı atlamak (living off the API):** `reg.exe` yerine doğrudan `RegSetValueEx` API'sini kendi süreci içinden çağırmak. Bu, komut satırı temelli Kural 1/2'yi tamamen köreltir; çünkü ortada `reg add` içeren bir süreç yoktur.
  **Karşı-tespit:** Süreç oluşturma katmanından registry katmanına geçin. Sysmon **Event ID 13** ile `TargetObject` alanında `...\CurrentVersion\Run\` içeren tüm value-set olaylarını izleyin; `Details` alanındaki dosya yolunu bağlamla değerlendirin. Bu görünürlük, aracı ne olursa olsun yazma eylemini yakalar.

- **Araç adını değiştirmek (renamed binary):** `reg.exe`'yi `svc.exe` olarak kopyalayıp çalıştırmak, `Image|endswith: '\reg.exe'` koşulundan kaçar.
  **Karşı-tespit:** Kural 2 ve 3'te olduğu gibi `OriginalFileName` alanına dayanın. PE metadata'sındaki orijinal ad kopyalamayla değişmez, dolayısıyla adı değiştirilmiş ikili yine yakalanır.

- **Dolaylandırma:** `wmic process call create`, `explorer.exe` üzerinden başlatma veya zamanlanmış görev üzerinden reg.exe tetikleme.
  **Karşı-tespit:** Kural 3 (WMI) gibi araç-dolaylandırma kurallarını devrede tutun; ayrıca `reg.exe`'nin ebeveyn süreç dağılımını taban çizgisiyle (baseline) karşılaştırın — beklenmedik ebeveyn = sinyal.

- **Yolu gizlemek / string parçalama:** Anahtar yolunu ortam değişkeni veya birleştirme ile obfuscate etmek, PowerShell'de string'i parçalayıp `+` ile birleştirmek.
  **Karşı-tespit:** `contains|all` gibi parçalı-eşleşen koşullar tam-string obfuscation'a kısmen dayanıklıdır. PowerShell tarafında **Script Block Logging (Event ID 4104)** ve module logging ile deobfuscated içeriği yakalayın; Kural 4'teki kötücül cmdlet korelasyonunu ekleyin.

- **Daha az izlenen kardeş anahtarlar:** `Run` yerine `RunOnce`, `RunServices`, `RunOnceEx`, `Winlogon\Userinit`, `Winlogon\Shell` gibi diğer ASEP'ler.
  **Karşı-tespit:** Tespit kapsamını yalnızca `\Run` ile sınırlamayın; kardeş ASEP anahtarlarını da izleme listesine ekleyin (Kural 2 zaten birden çok ASEP anahtarını hedefler).

### Tipik false positive kaynakları ve ayıklama

- **Meşru yazılım kurulumları ve güncelleyiciler:** Uygulama kurulumları sırasında installer'lar Run/RunOnce anahtarları yazar (örneğin güncelleme sonrası tek seferlik görevler için RunOnce). Bunlar Kural 1/2'yi tetikler.
  **Ayıklama:** İmzalı (signed) ve `Program Files` altındaki bilinen installer'ları ebeveyn süreç ve dosya imzasına göre allowlist'e alın. Yazılan verinin kullanıcı-yazılabilir dizin yerine `Program Files` altına işaret etmesi, meşruiyet lehine güçlü bir işarettir (Örnek A'daki yol koşulu bunu kullanır).

- **Kurumsal dağıtım ve yönetim araçları:** SCCM/Intune, login script'leri, GPO ile dağıtılan ortam ayarları meşru olarak reg.exe çağırabilir.
  **Ayıklama:** Bilinen yönetim sunucularından/servis hesaplarından gelen olayları bağlamla filtreleyin; belirli ebeveyn süreçleri (ör. yönetim ajanı) için istisna tanımlayın. İstisnaları kör "yoksay" yerine, dar (hesap + ebeveyn + hedef yol) biçimde yazın.

- **BT/geliştirici manuel işlemleri:** Bir yönetici sorun giderirken elle `reg add ... Run` çalıştırabilir.
  **Ayıklama:** İnteraktif oturum ve bilinen yönetici kullanıcı bağlamı düşük önceliğe çekilebilir; ancak tümüyle bastırmayın — insider veya ele geçirilmiş yönetici hesabı da aynı görünür. Bunun yerine bu olayları "düşük şiddet + gözden geçir" kuyruğuna alın.

- **`reg query` ve keşif komutları:** Salt-okuma reg kullanımları meşru olabilir.
  **Ayıklama:** Kural 2'nin tasarım kararını izleyin: `add` fiilini şart koşarak `query`/okuma çağrılarını baştan dışarıda bırakın; böylece discovery gürültüsü tespit yüzeyine hiç girmez.

### Kapatıcı ilke

Run key tespiti tek bir sihirli kurala değil, **katmanlı görünürlüğe** dayanır: süreç oluşturma (EID 1/4688) birincil katman, registry value-set (EID 13/4657) API-temelli kaçışa karşı ikinci katman, PowerShell script block (EID 4104) ve ebeveyn-çocuk korelasyonu ise bağlam katmanıdır. Tek başına yüksek false positive üreten "reg.exe var" sinyali; `add` fiili, Run yol imzası, hedef dosyanın konumu ve ebeveyn süreç bağlamıyla birleştiğinde yüksek güvenli, aksiyon alınabilir bir alarma dönüşür. Savunmacının işi hırsızın hangi kapıyı kullandığını ezberlemek değil, o kapının açıldığını gösteren tüm izleri aynı anda okuyabilmektir.
