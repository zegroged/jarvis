# Zerologon (CVE-2020-1472) — Tespit

## 1. Özet: saldırı + naif tespit (KISA)

Zerologon, Netlogon Remote Protocol'ün (MS-NRPC) kimlik doğrulama kripto şemasındaki bir kusurdur. AES-CFB8 modunun IV'sinin (initialization vector) sabit sıfır seçilmesi, saldırganın `NetrServerAuthenticate3` çağrısında ClientChallenge'ı tümüyle sıfır göndererek yaklaşık 256'da 1 olasılıkla geçerli bir "computed credential" üretebilmesine yol açar. Ortalama 256 deneme, saniyeler sürer. Kimliği doğrulanmamış bir saldırgan, sadece bir DC'ye SMB/RPC erişimi olan ağ konumundan, DC'nin makine hesabının (`DC01$`) parolasını Active Directory'de boş (empty/zero) değere sıfırlar. Ardından `DRSUAPI` (DCSync) ile `krbtgt` dahil tüm hash'leri çeker; domain admin. Public PoC'ler (SecuraBV `zerologon`, Mimikatz `::zerologon`, Impacket `secretsdump`/`netlogon` örnekleri) bunu tek komuta indirdi.

Naif tespit refleksi iki yöne gider:
- **Ağ/DC olayı:** `NetrServerAuthenticate3` veya `NetrServerPasswordSet2` çağrılarını izle; ya da Netlogon named pipe (`\PIPE\netlogon`, `\PIPE\lsass`) üzerinden anormal RPC.
- **Konak olayı:** Makine hesabı parolasının değiştiğini gösteren **Event ID 4742** (A computer account was changed) ve özellikle 2020 Ağustos yamasından sonra gelen **4741/5827/5828/5829** Netlogon güvenli kanal olayları.

Yukarıdaki gerçek Sigma kurallarından `SMB Spoolss Name Piped Usage` (bae2865c) ve `First Time Seen Remote Named Pipe - Zeek` (021310d9) referansları doğrudan dirkjanm.io'nun "a different way of abusing zerologon" yazısına bağlanır — çünkü Zerologon'un en tehlikeli varyantı sadece DC'yi bozmakla kalmaz, printer bug (`spoolss`) + unconstrained delegation ile relay'e evrilir. `Operator Bloopers` kuralı (4f154fb6) ise komut satırına düşen `zerologon` / `Invoke-Nightmare` string'ini yakalar. Bunlar naif katmandır. Asıl iş, bunları birbirine bağlamaktır.

## 2. Naif tespit neden yetmez

**Kör nokta 1: RPC çağrısı standart olarak loglanmaz.** `NetrServerAuthenticate3` ve `NetrServerPasswordSet2` işletim sisteminin varsayılan denetim politikasında hiçbir Security event üretmez. Bunları görmek için ya RPC firewall / EDR ETW seviyesinde MS-NRPC opnum'larını (opnum 26 = `NetrServerPasswordSet2`, opnum 2/26 aralığı) yakalayacak bir sensör gerekir, ya da ağda Zeek/Suricata DCE-RPC ayrıştırması. Çoğu SOC'de bu telemetri yoktur. "NetrServerAuthenticate3'ü izle" tavsiyesi kâğıt üzerinde doğru, sahada boş çıkar — çünkü kaynak log akmıyordur.

**Kör nokta 2: 4742 tek başına yalancıdır ve geç kalır.** Zerologon başarılı olduğunda AD'de makine hesabı parolası sıfırlanır ve **Event ID 4742** düşer. Ama 4742 son derece gürültülü bir olaydır: her makine hesabı parolasını normalde 30 günde bir kendisi değiştirir (bu da 4742 üretir), GPO değişiklikleri, `dNSHostName`/`servicePrincipalName` güncellemeleri, SCCM, Intune, cluster işlemleri hep 4742 doğurur. Kritik ayırt edici: Zerologon'da parolayı değiştiren **`Subject`** (SubjectUserName / SubjectSid) genellikle **`ANONYMOUS LOGON`** veya bir makine hesabıdır ve **hedef hesap ile özne aynıdır ama işlem uzaktan, kimliksiz kanaldan gelmiştir**. Naif "4742 gördüm alarm ver" kuralı günde yüzlerce meşru olayda boğulur.

