# LLMNR/NBT-NS Zehirleme ve NTLM Relay: Ağ İçi Kimlik Avının Anatomisi

## Giriş ve Kapsam

Kurumsal Active Directory ortamlarında bir saldırganın ilk dayanak noktasını (initial foothold) elde ettikten sonra en sık başvurduğu tekniklerin başında **LLMNR/NBT-NS zehirleme** ve bunun doğal devamı olan **NTLM relay** gelir. Bu iki teknik, herhangi bir yazılım açığı (exploit) sömürmeden, sadece protokollerin tasarım gereği güvendiği davranışları kötüye kullanarak çalışır. Yani bir buffer overflow ya da patch'lenmemiş bir CVE aramanıza gerek yoktur; protokolün kendisi zaten "yeterince güvenmeye" programlanmıştır.

Bu makale konuyu üç eksende ele alır: protokollerin neden bu şekilde davrandığı (kök neden), saldırının nasıl kurgulandığı (Responder ve relay araçları), ve en önemlisi bunun karşısında **SMB signing** başta olmak üzere hangi savunma katmanlarının nasıl konumlandırılması gerektiği. Amaç ezberletmek değil, "neden böyle oluyor" sorusuna cevap vermektir.

---

## Bölüm 1: İsim Çözümleme (Name Resolution) ve Kök Neden

### Windows istemcisi bir ismi nasıl çözer?

Bir Windows makinesi `\\dosyasunucu` gibi bir isme erişmeye çalıştığında, o ismi bir IP adresine çevirmesi gerekir. Bu süreç sırayla şu adımları izler:

1. Önce **HOSTS** dosyası ve yerel önbellek (cache) kontrol edilir.
2. Ardından **DNS** sunucusuna sorulur.
3. DNS başarısız olursa, işte kritik nokta burada devreye girer: Windows bir sonraki adımda **LLMNR** (Link-Local Multicast Name Resolution) ve **NBT-NS** (NetBIOS Name Service) mekanizmalarına başvurur.

LLMNR ve NBT-NS'nin DNS'ten temel farkı şudur: DNS, belirli ve otoriter bir sunucuya birebir (unicast) soru sorar. LLMNR ise soruyu **tüm yerel ağ segmentine multicast** olarak, NBT-NS ise **broadcast** olarak yayar. Yani makine ağa haykırır: "Buralarda `dosyasunucu` diye biri var mı? Varsa IP'sini söylesin."

### Kök neden: Kimlik doğrulaması olmayan bir güven modeli

İşte tüm zafiyetin kaynağı burasıdır. Bu yayına **kim cevap verirse**, istemci ona inanır. LLMNR ve NBT-NS protokollerinde cevabı verenin gerçekten o isim olup olmadığını doğrulayan hiçbir mekanizma yoktur. Kimlik doğrulaması (authentication) yok, imza (signature) yok, otorite yok. Protokol tamamen "aynı ağdaki komşularım dürüsttür" varsayımı üzerine kuruludur.

Bu varsayım küçük ev ağlarında (protokolün asıl tasarlandığı ortam) makul olabilir. Ancak yüzlerce, binlerce cihazın bulunduğu, tek bir kullanıcı istasyonunun bile kompromize olmasının yeterli olduğu kurumsal bir ağda bu varsayım tam bir felakettir.

### Zehirleme neden bu kadar kolay tetiklenir?

Önemli bir ayrıntı: Bu isim çözümleme talepleri çoğu zaman kullanıcının bilinçli bir eylemine bile ihtiyaç duymaz. Şu senaryolar sürekli LLMNR/NBT-NS trafiği üretir:

- Kullanıcının yanlış yazdığı bir sunucu adı (`\\fileserv1` yerine `\\fileservr1`) DNS'te bulunamaz ve LLMNR'a düşer.
- Artık var olmayan, ama Group Policy'de ya da eşlenmiş sürücülerde (mapped drive) hâlâ referans verilen eski sunucular.
- Bazı otomatik servis keşif mekanizmaları, yazıcı aramaları, `wpad` (Web Proxy Auto-Discovery) sorguları.

Özellikle **WPAD** meselesi kritiktir: Tarayıcılar otomatik proxy yapılandırması için ağda `wpad` isimli bir host arar. Bu isim DNS'te tanımlı değilse, LLMNR üzerinden aranır ve saldırgan bu ismi zehirleyerek kurbanın tüm web trafiğini kendi üzerinden geçirecek bir proxy dayatabilir. Yani sadece kimlik bilgisi değil, oturum trafiği de risk altındadır.

