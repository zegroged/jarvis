# SNMP Güvenliği: Community String Brute-force, SNMP Enumeration ve SNMPv3

## Giriş ve Neden Önemli

**SNMP (Simple Network Management Protocol)**, ağ cihazlarını (router, switch, firewall, yazıcı, sunucu, IP kamera, kesintisiz güç kaynağı vb.) uzaktan izlemek ve yönetmek için kullanılan çok yaygın bir protokoldür. Bir NMS (Network Management System) yazılımı bu protokol üzerinden cihazın CPU kullanımını, arayüz trafiğini, sıcaklığını, çalışma süresini ve daha yüzlerce metriği okuyabilir; bazı durumlarda konfigürasyon da yazabilir.

SNMP'nin güvenlik açısından kritik olmasının nedeni, kolaylık uğruna yıllarca **kimlik doğrulaması zayıf veya hiç şifrelemesiz** çalışmış olmasıdır. Kurumsal ağların büyük çoğunluğunda hâlâ eski sürümler, varsayılan ayarlarla açık durur. Bir saldırgan için SNMP; ağ topolojisini, cihaz envanterini, kullanıcı listelerini ve hatta konfigürasyonu sızdıran zengin bir bilgi kaynağıdır. Ayrıca UDP tabanlı olması nedeniyle **DDoS amplifikasyon** saldırılarında da kötüye kullanılabilir.

Bu makale mekanizmayı anlamayı, riski görmeyi ve en önemlisi **tespit ile savunma** kurmayı amaçlar. Amaç saldırı yürütmek değil, saldırının nasıl çalıştığını bilerek onu durdurabilmektir.

## SNMP Nasıl Çalışır: Temel Kavramlar

### Mimari Bileşenler

- **Agent (Ajan):** İzlenen cihazın üzerinde çalışan yazılım. UDP **161** portunu dinler ve sorulara cevap verir.
- **Manager / NMS:** Ajanlara sorgu gönderen merkezi izleme sistemi.
- **Trap / Inform:** Ajanın, bir olay gerçekleştiğinde (arayüz düştü, cihaz yeniden başladı) manager'a kendiliğinden bildirim göndermesidir. Trap'ler tipik olarak UDP **162** portuna gider.

### MIB ve OID

SNMP verisi ağaç yapısında düzenlenmiştir. **MIB (Management Information Base)**, bu ağacın "sözlüğü"dür; hangi verinin nerede durduğunu tanımlar. Ağaçtaki her düğümün benzersiz bir numarası vardır: **OID (Object Identifier)**. Örneğin sistem tanımını taşıyan `sysDescr` nesnesi `1.3.6.1.2.1.1.1.0` gibi bir OID'ye karşılık gelir.

Bu yapı, saldırgan açısından anahtar öneme sahiptir: OID'ler standarttır ve tahmin edilebilir. Yani community string ele geçirilirse, saldırgan **hangi soruyu soracağını zaten bilir**.

### İşlemler

- **GET / GET-NEXT / GET-BULK:** Değer okuma. GET-NEXT ve GET-BULK, ağacı sırayla gezerek (walk) toplu veri çekmeyi sağlar.
- **SET:** Değer yazma (konfigürasyon değiştirme).
- **WALK:** Bir alt ağacın tamamını gezmek için art arda GET-NEXT çağrılarının mantıksal toplamı; tek bir protokol komutu değil, izleme araçlarının sunduğu bir işlemdir.

## SNMP Sürümleri ve Güvenlik Modeli

Sürüm farkını anlamak, SNMP güvenliğinin özüdür.

### SNMPv1 ve SNMPv2c

Bu iki sürümde kimlik doğrulaması **community string** adı verilen düz metin bir "paroladan" ibarettir. Sorgu gönderen taraf doğru community string'i biliyorsa yetkili sayılır. İki temel community türü vardır:

- **Read-only (RO) community:** Genellikle varsayılan olarak `public`. Okuma yetkisi verir.
- **Read-write (RW) community:** Genellikle varsayılan olarak `private`. Yazma yetkisi de verir; çok daha tehlikelidir.

Kritik zayıflıklar:

1. **Şifreleme yok.** Community string ağ üzerinde düz metin gider. Aynı segmentte trafiği dinleyebilen biri onu okuyabilir.
2. **Bütünlük koruması yok.** Paket üzerinde oynanabilir.
3. **Zayıf kimlik doğrulama.** String tahmin edilebilir veya deneme-yanılma ile bulunabilir.

"v2c"deki "c" zaten "community-based" demektir; v2c, v2'nin güvenlik iyileştirmelerini bırakıp v1'in community modeliyle devam eden sürümdür.

### SNMPv3

