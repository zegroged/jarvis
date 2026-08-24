# Detection Engineering Yaşam Döngüsü ve Kural Mühendisliği

## Giriş: Neden Bu Disiplin Ayrı Olarak Var Olmalı

Bir kurumda "Sigma kuralları nasıl yazılır" veya "MITRE ATT&CK matrisi nedir" sorularının cevabı bilinse bile, ortaya çıkan tespit yeteneği çoğu zaman dağınık, tutarsız ve kısa ömürlü olur. Sebep şudur: kural yazmak bir *zanaat*tir, ama üretim hattı kurmak bir *mühendislik disiplini*dir. Tek bir Sigma kuralı yazmakla, yüzlerce kuralı sürüm kontrolü altında tutan, hangi ATT&CK tekniklerinin kapsandığını ölçen, false-positive oranını izleyen, kuralı üretime sokmadan önce test eden ve zamanla bozulmasını (rule decay) önleyen bir sistem kurmak arasında, tek bir evi inşa etmekle bir şehir imar planı yapmak kadar fark vardır.

Detection Engineering (Tespit Mühendisliği), bir SOC'un (Security Operations Center) reaktif alarm tüketicisinden, kendi tespit envanterini bilinçli olarak inşa eden, ölçen ve iyileştiren bir mühendislik fonksiyonuna dönüşmesidir. Bu makale, bu disiplinin yaşam döngüsünü — gereksinim yazımından emekliye ayırmaya kadar — kavramsal ve uygulamalı olarak ele alır.

## Kök Neden: Tespit Neden Kendiliğinden Kötüleşir

Bir tespit kuralı yazıldığı anda en iyi halindedir; sonrasında yalnızca bozulabilir. Bunun birkaç yapısal nedeni vardır:

**1. Ortam kayması (environment drift).** Kural yazıldığında hedef ortamın bir anlık görüntüsüne (snapshot) göre kalibre edilir. Ancak işletim sistemleri güncellenir, yeni yazılımlar kurulur, kullanıcı davranışları değişir, yeni bir meşru araç (ör. yeni bir IT yönetim aracı) devreye girer. Kuralın varsaydığı "normal" ile gerçek "normal" arasındaki fark büyür ve false-positive (yanlış pozitif) oranı zamanla artar.

**2. Saldırgan adaptasyonu.** Bir teknik popüler bir tespit kuralına yakalanmaya başladığında, saldırganlar (özellikle hedefli/APT tipte) tekniği değiştirir, gizler veya farklı bir LOLBin/araç kullanarak aynı hedefe ulaşır. Kural statik kalırsa, artık sadece "beceriksiz" saldırganları yakalayan bir kural haline gelir — ki bu düşük değerli bir tespit sinyalidir.

**3. Veri kaynağı değişkenliği.** Log formatı bir ajan güncellemesiyle değişebilir, bir alan adı yeniden adlandırılabilir, loglama seviyesi bir yapılandırma değişikliğiyle düşürülebilir. Kural mantığı aynı kalsa bile, beslediği veri artık kuralın beklediği şekilde gelmiyorsa kural sessizce kör olur (silent failure) — en tehlikeli bozulma türü, çünkü hiçbir alarm da vermez, hata da vermez.

**4. Kurumsal hafıza kaybı.** "Bu kuralı neden yazdık, hangi tehdide karşı, hangi varsayımlarla?" sorusunun cevabı kuralın kendisinde (bir sorgu ifadesinde) saklı değilse, yazan kişi ayrıldığında bu bilgi kaybolur. Kural bir "kara kutu" haline gelir; kimse dokunmaya cesaret edemez, kimse de güvenmez.

Bu dört kök neden, Detection Engineering'in neden tek seferlik bir yazım eylemi değil, sürekli bir **yaşam döngüsü (lifecycle)** yönetimi olması gerektiğini açıklar.

## Detection-as-Code Felsefesi