---

## Bölüm 2: Zehirleme Saldırısı ve Responder

### Responder ne yapar?

Bu saldırının fiili standart aracı **Responder**'dır. Responder ağı dinler ve gelen tüm LLMNR/NBT-NS (ve varsayılan olarak MDNS) sorgularına "Evet, aradığın o makine benim, IP adresim de şu" diye cevap verir. Yani sahte bir isim çözümleme otoritesi hâline gelir.

Responder aynı zamanda kendi bünyesinde sahte servisler barındırır: SMB, HTTP, FTP, MSSQL, LDAP gibi. Kurban makine, Responder'ı gerçek sunucu zannedip ona bağlanmaya çalıştığında, bu sahte servisler kurbandan kimlik doğrulaması ister.

### Neden hemen bir hash düşer?

Windows'un davranışsal bir özelliği burada saldırganın işine yarar: Windows istemcisi bir SMB paylaşımına bağlanmaya çalıştığında, arkada sessizce **oturum açmış kullanıcının kimlik bilgileriyle otomatik olarak kimlik doğrulaması yapmayı dener** (Single Sign-On davranışı). Kullanıcı hiçbir şey yazmadan, sadece sahte sunucuya bağlanma girişimi bile kimlik doğrulama akışını başlatır.

Bu kimlik doğrulaması NTLM üzerinden yapılır ve **challenge-response** yapısındadır:

1. Sunucu (burada Responder) istemciye rastgele bir **challenge** gönderir.
2. İstemci, kullanıcının parola hash'ini kullanarak bu challenge'ı işler ve bir **response** üretir.
3. Bu response, Responder'ın loglarına **Net-NTLMv2 hash** olarak düşer.

Burada dikkat edilmesi gereken kavramsal bir ayrım vardır: Responder'ın yakaladığı şey **Net-NTLMv2** yanıtıdır, doğrudan NTLM parola hash'i (yani `pass-the-hash` ile kullanılabilecek NT hash) değildir. Net-NTLMv2, challenge'a bağlı olduğu için doğrudan yeniden oynatılamaz (pass-the-hash yapılamaz) ama iki yöntemle sömürülür:

- **Çevrimdışı kırma (offline cracking):** Net-NTLMv2, hashcat gibi araçlarla sözlük/kaba kuvvet (brute force) saldırısına açıktır. Parola zayıfsa açık metin parola ortaya çıkar.
- **Relay:** Kırmaya hiç gerek kalmadan, bu kimlik doğrulama akışını canlı olarak başka bir hedefe aktarmak. İşte NTLM relay budur.

### Zehirlemenin sınırları

Dürüst olmak gerekirse, LLMNR/NBT-NS zehirleme **Layer 2** (aynı broadcast/multicast alanı) ile sınırlıdır. Saldırganın kurbanla aynı VLAN/ağ segmentinde olması gerekir; multicast ve broadcast trafiği router'ları geçmez. Bu, savunma açısından önemli bir kısıtlama sunar (segmentasyon).

---

## Bölüm 3: NTLM Relay Saldırısının Mantığı

### Relay neden çalışır? Challenge-response'un zayıf noktası

NTLM kimlik doğrulaması, kim ile konuştuğunu doğrulamak konusunda kör bir protokoldür. Kritik problem şudur: **NTLM, kimlik doğrulamasının hangi hedef için yapıldığını kanıta bağlamaz.** İstemci bir sunucuya kimlik doğrularken ürettiği response, o response'un başka bir sunucuya karşı kullanılmasını engelleyecek bir bağ (channel/target binding) içermez, ya da bu bağ zorunlu tutulmaz.

Saldırgan bu boşluğu şöyle kullanır: Responder yakaladığı kimlik doğrulama akışını **kendisi işlemek yerine**, bir aracı (man-in-the-middle) gibi davranıp gerçek bir hedef sunucuya (örneğin bir dosya sunucusu, bir LDAP/Domain Controller ya da bir MSSQL sunucusu) yönlendirir:

1. Kurban, saldırganın makinesine kimlik doğrulamaya başlar.
2. Saldırgan, kurbandan gelen kimlik doğrulama mesajlarını gerçek hedefe iletir.
3. Hedef sunucu bir challenge üretir; saldırgan bu challenge'ı kurbana geri iletir.
4. Kurban, kendi kimlik bilgileriyle challenge'a yanıt verir; saldırgan bu yanıtı hedefe iletir.
5. Hedef sunucu, kurbanın kimlik bilgilerinin geçerli olduğunu görür ve **saldırgana kurbanın yetkileriyle bir oturum açar.**