SNMPv3, güvenliği protokolün merkezine koyar. Community string yerine **USM (User-based Security Model)** kullanır ve üç güvenlik seviyesi sunar:

- **noAuthNoPriv:** Kimlik doğrulama yok, şifreleme yok. Sadece kullanıcı adı. Neredeyse v2c kadar zayıf.
- **authNoPriv:** Kimlik doğrulama var (mesaj bir parola/anahtardan türetilen hash ile doğrulanır), şifreleme yok. Veri hâlâ düz metin görünür ama sahte mesaj enjekte etmek zorlaşır.
- **authPriv:** Hem kimlik doğrulama hem şifreleme var. Önerilen ve gerçekten güvenli olan seviye budur.

SNMPv3'te iki ayrı parola/anahtar mantığı vardır: **authentication** (mesajın doğruluğu için) ve **privacy** (mesajın gizliliği/şifrelemesi için). Modern dağıtımlarda authentication için SHA ailesi, privacy için AES tercih edilmelidir. Eski **MD5** (auth) ve **DES** (priv) seçenekleri zayıf kabul edilir ve mümkünse kullanılmamalıdır.

Ek olarak SNMPv3, **engine ID** ve zaman/sayaç pencereleri sayesinde **replay (yeniden oynatma)** saldırılarına karşı da koruma sağlar.

## Saldırı Yüzeyi 1: Community String Brute-force

### Çalışma Mantığı

v1/v2c'de yetki tek bir string'e bağlı olduğundan, saldırgan bu string'i öğrenmeye çalışır. İki temel yol vardır:

1. **Varsayılan ve zayıf string denemesi:** `public`, `private`, `manager`, `cisco`, kurum adı, cihaz modeli gibi olası değerler bir sözlükten (wordlist) sırayla denenir. Pek çok cihaz yıllardır `public`/`private` ile açık kaldığı için bu yöntem şaşırtıcı derecede etkilidir.
2. **Trafik dinleme:** Aynı ağ segmentindeyse, saldırgan meşru NMS trafiğini pasif dinleyerek community string'i düz metin olarak yakalayabilir. Bu, brute-force'a hiç gerek bırakmaz.

Brute-force UDP üzerinden yapıldığından ve hız sınırı çoğu cihazda zayıf olduğundan, saniyede yüzlerce deneme mümkün olabilir. Kilitlenme (account lockout) mekanizması genellikle yoktur; bu da SNMPv1/v2c'yi brute-force'a doğal olarak açık kılar.

### Basitleştirilmiş Örnek Senaryo

Bir saldırgan bir switch'in `10.0.0.1` adresinde SNMP çalıştığını fark eder. Elindeki sözlükle RO community'yi dener; `public` tutar. Ardından RW community'yi araştırır; kurumda `private` bırakılmışsa artık cihaza **yazma** yetkisi de vardır. Bu noktada iş, salt bilgi sızıntısından cihaz konfigürasyonunu değiştirmeye kadar tırmanabilir.

## Saldırı Yüzeyi 2: SNMP Enumeration (Bilgi Sızması)

### Neden Bu Kadar Tehlikeli

Community string ele geçtiğinde asıl değer, ondan sonra **ne kadar çok bilginin okunabildiği**dir. Standart MIB'ler üzerinden bir saldırgan tipik olarak şunlara ulaşabilir:

- **Sistem bilgisi:** İşletim sistemi, donanım modeli, sürüm ve yama seviyesi (`sysDescr`). Bu, bilinen zafiyetleri eşlemek için altın değerindedir.
- **Ağ arayüzleri ve IP'ler:** Cihazın tüm arayüzleri, IP adresleri, alt ağ maskeleri. Ağ topolojisi çıkarılabilir.
- **ARP / routing tabloları:** Komşu cihazlar ve ağın nasıl bağlandığı ortaya çıkar; yanal hareket (lateral movement) için harita oluşur.
- **Çalışan process ve yüklü yazılım listesi:** Özellikle Windows host'larda ek MIB'lerle process ve servis adları görülebilir.
- **Kullanıcı hesapları:** Bazı sistemlerde yerel kullanıcı adları sızabilir.
- **TCP/UDP bağlantı tabloları:** Açık portlar ve mevcut bağlantılar.

Bir "SNMP walk", ajanın izin verdiği tüm ağacı gezerek bu bilgilerin toplu dökümünü çıkarır. Yani tek bir zayıf community, ağın önemli bir kısmının haritasını sunabilir. Bu, keşif (reconnaissance) aşamasını saldırgan için son derece verimli hâle getirir.

### RW Community ile Yükselme

