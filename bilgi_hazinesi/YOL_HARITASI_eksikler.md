# Bilgi Hazinesi — Eksik Kapsama Yol Haritası

> 18 alan uzmanı ajanının, mevcut 186 konuluk korpusu denetleyerek çıkardığı
> kapsama boşlukları. Bu, önümüzdeki aylarda üretilecek uzman içeriğin
> önceliklendirilmiş listesidir (genişleyen taksonomi). Toplam 194 boşluk.

## SİBER GÜVENLİK

### Web Uygulama Güvenliği
- **[🔴 YÜKSEK] Content Security Policy (CSP) Tasarımı ve Bypass Teknikleri**  
  Korpuste XSS var ama CSP'nin kendisi (nonce/hash stratejileri, strict-dynamic, unsafe-inline tuzaklari, JSONP/AngularJS/Iframe ile CSP bypass, dangling markup) ayri ve derin bir konu olarak yok. Modern XSS savunmasinin merkezi budur ve profesyonel pentest/savunma egitiminde ayri baslik olarak islenmesi gerekir.
- **[🔴 YÜKSEK] Tarayici Guvenlik Modelleri: Same-Origin Policy, Sandboxing, Site Isolation**  
  CORS yanlis yapilandirmasi listede var ama temel SOP mekanigi, postMessage guvenligi, iframe sandbox ozniteligi, COOP/COEP/CORP (cross-origin isolation) ve Spectre sonrasi site isolation gibi tarayicinin cekirdek izolasyon modelleri ayri kapsanmiyor; WAF/tarayici katmani odakli bir alanda bu temel olmadan diger konular eksik kalir.
- **[🔴 YÜKSEK] HTTP/2 ve HTTP/3 (QUIC) Protokol Duzeyi Saldirilari**  
  Request Smuggling listede ama klasik HTTP/1.1 odakli; HTTP/2 ozel duz metin/mux smuggling (H2.CL, H2.TE), stream multiplexing zafiyetleri (Rapid Reset/CVE-2023-44487 DoS), HPACK/QPACK sikistirma saldirilari ve HTTP/3-QUIC'e ozgu yeni saldiri yuzeyi ayri ve guncel bir alan; istenen mercek (HTTP/2-3 katmani) acikca bunu talep ediyor.
- **[🔴 YÜKSEK] WAF/RASP Atlatma Teknikleri ve Payload Obfuscation**  
  Web Cache Poisoning ve genel injection konulari var ama WAF imza atlatma (encoding katmanlari, HTTP parameter pollution, case/whitespace manipulasyonu, protokol seviyesi kaçaklar, RASP bypass) profesyonel red-team/bug bounty egitiminde kritik ayri bir modul; mercekte acikca istenmis ama listede yok.
- **[🟡 orta] Web Cache Deception**  
  Web Cache Poisoning kapsanmis ama farkli bir zafiyet sinifi olan Cache Deception (statik kaynak sanma yoluyla hassas sayfalarin cache'lenmesi) ayri bir teknik olup modern CDN/edge-cache mimarilerinde siklikla karistirilir; ayri islenmezse ogrenciler ikisini birbirine karistirir.
- **[🟡 orta] Client-Side Prototype Pollution'in DOM XSS'e Zincirlenmesi ve DOM Clobbering**  
  Prototype Pollution ve XSS ayri ayri var ama DOM Clobbering (HTML elemanlariyla JS degiskenlerini/global nesneleri ezme) ve bunun gadget zincirleriyle sanitizer bypass'ina donusmesi ayri, guncel (DOMPurify bypass'larinda kullanilan) bir teknik ve listede yok.
- **[🟡 orta] Single Page Application (SPA) ve Client-Side Routing Guvenligi**  
  Frontend Mimari genel baslik olarak var ama SPA'lara ozgu client-side yetkilendirme yanilgilari, hash-based routing acik parcalari, postMessage tabanli mikro-frontend iletisimi ve token'in localStorage/sessionStorage'da saklanmasinin XSS ile birlesimi gibi modern SPA'ya ozgu riskler ayri islenmiyor.
- **[🟡 orta] Guvenli Cerez Ozellikleri ve SameSite/Partitioned Cookie Mekanikleri**  
  Oturum Yonetimi genel baslikta var ama SameSite=Lax/Strict/None ayrintilari, CHIPS (Partitioned cookies), cookie prefix (__Host-/__Secure-), ve ucuncu taraf cerezlerin kaldirilmasi sonrasi ortaya cikan yeni saldiri/savunma dengeleri (bounce tracking, storage access API) ayri ve guncel bir alt konu.
- **[🟡 orta] Web Skimming / Magecart ve Ucuncu Taraf Script Tedarik Zinciri Riski**  
  Subdomain Takeover var ama sayfaya gomulen ucuncu taraf JS kutuphanelerinin (analytics, odeme widget'lari, reklam script'leri) ele gecirilmesiyle yapilan kart bilgisi hirsizligi (Magecart tarzi saldirilar) ve bunun Subresource Integrity (SRI) ile onlenmesi ayri, gercek dunyada cok yaygin gorulen bir saldiri sinifi.
- **[⚪ düşük] gRPC-Web ve Modern API Gateway Guvenligi**  
  GraphQL/gRPC gelistirici tarafinda var ama gRPC-Web'in tarayicidan tuketilmesi, API Gateway/BFF (Backend-for-Frontend) katmaninda yetkilendirme tutarsizliklari ve schema/introspection ifsasi guvenlik merceginden ayri ele alinmiyor; API Gateway'lerin merkezi rol oynadigi modern mimarilerde onemli bir bosluk.
- **[⚪ düşük] Bot Yonetimi, CAPTCHA Bypass ve Otomasyon Tespiti**  
  Rate Limiting var ama credential stuffing/scraping/otomatik hesap olusturmaya karsi bot tespiti (fingerprinting, davranissal analiz, CAPTCHA/Turnstile atlatma teknikleri) web uygulama guvenliginin buyuyen bir alt alani olup listede ayri yer almiyor.

### Kriptografi
- **[🔴 YÜKSEK] Post-Quantum Kriptografi (ML-KEM/Kyber, ML-DSA/Dilithium, SLH-DSA/SPHINCS+)**  
  NIST 2024 standartlari (FIPS 203/204/205) yayinlandi; 'harvest now, decrypt later' tehdidi ve klasik RSA/ECC'nin kirilma riski nedeniyle profesyonel bir kripto egitimi icin artik zorunlu bir konu, ancak listede hic yer almiyor.
- **[🔴 YÜKSEK] Uygulamali Kriptografik Saldirilar (Bleichenbacher, ROCA, Nonce Reuse/ECDSA-Sony, Bit-flipping, Length Extension)**  
  Padding Oracle disinda somut, tarihsel gercek CVE tabanli kriptografik istismar teknikleri eksik; teorik primitiflerin (RSA/ECC/HMAC) nasil yanlis kullanilinca kirildigini gosteren pratik saldiri sinifi kapsanmiyor.
- **[🔴 YÜKSEK] Sifreleme Modlari ve Yanlis Kullanim Riskleri (ECB/CBC/CTR/GCM, IV/Nonce yonetimi, AEAD)**  
  Simetrik Sifreleme basligi cok genel; mod secimi, IV tekrari, GCM nonce collision gibi gercek dunya zafiyetlerinin kaynagi olan pratik konu ayri ve derinlemesine islenmiyor.