Sonuç: Saldırgan parolayı hiç öğrenmeden, kurbanın kimliğiyle hedef sistemde kimlik doğrulanmış olur. Kurban bir Domain Admin ise ve hedef bir sunucu ise, felaket senaryosu tamamdır.

### Relay'in zincirleme kullanımları

NTLM relay'in tehlikesi, tek bir hedefle sınırlı olmamasıdır. Relay edilen kimlik neye yetkiliyse, saldırgan o yetkiyle iş yapabilir. Yaygın hedef ve senaryolar:

- **SMB'ye relay:** Hedef sunucuda dosyalara erişim, komut çalıştırma (kullanıcının o makinede yerel yönetici olması hâlinde). Klasik "relay ile uzaktan kod çalıştırma" senaryosu budur.
- **LDAP/LDAPS'e relay (Domain Controller'a):** Bu çok daha yıkıcıdır. Saldırgan, relay ettiği hesabın yetkisiyle dizinde değişiklik yapabilir. Örneğin **RBCD (Resource-Based Constrained Delegation)** manipülasyonu ya da kurban bilgisayar hesabı üzerinden delegasyon kötüye kullanımı gibi teknikler, makine hesaplarının relay edilmesiyle domain ele geçirmeye kadar gidebilir.
- **AD CS (Sertifika Servisleri) web kayıt uçlarına relay:** Bilgisayar hesaplarının HTTP tabanlı sertifika kayıt uçlarına relay edilerek kalıcı kimlik (sertifika) elde edilmesi. Bu, son yılların en etkili relay saldırı ailelerinden biridir.

### Makine hesaplarını zorla kimlik doğrulatma (coercion)