Eğer ele geçirilen community RW ise, SET işlemleriyle konfigürasyon değiştirilebilir. Klasik ve tarihsel olarak bilinen bir teknik, bazı cihazlarda SNMP üzerinden cihaz konfigürasyonunun bir TFTP/FTP sunucusuna kopyalatılmasıdır. Bu, cihaz parolaları dâhil tüm konfigürasyonun dışarı sızması anlamına gelebilir. Bu tür ayrıntıya girmeden şu ilkeyi belirtmek yeterlidir: **RW SNMP, ele geçirildiğinde neredeyse cihaz üzerinde yönetimsel kontrol demektir.**

## Saldırı Yüzeyi 3: SNMP Tabanlı DDoS Amplifikasyonu

### Amplifikasyon Mantığı

SNMP, UDP üzerinde çalışır. UDP bağlantısız olduğu için kaynak IP adresi **sahtelenebilir (spoofing)**. Amplifikasyon saldırısının temel fikri şudur:

1. Saldırgan, kaynak IP adresini **kurbanın adresi** olarak sahteler.
2. İnternete açık, yanıt veren bir SNMP ajanına küçük bir sorgu (özellikle çok veri döndüren `GET-BULK` türü) gönderir.
3. Ajan, büyük bir cevabı **kurbana** gönderir; çünkü paketteki kaynak adres odur.

Küçük istek → büyük yanıt oranına **amplifikasyon faktörü** denir. GET-BULK bir istekle ağacın geniş bir bölümünü döndürebildiği için bu oran yüksek olabilir. Binlerce açık ajan aynı anda kullanıldığında kurbana yüksek hacimli trafik akar; buna **reflection/amplification DDoS** denir.

Buradaki kök neden, **internete açık bırakılmış SNMP ajanları** ve **kaynak IP doğrulaması yapmayan ağlardır**. Saldırganın kendi bant genişliği küçük olsa da etkiyi katlar.

## Tespit (Detection)

Savunma yalnızca engellemek değil, saldırıyı görebilmektir.

- **Community brute-force tespiti:** UDP 161'e giden yoğun, kısa aralıklı sorgular ve çok sayıda **hatalı/başarısız community** denemesi güçlü bir işarettir. Cihaz logları veya NetFlow/IPFIX üzerinde, tek bir kaynaktan ajana giden anormal sorgu hacmi izlenmelidir.
- **Beklenmedik kaynaklar:** SNMP sorgusu yalnızca bilinen NMS sunucularından gelmelidir. Bunun dışında bir IP'den gelen SNMP trafiği alarm konusudur. IDS/IPS (örneğin imza tabanlı sistemler) SNMP keşif ve walk desenlerini yakalayabilir.
- **Walk deseni:** Kısa sürede çok sayıda ardışık OID sorgusu (GET-NEXT/GET-BULK yoğunluğu) tipik bir enumeration/walk imzasıdır.
- **Amplifikasyon tespiti:** Kendi ağınızdaki bir ajandan **dışarıya** doğru, isteği olmadan büyük SNMP yanıtları çıkıyorsa, ajanınız amplifikasyona alet ediliyor olabilir. Giden 161 kaynaklı büyük UDP yanıt hacmi izlenmelidir.
- **Log ve SIEM korelasyonu:** SNMP olaylarını merkezi bir SIEM'e taşıyıp NMS envanteriyle karşılaştırmak, meşru ile şüpheli trafiği ayırmanın en sağlam yoludur.

## Savunma (Defense)

Aşağıdaki önlemler önem sırasına yakın verilmiştir.

### 1. Mümkünse SNMPv3 kullan, authPriv seviyesinde

En temel adım budur. Yeni dağıtımlarda v1/v2c yerine **SNMPv3 authPriv** tercih edilmeli; authentication için SHA, privacy için AES kullanılmalıdır. Bu, hem düz metin community sorununu hem de trafik dinleme ve replay saldırılarını büyük ölçüde ortadan kaldırır.

### 2. SNMP gerekmiyorsa tamamen kapat

En güvenli ajan, çalışmayan ajandır. İzlemeye ihtiyaç duyulmayan cihazlarda SNMP servisi kapatılmalıdır. Özellikle yazıcılar, IoT ve eski cihazlarda SNMP çoğu zaman gereksiz yere açık kalır.

### 3. Varsayılan community string'leri asla bırakma

v2c kullanılmak zorundaysa `public`/`private` kesinlikle değiştirilmelidir. Tahmin edilmesi zor, uzun ve rastgele string'ler seçilmeli; RW community mümkünse hiç kullanılmamalı, kullanılıyorsa RO'dan tamamen farklı olmalıdır.

### 4. Kaynak IP kısıtlaması (ACL)

