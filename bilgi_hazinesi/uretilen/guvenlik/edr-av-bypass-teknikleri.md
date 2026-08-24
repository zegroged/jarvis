# EDR/AV Bypass Teknikleri: Kavramsal Anlayış ve Savunma

> Bu makale, savunmacıların (blue team) modern uç nokta savunmalarının nasıl
> atlatılmaya çalışıldığını **anlaması ve tespit etmesi** için yazılmıştır. Odak,
> operasyonel saldırı reçetesi değil; mekanizmanın mantığı ve buna karşı
> **tespit/savunma** katmanlarıdır — MITRE ATT&CK ve atomic-red-team gibi
> savunma kaynaklarının yaptığı gibi.

## Önce Savunmayı Anla: EDR Nasıl Görür?

Bypass tekniklerini anlamak için önce EDR'ın (Endpoint Detection and Response)
görme yöntemlerini bilmek gerekir:

1. **Userland API hooking:** EDR, `ntdll.dll` gibi kütüphanelerdeki kritik
   fonksiyonların başına küçük yönlendirmeler (hook) koyar. Program bu fonksiyonu
   çağırınca kontrol önce EDR'ın inceleme koduna uğrar. En eski ve en kolay
   atlatılan katmandır, çünkü **kullanıcı modunda** — yani saldırganın da
   eriştiği bellekte — yaşar.
2. **Kernel callback'leri:** Windows çekirdeği; process/thread oluşturma, image
   (DLL/sürücü) yükleme, registry ve nesne erişimi gibi olaylarda kayıtlı
   sürücülere bildirim gönderir (`PsSetCreateProcessNotifyRoutine`,
   `ObRegisterCallbacks` gibi). EDR bunları çekirdek sürücüsüyle dinler.
   **Çekirdek modunda** olduğundan kullanıcı modundaki bir saldırganın doğrudan
   dokunması çok daha zordur — savunmanın güçlü tarafı budur.
3. **ETW (Event Tracing for Windows):** İşletim sistemi, .NET runtime ve script
   motorları için zengin olay akışı üretir. Özellikle **ETW-TI (Threat
   Intelligence)** sağlayıcısı, çekirdek düzeyinde şüpheli bellek ve enjeksiyon
   olaylarını raporlar.
4. **AMSI (Antimalware Scan Interface):** Script motorları (PowerShell, VBScript,
   Office makroları) çalıştırılacak içeriği çalışma anında AV/EDR'a taratmak için
   AMSI'ye verir. Böylece diske hiç yazılmayan (fileless) script'ler bile bellekte
   taranabilir.

## Bypass Mantığı (Kavramsal)

Saldırganın amacı, bu görme katmanlarının **görüş alanından çıkmaktır.** Kavramsal
düzeyde başlıca yaklaşımlar:

- **Userland unhooking:** Saldırgan, EDR'ın `ntdll` üzerine koyduğu hook'ları fark
  edip kütüphanenin "temiz" bir kopyasını belleğe getirerek yönlendirmeyi geçmeye
  çalışır. Mantık: "EDR'ın gözünü kullanıcı modunda etkisizleştirebilirsem
  çağrılarım incelenmeden geçer." **Zayıf noktası:** Yalnızca *userland* hook'ları
  atlatır; çekirdek callback'leri ve ETW-TI hâlâ görür.
- **Direct/indirect syscalls:** Program normalde çekirdeğe `ntdll` fonksiyonları
  üzerinden ulaşır (EDR de oraya hook koyar). Saldırgan `ntdll`'i hiç kullanmadan
  doğrudan sistem çağrısı yapmayı dener; böylece userland hook'a uğramaz. Mantık
  aynıdır: kullanıcı modundaki gözü atlamak. Yine **çekirdek görünürlüğünü
  ortadan kaldırmaz.**
- **ETW patching:** Saldırgan, kendi süreci içindeki ETW olay üretimini susturmaya
  çalışır (ör. .NET veya AMSI ile ilgili olay sağlayıcısını devre dışı bırakmak).
  Amaç, telemetriyi kaynağında kesmek. **Zayıf noktası:** Kendi sürecinde ETW'yi
  susturmak, çekirdek düzeyinde (ETW-TI) veya başka süreçlerde üretilen olayları
  etkilemez; ayrıca "ETW aniden sustu" durumu kendisi bir anomali sinyalidir.