Relay saldırısını çok daha güçlü kılan bir tamamlayıcı teknik ailesi vardır: **authentication coercion** (kimlik doğrulama zorlaması). Saldırgan pasif bir şekilde LLMNR trafiğinin gelmesini beklemek yerine, belirli RPC arayüzlerini kullanarak bir sunucuyu (özellikle Domain Controller'ı) **kendi kontrolündeki makineye kimlik doğrulamaya zorlayabilir**. Bu teknik ailesinin bilinen örnekleri kamuoyunda çeşitli isimlerle anılır (örneğin printer bug / spooler tabanlı zorlama ve benzeri RPC kötüye kullanımları). Kavramsal olarak önemli olan nokta şudur: Saldırgan artık kullanıcı hatasına bağımlı değildir; yüksek yetkili bir makine hesabının kimliğini talep üzerine tetikleyebilir. Bu, LLMNR zehirlemesi + coercion + relay üçlüsünün neden bu kadar güçlü olduğunu açıklar.

---

## Bölüm 4: Savunma — SMB Signing Merkezli Katmanlı Yaklaşım

Şimdi işin en önemli kısmına, savunmaya geçelim. Savunma tek bir düğmeye basmakla bitmez; her katman farklı bir saldırı adımını hedefler. Mantık şudur: **Ya zehirlemeyi imkânsız kıl, ya kimlik doğrulama akışının başlamasını engelle, ya da relay'i kriptografik olarak boşa çıkar.**

### 4.1 SMB Signing: Relay'in kriptografik panzehiri

**SMB signing**, relay saldırısına karşı en temel ve en etkili savunmadır. Mantığı şudur: SMB signing etkinleştirildiğinde, oturum içindeki her SMB mesajı, kimlik doğrulaması sırasında türetilen bir oturum anahtarıyla imzalanır (message signing). 

Bu neden relay'i durdurur? Çünkü saldırgan ortadaki adam (man-in-the-middle) olarak sadece paketleri iletir; ama oturum anahtarına sahip olmadığı için hedefin beklediği geçerli imzaları **üretemez**. Kurban ile hedef arasında kurulan imza bütünlüğü, aradaki relay makinesini dışarıda bırakır. Saldırgan trafiği iletebilir ama imza doğrulaması başarısız olur ve hedef sunucu oturumu reddeder.

Kritik ayrım — **"enabled" ile "required" arasındaki fark:**

- SMB signing sadece "enabled/desteklenir" (supported) durumundaysa, taraflar anlaşırsa imzalanır; ama saldırgan araya girip imzalamayı devre dışı bırakmaya ("downgrade") ikna edebilir.
- SMB signing **"required" (zorunlu)** durumundaysa, imzasız oturum kesinlikle kabul edilmez. Relay'e karşı gerçek koruma **required** ayarıyla gelir.

Bu yüzden savunmada altın kural şudur: SMB signing özellikle **Domain Controller'lar ve hassas sunucular** için zorunlu (required) hâle getirilmelidir. Not: Modern Windows sürümlerinde SMB signing varsayılan davranışında sıkılaştırmalar yapılmıştır; ancak ortamda eski istemci/sunucuların bulunma ihtimali nedeniyle bu ayara güvenmeden, politika (Group Policy) ile açıkça zorunlu kılmak doğru yaklaşımdır.

**Uyarı — SMB signing'in kapsamı:** SMB signing yalnızca SMB'ye relay'i durdurur. Saldırgan kimliği **LDAP, HTTP (AD CS), MSSQL** gibi başka protokollere relay ediyorsa, SMB signing tek başına yetmez. Bu yüzden protokol bazında ek imzalama/binding koruması gerekir (bkz. 4.4).

### 4.2 LLMNR ve NBT-NS'yi tamamen kapatmak

En kökten savunma, zehirlemenin **hiç mümkün olmamasıdır**. LLMNR ve NBT-NS zaten büyük ölçüde eski (legacy) protokollerdir ve düzgün DNS altyapısı olan kurumsal ağlarda işlevsel olarak gereksizdir.

- **LLMNR**, Group Policy üzerinden merkezî olarak kapatılabilir (Multicast Name Resolution'ı devre dışı bırakan ayar). Bu, tüm domain genelinde tek noktadan uygulanabilir.
- **NBT-NS**'yi kapatmak biraz daha zahmetlidir çünkü ayar geleneksel olarak adaptör bazında (per-interface) tutulur. Bu genellikle DHCP seçenekleri veya bir başlangıç (startup) betiği ile yönetilir.
- **MDNS** de benzer bir zehirleme yüzeyi sunduğu için, gerektiğinde onun da ele alınması unutulmamalıdır.

Bu protokolleri kapatmadan önce **kesinlikle test edilmelidir**: Ağda hâlâ bu protokollere bağımlı eski uygulamalar olabilir. Doğru yol, önce bu trafiği pasif olarak izlemek (kim, neyi arıyor), gereksinimleri anlamak, sonra kademeli kapatmaktır.

### 4.3 Coercion ve NTLM'in kendisini azaltmak

- **NTLM'i devre dışı bırakma / kısıtlama:** Uzun vadeli en sağlam çözüm NTLM'e olan bağımlılığı azaltıp **Kerberos**'a geçmektir. NTLM tamamen kaldırılamasa bile, en azından Domain Controller'lara gelen NTLM kimlik doğrulaması denetim (audit) altına alınıp kademeli olarak kısıtlanabilir. Kerberos, karşılıklı kimlik doğrulama (mutual authentication) ve bilet (ticket) mantığı sayesinde bu tür relay'e yapısal olarak çok daha dirençlidir.
- **Coercion uçlarını sıkılaştırma:** Kimlik doğrulama zorlamasını mümkün kılan gereksiz RPC servislerinin (örneğin ihtiyaç yoksa Print Spooler servisinin Domain Controller'larda) kapatılması, saldırı yüzeyini daraltır.
- **Channel Binding / EPA (Extended Protection for Authentication):** LDAPS ve HTTP gibi TLS taşıyan servislerde, kimlik doğrulamasını TLS kanalına bağlayan (channel binding) korumalar etkinleştirilerek relay kriptografik olarak boşa çıkarılır. LDAP tarafında sunucunun imzalamayı/binding'i zorunlu kılması relay'in DC'ye yönelmesini engeller.

### 4.4 Ağ segmentasyonu ve tespit

- **Segmentasyon:** LLMNR/NBT-NS zehirleme Layer 2 ile sınırlı olduğundan, kullanıcı istasyonlarının aynı büyük düz bir ağda bulunmaması, VLAN'lar arası izolasyon ve gereksiz broadcast alanlarının küçültülmesi saldırının etki alanını daraltır.
- **Tespit (detection):** Savunmacılar kendi ağlarına **honeypot / tuzak** LLMNR sorguları enjekte edip, bu var olmayan isimlere cevap veren bir dinleyici (yani bir Responder) olup olmadığını izleyebilir. Var olmayan bir hosta gelen "cevap", ağda bir zehirleyici olduğunun güçlü bir işaretidir. Ayrıca birden çok isme aynı MAC/IP'den gelen olağan dışı çok sayıda LLMNR cevabı da tespit sinyalidir.

---

## Bölüm 5: Yaygın Hatalar

Sahada tekrar tekrar görülen ve savunmayı etkisiz kılan hatalar şunlardır:

- **SMB signing'i "enabled" bırakıp "required" yapmamak.** En sık yapılan hata budur. İmzalama desteklenir ama zorunlu değilse, downgrade ile saldırı yine mümkündür. Koruma zorunlulukla gelir.
- **Sadece SMB signing'e güvenip diğer relay hedeflerini unutmak.** LDAP, AD CS (HTTP) ve MSSQL relay yolları açık bırakılırsa saldırgan basitçe hedef protokolü değiştirir. Savunma protokol bazında düşünülmelidir.
- **LLMNR'i kapatıp NBT-NS'yi açık unutmak (ya da tersi).** İkisi ayrı mekanizmalardır; birini kapatmak diğerini kapatmaz. Saldırgan açık kalan protokolü kullanır.
- **Test etmeden toplu kapatma yapıp eski uygulamaları kırmak.** Bu, savunma girişiminin geri alınmasına ve zafiyetin yeniden açılmasına yol açar. Önce izle, sonra kademeli uygula.
- **Domain Controller'larda gereksiz servisleri (coercion uçları) açık bırakmak.** Bir DC'nin kimliğinin relay edilmesi domain ele geçirmeye giden en kısa yollardan biridir; DC'lerin saldırı yüzeyi özellikle daraltılmalıdır.
- **Yüksek yetkili hesapları rastgele istasyonlara oturum açtırmak.** Bir Domain Admin, kompromize bir kullanıcı makinesinde interaktif oturum açtığında ya da o makineye kimlik doğruladığında, o kimlik doğrulama akışı relay edilebilir. Yönetici hesaplarının kullanım hijyeni (tiered admin modeli) kritiktir.
- **NTLM kullanımını hiç denetlememek.** Neyin NTLM kullandığını bilmeden NTLM'i kısıtlamaya çalışmak servisleri kırar; bu yüzden önce audit, sonra kısıtlama yapılmalıdır.

---

## Bölüm 6: En İyi Pratikler (Özet Kontrol Listesi)

Bir savunmacının önceliklendireceği eylemler, etkiden yüksekten düşüğe doğru:

1. **DC'ler ve hassas sunucular başta olmak üzere SMB signing'i "required" yapın.** Relay'e karşı en yüksek getirili tek adım.
2. **LLMNR ve NBT-NS'yi (ve gerekiyorsa MDNS'i) merkezî politika ile kapatın.** Zehirlemenin kaynağını kurutur. Öncesinde trafiği izleyerek bağımlılıkları tespit edin.
3. **LDAP/LDAPS imzalama ve channel binding'i zorunlu kılın; AD CS web kayıt uçlarında EPA'yı etkinleştirin.** SMB dışı relay yollarını kapatır.
4. **NTLM kullanımını denetime alın ve kademeli olarak kısıtlayıp Kerberos'a yönelin.** Yapısal, uzun vadeli çözüm.
5. **Coercion'a açık gereksiz RPC servislerini, özellikle DC'lerde, kapatın.** Talep üzerine kimlik tetiklemesini zorlaştırır.
6. **Tiered admin modeli uygulayın; yüksek yetkili kimlikleri düşük güvenli makinelerden uzak tutun.** Relay edilecek değerli kimliği ortamdan çekin.
7. **Ağ segmentasyonu ile Layer 2 zehirleme alanını daraltın.**
8. **LLMNR honeypot ve anomali tespiti ile ağda aktif bir zehirleyici olup olmadığını sürekli izleyin.**

---

## Sonuç

LLMNR/NBT-NS zehirleme ve NTLM relay, "sistemde bir açık aramak" yerine "protokolün güven varsayımlarını kötüye kullanmak" felsefesinin en temiz örneğidir. Saldırının gücü basitliğinden gelir: kimliği doğrulanmamış bir isim çözümleme yayınına cevap vermek ve kimlik doğrulama akışını başka bir hedefe aktarmak. Savunmanın gücü ise katmanlı olmasından gelir. Tek başına hiçbir ayar sihirli değildir; ama **SMB signing'i zorunlu kılmak, eski multicast/broadcast isim çözümleme protokollerini kapatmak, protokol bazında imzalama/binding uygulamak ve NTLM bağımlılığını azaltmak** bir araya geldiğinde, saldırgan için elde kalan yol dramatik biçimde daralır. İyi savunma, saldırganın her adımını ayrı ayrı ekonomik olarak imkânsız kılmaktır.
