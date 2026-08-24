# Ağ Adli Bilişimi (Network Forensics)

## Tanım

Ağ adli bilişimi, bir ağ üzerinden geçen trafiğin yakalanması, saklanması ve analiz edilmesi yoluyla bir olayın ne zaman, nasıl ve kimin tarafından gerçekleştiğini ortaya çıkarma disiplinidir. Klasik "disk forensics"ten (disk adli bilişimi) temel farkı, incelenen delilin **uçucu (volatile)** olmasıdır: bir paket telden geçip gittikten sonra, onu bir yerde yakalamadıysanız, o delil sonsuza dek kaybolur. Diskteki bir dosyayı bir hafta sonra da inceleyebilirsiniz; ama bir C2 (command and control) beacon'ının dün gece 03:14'te attığı paketi, o an yakalamadıysanız geri getiremezsiniz.

Bu disiplinin iki ana veri kaynağı vardır. Birincisi **full packet capture (tam paket yakalama)**, yani `pcap` dosyaları: her paketin her byte'ının kaydı. İkincisi **flow/metadata** kayıtları: NetFlow, IPFIX veya Zeek loglarında olduğu gibi, "kim kiminle, ne zaman, ne kadar veri, hangi port üzerinden konuştu" özet bilgisi. Full packet en zengin delildir ama diski hızla doldurur; metadata ise çok daha ölçeklenebilir olduğu için haftalarca, aylarca saklanabilir. Olgun bir SOC (Security Operations Center) genellikle her ikisini birden tutar: metadata'yı uzun süre, full pcap'i ise kısa bir "rolling buffer" (dönen tampon) içinde.

Ağ adli bilişimini önemli kılan şey, **saldırganın diski temizleyebilmesine rağmen ağ izini kolayca silememesidir**. Bir saldırgan hedef makinedeki logları, event kayıtlarını, kendi araçlarını silebilir; ama trafik bağımsız bir noktada (SPAN port, TAP, ağ sensörü) kaydediliyorsa, o kayıt saldırganın erişemeyeceği bir yerdedir. Bu yüzden ağ delili, ihlal sonrası soruşturmalarda çoğu zaman en güvenilir kaynaktır.

## Kök Neden ve Çalışma Mantığı: Ağ Neden Bu Kadar Konuşkandır?

Ağ adli bilişiminin işe yaramasının temel nedeni, **hiçbir yazılımın sessizce çalışamamasıdır**. Bir malware, verisini dışarı sızdırmak (exfiltration), komut almak ya da güncelleme çekmek için eninde sonunda ağa çıkmak zorundadır. Tamamen offline çalışan bir malware zaten operatörüne hiçbir işe yaramaz; onu kontrol edemez, çaldığı veriyi alamaz. İşte bu zorunluluk, savunmacıya bir kaldıraç verir: **saldırgan gizlenmeye çalışsa da, iletişim kurmak zorunda olduğu için bir iz bırakır.**

TCP/IP'nin katmanlı yapısı bu izlerin okunmasını mümkün kılar. Her paket bir zarf gibidir: dış katmanda IP başlığı (kim kime), onun içinde TCP/UDP başlığı (hangi port, hangi oturum), en içte ise uygulama katmanı verisi (HTTP isteği, DNS sorgusu, TLS handshake vb.) bulunur. Analist bu katmanları soyarak trafiğin niyetini yeniden inşa eder. TCP'nin durum makinesi (SYN, SYN-ACK, ACK ile başlayan handshake, FIN/RST ile biten kapanış) sayesinde bir oturumun ne zaman başladığını, ne kadar sürdüğünü ve düzgün mü yoksa aniden mi koptuğunu görebilirsiniz.