**Kör nokta 3: Zaman penceresi.** Başarılı Zerologon'un imzası tek olay değil, **kısa pencerede yoğun tekrar**dır: saldırgan ortalama 256 kez `NetrServerAuthenticate3` dener. Bu, milisaniyeler-saniyeler içinde aynı kaynaktan onlarca-yüzlerce başarısız kimlik doğrulama demektir. Konak logu bu denemeleri göstermez; sadece nihai başarıyı (parola sıfırlama) gösterir. Yani konak tabanlı tespit **her zaman olaydan sonra** gelir — sömürü çoktan tamamlanmıştır.

**Atlatma:** Saldırgan parolayı hemen geri yazabilir (bazı PoC'ler orijinal makine parolasını restore etmeye çalışır ki DC güvenli kanalı bozulmasın ve tespit/operasyonel arıza gizlensin). Bu durumda 4742 iki kez düşer (sıfırlama + restore) veya restore sessizce yapılır; naif "parola boşa çekildi" tespiti restore edilmiş ortamda yanıltıcı biçimde "her şey normal" görünür.

**False positive seli:** `First Time Seen Remote Named Pipe` kuralı `netlogon` pipe'ını filter_keywords içinde tutar — yani netlogon named pipe kullanımı zaten "bilinen/beklenen" kabul edilir çünkü domain'de sürekli akar. Bu da tersinden sorun: netlogon pipe'ı o kadar normaldir ki, salt "netlogon pipe kullanıldı" hiçbir zaman alarm olamaz. Spoolss pipe kuralı da (bae2865c) yazar kendisi belirtir: yazıcı sunucusu rolü de üstlenen DC'ler sürekli tetikler (`falsepositives: Domain Controllers ... acting as printer servers`).

**Kör nokta 4: "Başarısız denemeler görünmez."** Zerologon'un 256 denemesinin önemli kısmı **başarısız** kimlik doğrulamadır. Ama `NetrServerAuthenticate3` başarısızlığı bir logon failure (4625) üretmez — bu Security katmanının failed-logon dünyasının dışında, RPC katmanında gerçekleşir. Yani "kısa pencerede çok sayıda başarısız oturum" tabanlı klasik brute-force tespitleri (4625 sayacı) Zerologon'a **tamamen kördür**. Analist "brute force uyarım tetiklenmedi, demek ki brute yok" diye düşünürse yanılır; buradaki brute farklı bir protokol düzleminde olur ve o düzlemde sensör yoksa iz bırakmaz. Bu, Zerologon'un neden bu kadar "sessiz" istismar edilebildiğinin de teknik açıklamasıdır.

**Kör nokta 5: Zaman damgası ve saat kayması.** Korelasyon zinciri saniyeler-dakika penceresine dayanır; ama üç farklı log kaynağı (ağ sensörü, DC Security, DC Directory Service) çoğu ortamda farklı zaman referanslarıyla, farklı ingest gecikmeleriyle SIEM'e ulaşır. Zeek verisi neredeyse gerçek zamanlı gelirken WEF/WEC üzerinden toplanan Security olayları dakikalar geç kalabilir. Naif "aynı saniye" penceresi bu gecikme yüzünden gerçek zinciri parçalar; pencereyi gevşetmek ise false positive'i artırır. Pratikte pencereyi olay kaynağının gerçek zaman damgasına (`_time`/`@timestamp` değil, olayın kendi `TimeCreated`'ı) göre kurmak ve ingest gecikmesini ayrı tutmak gerekir.

## 3. Korelasyon zinciri (asıl değer)

Tek sinyal zayıf. Yüksek güven için çok aşamalı, farklı bağlamlardan gelen sinyalleri kısa pencerede bağlamak gerekir. Zerologon'un gerçek dünya kill-chain'i:

**A — Sömürü denemesi (ağ/DC katmanı):**
Aynı kaynak IP → tek DC'ye, `\PIPE\netlogon` üzerinden **kısa pencerede (< 10 sn) yüksek hacimli `NetrServerAuthenticate3` çağrısı**, ardından tek bir `NetrServerPasswordSet2`. Zeek `dce_rpc.log` içinde `endpoint=netlogon`, `operation=NetrServerAuthenticate3` yoğunluğu. 2020 sonrası yamalı DC'lerde bu deneme **Event ID 5829** (vulnerable Netlogon secure channel connection reddedildi) veya izin modunda **5827/5828** üretir. Yamasız/uyumluluk modundaki DC'de ise 5829 yerine sessizce geçer.

**B — Parola sıfırlama (AD katmanı, farklı bağlam):**
A'dan saniyeler sonra, aynı DC'de **Event ID 4742** — hedef `DC01$` makine hesabı, `SubjectUserName = ANONYMOUS LOGON` veya sıfır/boş özne, `PasswordLastSet` değişti. Kritik: **bir makine kendi parolasını sıfırladığında özne o makinenin kendisi (sistem bağlamı) olur, uzaktan anonim değil.** Anonim özne + makine hesabı parola değişimi kombinasyonu neredeyse imzadır.

**C — Kimlik bilgisi hırsızlığı (AD replikasyon katmanı):**
B'den kısa süre sonra, bozulan makine hesabıyla kimlik doğrulanıp **DCSync**: `NetrServerPasswordSet2` sonrası aynı kaynaktan **Event ID 4662** — `Replicating Directory Changes` (`DS-Replication-Get-Changes`, GUID `1131f6aa-9c07-11d1-f79f-00c04fc2dcd2` ve `1131f6ad-...`) çağrısı, üstelik özne bir **Domain Controller olmayan** bir hesap. Ağda `drsuapi` opnum `DRSGetNCChanges`.

**Somut yüksek güven deseni:**
> `A` (kaynak_ip=X → DC01, `NetrServerAuthenticate3` sayısı > 100 / 10 sn)
> **+ kısa pencere (≤ 60 sn) `B`** (Event 4742, hedef=DC01$, özne=ANONYMOUS/boş, aynı DC01)
> **+ `C`** (Event 4662, `DS-Replication-Get-Changes`, özne ≠ bilinen DC hesabı, aynı X'e izlenebilir oturumdan)
> = **kesin Zerologon → DCSync ihlali.**

Bu üçlü aynı anda yanlış pozitif üretemez. Tek başına A tuning-gerektiren gürültü, tek başına B günlük operasyon, tek başına C bazen meşru replikasyon araçları — ama A→B→C sıralı ve saniyeler-dakika penceresinde asla masumca oluşmaz. Değerin tamamı bu ardışıklıkta ve farklı log kaynaklarını (ağ DCE-RPC + Security 4742 + Directory Service 4662) tek zaman çizelgesinde birleştirmektedir.

**Neden pencere kısa tutulmalı — ve neden bazen uzatılmalı:** Otomatik PoC'ler (SecuraBV `zerologon_tester` + exploit, Impacket) A→B→C'yi saniyeler içinde koşar; burada 60 sn pencere fazlasıyla yeterlidir ve dar tutmak false positive'i keser. Ama elle çalışan, "yavaş ve alçak" (low-and-slow) bir saldırgan B (parola sıfırlama) ile C (DCSync) arasına dakikalar-saatler koyabilir; hatta B'yi bir gün, C'yi ertesi gün yapabilir. Bu yüzden pratikte iki katmanlı kural mantıklıdır: (1) sıkı pencere (≤ 60 sn) A+B+C = **P1 anında**; (2) gevşek pencere (≤ 24 saat) B+C = **P2 araştır**. İkinci katman, parola zaten sıfırlanmış bir DC hesabının sonradan DCSync yapmasını, denemeler kaçırılmış olsa bile yakalar.

**Zincirin "sol tarafı" — ilk erişim bağlamı:** A adımının kaynağı (kaynak_ip=X) genellikle yeni ele geçirilmiş bir iç konaktır (phishing sonrası bir workstation, ya da internete açık bir VPN/edge cihazı). Olgun bir korelasyon, X'i geriye doğru da bağlar: X aynı gün içinde şüpheli bir process_creation (`Invoke-Nightmare`, encoded PowerShell), bir C2 beacon, ya da yeni bir uzak oturum kaynağı mı? Zerologon nadiren tek başına gelir; bir lateral movement zincirinin ortasındadır. `Operator Bloopers` kuralının (4f154fb6) `Invoke-Nightmare`/`zerologon` string'i tam da bu "sol taraf" bağlamında, X üzerinde çalışan operatörün hatası olarak devreye girer ve zinciri ilk-erişim konağına demirler.

**Alternatif zincir (dirkjanm varyantı — relay):**
Zerologon her zaman parola sıfırlamaz. dirkjanm.io'nun anlattığı yol: printer bug ile hedef DC'yi `spoolss` üzerinden saldırgan makinesine kimlik doğrulamaya zorla → NTLM relay → Netlogon oturumu. Burada zincir:
> `SMB Spoolss Name Piped Usage` (bae2865c, path IPC$, name=spoolss, kaynak = beklenmedik bir konak)
> **+ kısa pencerede** DC'den saldırgan konağına giden makine hesabı NTLM kimlik doğrulaması (Event 4624 tip 3, `DC01$`, kaynak workstation = beklenmedik)
> **+** ardından o oturumdan Netlogon/AD değişikliği
> = relay tabanlı Zerologon istismarı. Bu, salt "4742 gördüm" tespitinin tümüyle kaçırdığı yoldur, çünkü parola sıfırlama adımı farklı görünür.

## 4. False positive gerçeği ve triage yargısı

Sahada 4742 ve 4662 alarmları geldiğinde analistin oranı doğru okuması lazım. En sık yalancı kaynaklar:

- **SCCM / MECM ve Intune:** İstemci onarımı, yeniden kayıt, `Reset Computer Account Password` görevleri toplu 4742 üretir. İmza: özne meşru bir servis hesabı veya SCCM sunucu hesabı, kaynak iç yönetim sunucusu.
- **Yedekleme/geri yükleme ve imaj:** Bir makinenin snapshot'tan geri yüklenmesi güvenli kanalı bozar, makine parolayı yeniler → 4742. Küme (cluster) node failover'ları da.
- **Güvenlik tarayıcıları (Nessus/Qualys/Tenable):** Netlogon zafiyet plugin'leri (örn. Zerologon kontrol plugin'i) aslında `NetrServerAuthenticate3`'ü **sıfır challenge ile ama parola sıfırlama YAPMADAN** dener. Bu, A adımını (yoğun Authenticate3) meşru olarak tetikler. Ayırt edici: tarayıcı kaynağı bilinen scanner IP'sinden gelir, B (parola sıfırlama) ve C (DCSync) **asla** takip etmez. İyi bir Zerologon plugin'i güvenli kontrol yapar; kötü/eski PoC'ler gerçekten sıfırlar.
- **Meşru DCSync:** Azure AD Connect / Entra Connect senkron hesabı `DS-Replication-Get-Changes` iznine sahiptir ve düzenli 4662 üretir. Diğer DC'ler de birbirini replike ederken 4662 üretir. Bunlar allow-list'e girmeli.

**Analistin öncelik sıralaması (triage yargısı):**
1. **Önce C'yi doğrula (kanıt gücü en yüksek).** 4662 `DS-Replication-Get-Changes` öznesi bir DC hesabı mı, yoksa AD Connect hesabı mı, yoksa **rastgele bir workstation/kullanıcı** mı? Üçüncüsüyse P1 — DCSync gerçek. Bu tek soru çoğu vakayı ya kapatır ya patlatır.
2. **Sonra B'nin öznesini oku.** 4742'de özne `ANONYMOUS LOGON` / boş SID ise ve hedef bir **DC makine hesabı** ise, meşru hiçbir yönetim aracı böyle davranmaz → yükselt. Özne SCCM/servis hesabı ise düşür.
3. **A'yı bağlamla oku.** Yoğun `NetrServerAuthenticate3` kaynağı bilinen scanner mı? Öyleyse ve B/C yoksa, muhtemelen vulnerability scan; yine de scanner'ın gerçekten sıfırlama yapmadığını doğrula (DC'nin `PasswordLastSet` değeri değişmemiş olmalı).
4. **DC makine hesabı güvenli kanal sağlığı.** Şüpheli DC'de `nltest /sc_verify:<domain>` veya `Test-ComputerSecureChannel` başarısızsa, parola gerçekten bozulmuş → aktif istismar veya yarım kalmış saldırı. Bu operasyonel kanıttır ve genelde yan etki olarak diğer servislerin (DFS, replikasyon) bozulmasıyla kendini belli eder.

Pratik yargı: **4742+4662'yi izole alarm olarak P3 tutup, "özne anonim/beklenmedik + kısa pencerede zincir" koşulunu P1'e çıkaran** kademeli bir kural, hem seli keser hem gerçek olayı kaçırmaz.

## 5. Kaçınma → karşı-tespit

**Kaçınma 1 — Parolayı restore et.** Olgun saldırgan sıfırlamadan sonra makine hesabı parolasını orijinal (veya çalışır) değere geri yazar ki DC'nin güvenli kanalı bozulmasın, servisler çökmesin ve mavi takım "bir şey kırıldı" sinyali almasın. **Karşı-tespit:** Kısa pencerede aynı makine hesabı için **iki 4742** (sıfırla + geri yaz) veya olağandışı `PasswordLastSet` çift değişimi. Ayrıca AD'de makine hesabı parolasının bilgisayarın kendi zamanlanmış döngüsü dışında değişmesi — makine hesabı parolaları normalde makinenin kendisi tarafından 30 günde bir değişir; **DC'nin kendi parolasının başka bir bağlamdan değişmesi** başlı başına anomalidir.

**Kaçınma 2 — Doküman dışı: yavaşlatma / dağıtma.** 256 denemeyi tek patlamada yapmak yerine denemeleri zamana yayarak "yoğun tekrar" eşiğinin altında kalmak. **Karşı-tespit:** Hacim eşiğine değil, **`NetrServerAuthenticate3` içinde ClientChallenge alanının tümü sıfır olması** semantiğine dayan. Zeek/EDR seviyesinde challenge byte'larını görebiliyorsan, `all-zero client challenge` tek başına neredeyse deterministik bir imzadır — hiçbir meşru istemci sıfır challenge göndermez. Bu, hacimden bağımsız çalışır ve yavaşlatma atlatmasını yener.

**Kaçınma 3 — Relay yolu (parola sıfırlama yok).** dirkjanm varyantında AD'de parola hiç sıfırlanmaz; kimlik relay edilir. 4742 hiç düşmez. **Karşı-tespit:** İkinci derece — `spoolss` printer bug tetiği (bae2865c) + DC makine hesabının **beklenmedik bir konağa NTLM ile kimlik doğrulaması** (Event 4624/4776 çapraz). DC'nin bir workstation'a `NTLM` ile authenticate etmesi doğal değildir.

**Kaçınma 4 — Named pipe/taşıma değiştirme.** MS-NRPC hem `\PIPE\netlogon` (SMB) hem doğrudan TCP/135 + dinamik RPC üzerinden konuşulabilir. SMB pipe izlemene güvenen tespit, saldırgan doğrudan TCP RPC endpoint mapper'a giderse kör kalır. **Karşı-tespit:** Sadece SMB pipe'ı değil, **RPC endpoint UUID'ini** izle: Netlogon interface UUID `12345678-1234-abcd-ef00-01234567cffb`. Taşıma katmanından bağımsız olarak bu UUID'e giden `opnum 4` (`NetrServerReqChallenge`) → `opnum 26` (`NetrServerAuthenticate3`) → `NetrServerPasswordSet2` dizisi imzadır.

**Kaçınma 5 — Komut string'ini gizleme.** `Operator Bloopers` kuralı (4f154fb6) `zerologon` / `Invoke-Nightmare` gibi düz metinleri yakalar; saldırgan encoded PowerShell veya yeniden adlandırılmış araçla bunu kolayca atlar. Bu kural gerçekçi olarak yalnızca operatör hatasına (yanlış pencereye komut yapıştırma) karşı işe yarar; birincil tespit olarak güvenilmez.

**Kaçınma 6 — Challenge'ı tümüyle sıfır değil, "az sayıda sıfır byte" yapma.** Orijinal PoC ClientChallenge'ı 8 byte sıfır gönderir çünkü matematiksel olarak en kolay yol budur. Ancak "all-zero challenge" imzasına dayanan bir tespit, saldırgan farklı bir zayıf challenge kalıbı kullanırsa teorik olarak atlatılabilir. **Karşı-tespit:** Sadece byte kalıbına değil, **davranışa** da bak — meşru bir istemci `NetrServerReqChallenge` (opnum 4) ile önce challenge kurar, sonra tek `NetrServerAuthenticate3` yapar ve başarır. Zerologon'da ise **aynı kaynaktan tekrar tekrar ReqChallenge+Authenticate3 çifti** görülür, çünkü her deneme yeni bir oturum kurulumu gerektirir. Bu "tekrar eden challenge-kurulum döngüsü" byte kalıbından bağımsız bir davranışsal imzadır.

**Kaçınma 7 — Bozulan hesabı geri onarma dışında, replikasyonu farklı DC'ye yönlendirme.** DCSync'i saldırgan, ele geçirdiği DC değil de coğrafi olarak uzak, daha az izlenen bir DC'ye yöneltebilir. **Karşı-tespit:** 4662 tespitini tek bir "birincil" DC'ye değil, **tüm DC'lere** eşit uygula; DCSync'in hangi DC'den geldiği değil, **öznenin kim olduğu** belirleyicidir. Merkezi olmayan (per-DC) alarm mantığı bu kayma atlatmasını yener.

## 6. SIEM/saha gerçeği

**Field mapping ve varsayılan loglanmayanlar:**

| Sinyal | Kaynak | Varsayılan loglanır mı? | Anahtar alanlar |
|---|---|---|---|
| `NetrServerAuthenticate3` yoğunluğu | Zeek `dce_rpc.log` / EDR ETW | Hayır (sensör gerekir) | `endpoint`, `operation`, `id.orig_h` |
| Netlogon zafiyet olayı | Directory Service log | 2020-08 yaması sonrası kısmen | Event 5827/5828/5829 |
| Makine hesabı parola sıfırlama | Security | Evet (Account Management denetimi açıksa) | Event **4742**, `TargetUserName`, `SubjectUserName`, `SubjectLogonId` |
| DCSync | Security | Sadece `Audit Directory Service Access` + SACL açıksa | Event **4662**, `Properties` (GUID `1131f6aa...`) |
| Spoolss pipe | Zeek `smb_files` | Sensör gerekir | `path` endswith `IPC$`, `name=spoolss` |

**En kritik saha gerçeği:** **4662 varsayılan olarak yararlı biçimde loglanmaz.** `Audit Directory Service Access` alt kategorisi açık olmalı VE domain root nesnesinde uygun **SACL** ayarlanmış olmalı; aksi halde DCSync (C adımı) hiç görünmez. Birçok kurumda bu SACL yoktur, dolayısıyla korelasyon zincirinin en güçlü halkası kayıptır. Zerologon tespiti kurmadan önce **ilk iş**: DS Access denetimi + `DS-Replication-Get-Changes` için SACL doğrulaması.

**Splunk / Sentinel / Elastic farkı:**

- **Splunk:** 4742 ve 4662 `WinEventLog:Security` içinde gelir (Splunk_TA_windows). `NetrServerAuthenticate3` için Zeek verisi ayrı sourcetype'tır (`bro:dce_rpc:json` / `corelight`). Zinciri kurmak için `transaction`/`stats` ile üç farklı sourcetype'ı `dest=DC01` ve zaman penceresiyle join gerekir — pahalı; genelde `stats min(_time) max(_time) by ...` + `eval` pencere kontrolü daha ölçeklenir. Not: 4662'de `Object.Properties` içindeki replikasyon GUID'i tek satırda gelmez, `Accesses` ve `Properties` alanlarını ayrıştırmak gerekir.
- **Microsoft Sentinel:** `SecurityEvent` (4742/4662) + `Microsoft Defender for Identity` (MDI) en büyük avantajdır — **MDI, Zerologon'u ağ seviyesinde `NetrServerAuthenticate3` sıfır-challenge olarak zaten yerleşik tespit eder** ("Suspected Netlogon privilege elevation" / CVE-2020-1472 exploitation attempt uyarısı). Sentinel'de saf KQL yerine MDI alert'ini birincil, `SecurityEvent` korelasyonunu doğrulama olarak kullanmak en verimli mimaridir. Zeek verisi yoksa MDI bu boşluğu kapatan tek pratik yoldur.
- **Elastic:** ECS ile 4742 → `winlog.event_id`, `winlog.event_data.TargetUserName`, `winlog.event_data.SubjectUserName`. Zeek entegrasyonu (`filebeat` zeek module) DCE-RPC'yi `zeek.dce_rpc.operation` olarak getirir. EQL `sequence by winlog.computer_name with maxspan=1m` ile A→B→C zincirini native ifade etmek Elastic'in en güçlü yanıdır; `sequence` DSL bu ardışık-pencere desenine Splunk/Sentinel'den daha doğrudan oturur.

**Tuning öncelikleri:**
1. Scanner IP'lerini (Nessus/Qualys) A adımından **hariç tutma** — ama sadece A'dan; B/C hariç tutulmamalı (scanner asla sıfırlama yapmamalı, yaparsa gerçekten alarm).
2. AD Connect / Entra Connect senkron hesabını ve DC makine hesaplarını 4662 `DS-Replication-Get-Changes` allow-list'ine al.
3. SCCM/Intune servis hesaplarını 4742 özne allow-list'ine al — **ama özne `ANONYMOUS LOGON` veya boş ise asla whitelist'leme.**
4. Yamayı doğrula: DC'ler August 2020+ yamalı ve **enforcement modunda** (`FullSecureChannelProtection=1`) olmalı. Enforcement açıkken zaten çoğu sömürü 5829 ile reddedilir; bu durumda tespit stratejisi "başarılı ihlal" yerine "reddedilen deneme (5829 patlaması)"na kayar — ki bu daha erken ve daha temiz bir sinyaldir.
5. `nltest /sc_verify` ve `Test-ComputerSecureChannel` çıktısını DC sağlık izlemesine bağla — bozuk güvenli kanal, kaçırılmış bir istismarın operasyonel parmak izidir.

**Özet yargı:** Zerologon'da güvenilir tespit, tek bir Sigma kuralının değil, **ağ DCE-RPC (sıfır-challenge / opnum dizisi) + Security 4742 (anonim özne) + Directory Service 4662 (beklenmedik DCSync)** üçlüsünü kısa zaman penceresinde bağlayan korelasyonun işidir. Yama enforcement açıksa tespiti 5829 reddedilen-deneme sinyaline kaydır; 4662 için SACL denetimini kurmadan zincirin en güçlü halkası zaten kayıptır. Sahada işi bitiren şey imza ezberi değil, üç farklı log kaynağını tek zaman çizelgesinde okuyabilen boru hattıdır.