Detection-as-Code, yazılım mühendisliğinin olgun pratiklerini (sürüm kontrolü/version control, code review, CI/CD, otomatik test) tespit kurallarının üretimine uygulama fikridir. Kök mantık şudur: eğer bir kural, üretim ortamında çalışan ve güvenliği doğrudan etkileyen bir "kod" ise, ona bir yazılım parçası gibi davranılmalıdır — rastgele bir SIEM arayüzünde elle düzenlenen, kimin ne zaman değiştirdiği belirsiz bir metin parçası gibi değil.

### Pratikte ne anlama gelir

- **Sürüm kontrolü (Git):** Her kural bir dosya olarak (genellikle Sigma YAML formatında) bir repoda tutulur. Her değişiklik bir commit'tir; kimin, ne zaman, neden değiştirdiği `git blame` ve commit mesajlarıyla izlenebilir.
- **Code review / Pull Request süreci:** Yeni bir kural veya değişiklik, üretime girmeden önce en az bir başka mühendis tarafından incelenir. İncelemede bakılan şeyler: mantık doğru mu, ATT&CK eşlemesi doğru mu, hangi veri kaynağına bağımlı, test edildi mi.
- **CI/CD pipeline:** Kural repoya push edildiğinde otomatik olarak sözdizimi doğrulaması (syntax validation), ATT&CK etiket doğrulaması, birim testi (unit test — "bu log örneği tetiklemeli", "şu log örneği tetiklememeli") ve dönüşüm (ör. Sigma'dan SIEM'e özel sorgu diline `sigma-cli`/`pySigma` ile derleme) otomatik çalışır.
- **Ortam ayrımı (staging/production):** Yeni kural önce "sessiz mod"da (yalnızca loglar, alarm üretmez) veya bir test/staging tespit ortamında çalıştırılır, gerçek trafik üzerinde davranışı gözlemlenir, sonra üretime terfi eder.

### Neden önemli — savunma açısından fayda

Bu yaklaşımın savunmacıya kazandırdığı somut şeyler:
- **Geri alınabilirlik:** Kötü bir kural üretimde gürültü yaratırsa, bir önceki sürüme saniyeler içinde geri dönülebilir (`git revert`).
- **Denetlenebilirlik (auditability):** Bir uyum denetimi veya olay sonrası incelemede "bu tarihte hangi kurallar aktifti" sorusu kesin olarak cevaplanabilir.
- **Ölçeklenebilirlik:** Elle SIEM arayüzünden yönetilen 500 kural pratikte yönetilemez; kod olarak tutulan 500 kural test edilebilir, aranabilir, toplu güncellenebilir (ör. bir alan adı değiştiğinde tek bir `sed`/script ile tüm kurallarda güncelleme).

## Yaşam Döngüsünün Aşamaları

Detection Engineering yaşam döngüsü genellikle şu aşamalardan oluşur: **Gereksinim → Veri Kaynağı Değerlendirmesi → Taslak (Draft) → Test → Tuning → Dağıtım (Deploy) → İzleme → Emeklilik (Retirement)**. Her aşamayı kök mantığıyla inceleyelim.

### 1. Tespit Gereksinimi Yazma (Detection Requirement)

Bir kural yazmadan önce cevaplanması gereken soru "ne tespit ediyoruz ve neden?" sorusudur. İyi bir tespit gereksinimi şunları içerir:

- **Hedef davranış:** Hangi spesifik teknik veya davranış tespit edilecek (ör. "LSASS bellek dökümü" — kavramsal olarak: kimlik doğrulama materyallerinin bellekten çıkarılması).
- **Tehdit bağlamı:** Bu davranış hangi saldırı senaryosunda ortaya çıkar, hangi tehdit aktörü profilleriyle ilişkilendirilir (threat intelligence'tan beslenir).
- **Beklenen kaynak:** Bu davranış hangi log/telemetri kaynağında görünür olur (EDR süreç oluşturma olayı, Windows Security Event Log, ağ akışı vb.).
- **Başarı kriteri:** Kural neyi "yakaladı" sayılacak, hangi false-positive'ler kabul edilebilir kabul ediliyor.

Bu adımın atlanması, doğrudan "önce yaz, sonra ne olduğunu anlamaya çalış" tarzı reaktif mühendisliğe yol açar — ki bu, bir sonraki bölümde anlatılan kapsama boşluklarının asıl kaynağıdır.

### 2. Veri Kaynağı / Log Kaynağı Yeterliliği Değerlendirmesi (Data Source Coverage Assessment)

Bu, sıkça atlanan ama en kritik adımdır. Bir tespit fikri ne kadar zekice olursa olsun, **gerekli veri toplanmıyorsa kural sadece kağıt üzerinde var olur.**

Kök mantık: ATT&CK çerçevesi her teknik için "Data Sources" (veri kaynakları) alanını tanımlar (ör. Process Creation, Command Execution, File Creation, Network Traffic Flow). Bir kurum bu veri kaynaklarını toplayıp toplamadığını, hangi kapsamda (hangi host grubu, hangi loglama seviyesi, hangi saklama süresiyle) topladığını bilmeden "ATT&CK'i kapsıyoruz" demek yanıltıcıdır.

Pratik değerlendirme soruları:
- Bu veri kaynağı **hiç toplanıyor mu**? (ör. PowerShell Script Block Logging etkin mi, Sysmon kurulu mu, EDR o host grubunda dağıtılmış mı?)
- Toplanıyorsa **gerekli alan/detay seviyesinde mi**? (ör. süreç oluşturma logu komut satırı argümanlarını içeriyor mu, yoksa sadece süreç adını mı?)
- **Hangi kapsamda** toplanıyor? (tüm sunucular mı, yoksa yalnızca belirli bir segment mi — kör noktalar/blind spot'lar var mı?)
- **Ne kadar süre saklanıyor** ve **ne kadar gecikmeyle (latency) SIEM'e ulaşıyor**? (gerçek zamanlı tespit mi, retrospektif avlanma mı hedefleniyor?)

Bu değerlendirme genellikle bir **Data Source Coverage Matrix** (Veri Kaynağı Kapsama Matrisi) olarak tutulur: satırlarda log kaynakları, sütunlarda host grupları/ortamlar, hücrelerde kapsama durumu (tam/kısmi/yok). Bu matris, ATT&CK kapsama haritasının **önkoşulu**dur — çünkü bir teknik için kural yazılabilir olması, o teknik için gerekli veri kaynağının erişilebilir olmasına bağlıdır.

**Savunma çıkarımı:** Kurumlar sıklıkla "kaç ATT&CK tekniğini kapsıyoruz" sorusuna kural sayısıyla cevap verir, ama asıl soru "hangi teknikler için yeterli **veri** toplanabiliyor" olmalıdır. Veri kaynağı olmayan bir teknik için yazılan kural, test edilemeyen ve asla tetiklenmeyecek ölü koddur.

### 3. ATT&CK Kapsama Haritalama (Coverage Mapping)

Veri kaynağı değerlendirmesi tamamlandıktan sonra, mevcut ve planlanan kurallar ATT&CK matrisi üzerine haritalanır. Bunun amacı tek tek kural listesi değil, **stratejik görünürlük** sağlamaktır: hangi taktik/teknik alanlarında güçlüyüz, hangilerinde kör noktamız var.

Kavramsal olarak kapsama haritalama üç boyutta değerlendirilmelidir:

- **Genişlik (breadth):** Kaç farklı teknik/alt-teknik için herhangi bir tespit var.
- **Derinlik (depth):** Bir teknik için tek bir dar kural mı var, yoksa tekniğin farklı uygulama varyantlarını (procedure'lar) kapsayan birden fazla kural mı var? (Bir teknik "kapsanıyor" görünse de, saldırganın o tekniği uygulamanın 10 farklı yolundan sadece 1'i yakalanıyor olabilir.)
- **Güven seviyesi (confidence):** Kural gerçekten test edildi mi, canlı ortamda doğrulandı mı, yoksa teorik olarak mı yazıldı (henüz kanıtlanmamış).

Yaygın araçsal yaklaşım: MITRE ATT&CK Navigator gibi bir ısı haritası (heatmap) katmanı oluşturup, her hücreyi kapsama olgunluğuna göre renklendirmek (yok / veri var kural yok / kural var test edilmemiş / kural var test edilmiş ve tuning yapılmış). Bu, yönetime ve ekibe "bir sonraki yatırımı nereye yapmalıyız" sorusuna görsel bir cevap verir.

**Kritik uyarı:** Kapsama haritalama bir "tik atma" (checkbox) egzersizine dönüşme riski taşır. 200 teknik için 200 zayıf kural yazıp "kapsıyoruz" demek, kapsamın kalitesini yok sayar. Olgun programlar, kuruma özgü **tehdit modeline** göre önceliklendirme yapar (ör. bir finans kurumu için kimlik bilgisi hırsızlığı ve yanal hareket teknikleri, bir üretim tesisi için OT/ICS'ye köprü teknikleri daha yüksek öncelikli olabilir) — matrisin tamamını eşit ağırlıkta doldurmaya çalışmak kaynak israfıdır.

### 4. Taslak (Draft) ve Kural Yazımı

Gereksinim ve veri kaynağı netleştikten sonra kural yazımı başlar (Sigma formatı gibi araç-bağımsız bir dilde yazmak, birden fazla SIEM'e taşınabilirlik sağladığı için tercih edilir). Bu aşamada kök mantık: kural, **davranışı** modellemeli, tek bir **artefaktı** değil.

- **Kırılgan (brittle) kural örneği (kavramsal):** Belirli bir dosya adını veya sabit bir komut satırını arayan kural — saldırgan dosya adını değiştirdiği anda kural işe yaramaz hale gelir.
- **Dayanıklı (robust) kural örneği (kavramsal):** Bir davranış zincirini modelleyen kural — ör. "ofis doküman süreci → script yorumlayıcı çocuk süreç → ağ bağlantısı" gibi bir dizilim. Bu tür davranış tabanlı kurallar, saldırganın belirli bir aracı değiştirmesine karşı daha dayanıklıdır çünkü teknik seviyesinde çalışır, artefakt seviyesinde değil.

Bu prensip, Pyramid of Pain kavramıyla doğrudan ilişkilidir: hash ve IP gibi göstergeler saldırgan için değiştirmesi kolay ve ucuzdur; TTP (Tactics, Techniques, Procedures) seviyesinde tespit ise saldırganın tüm araç setini ve yaklaşımını değiştirmesini gerektirir, bu da saldırgana çok daha maliyetlidir.

### 5. Test: Kural Üretime Girmeden Önce Doğrulama

Test aşaması iki ayrı soruyu cevaplamalıdır: **"Kural gerçek saldırıyı yakalıyor mu?"** ve **"Kural meşru/normal aktiviteyi yanlışlıkla yakalamıyor mu?"**

**Pozitif test (true positive doğrulama):** Kuralın hedeflediği davranışın kontrollü bir şekilde (izole test ortamında, iyi belgelenmiş simülasyon araçlarıyla — ör. ATT&CK'e eşlenmiş açık kaynaklı saldırı simülasyon çerçeveleri) üretilip kuralın gerçekten tetiklendiğinin doğrulanmasıdır. Bu adım atlanırsa, kural "yazıldı ama hiç ateşlenmedi" durumunda kalabilir — teorik olarak doğru görünen mantığın pratikte bir alan adı yanlışlığı, bir zamanlama/sıralama varsayım hatası veya log şeması uyumsuzluğu yüzünden asla tetiklenmediği yaygın bir üretim hatasıdır.

**Negatif test (false-positive taraması):** Kuralın, geçmiş üretim loglarına (retrospektif) karşı çalıştırılıp kaç meşru olayı yanlışlıkla işaretlediğinin ölçülmesidir. Bu, kuralın "gürültü bütçesi"ni öngörmek için kritiktir — bir SOC analisti günde ele alabileceği alarm sayısıyla sınırlıdır; yüksek false-positive oranlı bir kural, gerçek tehdidi gürültüye gömer (alarm yorgunluğu / alert fatigue).

**Birim testi otomasyonu:** Olgun Detection-as-Code pipeline'ları, her kural için "bu log satırı eşleşmeli" ve "şu log satırı eşleşmemeli" test vakalarını otomatik çalıştırır — tıpkı yazılımda birim testi gibi. Bu, gelecekte kural üzerinde yapılacak bir değişikliğin (ör. bir alan yeniden adlandırıldığında yapılan güncelleme) mevcut tespit yeteneğini kırıp kırmadığını anında ortaya çıkarır (regression testing).

### 6. Tuning: False-Positive Azaltma Döngüsü

Bir kural üretime girdikten sonra genellikle ilk hali "gürültülü"dür. Tuning, kuralın hassasiyetini kaybetmeden gürültüsünü azaltma sürecidir. Kök mantık: **her filtre bir görme kaybı riski taşır** — bu yüzden tuning rastgele filtre eklemek değil, her filtrenin ne pahasına geldiğini bilerek yapılan bir mühendislik kararıdır.

Tipik tuning yaklaşımları:
- **Beyaz liste / istisna (allowlist/exception) ekleme:** Bilinen meşru bir sürecin (ör. kurumsal bir yönetim aracının) tetiklediği belirli bir örüntüyü hariç tutma. Risk: istisna çok geniş yazılırsa, saldırgan o istisnanın arkasına gizlenebilir (ör. meşru aracın adını taklit eden bir ikili/binary).
- **Eşik (threshold) ayarlama:** Sayma tabanlı kurallarda (ör. "kısa sürede çok sayıda başarısız oturum açma") eşiği ortamın gerçek temel çizgisine (baseline) göre kalibre etme.
- **Bağlamsal zenginleştirme (enrichment):** Kurala ek bağlam ekleyerek (ör. varlık kritikliği, kullanıcı rolü, ağ segmenti) false-positive'i azaltma — kuralın kendisini gevşetmek yerine, hangi bağlamda alarmın önceliklendirileceğini ayarlama.
- **Korelasyon:** Tek başına zayıf sinyal veren bir olayı, başka sinyallerle birleştirerek (ör. "hem A hem B hem de C aynı host'ta kısa sürede oldu") güven skorunu artırma — bu, tek bir kuralın eşik değerini düşürmek yerine sinyal biriktirme mantığıdır.

**Yaygın hata:** Tuning'i "alarmı kapat" olarak yorumlamak. Doğru tuning, **neden** o olayın false-positive olduğunu anlayıp mantığı daraltmaktır; yanlış tuning, rahatsız edici bir kuralı sessizce devre dışı bırakıp arkasındaki gerçek görünürlük kaybını fark etmemektir. Her tuning kararı, kimin onayladığı ve hangi gerekçeyle yapıldığı belgelenerek (yine Detection-as-Code'un code review sürecinin parçası olarak) izlenmelidir.

### 7. Dağıtım, İzleme ve Kural Sağlığı Metrikleri

Kural üretime girdikten sonra iş bitmez; **kural sağlığı (rule health)** sürekli izlenmelidir. Kavramsal olarak izlenmesi gereken metrikler:

- **Tetiklenme sıklığı (fire rate):** Kural hiç tetiklenmiyor mu (şüpheli — veri kaynağı koptu mu, mantık bozuldu mu), yoksa aşırı mı tetikleniyor (tuning gerekiyor)?
- **True positive / false positive oranı:** Analist geri bildirimiyle (bir alarmı "gerçek" veya "yanlış" olarak etiketlemesiyle) zamanla ölçülür.
- **Ortalama triyaj süresi (MTTT — mean time to triage):** Bu kuralın ürettiği alarmın ele alınması ne kadar sürüyor — çok karmaşık/belirsiz alarmlar analist zamanını gereksiz tüketir.
- **Veri kaynağı sürekliliği:** Kuralın bağımlı olduğu log kaynağının akışının kesilip kesilmediğinin (heartbeat/health check) izlenmesi — sessiz kör noktaları erken yakalamak için.

### 8. Emeklilik (Retirement) ve Yeniden Değerlendirme

Bir kural artık değer üretmiyorsa (sürekli false-positive, artık geçerli olmayan bir tekniği hedefliyor, veri kaynağı kalıcı olarak kayboldu) bilinçli olarak emekliye ayrılmalıdır. Kök mantık: kullanılmayan/güvenilmeyen kurallar SIEM'de "gürültü borcu" (detection debt) biriktirir — analistler zamanla o kurala güvenmemeyi öğrenir ve gerçek bir uyarı geldiğinde bile göz ardı edebilir. Düzenli kural incelemesi (periyodik "detection rule review") bu birikimi önler.

## Yaygın Hatalar

- **Gereksinim yazmadan doğrudan sorgu yazmaya başlamak:** "Neyi neden tespit ettiğimiz" belgelenmediği için kural bir süre sonra anlamsızlaşır, kimse dokunmaya cesaret edemez.
- **Veri kaynağı doğrulamadan kural yazmak:** Teorik olarak doğru ama hiçbir zaman tetiklenmeyecek "ölü" kurallar üretmek — sahte bir güvenlik hissi (false sense of security) yaratır.
- **Kapsama haritalamayı tik atma egzersizine indirgemek:** Nicelik (kaç teknik "kapsanıyor") üzerinden raporlamak, niteliği (derinlik, test edilmişlik, güven seviyesi) göz ardı etmek.
- **Tuning'i sessiz devre dışı bırakma ile karıştırmak:** Rahatsız eden bir kuralı, kök nedeni anlamadan kapatmak — görünürlük kaybını fark etmeden.
- **Sürüm kontrolü ve code review olmadan üretim SIEM'inde doğrudan düzenleme:** Değişikliklerin izlenemez, geri alınamaz ve denetlenemez olması.
- **Tek seferlik test, sürekli izleme yok:** Kural bir kez test edilip unutulduğunda, ortam kayması ve saldırgan adaptasyonu nedeniyle zamanla sessizce bozulmasının fark edilememesi.
- **Artefakt tabanlı kural yazıp davranış tabanlı düşünmemek:** Pyramid of Pain'in en altındaki (ucuz, kolay değiştirilebilir) göstergelere aşırı bağımlı kural seti kurmak, saldırganın küçük bir değişiklikle tüm tespiti atlatmasına izin verir.

## Sonuç

Detection Engineering, tek bir kuralın zekice yazılmasından çok daha fazlasıdır: gereksinimin doğru tanımlanması, gerekli verinin gerçekten var olduğunun doğrulanması, kapsamanın stratejik olarak haritalanması, kuralın hem pozitif hem negatif senaryolarla test edilmesi, gürültünün bilinçli olarak azaltılması, sağlığın sürekli izlenmesi ve değerini yitiren kuralın emekliye ayrılmasından oluşan bir döngüdür. Bu disiplin, Sigma kuralı yazma becerisi veya ATT&CK matrisini bilme ile aynı şey değildir — bunları besleyen, sürdüren ve güvenilir kılan üst düzey mühendislik çerçevesidir. Bir SOC'un gerçek olgunluğu, kaç kuralı olduğuyla değil, bu yaşam döngüsünü ne kadar disiplinli işlettiğiyle ölçülür.