Ajanlar yalnızca **bilinen NMS sunucularının** IP adreslerinden gelen sorgulara cevap verecek şekilde ayarlanmalıdır. Çoğu cihazda SNMP için bir erişim listesi (ACL) tanımlanabilir. Bu tek başına brute-force ve enumeration riskini ciddi biçimde düşürür.

### 5. Yalnızca okuma (read-only) ile sınırla

İzleme için genellikle salt okuma yeterlidir. RW yetkisi mümkünse hiç verilmemeli; verilecekse çok dar kapsamla ve ayrı güçlü kimlik doğrulamayla verilmelidir. Mümkünse **görünüm (view) sınırlaması** ile ajanın sadece gerekli OID alt ağacını göstermesi sağlanmalıdır; bu, enumeration ile sızacak bilgiyi azaltır.

### 6. Perimeter'da SNMP portlarını filtrele

UDP 161 ve 162, internet sınırında (firewall) dışarıya **kesinlikle kapalı** olmalıdır. İnternete açık SNMP, amplifikasyon saldırılarının hammaddesidir. İç ağda bile SNMP trafiği yönetim segmentine (management VLAN) hapsedilmelidir.

### 7. Anti-spoofing (amplifikasyona karşı)

Amplifikasyonun kökü sahte kaynak IP'dir. Ağ operatörleri, çıkış noktalarında kaynak adres doğrulaması (yaygın adıyla **BCP 38 / ingress filtering**) uygulayarak sahtelenmiş paketlerin ağdan çıkmasını engellemelidir. Bu, sizin ağınızın başka bir kurbana saldırı aracı olmasını önler.

### 8. Hız sınırlama ve izleme

Cihaz destekliyorsa SNMP sorgularına hız sınırı (rate limit) uygulamak brute-force ve amplifikasyonu zorlaştırır. Ayrıca SNMP trafiğini sürekli izlemek, sessiz sızıntıları görünür kılar.

## Yaygın Hatalar

- **"SNMP sadece okuma, zararsız" yanılgısı.** Salt okuma bile ağ topolojisini, cihaz sürümlerini ve zafiyet haritasını sızdırır. Enumeration, çoğu saldırının keşif temelidir.
- **Community'yi değiştirip şifreleme sanmak.** Community string değiştirmek onu **gizlemez**; v2c'de string hâlâ düz metin gider ve dinlenebilir. Gerçek gizlilik yalnızca SNMPv3 authPriv ile gelir.
- **SNMPv3'ü noAuthNoPriv ile kurmak.** "v3 kullanıyoruz" demek yeterli değildir; noAuthNoPriv seviyesinde v3 neredeyse v2c kadar zayıftır. Seviye **authPriv** olmalıdır.
- **Zayıf v3 algoritmaları.** authentication'da MD5, privacy'de DES bırakmak modern ortamda yetersizdir; SHA + AES tercih edilmelidir.
- **Kaynak kısıtlaması unutmak.** Güçlü community/parola konsa bile, dünyaya açık bir ajan brute-force ve amplifikasyona hedeftir. ACL ve firewall filtresi vazgeçilmezdir.
- **RW community'yi RO ile aynı yapmak.** Aynı string kullanmak, okuma yetkisi sızdığında yazma yetkisini de teslim etmek demektir.
- **Envanter eksikliği.** Hangi cihazlarda SNMP açık, bilmemek en büyük hatadır. Görünmeyen ajan korunamaz; düzenli tarama ile açık SNMP servisleri envanterlenmelidir.
- **Trap portunu (162) ihmal etmek.** Savunma çoğu zaman 161'e odaklanır; 162'nin de perimeter'da kapalı ve doğru yapılandırılmış olması gerekir.

## Özet

SNMP, ağ yönetiminde vazgeçilmez ama tarihsel olarak güvenlik açısından ihmal edilmiş bir protokoldür. v1/v2c'nin düz metin **community string** modeli, hem brute-force hem trafik dinleme ile kolayca aşılabilir; ele geçen bir community, **MIB enumeration** yoluyla ağ topolojisini ve cihaz bilgilerini geniş çapta sızdırır; UDP tabanlı ve internete açık ajanlar ise **amplifikasyon DDoS**'un aracı olur. Doğru cevap nettir: mümkün olan her yerde **SNMPv3 authPriv (SHA + AES)** kullanmak, gereksiz ajanları kapatmak, varsayılan string'leri değiştirmek, **kaynak IP ACL'leri** ile erişimi kısıtlamak, SNMP'yi yönetim segmentine hapsetmek ve perimeter'da 161/162 portlarını dışarıya kapatmak. Tespit tarafında ise anormal sorgu hacmini, bilinmeyen kaynakları ve giden büyük yanıtları izlemek, saldırıyı sessizce çalışmaya bırakmamanın anahtarıdır.