- **[🔴 YÜKSEK] Yan Kanal Saldirilari (Timing, Power Analysis/DPA, Cache-timing, Spectre/Meltdown'un kriptoya etkisi)**  
  Kriptografik protokollerin matematiksel guvenliginden bagimsiz, gercek donanim/yazilim implementasyonlarinda en yaygin kirilma nedenlerinden biri; korpusta hic yer almiyor.
- **[🟡 orta] Sifir Bilgi Ispatlari (zk-SNARK/zk-STARK) ve Guvenli Cok Partili Hesaplama (MPC)**  
  Web3/Akilli Sozlesme basligi altinda ustu kapali gecilebilir ama modern gizlilik-korumali protokollerin (blockchain, kimlik dogrulama, gizli oy) temelini olusturan bu alan ayri bir derinlik gerektirir.
- **[🟡 orta] Eliptik Egri Guvenlik Tuzaklari (Egri secimi, invalid curve/twist attacks, small subgroup, side-channel'a acik implementasyonlar)**  
  Asimetrik Sifreleme (RSA/ECC) genel basligi var ama ECC'ye ozgu implementasyon hatalari (ornegin invalid point saldirilari) ayri, somut bir alt konu olarak eksik.
- **[🟡 orta] Kriptografik Protokol Tasarimi ve Formel Dogrulama (Noise Protocol, Signal/Double Ratchet, protokol analiz araclari - Tamarin/ProVerif)**  
  TLS ic yapisi var ama uctan uca sifreleme mesajlasma protokolleri (Signal) ve protokollerin formel dogrulanmasi ayri, onemli bir uygulama alani olarak kapsanmiyor.
- **[🟡 orta] Anahtar Turetme Fonksiyonlari (KDF) ve Parola Tabanli Anahtar Turetme (HKDF, Argon2, PBKDF2/scrypt karsilastirmasi)**  
  Parola Saklama/Hashleme ile Anahtar/Sir Yonetimi basliklari arasinda kalan, anahtar turetmenin kendine ozgu tuzaklarini (domain separation, salt/info kullanimi) iceren spesifik konu ayrica islenmiyor.
- **[🟡 orta] Kripto Kutuphane Guvenligi ve Yanlis API Kullanimi (OpenSSL/libsodium/BouncyCastle yanlis kullanim kaliplari, FIPS uyumlulugu, kripto-agility)**  
  Gercek dunyada kriptografik zafiyetlerin cogu algoritma kirilmasindan degil, kutuphanelerin yanlis/guvensiz API kullanimindan kaynaklanir; 'dogru kullanim kaliplari' mercegi acisindan kritik ama eksik.
- **[⚪ düşük] Homomorfik Sifreleme (Kismi/Tam - FHE) ve Gizlilik Korumali Hesaplama**  
  Ileri duzey ama gittikce onem kazanan bir alan; gizli veri uzerinde islem yapma ihtiyaci olan bulut/AI senaryolarinda ozel bir konu olarak eksik.

### Ag Guvenligi
- **[🔴 YÜKSEK] SMB Protokol Guvenligi ve Saldirilari (SMB Relay, EternalBlue/MS17-010, SMB Signing, Null Session Enum)**  
  Listede LLMNR/NTLM Relay ve Pass-the-Hash var ama SMB'nin kendisi (protokol ic yapisi, SMBv1/2/3 farklari, SMB signing zorunlulugu, EternalBlue sinifi zafiyetler, smbclient/enum4linux ile enumerasyon) ayri ve derin islenmemis; kurumsal ic ag sizmalarinin buyuk kismi SMB uzerinden yuruyor.
- **[🔴 YÜKSEK] RDP Guvenligi (BlueKeep, RDP Session Hijacking, CredSSP/NLA, RDP uzerinden Pivoting/Proxying)**  
  Uzak masaustu protokolu hem sizma hem savunma tarafinda kritik saldiri yuzeyi; BlueKeep gibi RCE zafiyetleri, NLA atlatma, RDP restricted-admin/pass-the-hash senaryolari ve ransomware gruplarinin birincil giris noktasi olmasi listede yer almiyor.
- **[🔴 YÜKSEK] Trafik Analizi ve Derin Paket Inceleme (Wireshark/tcpdump ile Protokol Analizi, PCAP Forensics, Anomali Tespiti)**  
  Network Forensics genel baslik olarak var ama paket seviyesinde canli/offline trafik analizi metodolojisi (filtreleme, akis takibi, sifreli trafik metadata analizi, anomali imzalari) ayri, uygulamali bir yetkinlik alani olarak eksik; SOC/IR calismalarinin temel taslarindan biri.
- **[🔴 YÜKSEK] Ag Cihazlari Guvenligi (Router/Switch Sertlestirme, VLAN Hopping, STP Manipulasyonu, HSRP/VRRP Saldirilari, Router/Switch OS Zafiyetleri)**  
  Firewall/Segmentasyon var ama anahtarlama/yonlendirme katmanina ozgu saldirilar (VLAN hopping, DTP suistimali, STP kok koprusu ele gecirme, first-hop redundancy protokol saldirilari) ve cihaz yonetim arayuzu sertlestirmesi kapsam disinda.
- **[🔴 YÜKSEK] Network Traffic Anomaly/IDS-IPS Motorlari (Snort/Suricata Kural Yazimi, NetFlow/sFlow Analizi)**  
  SIEM/Sigma/Detection Engineering var ama ag katmaninda imza/anomali tabanli IDS/IPS kural gelistirme ve NetFlow/sFlow ile hacimsel trafik gorunurlugu ayri, pratik bir beceri olarak eksik; ag guvenligi savunma tarafinin merkezinde yer alir.
- **[🟡 orta] SNMP Guvenligi (Community String Brute-force, SNMP Enumeration, SNMPv3 Guvenligi)**  
  Ag cihazi yonetiminde yaygin protokol; varsayilan community string'ler, MIB enumerasyonu ile ag topolojisi/cihaz bilgisi sizdirma ve SNMP tabanli DDoS amplifikasyonu konusu kapsamda yok.
- **[🟡 orta] Kablosuz Ileri Saldirilar (Evil Twin, KARMA/KARMA saldirilari, WPS Bruteforce, Enterprise WiFi/802.1X EAP Saldirilari, Bluetooth/BLE Guvenligi)**  
  Gorev tanimi acikca 'kablosuz ileri' istiyor; mevcut WPA2/3 basligi temel sifreleme katmanini kapsiyor ama sahte AP saldirilari, kurumsal 802.1X/EAP zafiyetleri (EAP-MD5, PEAP downgrade) ve Bluetooth/BLE saldiri yuzeyi ayri ve eksik.
- **[🟡 orta] Ag Tabanli DoS/DDoS Saldirilari ve Mitigasyonu (SYN Flood, Amplifikasyon Saldirilari, BGP/Anycast tabanli Mitigasyon)**  
  Listede genel bir DDoS/DoS basligi yok; TCP/IP saldiri yuzeyi var ama hacimsel/protokol tabanli DoS teknikleri ve savunma mimarisi (scrubbing, rate-limiting, anycast) ayri bir konu olarak islenmemis.
- **[🟡 orta] Network Access Control ve 802.1X Kimlik Dogrulama (NAC, Port Security, MACsec)**  
  Zero Trust genel kavram olarak var ama ag katmaninda cihaz/port bazli erisim kontrolu (802.1X, NAC cozumleri, port security, MACsec ile hat sifreleme) somut ve ayri bir uygulama alani olarak eksik.
- **[🟡 orta] BGP ve Yonlendirme Protokolu Guvenligi (BGP Hijacking, Route Leak, OSPF/EIGRP Saldirilari, RPKI)**  
  Internet omurgasi ve kurumsal WAN yonlendirme protokollerine yonelik saldirilar (BGP route hijack/leak, IGP protokol saldirilari, RPKI ile savunma) tamamen kapsam disinda ama ag guvenligi uzmanliginin onemli bir parcasi.

### OS Güvenliği ve Yetki Yükseltme (Linux/Windows Internals, Kernel, EDR Bypass, Credential Access)
- **[🔴 YÜKSEK] Windows Kernel Exploitation ve Driver Zafiyetleri (BYOVD dahil)**  
  Listede Windows Privesc genel basligi var ama kernel-mode exploitation (token stealing, arbitrary read/write primitives, pool corruption, BYOVD ile imzali savunmasiz surucu istismari) ayri ve derin bir uzmanlik alani; modern EDR bypass ve ring0 saldirilarinin merkezinde bu var, yuzeysel kalirsa profesyonel seviyeye ulasmaz.
- **[🔴 YÜKSEK] Linux Kernel Exploitation (eBPF, use-after-free, LPE CVE'leri)**  
  Linux Privesc genelde userland yanlis yapilandirma (SUID, cron, PATH) odakli anlatilir; kernel-level LPE (eBPF verifier bypass'lari, race condition'lar, slab/heap UAF zincirleri, dirty pipe/dirty cow tarzi teknikler) ayri, derinlemesine ele alinmasi gereken bir konu.
- **[🔴 YÜKSEK] EDR/AV Bypass Teknikleri (userland hooking bypass, ETW patching, AMSI bypass, direct/indirect syscalls)**  
  Görev tanımında 'EDR bypass' acikca mercek olarak belirtilmis ama 186 konu listesinde yok; EDR/Davranissal Tespit sadece savunma tarafini kapsiyor. Saldiri tarafi (unhooking, ETW/AMSI patching, syscall stubs ile userland hook atlatma, hardware breakpoint tespiti) kritik bir bosluk.
- **[🔴 YÜKSEK] Credential Dumping Derinlemesine (LSASS erisim teknikleri, DPAPI, Credential Guard/LSA Protection atlatma)**  
  Pass-the-Hash/Ticket ve Kerberoasting var ama LSASS bellek dump yontemleri (MiniDump API, direct syscalls, handle duplication, PPL/LSA Protection bypass), DPAPI sir cozme, Credential Guard mimarisi ve atlatma teknikleri kapsanmiyor; 'Credential Access' merceginin cekirdegi bu.
- **[🔴 YÜKSEK] Windows Access Token / Privilege Manipulation (SeDebugPrivilege, SeImpersonate, JuicyPotato ailesi)**  
  Windows Privesc genel basligi altinda kaybolan, ama pratikte en cok kullanilan token/privilege istismar teknikleri (token impersonation, potato saldirilari, named pipe impersonation) ayri ve somut bir konu olarak ele alinmali.
- **[🟡 orta] Windows/Linux Kernel Ic Mimarisi (process/object model, SRM, PatchGuard, LSASS/SAM/SYSTEM ic yapisi)**  
  Saldiri tekniklerini gercekten anlamak icin isletim sistemi kernel mimarisinin (Windows object manager, security reference monitor, EPROCESS/ETHREAD yapilari; Linux task_struct, credential yapilari, namespace/cgroup ic isleyisi) temel duzeyde islenmesi gerekiyor; simdiki listede sadece uygulamali privesc var, teorik zemin eksik.
- **[🟡 orta] macOS Guvenligi ve Privesc (TCC, SIP, entitlements, codesigning bypass)**  
  Listede Windows ve Linux var ama macOS tamamen yok; kurumsal ortamlarda macOS endpoint'leri yayginlasti ve TCC/SIP atlatma, entitlement suistimali, launch daemon persistence gibi konular profesyonel bir OS guvenligi korpusunda beklenir.
- **[🟡 orta] Rootkit/Bootkit Teknikleri ve UEFI/Firmware Guvenligi (Secure Boot bypass, SMM saldirilari)**  
  Persistence konulari kullanici/kernel seviyesinde kaliyor; firmware/bootkit seviyesi (UEFI rootkit, Secure Boot atlatma, SMM/ring-2 saldirilari, TPM ile ilgili zayifliklar) yetki yukseltme ve kalicilik zincirinin en derin katmani olarak eksik.
- **[🟡 orta] Sandbox/Isolation Kacisi (AppContainer, Job Objects, seccomp/namespace escape - Windows ozelinde)**  
  Konteyner Kacisi/Docker var ama Windows'a ozgu izolasyon mekanizmalarindan (AppContainer, Job Objects, Windows Sandbox) kacis teknikleri ve Linux'ta konteyner disi seccomp/namespace zafiyetlerinin genel-amach (non-Docker) istismari ayrica ele alinmali.
- **[⚪ düşük] Anti-Forensics ve Log/Artifact Manipulasyonu (timestomping, event log temizleme, USN journal, shadow copy silme)**  
  Disk/Memory Forensics savunma tarafini kapsiyor ama saldirgan tarafinin iz silme teknikleri (timestomp, event log manipulation/clear, prefetch/amcache temizleme, shadow copy silme) yetki yukseltme sonrasi kalicilik zincirinin dogal bir parcasi ve eksik.
- **[⚪ düşük] Windows Servis/Zamanlanmis Gorev Istismari ve DLL Hijacking/Search Order derinlemesine**  
  LOLBins/GTFOBins genel kapsiyor ama DLL search order hijacking, phantom DLL, servis binary/config yol izinleri gibi klasik Windows privesc vektorlerinin sistematik ve derin islenmesi ayri bir alt-konu olarak kayip; cok yaygin kullanilan gercek dunya teknigi.

### Active Directory ve Kimlik
- **[🔴 YÜKSEK] Entra ID (Azure AD) Hibrit Kimlik ve Senkronizasyon Saldirilari (Entra Connect/AAD Connect, PHS/PTA/Federasyon)**  
  Listede Kerberos/NTLM merkezli klasik on-prem AD zengin ama Entra Connect senkron hesabinin (MSOL/ADSync) ele gecirilmesi, Pass-Through Authentication agent zafiyeti, Seamless SSO Kerberos anahtari (AZUREADSSOACC$) hirsizligi gibi hibrit ortami on-prem'den buluta kopru olarak kullanan saldiri zincirleri hic yok; gunumuz kurumsal ortamlarinin buyuk cogunlugu hibrit oldugu icin bu kritik bir bosluk
- **[🔴 YÜKSEK] Entra ID Token/Kimlik Bilgisi Hirsizligi ve Kotuye Kullanimi (Primary Refresh Token, Device Code Phishing, Illicit Consent Grant, Token Tampering/nOAuth)**  
  OAuth/OIDC genel saldirilari kapsanmis ama Entra'ya ozgu PRT cikarma (ROADtools/AADInternals ile), cihaz kodu kimlik avi, Ustune razı olma (consent phishing) ile kalici kiracı erisimi, ve token replay/tampering AD+bulut kimlik saldiri zincirlerinin gunumuzde en yaygin baslangic vektorlerinden; ayri ve derin ele alinmali
- **[🔴 YÜKSEK] Entra ID Conditional Access Atlatma ve Kesif (Device Registration/Join Kotuye Kullanimi, Legacy Auth, Named Location Spoofing)**  
  Kosullu erisim politikalari modern kimlik savunmasinin temel tasi; saldirganlarin cihaz kaydi ile guvenilir cihaz taklidi, eski kimlik dogrulama protokolleriyle MFA atlatma ve politika bosluklarindan yararlanma teknikleri korpuste hic yer almiyor
- **[🔴 YÜKSEK] Cross-Tenant ve Hibrit Federasyon Saldirilari (AD FS Golden SAML, Guest/B2B Kotuye Kullanimi, Tenant-to-Tenant Pivot)**  
  SAML saldirilari genel olarak var ama AD FS ozelinde token imzalama sertifikasinin (Golden SAML) DKM'den cikarilmasi, cok kiracili ortamlarda B2B guest hesaplariyla yanal gecis ve federasyon guven iliskilerinin kotuye kullanimi AD'nin en gelismis kalici erisim tekniklerinden biri ve tamamen eksik
- **[🔴 YÜKSEK] AD Trust Iliskileri Saldirilari (Forest/Domain Trust Kotuye Kullanimi, SID History Injection/Sidejacking, Cross-Forest Kerberoasting)**  
  Tekli domain icindeki teknikler (Kerberoasting, DCSync, Golden Ticket) kapsanmis ama coklu orman/domain guven mimarilerinde SID History enjeksiyonu, cross-forest delegasyon istismari ve trust key uzerinden orman sinirini asma teknikleri buyuk kurumsal ortamlarda kritik ve eksik
- **[🔴 YÜKSEK] Entra ID Uygulama ve Servis Sorumlusu (Service Principal/Managed Identity) Yetki Yukseltme Zincirleri (Azure RBAC + Graph API Izin Kotuye Kullanimi)**  
  Bulut ortamlarinda uygulama kayitlarina asiri genis Graph API izinleri (ornegin RoleManagement.ReadWrite.Directory) verilmesi ve Managed Identity uzerinden Azure kaynaklarina yatay/dikey yetki yukseltme, modern 'AD sonrasi' kimlik saldiri yuzeyinin merkezinde ama korpuste hic yok
- **[🟡 orta] Grup Politikasi (GPO) Saldirilari ve Kotuye Kullanimi**  
  GPO uzerinden yetki yukseltme (yazilabilir GPO'lara zararli script/scheduled task enjeksiyonu, SYSVOL uzerinden kimlik bilgisi sizmasi ornegin eski GPP parolalari) AD ortamlarinda cok yaygin bir yanal gecis ve kalicilik vektoru ama listede GPO'ya ozel bir konu yok
- **[🟡 orta] AD Sertifika Hizmetleri Otesi Kimlik Federasyonu: PKINIT ve Smart Card/Sertifika Tabanli Kimlik Dogrulama Zayifliklari**  
  ADCS saldirilari (ESC1-ESC8 gibi) genel olarak listelenmis ama PKINIT protokolunun kendisi, sertifika tabanli on-auth zayifliklari ve bunun Kerberos ile etkilesimi ayri bir derinlik gerektirir; mevcut ADCS basligi genelde sablon kotuye kullanimini kapsar, protokol seviyesini degil
- **[🟡 orta] Kimlik Govern Yonetimi ve Ayricalikli Erisim Yonetimi (PAM, Tiering Model / Kirmizi Orman, Just-In-Time Erisim, PIM)**  
  Saldiri teknikleri agirlikli kapsanmis ama savunma tarafinda Microsoft'un Tiering/Katmanlama modeli, Privileged Access Workstation kavrami, Entra PIM ile zamanla sinirli rol atamasi gibi AD kimlik guvenliginin yapisal savunma cercevesi eksik; hem saldiri hem savunum icin gerekli
- **[🟡 orta] NTLM/Kerberos Protokol Sertlestirme ve Modern Azaltmalar (LDAP Signing/Channel Binding, NTLM Devre Disi Birakma, Kerberos Armoring/FAST, Credential Guard)**  
  LLMNR/NTLM Relay saldirisi var ama bunun karsi tarafi olan savunma/sertlestirme mekanizmalari (LDAP signing zorunlulugu, EPA/channel binding, Credential Guard'in Pass-the-Hash'i nasil engelledigi) ayri ele alinmiyor; saldiri-savunma dengesi icin onemli

### Binary Exploitation ve Dusuk Seviye
- **[🔴 YÜKSEK] Modern Heap Exploitation (glibc ptmalloc2 ileri - tcache poisoning, safe-linking, house of serisi teknikler)**  
  Listede genel 'Heap Exploitation' var ama modern glibc korumalari (tcache, safe-linking, House of Force/Spirit/Orange gibi guncel teknikler) ayri ve derin islenmezse pratik CTF/gercek dunya heap exploit yetenegi olusmaz. Bu, buyuk model icin en kritik yuzeysel kalan konu.
- **[🔴 YÜKSEK] Kernel Exploitation (Linux/Windows kernel, UAF, privilege escalation via kernel bugs, SMEP/SMAP/KASLR bypass)**  
  Listede hic yok. Windows/Linux Privesc kullanici-alani teknikleri kapsanmis ama cekirdek exploit gelistirme (driver zafiyetleri, syscall fuzzing, kernel ROP, KPTI/SMEP/SMAP atlatma) tamamen eksik; ciddi bir binary exploitation korpusunda olmazsa olmaz.
- **[🔴 YÜKSEK] Tarayici/V8 Exploitation (JS engine internals, JIT bug'lari, type confusion, sandbox escape)**  
  Modern istismarin en aktif alanlarindan biri (Chrome/V8, WebKit/JSC); listede hicbir tarayici motoru ic yapisi veya JS engine exploit konusu yok. Sifir gun arastirmasi ve modern APT teknikleri icin kritik bir bosluk.
- **[🔴 YÜKSEK] ARM/AArch64 Mimarisi ve Exploitation (calling convention, ROP/JOP on ARM, PAC/BTI atlatma, TrustZone)**  
  Mevcut ROP/Stack Overflow konulari x86/x64 odakli gorunuyor; mobil ve gomulu dunyanin standardi olan ARM mimarisine ozgu exploit teknikleri (register tabanli calling convention, Pointer Authentication, Branch Target Identification, TrustZone/TEE) hic yer almiyor.
- **[🔴 YÜKSEK] Gomulu/IoT Firmware Guvenligi (firmware extraction, UART/JTAG/SWD, bootloader/secure boot atlatma, binwalk/firmadyne)**  
  Listede IoT/gomulu sistem exploitasyonu tamamen yok (ICS/OT var ama farkli bir alan - SCADA protokolleri). Firmware sokme, donanim arayuzleri uzerinden erisim, secure boot/chain-of-trust atlatma gunumuz IoT pentestinin temelini olusturuyor.
- **[🟡 orta] Kernel Exploit Mitigations (SMEP, SMAP, KASLR, KPTI, CFI/CET, kernel-mode ASLR)**  
  Genel 'Exploit Mitigations' konusu ASLR/DEP/canary gibi kullanici-alani korumalarina odaklaniyor; cekirdek seviyesi korumalar ve bunlarin atlatilmasi ayri ve derinlemesine islenmesi gereken bir konu.
- **[🟡 orta] Hypervisor/VM Escape (QEMU/KVM, Xen, VMware zafiyetleri, sanallastirma sinir ihlalleri)**  
  Konteyner kacisi kapsanmis ama tam sanallastirma (hypervisor) katmanindaki kacis teknikleri farkli bir tehdit yuzeyi; bulut altyapisi guvenligi icin gittikce onem kazanan bir konu, listede yok.
- **[🟡 orta] Sembolik Yururtme ve Concolic Testing (angr, KLEE ile otomatik exploit/PoC uretimi)**  
  Fuzzing kapsanmis ama sembolik/concolic execution farkli ve tamamlayici bir teknik (path constraint cozme, otomatik girdi uretimi, CTF/binary analizde otomasyon); modern binary exploitation arastirmasinda fuzzing kadar onemli ama listede yok.
- **[🟡 orta] Yan Kanal Saldirilari (Spectre/Meltdown, cache timing, Rowhammer)**  
  Donanim seviyesi mikromimari zafiyetler (spekulatif yururtme, DRAM bit-flip) hicbir listede yer almiyor; modern CPU guvenligi ve dusuk seviye savunma tasarimi icin onemli bir bosluk.
- **[🟡 orta] Windows Kernel-Specific Exploit Yuzeyi (IOCTL fuzzing, driver zafiyetleri, Windows Kernel pool exploitation, HVCI/VBS atlatma)**  
  Windows Privesc/Persistence kullanici alaninda kaliyor; kernel driver saldiri yuzeyi (arbitrary read/write, pool spraying, EoP zincirleri) ve modern Windows sanallastirma tabanli korumalarin (VBS/HVCI) atlatilmasi ayri uzmanlik alani, eksik.
- **[⚪ düşük] Statik/Dinamik Binary Enstrumentasyon (Pin, DynamoRIO, QBDI ile runtime analiz ve tacit exploitation)**  
  Genel 'Dinamik Analiz' var fakat binary enstrumentasyon araclarinin (kod kapsama, taint analizi, otomatik ROP gadget bulma icin dinamik enstrumentasyon) ozel kullanim alani ayrintili islenmiyor; ileri seviye arastirmacilar icin faydali ama oncelik daha dusuk.
- **[⚪ düşük] Gomulu Gercek-Zamanli Isletim Sistemleri Guvenligi (RTOS - FreeRTOS/Zephyr, MPU tabanli izolasyon zafiyetleri)**  
  IoT firmware konusuna komsu ama farkli: RTOS'a ozgu bellek koruma birimi (MPU) yapilandirma hatalari ve gorev izolasyonu zafiyetleri niş ama gomulu guvenlik uzmanligi icin tamamlayici bir alan.

### Tersine Mühendislik ve Malware
- **[🔴 YÜKSEK] Gelismis Anti-Debugging ve Anti-VM/Sandbox Kacinma Teknikleri**  
  Korpusta genel 'Packing/Obfuscation' var ama malware'in analiz ortamini tespit edip davranisini gizlemesi (PEB/NtGlobalFlag kontrolleri, timing-based kontroller, CPUID/hypervisor bayraklarindan VM tespiti, sanal donanim/MAC adresi taramasi, kullanici etkilesimi bekleme) ayri ve derin bir yetenek alani. Bu konu olmadan bir analiz egitimi 'gercek dunya' malware'ine karsi yetersiz kalir.
- **[🔴 YÜKSEK] Gelismis Unpacking ve Runtime/In-Memory Kod Cozme (Custom Packers, VM-based Protectors)**  
  Mercek acikca 'ileri unpacking' diyor ama listede sadece yuzeysel 'Packing/Obfuscation' basligi var. VMProtect/Themida/Enigma gibi sanal makine tabanli koruyucularin analizi, OEP (Original Entry Point) bulma teknikleri, import tablosu yeniden insasi (IAT rebuilding), dump-and-fix yontemleri ayri, teknik derinlik gerektiren bir konu.
- **[🔴 YÜKSEK] Firmware / Gomulu Sistem Tersine Muhendisligi (UEFI/BIOS, Router/IoT Firmware Analizi)**  
  Mercek 'firmware RE' diyor ama listede hicbir firmware konusu yok. Binwalk ile firmware cikarma, dosya sistemi (SquashFS/JFFS2) analizi, bootloader/UEFI modulu tersine muhendisligi, ARM/MIPS mimarilerinde RE, donanim arayuzleri (UART/JTAG/SPI) uzerinden erisim bu alanin temelidir ve tamamen eksik.
- **[🔴 YÜKSEK] Mobil Malware Tersine Muhendisligi (Android APK/DEX, iOS Mach-O Derinlemesine Analiz)**  
  Genel 'Mobil Guvenlik' konusu var ama bu pentest/uygulama guvenligi merceginde; mercek burada acikca 'mobil RE' istiyor. Smali/DEX bytecode analizi, ART/Dalvik ic yapisi, APK'da native .so kutuphanelerinin RE'si, Frida ile runtime hooking/enstrumantasyon, iOS icin class-dump/Mach-O sifre cozme ayri, ozel bir uzmanlik.
- **[🔴 YÜKSEK] Malware Aile Analizi ve Vaka Calismalari (Ransomware Otesi: Bankacilik Truva Atlari, Botnet'ler, Rootkit/Bootkit, Wiper'lar)**  
  Listede sadece 'Ransomware Anatomisi' var; mercek 'malware aileleri' diyor. Emotet/QakBot gibi bankacilik truva atlarinin enjeksiyon zincirleri, botnet C2 protokolleri ve DGA (Domain Generation Algorithm), kernel-mode rootkit/bootkit teknikleri (MBR/VBR enfeksiyonu, driver imzalama atlatma), wiper malware'lerin yikim mekanizmalari kapsam disi kalmis somut vaka bilgisidir.
- **[🟡 orta] Yazilim Su Isareti Kaldirma ve Lisans Koruma Kirma (Keygen/Patch/Crackme Metodolojisi)**  
  Klasik RE egitiminin bir parcasi olan lisans dogrulama rutinlerinin bulunmasi, seri numara algoritmalarinin tersine cevrilmesi (keygenning), binary patching ile kontrol atlatma; akademik/CTF RE becerisi olarak onemli ama saldiri yuzeyi acisindan malware'den daha dusuk oncelikli.
- **[🟡 orta] .NET / Java Bytecode Tersine Muhendisligi ve Deobfuscation (ConfuserEx, ProGuard/DexGuard)**  
  .NET (IL/MSIL, dnSpy/ILSpy ile decompile) ve Java bytecode uzerinde calisan malware/ticari yazilimlarin analizi native binary RE'den farkli arac ve teknik gerektirir; ozellikle .NET tabanli RAT/stealer'larin (ornegin AgentTesla tarzi) yaygin oldugu gunumuzde onemli bir bosluk.
- **[🟡 orta] Derleyici/IR Duzeyinde Analiz ve Binary Fark Analizi (Decompiler IR, BinDiff/Diaphora ile Patch Diffing)**  
  Ghidra P-Code/IDA Hex-Rays gibi decompiler ara temsillerinin okunmasi ve yamalar arasi fonksiyon eslestirme (1-day exploit gelistirme ve patch analizinde kritik) net bir 'statik analiz/RE' basligi altinda yuzeysel kalmis; profesyonel zafiyet arastirmasinin standart is akisidir.
- **[🟡 orta] Cok Mimarili Assembly ve Calling Convention Uzmanligi (ARM32/64, MIPS, x86 Otesi)**  
  Listedeki 'Bellek Yerlesimi/Stack Buffer Overflow/ROP' agirlikli x86/x64 odakli gorunuyor; IoT/mobil/firmware malware analizinin buyuk kismi ARM ve MIPS mimarilerinde gecer, farkli calling convention, endianness ve komut setleri icin ayri ogretim materyali gerekir.
- **[⚪ düşük] Donanim Destekli Tersine Muhendislik (JTAG/SWD Debug, Yonlendirilmis Guc Analizi/Glitching, Yan Kanal Saldirilari)**  
  Firmware RE'nin ileri seviyesi olarak fiziksel erisimli donanim analizini (voltage glitching, JTAG uzerinden debug erisimi, side-channel/guc analizi ile anahtar cikarma) kapsar; profesyonel donanim guvenligi/RE ekiplerinde nis ama degerli bir yetenek, genis kitleye gore oncelik daha dusuk.

### Bulut ve Konteyner Güvenliği
- **[🔴 YÜKSEK] Kubernetes RBAC ve Pod Security Admission (PSA) Derinlemesine**  
  Korpusta 'Kubernetes Guvenlik' genel basligi var ama RBAC yanlis yapilandirmalari (wildcard cluster-role binding, ServiceAccount token otomatik mount, escalate/impersonate verb'leri), Pod Security Standards (restricted/baseline/privileged) ve eski PodSecurityPolicy gecisi gibi K8s'e ozgu en kritik yetki yukseltme vektorleri ayri ve derinlemesine islenmemis; gercek dunya K8s sizmalarinin buyuk cogunlugu bu katmanda gerceklesiyor.
- **[🔴 YÜKSEK] Container Image Supply Chain Guvenligi (SBOM, Imza, Provenance - Sigstore/Cosign, SLSA)**  
  CI/CD supply chain merceginde belirtilmesine ragmen korpusta imaj imzalama (cosign/Notary v2), SBOM uretimi/dogrulama (Syft/Grype), SLSA seviyeleri ve provenance attestation ayri bir konu olarak yok; SolarWinds sonrasi endustri standardi haline gelen bu pratikler olmadan 'Konteyner Kacisi' konusu tek basina yetersiz kaliyor.
- **[🔴 YÜKSEK] IaC Guvenlik Taramasi ve Policy-as-Code (Terraform/OPA/Kyverno/Checkov)**  
  Genel 'IaC' basligi var ama admission controller seviyesinde policy-as-code (OPA/Gatekeeper, Kyverno kurallari), Terraform plan/state guvenlik taramasi (tfsec, Checkov) ve drift tespiti kapsanmiyor; bulut-native guvenligin onleyici kontrol katmani bu.
- **[🔴 YÜKSEK] Serverless/FaaS Guvenligi (Lambda/Cloud Functions Ozgu Saldiri Yuzeyi)**  
  Mercekte 'serverless' acikca belirtilmis ama listede yok; asiri genis IAM execution role'leri, event-injection (S3/SQS/API Gateway tetikleyicileri uzerinden), soguk baslatma sirlari sizdirma, ve fonksiyonlar-arasi yatay hareket klasik konteyner/VM modelinden tamamen farkli bir tehdit modeli gerektiriyor.
- **[🔴 YÜKSEK] Bulut IAM Yetki Yukseltme Zincirleri (Azure/GCP Privilege Escalation Paths)**  
  AD ACL/BloodHound tarzi analiz on-premise AD icin var ama Azure AD/Entra ID (rol atamalari, App Registration/Service Principal suistimali, Managed Identity token calma) ve GCP IAM (impersonation zincirleri, custom role escalation) icin es deger 'bulut BloodHound' konusu (ROADtools/PurpleKnight, GCP IAM Privilege Escalation teknikleri) eksik; AWS disinda kalan iki buyuk bulut saglayicisinin kimlik katmani neredeyse hic yok.
- **[🟡 orta] Kubernetes Ag Politikalari, Servis Mesh ve mTLS Guvenligi (Istio/Linkerd/CNI)**  
  K8s icindeki east-west trafik izolasyonu (NetworkPolicy/CNI eklentileri), servis mesh mTLS uygulamasi ve sidecar injection guvenligi konteyner segmentasyonunun temel tasi ama mevcut 'Firewall/Segmentasyon' genel ag konusuyla ortusmuyor, K8s'e ozgu ele alinmamis.
- **[🟡 orta] Bulut Tespit ve Mudahale (Cloud-Native Detection & Response - CloudTrail/GuardDuty, Falco, CDR)**  
  SIEM/Threat Hunting genel olarak var ama bulut/konteyner ortamina ozgu runtime tespit araclari (Falco kurallari, eBPF tabanli davranissal izleme), CloudTrail/Azure Activity Log/GCP Audit Log analizi ve CDR (Cloud Detection & Response) araclari ayri bir konu olarak yok; bulut olay mudahalesi klasik IR'dan farkli beceri seti gerektiriyor.
- **[🟡 orta] Multi-Tenant Izolasyon ve Konteyner Runtime Guvenligi (gVisor/Kata/seccomp/AppArmor)**  
  Konteyner Kacisi zafiyetleri var ama savunma tarafinda runtime sandboxing (gVisor, Kata Containers), seccomp profilleri, AppArmor/SELinux ile capability kisitlama ve guvenli varsayilanlar konusu eksik; saldiri konusu var, savunma/sertlestirme karsiligi zayif.
- **[🟡 orta] Bulut Sir ve Kimlik Bilgisi Yonetimi (Cloud Secrets Management - KMS/Key Vault/Secret Manager, OIDC Federasyonu)**  
  Genel 'Anahtar/Sir Yonetimi' var ama bulut saglayicisina ozgu KMS/Key Vault/Secret Manager entegrasyonu, CI/CD'den buluta OIDC federasyonu ile statik anahtarsiz kimlik dogrulama (GitHub Actions OIDC -> AWS/Azure) ve secret sprawl tespiti (git repo, konteyner katmanlari, env degiskenleri) eksik.
- **[⚪ düşük] Bulut Guvenlik Duruş Yonetimi ve CNAPP (CSPM/CWPP/CIEM Butunlesik Yaklasim)**  
  'Bulut Yanlis Yapilandirma' konusu parca parca kapsiyor ama CSPM (Cloud Security Posture Management), CWPP (Cloud Workload Protection) ve CIEM (Cloud Infrastructure Entitlement Management) araclarinin butunlesik CNAPP yaklasimi ve bunlarin surekli uyum/skorlama mantigi ayri, kurumsal seviyede onemli bir cerceve olarak islenmemis.

### Mavi Takim: Tespit/IR/Forensics
- **[🔴 YÜKSEK] Detection Engineering Yasam Dongusu ve Kural Muhendisligi (Detection-as-Code, ATT&CK kapsama haritalama, false-positive tuning, kural test/versiyonlama)**  
  Korpusta Sigma Kurallari ve MITRE ATT&CK Kullanimi ayri basliklar olarak var ama bunlarin uretim surecini yoneten ust disiplin eksik: tespit gereksinimi yazma, veri kaynagi yeterliligi degerlendirme (Data Source/Log Source coverage), kural yasam dongusu (draft->test->tune->deploy->deprecate), FP oranini olcme, Detection-as-Code (git ile kural versiyonlama, CI/CD ile test) pratikleri. Bu, Sigma'yi 'nasil yazarim'dan 'nasil bir program olarak yonetirim'e tasiyan profesyonel seviye bosluk.
- **[🔴 YÜKSEK] SOC Operasyon Modeli ve Triage/Escalation Sureci (alert triage, tier1/2/3 is akisi, SOAR playbook otomasyonu, alarm yorgunlugu yonetimi)**  
  Incident Response basligi var ama bir SOC'un gunluk operasyonel dokusu (alarm kuyruklama, triage kriterleri, tier yukselme kurallari, SOAR ile otomatik yanit/playbook orkestrasyonu, alert fatigue/metrikleri - MTTD/MTTR) ayri ve derin bir konu; IR genelde 'olay sonrasi' surece odaklanir, SOC ise gunluk operasyona odaklanir - bu ayrim korpusta yok.
- **[🔴 YÜKSEK] Bulut-Native Forensics ve Log Kaynaklari (AWS CloudTrail/GuardDuty derin analiz, Azure Sentinel/Defender, GCP Cloud Audit Logs, container/serverless adli analiz, ephemeral ortamda kanit toplama)**  
  Disk/Memory/Network Forensics var ama hepsi klasik on-prem/endpoint odakli. Bulut ortaminda kalici disk yok, log kaynaklari servis bazli dagitilmis, konteynerler saniyeler icinde kayboluyor - farkli metodoloji (CloudTrail/VPC Flow Logs korelasyonu, snapshot alma, IAM olay zinciri analizi) gerektirir. AWS Guvenlik basligi savunma/yapilandirma odakli, forensics/IR aciligi ayri.
- **[🔴 YÜKSEK] Kimlik Odakli Tespit ve Identity Threat Detection (Azure AD/Entra ID sign-in anomali analizi, Okta/SSO log analizi, imkansiz seyahat, oturum ele gecirme tespiti, ITDR)**  
  Kerberos/AD saldiri teknikleri kapsanmis ama bunlarin BULUT kimlik katmaninda (Azure AD, Okta) TESPIT tarafi (sign-in log korelasyonu, risky sign-in, conditional access ihlali, token replay tespiti, ITDR araclari) yok; modern saldirilarin buyuk kismi artik kimlik katmaninda gerceklesiyor.
- **[🟡 orta] Log Yonetimi Mimarisi ve Veri Boru Hatti (log toplama/normalizasyon/zenginlestirme, log pipeline - Fluentd/Logstash/Vector, retention/maliyet dengesi, log bütünlügü/immutability, saat senkronizasyonu)**  
  SIEM/Detection Engineering ve Loglama/Telemetri basliklar var ama bir Mavi Takim uzmaninin gunluk ugrastigi log pipeline mimarisi (kaynak->toplayici->normalizasyon->depolama), log butunlugu/degistirilemezlik (WORM, hash zinciri) ve olcek/maliyet trade-off'lari (hot/warm/cold depolama) somut olarak eksik - bu forensics kanitlarinin gecerliligi icin kritik.
- **[🟡 orta] Deception Teknolojileri ve Honeypot/Honeytoken Operasyonu (canary token, honeypot/honeynet kurulumu, decoy credential, erken uyari tuzaklari)**  
  Tespit alaninda proaktif bir savunma katmani olan aldatma (deception) teknikleri korpusta hic yok; Threat Hunting ile yakindan iliskili ama farkli bir yaklasim - saldirganin varligini dusuk yanlis-pozitifle erken tespit etmenin endustri standardi bir yontemi.
- **[🟡 orta] Insider Threat Tespiti ve Kullanici Davranis Analitigi (UEBA, veri sizintisi/DLP tespiti, ayricalikli kullanici izleme, anomali skorlama)**  
  EDR/Davranissal Tespit dis tehdit/malware odakli; ic tehdit (calisanin veri sizdirmasi, yetki kotuye kullanimi) farkli veri kaynaklari (DLP, UEBA, dosya erisim loglari) ve farkli davranissal taban cizgisi (baseline) gerektirir - kurumsal DFIR programlarinda ayri bir disiplin olarak ele alinir.
- **[🟡 orta] Adli Bilisim Kanit Zinciri ve Hukuki Sureç (chain of custody, adli imaj alma standartlari - E01/AFF4, hash dogrulama, mahkemede kabul edilebilirlik, adli rapor yazimi)**  
  Disk/Memory/Network Forensics teknik analiz araclarini kapsiyor olabilir ama adli surecin hukuki/prosedurel omurgasi (kanit zinciri belgeleme, imaj hash dogrulama, mahkemede kabul edilebilirlik kriterleri, adli rapor formati) profesyonel DFIR sertifikasyonlarinin (GCFE/GCFA) merkezinde olan ama teknik analizden ayri bir yetkinlik.
- **[🟡 orta] Purple Team Operasyonlari ve Tespit Dogrulama (atomic testing ile tespit kapsama testi, tespit boşluk analizi, adversary emulation planlama, breach-and-attack simulation)**  
  atomic-red-team kaynak olarak yutulmus ve Pentest Metodoloji/Threat Hunting var ama bunlari birlestiren 'yazdigim Sigma kurali gercekten çalisiyor mu' dongusu (purple team egzersizi tasarimi, BAS araclari, tespit kapsama matrisi olusturma) ayri bir metodolojik konu olarak eksik.
- **[⚪ düşük] E-posta Guvenligi Tespiti ve Analizi (e-posta header/routing analizi, SPF/DKIM/DMARC dogrulama ve bypass tespiti, phishing kit analizi, e-posta ag gecidi telemetrisi)**  
  Phishing/Sosyal Muhendislik saldiri tarafini kapsiyor ama bir SOC analistinin supheli e-postayi teknik olarak inceleme yetenegi (header analizi, SPF/DKIM/DMARC zincirini okuma, URL/ek yeniden yazma sistemleri) ayri, gunluk en sik karsilasilan triage gorevlerinden biri.

### GRC, Yükselen ve Yatay Alanlar
- **[🔴 YÜKSEK] LLM/AI Güvenliği (OWASP Top 10 for LLM, Prompt Injection, Jailbreak, RAG Zehirleme, Model/Veri Zehirleme, Agentic AI Güvenliği)**  
  Kapsanan 186 konu listesinde AI/LLM güvenliği hiç yok; 2024-2026 döneminde kurumsal saldırı yüzeyinin en hızlı büyüyen parçası. Doğrudan prompt injection (direct/indirect), jailbreak teknikleri, training/RAG veri zehirleme, model çalma, guardrail atlatma, agentic/tool-calling ajanlarında yetki sızması ve MCP güvenliği gibi alt konular olmadan profesyonel bir 2026 korpusu eksik kalır.
- **[🔴 YÜKSEK] Yazılım Tedarik Zinciri Güvenliği (SBOM, SLSA, Bağımlılık/Paket Zehirleme, Reproducible Builds, CI/CD Pipeline Güvenliği, Imza/Attestation)**  
  Listede DevSecOps/CI-CD güvenliği ve SBOM/SLSA çerçeveleri yok; SolarWinds, XZ Utils, npm/PyPI tiposquatting gibi büyük olaylar bu alanın kritikliğini gösteriyor. Mevcut kapsam Secure SDLC ve CI/CD'yi genel gelistirici pratiği olarak veriyor ama tedarik zinciri tehdit modeli (yazılım imzalama, bağımlılık grafiği analizi, build sistemi ele geçirme) ayrı ve derin bir konu olarak eksik.
- **[🔴 YÜKSEK] Uyum Çerçeveleri Derinlemesine (ISO 27001 Ek-A Kontrolleri, NIST CSF 2.0/800-53, PCI DSS 4.0, SOC 2, KVKK/GDPR Teknik Gereksinimler, DORA, NIS2)**  
  Kapsanan listede tek satır 'Risk Degerlendirme' ve 'Threat Modeling/STRIDE' var ama somut uyum standartlarının kontrol maddeleri, denetim kanıtı toplama, gap analizi ve teknik-uyum eşleştirmesi (ör. PCI DSS segmentasyon testi, KVKK veri işleme envanteri) hiç yok. GRC uzmanlığının çekirdeği bu olduğu için ciddi bir boşluk.
- **[🟡 orta] Bug Bounty / Sorumlu Ifsa Programı Yönetimi (Program Tasarımı, Kapsam Belirleme, Triage, VDP vs Bounty, Ödül Modelleri, Raporlama Kalitesi)**  
  Pentest Metodoloji var ama bug bounty'nin kendine özgü süreci (program politikası yazımı, triage/duplicate yönetimi, researcher iletişimi, ödül belirleme, hall-of-fame/hukuki güvence) ayrı bir disiplin; korpusta yok.
- **[🟡 orta] Mobil Güvenlik Derinlemesine (iOS Keychain/Jailbreak Tespiti Atlatma, Android Keystore/Root Tespiti, Frida/Objection ile Runtime Enstrümantasyon, Mobil Uygulama Tersine Muhendislik, Mobil Sertifika Sabitleme Atlatma)**  
  Listede sadece genel 'Mobil Guvenlik' başlığı var; MASTG yutulmuş ama pratik saldırı teknikleri (Frida enstrümantasyonu, SSL pinning bypass, IPC/Intent istismarı, platform-özel depolama analizi) alt konu olarak yok, yüzeysel kalıyor.
- **[🟡 orta] ICS/OT Güvenliği Derinlemesine (Purdue Modeli, Modbus/DNP3/OPC-UA Protokol Saldırıları, PLC/RTU Güvenliği, SCADA Tarihsel Olaylar - Stuxnet/Triton, IEC 62443)**  
  Listede tek satır 'ICS/OT Guvenlik' var, protokol seviyesi ve endüstri standardı (IEC 62443) derinliği belirtilmemiş; bu ihtisas alanı genel siber güvenlik bilgisinden çok farklı protokol ve mimari bilgisi gerektirir, yüzeysel kalma riski yüksek.
- **[🟡 orta] Üçüncü Taraf/Tedarikçi Risk Yönetimi (TPRM, Vendor Risk Assessment, Due Diligence Anketleri, Bulut Servis Sağlayıcı Risk Değerlendirme)**  
  GRC'nin merkezi pratiklerinden biri; kurumların çoğu ihlali tedarikçi/üçüncü taraf üzerinden yaşıyor (ör. MOVEit, Kaseya). Korpuste tedarik zinciri sadece yazılım bağımlılığı açısından değil, sözleşmesel/operasyonel risk yönetimi açısından da eksik.
- **[🟡 orta] Gizlilik Mühendisliği (Privacy by Design, PII Sınıflandırma/Veri Haritalama, Anonimleştirme/Pseudonimizasyon Teknikleri, Veri Saklama/Imha Politikaları, DPIA)**  
  KVKK/GDPR uyumun yasal boyutu var ama teknik gizlilik mühendisliği (k-anonimlik, differential privacy, veri minimizasyonu, DPIA sureci) ayrı bir uzmanlık alanı ve korpusta yok; GRC'nin veri koruma ayağı eksik kalıyor.
- **[⚪ düşük] Siber Sigorta ve İş Sürekliliği/Felaket Kurtarma (BCP/DRP, RTO/RPO, Siber Sigorta Poliçe Değerlendirme, Tabletop Egzersizleri)**  
  Incident Response var ama organizasyonel süreklilik planlama (RTO/RPO hesaplama, DR test senaryoları, siber sigorta kapsamı/istisnaları) GRC'nin yönetimsel tarafında ayrı bir konu; şu an korpusta karşılığı yok.
- **[⚪ düşük] Kurumsal Yönetişim ve Siber Güvenlik Metrikleri (Yönetim Kurulu Raporlama, KRI/KPI Tasarımı, Güvenlik Olgunluk Modelleri - CMMI/C2M2, Bütçe/ROI Gerekçelendirme)**  
  Teknik derinliğin aksine GRC'nin 'G' (governance) tarafı -yönetim kuruluna raporlama, olgunluk modeli değerlendirmesi, güvenlik yatırımı gerekçelendirme- korpusta hiç temsil edilmiyor; profesyonel GRC uzmanları için gerçek gündelik iş bu.

## YAZILIM

### Programlama Dilleri
- **[🔴 YÜKSEK] PHP Guvenligi (Type Juggling, Object Injection/Unserialize, LFI Zincirleri, Wrappers)**  
  PHP hala web'in buyuk bir kismini calistiriyor (WordPress/Laravel ekosistemi) ancak listede hic yer almiyor; type juggling (== vs ===), phar:// deserialization saldirilari, magic method (__wakeup/__destruct) istismari gibi dile ozgu zafiyet siniflari profesyonel bir korpusta mutlaka olmali.
- **[🔴 YÜKSEK] Ruby / Ruby on Rails Guvenligi (Mass Assignment, YAML.load, ERB SSTI, Rails-ozgu Deserialization)**  
  Ruby listede hic gecmiyor; Rails'in kendine ozgu Marshal.load ve YAML.load kaynakli RCE zincirleri (ör. CVE-2013-0156) ile ActiveRecord mass assignment gibi konular sektorde bilinen onemli bir saldiri sinifidir.
- **[🔴 YÜKSEK] C Ileri Guvenlik: Undefined Behavior Istismari ve Derleyici Optimizasyon Tuzaklari**  
  Liste 'Bellek Yerlesimi/Stack Overflow/ROP/Heap' gibi genel exploitation konularini kapsiyor ama C dilinin kendi UB (signed overflow, strict aliasing, uninitialized read) kaynakli ozel derleyici-optimizasyon tuzaklari ve bunlarin gercek CVE'lere donusmesi ayri, derinlemesine bir konu olarak eksik.
- **[🔴 YÜKSEK] Dil-Agnostik Supply Chain Guvenligi: Paket Yoneticisi Ekosistem Saldirilari (npm/pip/RubyGems/Composer/crates.io Typosquatting, Dependency Confusion)**  
  Her dilin kendi paket yoneticisi ekosistemi var (npm, pip, Composer, RubyGems, crates.io, NuGet) ve bunlara ozgu typosquatting/dependency confusion/postinstall script saldirilari listede hic yer almiyor; modern tedarik zinciri saldirilarinin en yaygin vektoru oldugundan yuksek oncelikli.
- **[🟡 orta] Kotlin / Android Guvenligi (Null Safety Bypass, Coroutine Guvenlik Tuzaklari, JNI Interop)**  
  Kotlin hic islenmemis; Android tarafinda Java/Kotlin interop kaynakli null-safety atlatmalari, coroutine context leak'leri ve JNI/native bridge riskleri Mobil Guvenlik konusundan bagimsiz, dile ozgu bir bosluk.
- **[🟡 orta] Swift Guvenligi ve iOS Bellek/ARC Modeli**  
  Swift/iOS tarafi tamamen eksik; ARC (Automatic Reference Counting) kaynakli retain-cycle/use-after-free benzeri hatalar, Codable/unsafe pointer API'leri (UnsafeMutablePointer) ve Keychain kullanim hatalari dile ozgu onemli konular.
- **[🟡 orta] WebAssembly (Wasm) Guvenligi ve Sandbox Kacislari**  
  Rust/Go/C gibi dillerin derlendigi hedef olarak WebAssembly hic bahsedilmemis; Wasm sandbox modeli, memory linear model istismari ve tarayici ici Wasm kaynakli saldirilar modern web guvenliginin buyuyen bir parcasi.
- **[🟡 orta] Diller Arasi FFI/Interop Guvenlik Sinirlari (Python-C, Node.js Native Addons, JNI, P/Invoke)**  
  Listede her dil ayri ele alinmis ama diller arasi gecis noktalarinda (ctypes/cffi, N-API, JNI, P/Invoke) olusan tur guvenligi kaybi ve bellek sahiplik hatalari ayri bir konu olarak islenmemis; bu sinirlar genellikle en az denetlenen ve en riskli kod yollaridir.
- **[⚪ düşük] Scala / JVM Fonksiyonel Dil Guvenligi (Deserialization, Akka Actor Guvenligi)**  
  Scala hic yok; JVM tabanli oldugu icin Java/JVM konusuyla kismen ortusuyor ama Akka mesajlasma modeli ve implicit/case class tabanli deserialization riskleri dile ozguldur, oncelik dusuk ama profesyonel kapsam icin bahsedilmeli.
- **[⚪ düşük] Perl Guvenligi (Legacy CGI, Taint Mode, Regex Injection)**  
  Perl tamamen listede yok; eski ama hala kritik altyapida (network ekipmani, legacy CGI script'leri) calisan bir dil oldugundan taint mode atlatma ve regex/command injection ozgu konulari dusuk oncelikli ama gercek bir boslukdur.
- **[⚪ düşük] Objective-C Bellek Guvenligi ve Legacy iOS Kod Tabani Analizi**  
  Swift'in yani sira Objective-C legacy kod tabanlarinda manual retain/release, message-passing (selector injection) gibi konular listede yok ve halen buyuk kurumsal iOS kod tabanlarinda karsilasilan bir alan.
- **[⚪ düşük] Erlang/Elixir ve BEAM VM Guvenligi (Atom Tablosu Tukenmesi, Dagitik Node Guvenligi)**  
  Yuksek eszamanlilik gerektiren sistemlerde (telekom, mesajlasma) kullanilan Erlang/Elixir hic yok; BEAM'in dagitik node authentication (cookie tabanli) zayifligi ve atom table exhaustion DoS'u dile ozgu ilginc bir konu.

### Veri Yapilari ve Algoritmalar
- **[🔴 YÜKSEK] Hesaplama Karmasikligi Teorisi (P, NP, NP-Tam, NP-Zor, Indirgemeler)**  
  Listede Big-O (pratik analiz) var ama P vs NP, NP-tamlik ispatlari, indirgeme teknikleri, karar/optimizasyon problemleri ayrimi gibi teorik temel eksik. Bir guvenlik+yazilim modelinin kriptografinin neden guvenli oldugunu (one-way fonksiyonlar, NP-zorluk varsayimlari) anlamasi icin bu teorik zemin sarttir; sifreleme konulari bu temel olmadan yuzeysel kalir.
- **[🔴 YÜKSEK] Ileri Graf Algoritmalari (Max-Flow/Min-Cut, Baglanti/SCC, En Kisa Yol Varyantlari, Eslesme)**  
  Liste sadece genel 'Graf Algoritmalari' basligi iceriyor; ag akisi (Ford-Fulkerson/Dinic), iki parcali eslesme (Hopcroft-Karp), guclu bagli bilesenler (Tarjan/Kosaraju), Bellman-Ford/Johnson gibi negatif agirlikli/tum-ciftler en kisa yol algoritmalari agi guvenligi, kapasite planlama ve ag analizi konularinda dogrudan kullanilir ama ayrica derinlestirilmemis.
- **[🔴 YÜKSEK] Ileri Veri Yapilari (Trie, Segment Tree, Fenwick/BIT, Union-Find, Skip List, Bloom Filter, Suffix Yapilari)**  
  Listede sadece temel agaclar/heap var; Trie (parola/otomatik tamamlama, IDS imza eslestirme), Bloom Filter (buyuk olcekli tekrar kontrolu, tehdit istihbarati onbellekleme), Segment Tree/Fenwick (araligi sorgulama), Union-Find (aglarda baglanti/kumeleme, Kruskal), Suffix Array/Tree (string arama, malware imza analizi) profesyonel sistemlerde yaygin kullanilir ama korpuste yer almiyor.
- **[🔴 YÜKSEK] Sayi Teorisi ve Modular Aritmetik Algoritmalari (Hizli Us Alma, Genisletilmis Oklid, CRT, Asallik Testleri, Mod Ters)**  
  RSA/ECC/DH gibi kriptografi konulari kapsanmis ama bunlarin altinda yatan algoritmik makine (Miller-Rabin asallik testi, hizli modular us alma, genisletilmis Oklid ile mod ters bulma, Cin Kalan Teoremi) ayri bir konu olarak yok; bu algoritmalarin karmasikligi ve yan-kanal risklerini anlamadan kriptografik implementasyon guvenligi degerlendirilemez.
- **[🔴 YÜKSEK] Veri Yapilarinda Yan-Kanal ve Algoritmik Karmasiklik Saldirilari (Algorithmic Complexity Attacks, Zamanlama Sizintisi)**  
  Hash tablosu collision DoS saldirilari (hash flooding), kotu secilmis pivot ile quicksort'u O(n^2)'ye dusurme, regex catastrophic backtracking (ReDoS) gibi 'algoritma karmasikligini silah haline getirme' konulari; guvenlik odakli bir DSA modulunde kritik ama listede yer almiyor -- DoS ve zamanlama yan kanal saldirilarinin algoritmik kokeni bu.
- **[🟡 orta] Rastgele/Olasilikli Algoritmalar ve Amortize Analiz**  
  Randomized quicksort, reservoir sampling, Monte Carlo/Las Vegas algoritma siniflari, amortize analiz teknikleri (agregat, muhasebe, potansiyel yontemi) listede yok; hash tablosu yeniden boyutlandirma, rastgele algoritma garantileri ve DoS-dirençli veri yapilari tasarimi icin gereklidir (ozellikle hash flooding saldirilarina karsi savunma).
- **[🟡 orta] String Eslestirme ve Sikistirma Algoritmalari (KMP, Rabin-Karp, Aho-Corasick, Levenshtein, Huffman/LZ77)**  
  Liste 'String Algoritmalari' basligini genel geçer tutuyor; cok-desenli arama (Aho-Corasick — IDS/antivirus imza motorlarinin temeli), bulanik eslestirme (Levenshtein/Damerau — log analizi, phishing domain tespiti) ve sikistirma algoritmalari (Huffman, LZ77/78 — zip bombasi/DoS analizi icin) ayri ve derin islenmemis.
- **[🟡 orta] Hesaplanabilirlik Teorisi (Turing Makineleri, Durma Problemi, Karar Verilemezlik)**  
  Malware analizi ve statik/dinamik analiz konulari kapsanmis ama bunlarin teorik siniri olan Durma Problemi ve karar verilemezlik (neden genel malware tespitinin algoritmik olarak imkansiz oldugu) eksik; bu, tespit sistemlerinin neden heuristik/olasiliksal kalmak zorunda oldugunu aciklayan temel teoridir.
- **[🟡 orta] Paralel ve Dagitik Algoritmalar (Kilitsiz Veri Yapilari, Consensus Algoritmalari - Paxos/Raft, MapReduce Modeli)**  
  Dagitik sistemler/tutarlilik modelleri yazilim tarafinda var ama algoritmik temel (lock-free/wait-free veri yapilari, CAS tabanli yapilar, Paxos/Raft consensus algoritmalarinin adim adim islevi, MapReduce hesaplama modeli) ayri bir algoritmik konu olarak eksik; race condition ve concurrency guvenligini anlamak icin cekirdek algoritma bilgisi gerekir.
- **[⚪ düşük] Yaklasik/Sezgisel Optimizasyon Algoritmalari (A*, Genetik Algoritmalar, Simulated Annealing, Yaklasim Algoritmalari)**  
  Fuzzing ve pentest metodolojisinde yol/durum uzayi aramasi (ornegin sembolik yururlukte A* veya genetik algoritma tabanli fuzzing girdi uretimi) kullanilir; NP-zor problemlere yaklasik cozum teknikleri (yaklasim algoritmalari, yerel arama) korpuste yok.

### Sistem Programlama ve OS Ickileri
- **[🔴 YÜKSEK] Derleyici Ic Yapisi ve Optimizasyon (Lexer/Parser/AST/IR/Backend, LLVM)**  
  Listede 'Derleyiciler' baslik olarak var ama korpus mercegi acikca derleyici/runtime ic yapisini one cikariyor. SSA formu, IR optimizasyon gecisleri (constant folding, inlining, loop unrolling), register allocation, LLVM/GCC boru hatti gibi profesyonel seviyede kritik alt konular olmadan 'derleyiciler' basligi yuzeysel kalir. Bu derinlik olmadan hem exploit gelistirme (derleyici kaynakli mitigasyonlari anlamak) hem de performans muhendisligi eksik kalir.
- **[🔴 YÜKSEK] Runtime Ic Yapisi: VM Tasarimi, JIT Derleme, Bytecode Yorumlayicilar**  
  Java/JVM ve JavaScript Derin basliklari var ama JIT derleme stratejileri (tiered compilation, inline caching, deoptimization), bytecode yorumlayici tasarimi ve VM guvenlik sinirlari (sandbox kacislari, JIT spraying gibi exploit teknikleri) ayri ve derin bir konu olarak eksik. Tarayici/V8/JVM exploitasyonunun temelini olusturur.
- **[🔴 YÜKSEK] Lock-Free ve Wait-Free Programlama, Bellek Siralama Modelleri (Memory Ordering/Atomics)**  
  Gorev merceginde acikca istenen 'lock-free' konusu listede yok. Atomic islemler, CAS (compare-and-swap), memory_order (acquire/release/seq_cst), false sharing, ABA problemi gibi konular hem guvenlik (race condition sinif zafiyetleri) hem sistem performansi icin kritik ve tamamen eksik.
- **[🔴 YÜKSEK] GPU Programlama ve Paralel Hesaplama (CUDA/OpenCL, SIMD, Heterojen Bellek Modelleri)**  
  Gorev merceginde acikca istenen GPU/paralel konusu korpuste yok. GPU bellek modeli, warp/thread divergence, CUDA/OpenCL guvenlik yuzeyi (ornegin GPU tabanli side-channel'lar, kernel exploitation), SIMD/vektorizasyon gibi konular modern sistem programlamada ve ML altyapi guvenliginde onemli bir bosluk.
- **[🔴 YÜKSEK] Gomulu Sistemler ve RTOS (Real-Time Isletim Sistemleri, Bare-Metal Programlama)**  
  Gorev merceginde acikca istenen gomulu konusu eksik. Interrupt handling, bare-metal firmware gelistirme, RTOS zamanlama garantileri, bellek kisitli ortamlarda guvenlik (stack/heap yoklugu), firmware guvenligi (secure boot, UEFI, TPM) ICS/OT basligiyla kismen kesisir ama gomulu sistem programlama seviyesinde ayri ve derin degildir.
- **[🔴 YÜKSEK] Isletim Sistemi Cekirdek Ic Yapisi: Kernel Modulleri, Syscall Uygulamasi, Kernel Exploitation**  
  System Call, Sanal Bellek, Process/Thread/Scheduling gibi kullanici seviyesinden bakan konular var ama kernel tarafinin kendisi (kernel modul yazimi, syscall tablosu, kernel bellek tahsisi/slab allocator, kernel privilege escalation/exploitation - ornegin UAF in kernel, ROP in kernel) eksik. Linux/Windows Privesc konulari kullanici tarafi teknikleri kapsiyor olabilir ama kernel exploitation'in kendisi (LPE zafiyet siniflari, kernel mitigasyonlari - SMEP/SMAP/KASLR) ayri, derin bir konu olarak yok.
- **[🔴 YÜKSEK] Donanim Yan Kanal Saldirilari (Spectre/Meltdown, Cache Timing, Rowhammer)**  
  CPU mikromimari kaynakli saldirilar (spekulatif calistirma zafiyetleri, cache-tabanli side-channel, Rowhammer bellek bozulmasi) hicbir basligin altinda acikca yer almiyor. Bellek Yerlesimi ve Exploit Mitigations ile kesisse de mikromimari seviyesindeki bu saldiri sinifi sistem programlama uzmanliginin ayirt edici, kritik bir parcasidir.
- **[🟡 orta] Dosya Formati ve Yukleyici Ic Yapisi (ELF/PE/Mach-O Derinlemesine)**  
  Linker/Loader baslik olarak var ama ELF/PE/Mach-O ikili format ic yapisinin kendisi (section/segment tablolari, relocation, dynamic linking mekanizmasi, TLS implementasyonu) malware analizi, RE ve exploit gelistirme (ornegin PE enjeksiyonu, ELF parazit enfeksiyonu) icin kritik bir on kosuldur ve suan yuzeysel kalabilir.
- **[🟡 orta] Dosya Sistemi Ic Yapisi ve Depolama Motorlari (Journaling, COW, inode/B-tree Tabanli FS)**  
  Dosya Sistemleri genel baslik olarak var ama journaling mekanizmalari, copy-on-write (ZFS/Btrfs), inode yapisi, dosya sistemi forensics ile dogrudan baglantili ic detaylar (crash consistency, fsck mantigi) yuzeysel kalabilir; disk forensics'in dogru yorumlanmasi bu derinligi gerektirir.
- **[🟡 orta] Hypervisor ve Sanallastirma Ic Yapisi (Tip-1/Tip-2, VM Kacisi, VT-x/AMD-V)**  
  Konteyner Kacisi/Docker var ama tam sanallastirma katmani (hypervisor tasarimi, donanim destekli sanallastirma uzantilari, VM escape zafiyet sinifi, nested virtualization) ayri bir konu olarak eksik; bulut guvenligi ve kernel-altinda tehdit modellemesi icin onemlidir.

### Ağlar ve Protokoller
- **[🔴 YÜKSEK] QUIC Protokol İç Yapısı**  
  QUIC (RFC 9000) artik HTTP/3'un temeli ve modern CDN/tarayici trafiginin buyuk kismini olusturuyor. Baglanti kurulumu (0-RTT/1-RTT), stream multiplexing, connection migration, head-of-line blocking cozumu, ve QUIC'e ozgu saldiri yuzeyleri (0-RTT replay, amplifikasyon/DoS, connection ID spoofing) listede yok; sadece 'HTTP/1-2-3' basligi var ama protokol ic mekanizmasi ayri ve derin bir konu.
- **[🔴 YÜKSEK] gRPC Derinlemesine (HTTP/2 Framing, Interceptor, Deadline/Cancellation)**  
  Liste 'GraphQL/gRPC' basligini yuzeysel geciyor; gRPC'nin HTTP/2 uzerindeki framing detaylari, streaming turleri (unary/server/client/bidi), interceptor zinciri, deadline propagation, ve gRPC-ozel guvenlik (mTLS zorunlulugu, reflection API'nin ifsa riski, protobuf deserialization saldirilari) ayri, profesyonel seviyede ele alinmali.
- **[🔴 YÜKSEK] Ag Programlama (Soket API, Non-blocking I/O, epoll/io_uring)**  
  Dusuk seviye soket programlama (BSD sockets, select/poll/epoll/kqueue/io_uring), non-blocking/async I/O modelleri, backpressure ve buffer yonetimi tamamen eksik. Bu, hem performans muhendisligi hem de ag tabanli exploit gelistirme (custom TCP client/server, raw socket saldirilari) icin temel bir yetkinlik.
- **[🔴 YÜKSEK] Service Mesh Mimarisi (Istio/Linkerd, Sidecar Proxy, mTLS Otomasyonu)**  
  Kubernetes ortamlarinda servisler-arasi trafik yonetimi artik service mesh ile yapiliyor; sidecar proxy modeli (Envoy), mTLS otomatik rotasyonu, trafik politikalari (retry/circuit breaking mesh seviyesinde), ve mesh'e ozgu saldiri yuzeyi (sidecar bypass, control plane ele gecirme) listede hic yok.
- **[🔴 YÜKSEK] BGP ve Yonlendirme Protokolleri Guvenligi**  
  Internet'in omurgasi olan BGP (route hijacking, route leak, RPKI/ROV ile savunma) ve ic ag yonlendirme protokolleri (OSPF/EIGRP) tamamen eksik. BGP hijack gercek dunyada trafik yonlendirme saldirilarinin en kritik vektorlerinden biri ve simdiki listede (Nmap, Firewall, VPN, ARP/DNS) bu seviye yonlendirme konusu yok.
- **[🟡 orta] Yuk Dengeleme ve Reverse Proxy Protokol Detaylari (L4 vs L7, PROXY protocol, HTTP keep-alive/connection reuse tuzaklari)**  
  'Load Balancing' basligi var ama genel gelistirici perspektifinden; protokol seviyesinde L4/L7 farklarinin ag paketi duzeyinde nasil calistigi, PROXY protocol header injection, ve request smuggling'in load balancer/reverse proxy zincirindeki kok nedeni (connection reuse mismatch) ag protokolleri merceginden ayrica islenmeli.
- **[🟡 orta] Modern DNS Protokolleri (DoH/DoT/DNSSEC/DNS-over-QUIC)**  
  Liste 'DNS Saldirilari' ve 'DNS (gelistirici)' iceriyor ama sifreli/dogrulanan DNS protokol varyantlarinin (DoH, DoT, DNSSEC zincir dogrulama, DNS-over-QUIC) ic yapisi ve bunlarin egzoz/tespit zorlugu (DoH ile DNS filtreleme atlatma) ayri, protokol-odakli bir konu olarak eksik.
- **[🟡 orta] Ag Zaman Senkronizasyonu ve Saldirilari (NTP/PTP)**  
  NTP amplifikasyon DDoS, NTP/PTP spoofing ile zaman kaymasi saldirilari (Kerberos saat toleransini bozma, TLS sertifika gecerlilik kontrolünü atlatma) gibi kritik bagimliliklari olan bir protokol ailesi listede yok.
- **[🟡 orta] Multicast/Anycast ve WebRTC Ag Protokolleri (ICE/STUN/TURN)**  
  Gercek zamanli iletisim (video/ses) ve CDN/anycast dagitimi icin kullanilan NAT gecisi protokolleri (STUN/TURN/ICE) ve bunlarin IP sizdirma/gizlilik riskleri (WebRTC IP leak) modern web uygulamalari icin onemli ama tamamen eksik.
- **[⚪ düşük] Ag Protokolu Fuzzing ve Ters Muhendislik (özel/bilinmeyen protokoller)**  
  Genel 'Fuzzing' basligi var ama ag protokolune ozel fuzzing (stateful protocol fuzzing, Boofuzz/Peach benzeri yaklasimlar, PCAP analizinden protokol grameri cikarma) ayri bir uzmanlik alani ve pentest/RE ile kesisen ama ag protokolleri merceginden ele alinmasi gereken bir bosluk.
- **[⚪ düşük] SDN ve Ag Otomasyonu Guvenligi (OpenFlow, Ag Telemetri Protokolleri - NetFlow/sFlow/gNMI)**  
  Yazilim tanimli aglarda kontrol duzlemi (OpenFlow controller) saldirilari ve modern ag gozlemlenebilirligi icin kullanilan NetFlow/sFlow/gNMI/Telemetry protokolleri, buyuk kurumsal/servis saglayici ortamlarda kritik ama listede karsiligi yok.

### Veritabanları ve Veri Katmanı
- **[🔴 YÜKSEK] MVCC ve Transaction Isolation İç Yapısı (PostgreSQL/InnoDB derinliği)**  
  Listede 'ACID/Transactions' ve 'Iliskisel Model/SQL' genel basliklar olarak var ama MVCC'nin somut mekanigi (tuple versiyonlama, snapshot isolation, vacuum/garbage collection, undo/redo log farklari, phantom read/write skew, serializable snapshot isolation) profesyonel seviyede ayri ve derin bir konu. Bu konu hem performans ayari hem de guvenlik acisindan (ornegin isolation seviyesi yanlis secildiginde olusan race condition tabanli is mantigi zafiyetleri) kritik; 'Web Race Condition' konusu DB tarafindaki isolation-level kaynakli acigi kapsamiyor.
- **[🔴 YÜKSEK] Write-Ahead Logging (WAL), Crash Recovery ve Durability Mekanizmalari**  
  WAL, checkpointing, redo/undo loglari, fsync/durability garantileri, ARIES algoritmasi gibi konular veritabani internals'in temel tasi ama listede yok. Yanlis WAL/fsync yapilandirmasi veri kaybina ve forensics sirasinda yanlis sonuc cikarilmasina yol acar; 'Disk Forensics' konusuyla da kesisir ama DB-spesifik recovery mekanigi ayri ele alinmali.
- **[🔴 YÜKSEK] Veritabani Guvenligi Sertlestirme (DB Hardening: least-privilege roller, RLS, TDE, audit logging)**  
  Listede 'Sistem Sertlestirme' genel bir baslik ama veritabanina ozgu sertlestirme (row-level security, column-level encryption/TDE, priv escalation vektorleri icin GRANT/ROLE hijyeni, connection string/secrets sizintisi, veritabani audit trail yapilandirmasi) SQL Injection sonrasi 'etki azaltma' katmanini olusturur ve ayri, somut bir konu olarak eksik.
- **[🔴 YÜKSEK] Veri Ambari / OLAP Mimarisi ve Kolon-Yonelimli Depolama (Data Warehousing, Star/Snowflake Schema, Columnar Storage)**  
  Listedeki tum veritabani konulari OLTP odakli (iliskisel model, NoSQL, replikasyon). Modern veri muhendisliginin buyuk bir kismi OLAP/analitik depolama (Snowflake, BigQuery, ClickHouse, Redshift tarzi kolon-yonelimli motorlar, star/snowflake schema, slowly changing dimensions) uzerine kurulu ve tamamen eksik.
- **[🔴 YÜKSEK] ETL/ELT Pipeline Tasarimi ve Veri Orkestrasyonu (Airflow/dbt tarzi)**  
  'Veri muhendisligi' mercek alani icinde acikca belirtilmis ama listede karsiligi yok. Idempotency, backfill, DAG tasarimi, veri kalite kontrolleri (data quality/validation) ve orchestration guvenligi (ornegin Airflow'da kod enjeksiyonu, DAG'lar araciligiyla RCE) hem yazilim hem guvenlik acisindan onemli bir bosluk.
- **[🔴 YÜKSEK] Stream Processing ve Olay Tabanli Veri Isleme (Kafka internals, exactly-once semantics, windowing)**  
  Mercek alaninda 'streaming' acikca belirtilmis. Listede 'Event-Driven/CQRS' ve 'Mesaj Kuyruklari' var ama bunlar uygulama mimarisi seviyesinde; Kafka/Kinesis/Flink gibi sistemlerin ic yapisi (partition/offset yonetimi, consumer group rebalancing, exactly-once vs at-least-once, watermark/windowing, topic ACL guvenligi) ayri ve derin bir konu olarak eksik.
- **[🔴 YÜKSEK] Dagitik Veritabani Konsensus ve Replikasyon Protokolleri (Raft/Paxos, Quorum, Split-Brain)**  
  'Replikasyon/Sharding' ve 'CAP Teoremi' yuzeysel duzeyde var ama konsensus algoritmalarinin kendisi (Raft, Paxos, quorum okuma/yazma, leader election, split-brain senaryolari, conflict-free replicated data types/CRDT) profesyonel dagitik DB uzmanliginin merkezinde ve ayri, somut bir konu olarak eksik.
- **[🟡 orta] Arama Motoru Ic Yapisi (Elasticsearch/Lucene: ters indeks, relevance scoring, sharding)**  
  Mercek alaninda 'arama' acikca belirtilmis ama listede karsiligi yok. Ters indeks (inverted index) yapisi, BM25/TF-IDF skorlama, analyzer/tokenizer pipeline, Elasticsearch/OpenSearch guvenligi (yetkisiz sorgu erisimi, query injection) tamamen eksik bir alan.
- **[🟡 orta] Veritabani Yedekleme, Point-in-Time Recovery ve Felaket Kurtarma (DB-spesifik)**  
  Genel 'Incident Response' var ama veritabanina ozgu backup stratejileri (full/incremental/differential, point-in-time recovery, RPO/RTO hesaplama, yedek sifreleme ve yedek hirsizligi tehdit modeli) ayri, somut ve ransomware sonrasi kurtarma acisindan kritik bir bosluk.
- **[🟡 orta] SQL Injection Sonrasi Veritabani-Spesifik Sizma Teknikleri (Blind/Out-of-band, DB motoruna ozgu fonksiyon istismari)**  
  'SQL Injection' genel baslik olarak var ama veritabani motoruna ozgu ileri sizma teknikleri (MSSQL xp_cmdshell, PostgreSQL COPY/lo_import ile RCE, Oracle PL/SQL injection, MySQL FILE privilege ile dosya okuma/yazma) DB uzmanligi merceginden ayri ve derin islenmesi gereken bir konu; genel SQLi konusu bu motor-spesifik derinligi genelde kapsamaz.
- **[⚪ düşük] Veri Sanallastirma/Katalog ve Data Lineage/Governance (Data Catalog, Lineage Tracking, PII Discovery)**  
  Buyuk veri muhendisligi organizasyonlarinda veri kesfi (data catalog), soy izleme (lineage) ve otomatik PII/hassas veri tespiti (data governance) profesyonel bir gereksinim; listede yok ve KVKK/GDPR benzeri uyum baglaminda guvenlik ile de kesisiyor.
- **[⚪ düşük] Veritabani Performans Ic Mekanizmalari: Query Planner/Optimizer Internals ve Execution Plan Analizi**  
  'Query Optimizasyonu' basligi var ama genelde yuzeysel indeks/sorgu yazma tavsiyeleri seviyesinde kaliyor; optimizer'in ic isleyisi (cost-based optimization, statistics/histogram, join order secimi, execution plan okuma - EXPLAIN ANALYZE derinligi) ayri, ileri seviye bir konu olarak eksik kalabilir.

### Dagitik Sistemler ve Sistem Tasarimi
- **[🔴 YÜKSEK] Konsensus Algoritmalari (Raft/Paxos/Multi-Paxos/EPaxos)**  
  Listede 'Dagitik Sistemler' baslik olarak var ama Raft lider secimi, log replikasyonu, uyelik degisikligi (joint consensus), Paxos ve varyantlari (Multi-Paxos, Fast Paxos, EPaxos), quorum matematigi gibi somut mekanizmalar acikca ayri konu olarak gecmiyor. Bu, 'consensus' merceginin tam ozudur ve profesyonel bir dagitik sistemler egitiminde en kritik teorik temeldir; sadece isim gecmesi yeterli derinlik saglamaz.
- **[🔴 YÜKSEK] Dagitik Sistemlerde Zaman ve Siralama (Logical Clocks, Vector Clocks, Lamport Timestamps, Hybrid Logical Clocks, TrueTime/Spanner)**  
  Olay siralamasi, nedensellik (causality) ve dagitik saat senkronizasyonu olmadan consensus, replikasyon ve tutarlilik modelleri tam anlasilamaz. Google Spanner'in TrueTime yaklasimi ve HLC gibi pratik cozumler gercek mimari vaka calismalari icin temel olusturur, ancak listede yer almiyor.
- **[🔴 YÜKSEK] Dagitik Islem Yonetimi ve Atomik Commit (2PC/3PC, Saga Pattern, TCC)**  
  ACID/Transactions tekil veritabani baglaminda var ama dagitik islemlerin nasil koordine edildigi (Two-Phase/Three-Phase Commit, Saga orkestrasyon/koreografi, Try-Confirm-Cancel) ayri ve kritik bir konu; mikroservis mimarilerinde veri tutarliligi icin vazgecilmezdir ve su an yuzeysel/eksik.
- **[🔴 YÜKSEK] Dagitik Konsensus Veri Yapilari ve Koordinasyon Servisleri (ZooKeeper, etcd, Chubby)**  
  Consensus teorisinin pratikte nasil urunlestigi (lider secimi, dagitik kilitleme, konfigurasyon yonetimi, service discovery) gercek mimari vaka calismasi acisindan cok onemli; Kubernetes'in etcd'ye, pek cok sistemin ZooKeeper/Chubby'ye dayandigi dusunulurse buyuk bir bosluk.
- **[🔴 YÜKSEK] Gercek Dagitik Sistem Mimarisi Vaka Calismalari (Google Spanner, Amazon Dynamo, Cassandra, Kafka Ic Mimarisi, HDFS/GFS)**  
  Gorev tanimi acikca 'gercek mimari vaka calismalari' istiyor; listede CAP Teoremi, Replikasyon/Sharding gibi genel kavramlar var ama Dynamo'nun consistent hashing + vector clock tasarimi, Spanner'in TrueTime+Paxos birlesimi, Cassandra'nin gossip protokolu, Kafka'nin ISR/log replikasyonu gibi somut, isimlendirilmis sistem analizleri eksik.
- **[🔴 YÜKSEK] Kapasite Planlama ve Olcek Matematigi (Back-of-envelope Estimation, Little's Law, Kuyruk Teorisi/Queueing Theory)**  
  Gorev tanimi acikca 'kapasite' merceginden bahsediyor; QPS/latency/storage tahmini, Little's Law (L=λW), M/M/1 kuyruk modelleri gibi kapasite planlamanin matematiksel temelleri listede hic yok. Sistem tasarim mulakatlarinin ve gercek kapasite planlamasinin bel kemigidir.
- **[🟡 orta] Dagitik Sistemlerde Hata Modelleri ve Byzantine Fault Tolerance**  
  Resilience Patterns var ama fail-stop/fail-silent/Byzantine hata modelleri arasindaki fark, PBFT gibi Byzantine-tolerant consensus algoritmalari (blockchain/kritik sistemler icin onemli) ayri ele alinmamis; consensus konusunun tamamlayici parcasidir.
- **[🟡 orta] Gossip Protokolleri ve Epidemik Yayilim (Gossip/Epidemic Protocols, SWIM, Anti-Entropy)**  
  Cassandra, Consul, Riak gibi gercek sistemlerin uyelik yonetimi ve hata tespiti icin kullandigi temel dagitik sistem tekniklerinden biri; olceklenebilirlik ve node kesif mekanizmalari icin onemli ama listede yer almiyor.
- **[🟡 orta] Dagitik Kilitleme ve Liderlik Secimi (Distributed Locking, Leader Election, Fencing Tokens)**  
  Redis-tabanli (Redlock tartismasi dahil) ya da ZooKeeper-tabanli dagitik kilit mekanizmalari, split-brain onleme ve fencing token kullanimi pratikte cok sik karsilasilan ama listede acikca kapsanmayan bir alt konu.
- **[🟡 orta] Idempotency ve Exactly-Once/At-Least-Once Teslimat Semantikleri**  
  Mesaj kuyruklari listede var ama teslimat garantileri (at-most-once/at-least-once/exactly-once), idempotency anahtarlari ve deduplication stratejileri dagitik sistem tasariminda kritik bir pratik detay olup ayri derinlestirilmemis.
- **[🟡 orta] Coklu Bolge / Coklu Veri Merkezi Mimarileri ve Felaket Kurtarma (Multi-Region Architecture, Active-Active/Active-Passive, RPO/RTO)**  
  Buyuk olcekli gercek sistemlerin kapasite ve dayaniklilik planlamasinin merkezinde yer alir; bolgeler arasi replikasyon gecikmesi, failover stratejileri ve RPO/RTO hesaplari listede acikca yok.
- **[⚪ düşük] Backpressure ve Akis Kontrolu (Flow Control/Backpressure Yonetimi)**  
  Rate Limiting listede var ama sistemin asiri yuklenmeye karsi ic mekanizmalari (reactive streams backpressure, kuyruk doluluk yonetimi, load shedding stratejileri) ayri ve kapasite planlamasiyla dogrudan ilgili bir alt konu olarak eksik.

### Yazilim Muhendisligi Pratikleri
- **[🔴 YÜKSEK] DevSecOps ve Guvenlik Pipeline Entegrasyonu (SAST/DAST/SCA/IaC Tarama Otomasyonu)**  
  Listede Secure SDLC ve CI/CD ayri ayri var ama bunlarin kesisimi olan 'guvenligin pipeline'a gomulmesi' (SAST/DAST/SCA araclari, kalite kapilari, break-the-build esikleri, sonuc triage sureci) profesyonel bir DevSecOps muhendisi icin ayri ve derin bir konu; su an ne CI/CD ne Secure SDLC basligi bunu yeterince kapsiyor.
- **[🔴 YÜKSEK] Yazilim Tedarik Zinciri Guvenligi (SBOM, SLSA, Bagimlilik Imzalama, Sigstore/cosign)**  
  Listede CVE/vuln management var ama SBOM uretimi, SLSA seviyeleri, paket imzalama, provenance dogrulama, dependency confusion gibi tedarik zinciri guvenligi ayri ve gunumuzde kritik onemde bir alt-alan; kapsanmiyor.
- **[🔴 YÜKSEK] Gizli Bilgi (Secrets) Yonetimi ve CI/CD Icinde Sizinti Onleme**  
  Kriptografi tarafinda 'Anahtar/Sir Yonetimi' var ama bu daha cok kriptografik anahtar odakli; DevSecOps mercekinde secrets scanning (git-secrets, gitleaks), Vault/KMS entegrasyonu, CI degiskenlerinin korunmasi, pipeline'da sizinti tespiti ayri ve pratik bir muhendislik konusu olarak eksik.
- **[🔴 YÜKSEK] Gozlemlenebilirlik Derinlik: Dagitik Izleme (Distributed Tracing), OpenTelemetry, SLO/SLI/Hata Butcesi**  
  Kullanicinin mercegi acikca 'gozlemlenebilirlik derin' diyor; listede sadece genel 'Observability' ve 'Loglama/Telemetri' var, ama OpenTelemetry standardi, trace context propagation, SLI/SLO tanimlama, error budget yonetimi, alerting fatigue/noise azaltma gibi somut derinlik konulari ayri ele alinmamis.
- **[🔴 YÜKSEK] Dokumantasyon Muhendisligi (ADR, API Referans Uretimi, Docs-as-Code, Runbook Standartlari)**  
  Kullanicinin mercegi 'dokumantasyon' diyor ama listede dokumantasyona dair hicbir baslik yok; Architecture Decision Records, docs-as-code akisi, otomatik API dokuman uretimi (OpenAPI/Swagger), onboarding/runbook dokumantasyon standartlari tamamen eksik bir bosluk.
- **[🔴 YÜKSEK] Mimari Stiller Karsilastirmasi (Hexagonal/Onion/Clean Architecture, Katmanli vs Modular Monolit vs Serverless)**  
  Mikroservis/Monolit ve DDD var ama bunlarin somut mimari desenleri (Hexagonal/Ports&Adapters, Clean Architecture, Onion Architecture, Modular Monolith, Serverless/FaaS mimarisi) ayri, kullanicinin mercek olarak vurguladigi 'mimari stiller' basligi altinda acikca eksik.
- **[🟡 orta] Feature Flag / Kademeli Yayin Stratejileri (Canary, Blue-Green, Dark Launch)**  
  Resilience Patterns ve CI/CD basliklari var ama modern dagitim stratejileri (feature flag yonetimi, canary/blue-green/rolling deploy, rollback otomasyonu, deney/A-B altyapisi) ayri, gunumuz yazilim muhendisliginde standart bir pratik ve simdi eksik.
- **[🟡 orta] Kod Kalitesi Metrikleri ve Statik Kalite Kapida Yonetimi (Cyclomatic Complexity, Teknik Borc Olcumu, Kod Kokusu Katalogu)**  
  Temiz Kod/Refactor ve Kod Inceleme var ama bunlarin olculebilir/metrik tarafi (teknik borc kantifikasyonu, complexity/coupling metrikleri, kod kokusu taksonomisi, kalite kapisi esikleri SonarQube tarzi araclarla) ayri bir muhendislik disiplini olarak eksik kaliyor.
- **[🟡 orta] API Versiyonlama ve Geriye Uyumluluk Yonetimi**  
  REST API Tasarimi ve API Tasarim Ilkeleri var ama versiyonlama stratejileri (semver, breaking change yonetimi, deprecation policy, contract testing/Pact) somut olarak ayri bir alt-baslik degil; profesyonel API gelistirmede siklikla ihtiyac duyulan bir konu.
- **[🟡 orta] Performans ve Yuk Testi Muhendisligi (Load/Stress/Soak Testing, Kapasite Planlama)**  
  Test Stratejileri genel gecer; performans/yuk/stres/dayaniklilik testleri ve kapasite planlama ayri bir muhendislik pratigi olarak kapsanmiyor, uretim sistemlerinde kritik bir bosluk.
- **[⚪ düşük] Yazilim Lisanslama ve Acik Kaynak Uyumluluk (License Compliance, Copyleft Riskleri)**  
  Tedarik zinciri guvenligiyle iliskili ama ayri bir konu: acik kaynak lisans taramasi, copyleft/GPL riskleri, license compliance otomasyonu kurumsal yazilim gelistirmede onemli fakat listede yok.

### Web/Frontend, API ve Mobil Gelistirme
- **[🔴 YÜKSEK] Modern Frontend State Yonetimi ve Reaktivite (React/Vue/Signals, Hydration, Sunucu Bilesenleri)**  
  Liste 'Frontend Mimari' ve 'Web Performans' gibi genel basliklar iceriyor ama React Server Components, hydration mismatch hatalari, signal tabanli reaktivite (SolidJS/Vue 3), state hydration guvenlik riskleri (client'a sizan sunucu verisi) gibi 2024+ modern frontend'in cekirdek konulari ayri ve derinlemesine kapsanmiyor. Bu, gunumuz production frontend hatalarinin buyuk kismini olusturuyor.
- **[🔴 YÜKSEK] Mobil Uygulama Guvenligi Derinlemesine: Platform-Ozgu Saldiri Yuzeyi (iOS Keychain/Android Keystore, Deep Link/Intent Hijacking, Kod Obfuskasyon/Root-Jailbreak Tespiti)**  
  Liste sadece genel 'Mobil Guvenlik' basligi iceriyor; MASTG yutulmus ama korpusta ayri konu olarak deep link/universal link hijacking, insecure data storage (Keychain/Keystore yanlis kullanimi), certificate pinning bypass, WebView JavaScript bridge zafiyetleri gibi somut, sik goruelen mobil pentest konulari eksik/yuzeysel kaliyor.
- **[🔴 YÜKSEK] Mobil Native Gelistirme: iOS (Swift/SwiftUI) ve Android (Kotlin/Jetpack Compose) Mimarisi**  
  Kapsanan diller listesinde (Python, C, C++, Rust, Go, JS, TS, C#, Java) Swift ve Kotlin native mobil gelistirme dilleri/frameworkleri yer almiyor; ne dil ozellikleri ne de platform yasam dongusu (Activity/ViewController lifecycle, memory management ARC) kapsanmis, oysa mobil gelistirme mercekte acikca hedef alaniniz icinde.
- **[🔴 YÜKSEK] API Gateway Mimarisi ve Yonetimi (Kong/Envoy/APISIX, Sema Dogrulama, Versiyonlama Stratejileri)**  
  Mercek acikca 'API gateway' diyor ama listede sadece REST/GraphQL/gRPC tasarimi ve Rate Limiting var; gateway'e ozgu konular (routing, request/response transformation, API composition, backend-for-frontend pattern, OpenAPI/schema-first tasarim ve dogrulama, API versiyonlama/deprecation stratejileri) ayri bir konu olarak yer almiyor.
- **[🔴 YÜKSEK] Gercek Zamanli Iletisim Derinligi: WebRTC, Server-Sent Events, Push Notification Mimarisi (APNs/FCM)**  
  Mercek 'gercek zamanli' diyor; listede sadece WebSocket var. WebRTC (P2P medya/veri kanali, STUN/TURN/ICE), SSE, ve mobil push bildirim altyapisi (APNs/FCM token yonetimi, guvenlik) gercek zamanli sistemlerin buyuk bir kismini olusturuyor ve tamamen eksik.
- **[🔴 YÜKSEK] WebAssembly (WASM): Calisma Modeli, Guvenlik Sandbox'i ve Saldiri Yuzeyi**  
  Mercek acikca WASM'i belirtiyor ama listede hic WASM konusu yok; WASM sandbox kacislari, memory-safety varsayimlari, WASI guvenligi ve tarayicida native-hiz kod calistirmanin getirdigi yeni tehdit modeli profesyonel bir korpus icin kritik bir bosluk.
- **[🟡 orta] Mobil API Guvenligi: Mobil-Backend Iletisimi, Certificate/Public Key Pinning, API Anahtari/Sir Gizleme, Reverse-Engineering ile Endpoint Kesfi**  
  IDOR/JWT gibi genel API zafiyetleri kapsanmis ama mobil istemcinin backend'e nasil guvenli konustugu (pinning, obfuscated API keys, app-attestation/Play Integrity/DeviceCheck) ayri bir yuzey; bu konu hem mobil hem API kesisiminde ozel teknikler gerektirir ve simdiki listede kaybolmus durumda.
- **[🟡 orta] Cross-Platform Mobil Gelistirme (React Native / Flutter) Mimarisi ve Guvenlik Farklari**  
  Gunumuz mobil gelistirmesinin buyuk kismi React Native/Flutter ile yapiliyor; bridge mimarisi (JS-native koprusu), Flutter'in Dart derlemesi/binary analiz zorlugu gibi native'den farkli guvenlik ve performans ozellikleri korpusta hic yer almiyor.
- **[🟡 orta] Frontend Tedarik Zinciri Guvenligi (npm/yarn Bagimlilik Zafiyetleri, Subresource Integrity, CDN Tehlikeleri, Build-time Supply Chain Saldirilari)**  
  Prototype Pollution gibi bazi frontend zafiyetleri var ama npm paket ele gecirme (typosquatting, dependency confusion), SRI kullanimi, CI/CD build surecinde enjekte edilen zararli script (event-stream vakasi gibi) frontend'e ozgu ve ayri, onemli bir tedarik zinciri riski olarak eksik.
- **[🟡 orta] SSR/SSG/Edge Rendering Mimarileri ve Guvenlik Etkileri (Next.js/Nuxt, Edge Functions, ISR)**  
  Mercek acikca 'SSR' diyor; listede genel 'Frontend Mimari' var ama SSR'a ozgu riskler (sunucu tarafinda calisan kodun client secrets sizdirmasi, edge runtime kisitlamalari, ISR cache zehirlenmesi, getServerSideProps/loader fonksiyonlarinda yetkilendirme hatalari) ayri ele alinmamis.
- **[⚪ düşük] Frontend Erisilebilirlik (a11y) ve I18n/L10n Muhendisligi**  
  Profesyonel seviyede frontend gelistirme WCAG uyumu, ARIA kullanimi ve uluslararasilastirma (RTL destegi, locale-aware formatlama) konularini icerir; guvenlik agirlikli olmasa da 'Web/Frontend gelistirme' basligi altinda tam profesyonel kapsam icin eksik kalan bir alan.
- **[⚪ düşük] Mobil Uygulama Dagitim ve Guncelleme Guvenligi (Code Signing, OTA/CodePush Guncellemeleri, App Store Inceleme Atlatma Teknikleri)**  
  Mobil persistence/uygulama guvenligi genel olarak kapsanmis olsa da, imzalama zinciri (code signing, provisioning profile), OTA guncelleme kanallarinin ele gecirilmesi (React Native CodePush gibi) ve store review bypass teknikleri ayri, pratikte saldirganlarin kullandigi bir yuzey olarak eksik.