Modern trafiğin büyük kısmının **şifreli (TLS)** olması, bu resmi bir miktar zorlaştırır ama tahmin edildiği kadar değil. Şifreleme, paketin *içeriğini* gizler; ama *metadata'sını* değil. Bir TLS oturumunda dahi şu bilgiler açıktır ya da çıkarılabilirdir: bağlantının hedef IP'si ve portu, SNI (Server Name Indication) alanındaki hedef alan adı, sertifika bilgileri, oturumun ne zaman kurulduğu, ne kadar veri aktığı, paketlerin zamanlaması ve boyut dağılımı. Adli analist bu "dış" sinyallerden çok şey çıkarır. Buna trafik analizi denir ve şifreleme onu tamamen engelleyemez; çünkü **zamanlama ve hacim, içeriğin kendisi kadar konuşkandır.**

## pcap Analizi: Delili Okumak

pcap analizi, ham paket yakalama dosyasını alıp anlamlı bir olay anlatısına dönüştürme sürecidir. Temel araçlar Wireshark (grafik arayüz, derin inceleme için), `tshark` (Wireshark'ın komut satırı kardeşi, otomasyon ve büyük dosyalar için) ve `tcpdump` (yakalama ve hızlı filtreleme için) etrafında döner.

İş akışı genellikle şöyle ilerler. Önce **üst seviye bir görünüm** alınır: hangi IP'ler var, en çok konuşan çiftler kimler, hangi protokoller baskın? Wireshark'ta bunun için "Statistics > Conversations" ve "Statistics > Protocol Hierarchy" ekranları paha biçilmezdir. Bu adım, gigabyte'larca trafiği "şu iki host arasında anormal miktarda veri akmış" gibi tek bir odak noktasına indirger.

Ardından **filtreleme** gelir. Wireshark'ın display filter dili (örneğin `ip.addr == ... && tcp.port == ...` mantığında) ile ilgisiz trafik ayıklanır. Burada kritik bir ayrım vardır: **capture filter** (BPF sözdizimi, yakalama anında uygulanır, atılan paket geri gelmez) ile **display filter** (yakalanmış veriyi görüntülerken uygular, geri alınabilir) aynı şey değildir. Adli bağlamda genellikle her şeyi yakalayıp sonra display filter ile daraltmak tercih edilir; çünkü capture aşamasında attığınız bir paket, sonradan ihtiyaç duyacağınız delil olabilir.

pcap analizinin en güçlü hamlelerinden biri **stream reassembly**'dir. TCP verisi paketlere bölünmüş halde gelir; Wireshark'ta "Follow TCP Stream" ile bu parçalar tekrar birleştirilip bir HTTP isteğinin ya da bir komut oturumunun tamamı okunabilir. Benzer şekilde, trafikte taşınan dosyalar (indirilen bir exe, sızdırılan bir belge) paketlerden yeniden inşa edilip diske çıkarılabilir (file carving / export objects). Bir malware'in indirdiği payload'ı bu şekilde çıkarıp hash'ini alıp threat intelligence ile karşılaştırmak, klasik bir adli hamledir.

Somut bir örnek düşünelim: Bir kullanıcının makinesinden şüpheleniyorsunuz. pcap'i açıyorsunuz, Protocol Hierarchy'de DNS trafiğinin anormal derecede yüksek olduğunu görüyorsunuz. DNS sorgularına filtre uygulayınca, `a8f3d9...[uzun rastgele string]...example[.]com` biçiminde, uzun ve okunmaz alt alan adlarına (subdomain) yapılan yüzlerce sorgu görüyorsunuz. Bu, **DNS tunneling** üzerinden veri sızdırmanın klasik imzasıdır: veri, DNS sorgularının subdomain kısmına encode edilerek dışarı taşınmaktadır. Bu tespiti sadece metadata'dan, paketlerin içeriğini bile açmadan yapabilirsiniz.

## Zeek: Trafiği Anlatıya Çevirmek

Wireshark tek bir olayı derinlemesine incelemek için mükemmeldir ama gigabyte'larca trafikte "neyin peşine düşeceğinizi" bilmediğinizde yavaş kalır. İşte **Zeek** (eski adıyla Bro) burada devreye girer. Zeek bir paket yakalayıcı değil, bir **ağ trafiği analiz çerçevesidir**: ham trafiği izler ve onu yapılandırılmış, insan tarafından okunabilir loglara dönüştürür.

Zeek'in temel felsefesi şudur: her paketi değil, her **olayı** kaydet. Zeek bir TCP oturumunu görür ve `conn.log` içine tek bir satır yazar: kaynak IP, hedef IP, portlar, protokol, süre, gönderilen/alınan byte sayısı, bağlantının durumu. Bir DNS sorgusu görür, `dns.log`'a yazar. Bir TLS handshake görür, `ssl.log`'a sertifika ve SNI bilgisini yazar. Bir HTTP isteği görür, `http.log`'a host, URI, user-agent ve yanıt kodunu yazar. Dosya transferi görür, `files.log`'a dosyanın hash'ini ve türünü yazar.

Bu dönüşümün kök nedeni ölçeklenebilirliktir. 1 TB'lık bir pcap'i her seferinde Wireshark'la taramak pratik değildir; ama aynı trafiğin Zeek logları belki birkaç gigabyte'tır ve bunları `grep`, `awk`, `zeek-cut` ya da bir SIEM ile saniyeler içinde sorgulayabilirsiniz. Zeek, "hangi paket" sorusunu "hangi davranış" sorusuna çevirir. Adli soruşturmada genellikle önce Zeek loglarında ipucu bulunur ("şu host şu saatte bilinmeyen bir IP'ye 4 GB veri göndermiş"), sonra o zaman aralığının pcap'i Wireshark'ta detaylı incelenir. İkisi rakip değil, tamamlayıcıdır.

Zeek ayrıca **scriptable**'dır: kendi Zeek diliyle özel dedektörler yazabilirsiniz. Örneğin "aynı hedefe, düzenli aralıklarla, benzer boyutta bağlantı kuran her host'u işaretle" mantığında bir beacon dedektörü Zeek script olarak yazılabilir. Bu, Zeek'i statik bir loglayıcıdan aktif bir tespit motoruna dönüştürür.

## Beacon Tespiti: Düzenliliğin İhaneti

Bir sisteme sızan saldırgan, kalıcı kontrol için genellikle bir **C2 (command and control)** altyapısı kurar. Ele geçirilen makinedeki implant (Cobalt Strike beacon, bir RAT, özel bir malware), operatöründen komut almak için düzenli aralıklarla C2 sunucusuna "ben buradayım, emrin var mı?" diye bağlanır. İşte bu düzenli "yoklama" trafiğine **beaconing** denir ve ağ adli bilişiminin en verimli av alanlarından biridir.

Beacon tespitinin çalışma mantığı şu içgörüye dayanır: **insan trafiği düzensizdir, makine trafiği düzenlidir.** Gerçek bir kullanıcı bir siteyi bazen açar bazen açmaz, bazen 2 dakika bazen 40 dakika kalır, istekleri düzensiz aralıklarla gelir. Oysa bir beacon, kodlanmış bir zamanlayıcıyla çalışır: örneğin her 60 saniyede bir, sürekli, günlerce. Bu **periyodiklik** ele veren imzadır. Bir host'un tek bir dış IP'ye, saatlerce, neredeyse sabit aralıklarla, birbirine çok benzer boyutlarda bağlantı kurduğunu görürseniz, bu güçlü bir C2 sinyalidir.

Tespit pratikte şöyle yapılır. Zeek `conn.log`'undan bir kaynak-hedef çifti için bağlantı zaman damgaları çıkarılır. Ardışık bağlantılar arasındaki zaman farkları (delta) hesaplanır. Eğer bu delta'ların dağılımı çok dar bir bant içinde toplanıyorsa (düşük varyans, düşük standart sapma), bu periyodikliğin işaretidir. Aynı şekilde gönderilen byte miktarlarının tekdüzeliği de dikkate alınır. RITA (Real Intelligence Threat Analytics) gibi araçlar tam olarak bunu yapar: Zeek loglarını alıp her host çifti için bir "beacon skoru" hesaplar.

Saldırganlar bunu bildikleri için **jitter** eklerler: beacon aralığına rastgele bir sapma katarlar (örneğin "60 saniye ± %30"), böylece trafik daha az düzenli görünür. Bu, saf periyodiklik testini kandırabilir. İşte savunma ile istismarın birbirini kovaladığı yer burasıdır. Savunmacının cevabı, katı periyodiklik yerine **istatistiksel dağılım analizidir**: jitter'lı trafik bile, tamamen rastgele insan trafiğinden istatistiksel olarak ayrışır; çünkü jitter genellikle bir merkez değer etrafında simetrik bir dağılım oluşturur, oysa gerçek insan davranışı ağır kuyruklu (heavy-tailed) ve öngörülemezdir. Ayrıca beacon'lar genellikle 7/24 devam eder; bir insan makinesinin gece 03:00'te dahi düzenli konuşması başlı başına şüphelidir.

**İstismar tarafından bakınca** saldırganın beacon'ı gizleme repertuarı geniştir: jitter ekleme, meşru bulut servislerini C2 olarak kullanma (domain fronting, CDN arkasına saklanma), meşru user-agent taklidi, uzun sleep aralıkları (günde birkaç kez bağlanma, tespiti zorlaştırır ama kontrolü de yavaşlatır). **Savunma tarafından** ise korelasyon güçlüdür: tek bir sinyal yeterli değilse, "düzenli aralık + bilinmeyen/genç domain + düşük itibar + JA3 fingerprint eşleşmesi + coğrafi anormallik" gibi zayıf sinyalleri birleştirmek yüksek güvenilirlikli bir tespit verir.

## Exfiltration (Veri Sızdırma) Tespiti

Exfiltration, bir saldırının çoğu zaman nihai amacıdır: çalınan verinin kurumdan dışarı taşınması. Adli bilişim açısından exfil, iki soruyu cevaplamayı gerektirir: **veri gerçekten çıktı mı, çıktıysa ne kadar ve neyin içine gizlenerek?**

Sızdırmanın en kaba biçimi **hacim anomalisidir**. Normalde bir iç sunucu dışarıya günde birkaç yüz megabyte gönderiyorsa ve bir gece aniden 50 GB dışarı akmışsa, bu bir alarmdır. Zeek `conn.log`'undaki `orig_bytes` (kaynağın gönderdiği byte) alanı burada anahtardır. Kritik bir nokta: exfil'de trafik genellikle **asimetriktir**. Sıradan web gezintisinde çok indirir az yüklersiniz (download > upload); exfil'de ise tersine, bir iç host anormal derecede çok *upload* yapar. Bu yön tersliği güçlü bir işarettir.

Ama akıllı saldırgan tek seferde 50 GB göndermez; bu çok gürültülüdür. Onun yerine **low and slow** (yavaş ve sessiz) yaklaşır: veriyi günlere yayar, küçük parçalar halinde, meşru trafiğe karışacak biçimde gönderir. Bu, hacim eşiğine dayalı basit alarmları atlatır. Savunmanın cevabı yine metadata korelasyonudur: yavaş exfil bile, bir iç host'un normalde konuşmadığı bir dış hedefe, uzun süre, ısrarla veri göndermesi biçiminde bir kalıp bırakır.

Exfil ayrıca sıklıkla **kanal gizleme (covert channel)** kullanır. En yaygınları:

- **DNS tunneling**: Yukarıda anlatıldığı gibi, veri DNS sorgularının subdomain'lerine encode edilir. DNS neredeyse hiçbir yerde bloklanmadığı ve az izlendiği için idealdir. İmzası: anormal uzunlukta ve yüksek entropili (rastgele görünen) alt alan adları, tek bir domain'e olağandışı sayıda sorgu, TXT/NULL kayıt tiplerinin aşırı kullanımı.
- **HTTP/HTTPS POST**: Veri normal web trafiği gibi bir sunucuya POST edilir. TLS içindeyse içerik görünmez ama gönderilen byte hacmi ve hedef itibarı hâlâ analiz edilebilir.
- **ICMP tunneling**: Veri ping paketlerinin payload alanına gizlenir; normalde boş olması gereken ICMP payload'larının dolu ve büyük olması şüphelidir.
- **Meşru bulut servisleri**: Veri bir bulut depolama ya da paylaşım servisine yüklenir. Hedef "meşru" göründüğü için tespiti en zor olanıdır; burada hacim, zamanlama ve kullanıcının o servisi normalde kullanıp kullanmadığı (baseline) belirleyici olur.

**Savunma tarafından** exfil tespitinin altın kuralı **baselining**'dir: "normal"i bilmeden "anormal"i göremezsiniz. Her host ve servis için tipik trafik profili (kiminle konuşur, ne kadar, hangi saatlerde, hangi yönde) çıkarılır; sapmalar araştırılır. DNS için entropi ve sorgu uzunluğu analizi, upload/download oranı izleme, yeni ve düşük itibarlı hedeflere yapılan büyük transferlerin işaretlenmesi, DLP (Data Loss Prevention) ile korelasyon temel savunma katmanlarıdır. **İstismar tarafından** ise saldırganın hedefi bu baseline'a mümkün olduğunca benzemektir: meşru portları kullanmak, meşru servislere sığınmak, şifrelemek ve yavaşlamak.

## Yaygın Hatalar

**Yalnızca full pcap'e güvenmek ve retention'ı ihmal etmek.** Full packet capture disk açısından pahalıdır; birçok kurum yalnızca birkaç saatlik ya da günlük rolling buffer tutar. İhlal genellikle haftalar sonra fark edilir ve o zaman kritik pcap çoktan üzerine yazılmıştır. Metadata (Zeek/NetFlow) çok daha uzun saklanabildiği için, uzun retention'ın metadata üzerine kurulmaması ciddi bir eksikliktir.

**Şifreli trafik karşısında pes etmek.** "Trafik TLS, içini göremiyorum, o zaman analiz edilemez" yanılgısı yaygındır. Oysa SNI, sertifika bilgisi, JA3/JA3S fingerprint'leri, zamanlama, hacim ve yön, şifreleme olmadan da zengin sinyal sağlar. Beaconing ve exfil'in çoğu zaten metadata'dan tespit edilir.

**Zaman senkronizasyonunu ihmal etmek.** Adli analizde olayları doğru sıralamak (timeline) her şeydir. Sensörlerin, sunucuların ve logların saatleri NTP ile senkron değilse, olay örgüsü bozulur ve delil mahkemede sorgulanabilir hale gelir. Ayrıca tüm zaman damgalarının UTC gibi tek bir referansa çekilmemesi de kaosa yol açar.

**Delil bütünlüğünü (chain of custody) korumamak.** Yakalanan pcap'in hash'i alınmalı, kim tarafından, nerede, hangi araçla yakalandığı belgelenmelidir. Aksi halde delil hukuki değerini kaybeder. Ayrıca yakalama noktasının doğru seçilmemesi (örneğin NAT'ın arkasından yakalama, gerçek iç IP'leri gizler) analizi baştan sakatlar.

**SPAN port'a körü körüne güvenmek.** SPAN (port mirroring) yoğun trafik altında paket düşürebilir; kritik ortamlarda pasif bir **TAP** daha güvenilirdir. Düşen paketler, tam olarak aradığınız delil olabilir ve bu kaybı fark etmezsiniz bile.

**Tek bir sinyale dayalı alarm.** Ne saf periyodiklik beacon demektir (meşru yazılım güncelleme kontrolleri de periyodiktir), ne de tek başına yüksek hacim exfil demektir (yedekleme trafiği de büyüktür). Korelasyonsuz alarmlar analisti yanlış pozitiflerle boğar ve gerçek tehditlerin gözden kaçmasına yol açar.

## En İyi Pratikler

**Katmanlı görünürlük kurun.** Full pcap'i kısa süreli ve hedefli (kritik segmentler, DMZ) tutun; metadata'yı (Zeek logları, NetFlow/IPFIX) uzun süreli ve geniş kapsamlı toplayın. Böylece hem "ne oldu" (metadata, uzun geçmiş) hem de "tam olarak nasıl oldu" (pcap, yakın geçmiş) sorularına cevap verebilirsiniz.

**Yakalama noktasını stratejik seçin.** Ağ çıkışını (egress) mutlaka izleyin; çünkü beacon ve exfil oradan geçer. Mümkünse NAT'tan önce, gerçek iç IP'lerin görünür olduğu noktada yakalayın. Doğu-batı (iç ağ içi, lateral movement) trafiğini de kör noktada bırakmayın.

**Baseline oluşturun ve sürdürün.** Anomali tespiti ancak "normal"in tanımıyla mümkündür. Her segment, host grubu ve kritik servis için tipik trafik profilini çıkarın ve düzenli güncelleyin. Sapmaları otomatik işaretleyecek kurallar yazın.

**Metadata'yı SIEM'e ve threat intelligence'a bağlayın.** Zeek loglarını merkezî bir sisteme akıtın; hedef IP ve domain'leri itibar ve IOC (indicator of compromise) beslemeleriyle otomatik zenginleştirin. JA3/JA3S ve SSL sertifika fingerprint'lerini bilinen kötü amaçlı imzalarla eşleştirin.

**Korelasyona dayalı tespit yazın.** Beacon için "periyodiklik + genç domain + düşük itibar + 7/24 süreklilik" gibi çoklu zayıf sinyali birleştirin. Exfil için "yön asimetrisi + hacim anomalisi + yeni hedef + baseline sapması"nı birlikte değerlendirin. Tek sinyalli değil, çok sinyalli kararlar verin.

**Yakalama altyapısını sağlamlaştırın.** Yoğun ortamlarda SPAN yerine TAP kullanın, paket düşüşünü izleyin, NTP ile tüm saatleri senkronize edin, tüm zaman damgalarını UTC'ye normalize edin. Yakalanan delilin hash'ini alıp chain of custody'yi belgeleyin.

**Otomatikleştirin ama insanı çıkarmayın.** Zeek script'leri ve RITA benzeri araçlarla ilk elemeyi otomatikleştirin; ama nihai kararı, bağlamı bilen bir analiste bırakın. Ağ adli bilişiminde en değerli varlık, "bu düzenli trafik meşru bir güncelleme kontrolü mü, yoksa bir C2 beacon mı" ayrımını yapabilen deneyimli gözdür. Araçlar sinyali bulur; niyeti anlayan analisttir.

## Kapanış

Ağ adli bilişimi, saldırganın kaçınılmaz zayıflığından güç alır: kontrol ve veri hırsızlığı için iletişim kurmak zorundadır, iletişim de iz bırakır. pcap ham gerçeği, Zeek bu gerçeğin ölçeklenebilir anlatısını verir. Beacon tespiti makine düzenliliğinin insan düzensizliğinden ayrışmasını sömürür; exfil tespiti ise "normal"in bilgisiyle "anormal"i yakalar. Her ikisinde de savunmanın kalıcı üstünlüğü tek bir metriğe değil, zayıf sinyallerin korelasyonuna ve sağlam bir baseline'a dayanmasından gelir. Şifreleme içeriği gizler ama davranışı gizleyemez; ve davranış, çoğu zaman itirafın kendisidir.