- **AMSI bypass:** Saldırgan, script motorunun AMSI'ye içerik göndermesini ya da
  AMSI'nin "temiz" cevabı döndürmesini bozmaya çalışır. Amaç, bellekte çalışan
  script'in taranmadan geçmesi. **Zayıf noktası:** AMSI yalnızca bir katmandır;
  script bloğu loglama, davranışsal tespit ve çekirdek telemetrisi devrededir.

Ortak tema: bu tekniklerin çoğu **kullanıcı modundaki** görünürlüğü hedefler.
Modern savunmanın kilit dersi de budur: kullanıcı modu saldırganın oyun alanıdır;
güçlü tespit **çekirdek ve davranış** düzeyinde kurulmalıdır.

## Tespit ve Savunma (Asıl Değer)

1. **Çekirdek temelli telemetriye güven.** Userland hook'lara aşırı bağımlı bir
   EDR, unhooking/syscall teknikleriyle kör kalabilir. Kernel callback'leri,
   ETW-TI ve Microsoft'un çekirdek koruma özellikleri (VBS/HVCI) kullanıcı
   modundan silinemeyen bir görüş sağlar. Ürün seçimi ve yapılandırmada çekirdek
   görünürlüğünü önceliklendirin.
2. **"Kör nokta" anomalilerini avla.** Bir sürecin `ntdll`'i diskteki orijinaliyle
   uyuşmayan biçimde belleğe yeniden eşlemesi (unhooking izi), ETW oturumlarının
   beklenmedik biçimde susması, veya AMSI ile ilgili fonksiyonların bellekte
   değiştirilmesi — bunların hepsi *tekniğin kendisini gizlese de* geride iz
   bırakır. "Telemetri sustu" sessizliğini bir alarm olarak modelleyin.
3. **Syscall anomali tespiti.** Meşru programlar çekirdeğe genellikle `ntdll`
   içinden geçer. Doğrudan/dolaylı syscall'lar, çağrı yığınında (call stack)
   `ntdll` çerçevesi olmadan çekirdeğe iniş gibi anormal desenler bırakır; modern
   EDR'lar stack tabanlı bu anomaliyi arar.
4. **Davranışa odaklan, imzaya değil (IOA > IOC).** Bir teknik userland'de
   gizlense bile, *amacı* (credential erişimi, lateral movement, persistence) bir
   noktada davranışa döner. LSASS'a erişim, şüpheli process ağaçları, beklenmedik
   ağ çıkışları gibi davranışlar bypass'tan bağımsız görünür kalır. Pyramid of
   Pain: TTP'yi değiştirmek saldırgan için en pahalı olandır.
5. **Betik görünürlüğünü katmanla.** AMSI'ye tek başına güvenmeyin: PowerShell
   Script Block Logging ve Module Logging, komut satırı yakalama (Sysmon) ve
   merkezî log ile AMSI bypass'ının etkisini sınırlayın.
6. **Saldırı yüzeyini küçült.** Uygulama allow-listing (WDAC/AppLocker), imzasız
   kod ve bilinen istismar araçlarının yürütülmesini engelleyerek birçok bypass
   zincirinin ilk halkasını kırar.
7. **Purple team ile ölç.** Atomic Red Team gibi araçlarla bu teknikleri kontrollü
   biçimde tetikleyip EDR'ınızın gerçekten tespit edip etmediğini doğrulayın;
   boşluk bulursanız tespit yazın. Amaç yakalamak değil, **savunmayı ölçüp
   iyileştirmektir.**

## Blue Team Özeti

EDR/AV bypass teknikleri, neredeyse tümüyle **kullanıcı modu görünürlüğünü**
hedefler. Bu yüzden dayanıklı savunma üç ilkeye dayanır: (1) çekirdek ve ETW-TI
gibi kullanıcı modundan silinemeyen telemetriye yaslan; (2) tekniğin *susturma
girişimini* bir anomali sinyali olarak yakala (sessizlik = alarm); (3) imza yerine
davranışa odaklan, çünkü saldırganın nihai amacı gizlense de eylemleri iz bırakır.
Bir tekniği "görünmez" kılan şey, çoğu zaman onu görünür kılan başka bir izi
doğurur — savunmacının işi o izi aramaktır.
