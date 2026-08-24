# Phishing ve Sosyal Mühendislik

## Tanım

Sosyal mühendislik (social engineering), teknik bir güvenlik açığından çok **insan psikolojisindeki açıkları** hedef alan saldırı disiplinidir. Saldırgan, bir sistemi kırmak yerine o sisteme meşru erişimi olan kişiyi kandırarak erişimi, bilgiyi ya da bir eylemi elde eder. Phishing (oltalama) ise sosyal mühendisliğin en yaygın ve en ölçeklenebilir alt türüdür: kurbanı, güvenilir bir kaynaktan geliyormuş gibi görünen bir mesajla (e-posta, SMS, sesli arama, anlık mesaj) manipüle ederek kimlik bilgisi ifşa etmeye, kötü amaçlı bir eki açmaya ya da bir bağlantıya tıklamaya yöneltir.

Terminolojide bazı alt kırılımlar vardır ve bunları doğru ayırmak önemlidir: **spear phishing** belirli bir kişiyi hedefleyen, kişiselleştirilmiş saldırıdır; **whaling** üst düzey yöneticileri (CEO, CFO) hedefler; **smishing** SMS üzerinden, **vishing** ise telefon/sesli kanaldan yapılır. **BEC (Business Email Compromise)**, kurumsal e-posta hesaplarının ele geçirilmesi ya da taklit edilmesiyle genellikle para transferini hedefleyen, teknik olarak "sade" ama finansal etkisi çok yüksek bir kategoridir.

## Kök Neden: Neden Sosyal Mühendislik İşe Yarar

Sosyal mühendisliğin çalışma mantığını anlamak için tek bir cümleye indirgeyelim: **insan beyni, her kararı yavaş ve analitik biçimde vermez.** Günlük iş akışında insanlar çoğu kararı hızlı, otomatik ve sezgisel bir "hızlı düşünme" moduyla verir. Saldırgan tam olarak bu otomatik modu tetikler ve kurbanın "yavaş düşünme" (durup sorgulama) moduna geçmesini engeller. İşte bu manipülasyonun dayandığı temel psikolojik kaldıraçlar:

- **Otorite (authority):** İnsanlar yetkili görünen bir kaynağın talebini sorgulamadan yerine getirmeye eğilimlidir. "IT departmanından", "genel müdürden" ya da "bankadan" geliyormuş gibi görünen bir mesaj, sorgulama refleksini baskılar.
- **Aciliyet ve kıtlık (urgency/scarcity):** "Hesabınız 24 saat içinde kapatılacak", "son 3 fatura ödenmedi" gibi zaman baskısı, kurbanın düşünmeden hareket etmesini sağlar. Aciliyet, doğrulama adımlarını atlatmanın en güçlü aracıdır.
- **Güven ve tanıdıklık (trust/familiarity):** Tanıdık bir marka logosu, doğru görünen bir gönderen adı ya da bir meslektaşın ismi, mesajı meşrulaştırır.
- **Karşılıklılık ve yardımseverlik (reciprocity):** İnsanlar yardımcı olmak ister. "Yeni başladım, sistemde takıldım, şu bilgiyi paylaşır mısın?" tarzı talepler bu eğilimi sömürür.
- **Sosyal kanıt (social proof) ve korku:** "Herkes bu güncellemeyi yaptı" ya da "hesabınızda şüpheli bir işlem tespit edildi" gibi ifadeler davranışı yönlendirir.

Buradaki kritik nokta şudur: Bu zaaflar bir "eğitim eksikliği" değil, **insan bilişinin normal çalışma biçimidir.** Bu yüzden sosyal mühendislik hiçbir zaman tamamen "yamalanamaz"; ancak katmanlı savunmayla riski yönetilebilir hale getirilir. Teknik bir sistemde bir açığı kapattığınızda o açık kapanır; insanda ise aynı zaafiyet her yeni çalışanla, her yorgun günde, her yoğun dönemde yeniden ortaya çıkar. Savunmanın neden tek bir eğitim oturumuyla bitmediğinin kök nedeni budur.

## Bir Saldırının Anatomisi: Pretext ve Payload

Her ciddi sosyal mühendislik saldırısı iki temel bileşen üzerine kurulur: **pretext** (senaryo/bahane) ve **payload** (asıl zararlı yük). Bu ikisini ayırmak, hem saldırıyı analiz etmek hem de savunmayı doğru katmana yerleştirmek için şarttır.

### Pretext: İnandırıcı Senaryo Kurma

Pretext, saldırganın kurbanı ikna etmek için uydurduğu bağlam ve kimliktir. İyi bir pretext, kurbanın zaten beklediği ya da makul bulduğu bir duruma yaslanır — bu yüzden en tehlikeli phishing, "sizi milyoner yaptık" tarzı kaba örnekler değil, iş akışına doğal biçimde oturan mesajlardır.

Pretext'in inandırıcılığı büyük ölçüde **OSINT (Open Source Intelligence)** ile toplanan bilgiye dayanır. Saldırgan; LinkedIn'den kurumun organizasyon şemasını, kimin kime rapor verdiğini, hangi yazılımların kullanıldığını (iş ilanlarından teknoloji yığını sızar), sosyal medyadan çalışanların tatil/etkinlik bilgilerini toplar. Örneğin CEO'nun konferans için şehir dışında olduğunu bilen bir saldırgan, tam o pencerede CFO'ya "acil transfer" talebi gönderdiğinde pretext çok daha inandırıcı olur; çünkü "patrona hemen soramama" durumu senaryoya doğal biçimde oturur.

Somut bir pretext örneği: Saldırgan, kurumun kullandığı bulut e-posta sağlayıcısını tespit eder, gerçeğine çok benzeyen bir alan adı kaydeder (örneğin `sirket-guvenlik.com` gibi, gerçeği `sirketguvenlik.com` olan), ve "Parolanızın süresi doldu, 24 saat içinde yenilemezseniz hesabınız kilitlenecek" mesajı gönderir. Mesajdaki bağlantı, gerçek giriş sayfasının **piksel piksel kopyası** olan sahte bir sayfaya gider.

### Payload: Asıl Zararlı Yük

Payload, kurban pretext'e kandıktan sonra tetiklenen asıl amaçtır. Başlıca payload türleri:

- **Kimlik bilgisi hasadı (credential harvesting):** Sahte giriş sayfası (bir "phishing kit" ile inşa edilir), girilen kullanıcı adı ve parolayı saldırganın sunucusuna gönderir. Bu en yaygın payload'dır çünkü kurumsal sistemlere doğrudan meşru giriş sağlar.
- **Kötü amaçlı ek (malicious attachment):** Genellikle makro içeren Office belgeleri, sıkıştırılmış arşivler (parola korumalı ZIP ile tarama atlatma), ya da `.lnk`, disk imajı gibi az bilinen dosya türleri. Kurban dosyayı açtığında bir "loader" çalışır ve arka planda asıl kötü amaçlı yazılımı (info-stealer, ransomware, RAT) indirir.
- **Kötü amaçlı bağlantı (drive-by / yönlendirme):** Kurbanı, tarayıcı ya da eklenti açığını sömüren bir sayfaya götürür.
- **MFA atlatma (adversary-in-the-middle):** Modern phishing kit'lerinin önemli bir kısmı artık, kurbanla gerçek servis arasında **reverse proxy** olarak durur. Kurban gerçek siteye benzeyen proxy'ye parolasını ve tek kullanımlık kodunu girer; saldırgan bunları gerçek zamanlı olarak gerçek servise iletir ve **oturum çerezini (session cookie/token)** çalar. Bu, SMS ya da uygulama tabanlı OTP'yi bile geçersiz kılabilir — çünkü çalınan şey artık kod değil, doğrulanmış oturumun kendisidir.

Buradaki kavramsal ders şudur: Payload'ı durdurmak için doğru katmanı seçmek gerekir. Kimlik bilgisi hasadına karşı **phishing'e dayanıklı MFA**, kötü amaçlı eke karşı **e-posta sanitizasyonu ve endpoint kontrolü**, MFA atlatmaya karşı da **cookie'ye değil cihaza bağlı kimlik doğrulama** gerekir. Tek bir kontrol her payload'ı kapatmaz.

## Sömürü Mantığı ve Savunma: Katman Katman

Aşağıda saldırının her aşamasında hem istismar mantığını hem de ona karşılık gelen savunmayı birlikte veriyorum. Amaç, savunmayı "yapılacaklar listesi" olarak değil, saldırının hangi mekanizmasını nasıl kırdığını anlayarak kurmak.

### Gönderen Kimliğinin Taklidi ve E-posta Kimlik Doğrulama

**İstismar mantığı:** Klasik SMTP protokolü, bir e-postanın "From" (Kimden) alanına istediğinizi yazmanıza izin verir; protokolün kendisi gönderenin gerçekliğini doğrulamaz. Bu yüzden saldırgan, e-postayı sizin alan adınızdan geliyormuş gibi gösterebilir (**spoofing**) ya da göz yanılgısı yaratan benzer alan adları (**typosquatting** — `rn` yerine `m`, `l` yerine `I`) kullanabilir.

**Savunma:** Alan adı kimlik doğrulamasının üç ayağı burada devreye girer:
- **SPF (Sender Policy Framework):** Alan adınız adına hangi sunucuların posta gönderebileceğini DNS'te ilan eder. Alıcı sunucu bunu doğrular.
- **DKIM (DomainKeys Identified Mail):** Giden postaya kriptografik bir imza ekler; alıcı, imzayı DNS'teki public key ile doğrulayarak içeriğin yolda değişmediğini ve alan adından geldiğini teyit eder.
- **DMARC:** SPF ve DKIM sonuçlarını bir **politikaya** bağlar (`none` / `quarantine` / `reject`) ve başarısız mesajlara ne yapılacağını söyler; ayrıca raporlama sağlar.

Yaygın hata: Kurumlar DMARC'ı kurar ama politikayı sonsuza dek `p=none` (yalnızca izle) modunda bırakır. Bu, spoofing'e karşı hiçbir zaman koruma sağlamaz; yalnızca görünürlük verir. Doğru yaklaşım, raporları izleyip meşru gönderim kaynaklarını hizaladıktan sonra kademeli olarak `reject`'e geçmektir. Ayrıca DMARC yalnızca **kesin alan adı taklidini** engeller; **benzer** alan adı (lookalike) saldırılarını engellemez — çünkü o alan adı saldırgana aittir ve kendi SPF/DKIM'ini geçerli biçimde kurabilir.

### Kimlik Bilgisi Hasadı ve MFA'nın Doğru Türü

**İstismar mantığı:** Sahte giriş sayfasına düşen kurban parolasını verir; parola tek başına savunma katmanıysa oyun biter.

**Savunma ve nüans:** MFA (çok faktörlü kimlik doğrulama) burada kritik ama **her MFA eşit değildir.** SMS ile gelen kod ve uygulama tabanlı tek kullanımlık kod (TOTP), yukarıda anlatılan adversary-in-the-middle proxy saldırısıyla ele geçirilebilir; çünkü kullanıcı o kodu sahte sayfaya girer. Buna karşı gerçek çözüm **phishing'e dayanıklı (phishing-resistant) kimlik doğrulamadır**: FIDO2 / WebAuthn tabanlı donanım anahtarları ya da platform passkey'leri. Bunların işe yaramasının kök nedeni şudur: Kimlik doğrulama, kullanıcının hangi alan adında olduğuna kriptografik olarak **bağlıdır** (origin binding). Kullanıcı yanlışlıkla sahte bir alan adındaysa, anahtar imzayı o alan adı için üretir ve gerçek servise uymaz — yani kullanıcı kandırılsa bile protokol kandırılamaz. Ek olarak, çalınan bir oturumun etkisini sınırlamak için **kısa oturum ömrü**, **koşullu erişim** (bilinmeyen cihaz/coğrafyada yeniden doğrulama) ve **token binding** gibi kontroller MFA atlatmanın etkisini azaltır.

### Kötü Amaçlı Ek/Bağlantı ve Teknik Filtreleme

**İstismar mantığı:** Payload dosyada ya da bağlantının ucundadır; kullanıcının açması yeterlidir.

**Savunma:**
- **E-posta güvenlik ağ geçidi (secure email gateway)** ve **sandboxing:** Şüpheli ekler, kullanıcıya ulaşmadan izole bir ortamda "patlatılarak" (detonation) davranışları gözlemlenir.
- **Bağlantı yeniden yazma (URL rewriting / time-of-click protection):** Bağlantılar geçit üzerinden yeniden yazılır; tıklama anında hedef yeniden kontrol edilir. Bu önemlidir çünkü saldırganlar bağlantıyı, e-posta tarandıktan **sonra** zararlı hale getirebilir.
- **Endpoint tarafında sertleştirme:** Office makrolarını internetten gelen dosyalarda varsayılan olarak engellemek, bilinen tehlikeli dosya türlerini karantinaya almak, ve **EDR** ile loader davranışını (beklenmedik process spawn, network beaconing) tespit etmek.
- **En az ayrıcalık (least privilege) ve ağ segmentasyonu:** Bir kullanıcı kandırılıp cihazı ele geçirilse bile, saldırganın yatay hareketini (lateral movement) sınırlar. Bu, "ihlal olacağını varsay" (assume breach) prensibinin somut karşılığıdır.

### İç Süreçler ve BEC'e Karşı Doğrulama

**İstismar mantığı:** BEC'te çoğu zaman kötü amaçlı yazılım bile yoktur; yalnızca inandırıcı bir e-posta ve bir para transferi talebi vardır. Saldırgan, tedarikçi taklidi yaparak fatura banka bilgisini değiştirir (invoice fraud) ya da CEO taklidiyle acil transfer ister.

**Savunma — teknik olmaktan çok süreçsel:** Buradaki en güçlü kontrol **kanal dışı doğrulamadır (out-of-band verification).** Yani ödeme bilgisi değişikliği ya da belli bir eşiği aşan transfer, mutlaka **ayrı ve önceden bilinen** bir kanaldan (e-postaya cevap değil, kayıtlı telefon numarasından arama) teyit edilmelidir. İkinci güçlü kontrol **çift onaydır (dual authorization / four-eyes principle):** Kritik finansal işlemler tek kişinin insafına bırakılmaz. Bu iki kontrolün neden bu kadar etkili olduğunun kök nedeni: BEC, aciliyet ve otorite psikolojisini sömürür; kanal dışı doğrulama ve çift onay, tam da o "hızlı, tek başına karar" anını kırar.

## Farkındalık: Neden ve Nasıl

Teknik kontroller ne kadar iyi olursa olsun, bazı mesajlar kullanıcıya ulaşacaktır; bu yüzden **insan katmanı savunmanın parçasıdır, zayıf halkası değil** — doğru kurgulandığında. Ancak farkındalık programlarının çoğu, yanlış kurgulandığı için işe yaramaz.

Etkili bir farkındalık yaklaşımının prensipleri:

- **Suçlama değil, refleks inşası:** Amaç kullanıcıyı "aptal" konumuna düşürmek değil, şüphe anında ne yapacağını (raporlama düğmesine basmak) otomatikleştirmektir. Suçlayıcı kültür, kullanıcıların yanlış tıkladıklarında **saklanmasına** yol açar; oysa erken raporlama, olay müdahalesi için en değerli zaman kazandıran şeydir.
- **Raporlamayı kolaylaştırmak:** Tek tıkla "şüpheli e-postayı bildir" düğmesi olmalıdır. Raporlama zor ya da cezalandırıcıysa yapılmaz.
- **Simüle phishing tatbikatları — ölçmek için, ceza için değil:** Kontrollü sahte phishing kampanyaları, hangi senaryoların kimlerde işe yaradığını gösterir. Ancak ölçüt yalnızca "tıklama oranı" olmamalıdır; **raporlama oranı** en az onun kadar önemlidir. Yüksek raporlama oranı, sağlıklı bir güvenlik kültürünün en iyi göstergesidir.
- **Bağlama özel eğitim:** Muhasebeye fatura dolandırıcılığı, İK'ya sahte özgeçmiş ekleri, yöneticilere whaling örnekleri gösterilmelidir. Genel eğitim, herkese uygun ama kimseye tam uygun değildir.

Yaygın bir hata: Yıllık tek bir zorunlu eğitim videosunu "farkındalık" saymak. Kök neden bölümünde açıkladığımız gibi, sömürülen zaaflar insan bilişinin sürekli özellikleridir; dolayısıyla farkındalık da sürekli, kısa ve tekrarlı olmalıdır — yılda bir kez değil.

## Yaygın Hatalar

Kurumların sosyal mühendislik savunmasında tekrar tekrar düştüğü hatalar, çoğunlukla "kontrolün varlığını, kontrolün etkinliğiyle karıştırmaktan" kaynaklanır:

- **DMARC'ı `p=none`'da bırakmak.** Kurulmuş görünür ama koruma sağlamaz.
- **Her MFA'yı eşit saymak.** SMS OTP, hiç MFA olmamasından iyidir ama phishing'e dayanıklı değildir; kritik varlıklar için FIDO2/passkey gerekir.
- **İç ağa aşırı güven (implicit trust).** "İçeriden gelen istek güvenlidir" varsayımı, bir hesap ele geçirildiğinde çöker. Zero trust yaklaşımı tam da bu varsayımı reddeder.
- **Simüle phishing'i ceza aracına çevirmek.** Bu, raporlamayı öldürür ve gerçek olaylarda görünürlüğü azaltır.
- **Yöneticileri istisna tutmak.** En çok hedeflenen (whaling) ve en çok yetkiye sahip kişiler çoğu zaman güvenlik kontrollerinden muaf tutulmak ister; bu, en değerli hedefi en zayıf noktaya çevirir.
- **Yalnızca e-postaya odaklanmak.** Smishing, vishing ve anlık mesajlaşma kanalları hızla büyüyor; savunma tüm iletişim kanallarını kapsamalıdır. Özellikle sesli kanalda, gerçek zamanlı ses klonlama artık pretext'i çok daha inandırıcı kılabiliyor.
- **Olay müdahale planının olmaması.** "Bir kullanıcı kimlik bilgisini verdi" senaryosunda saatler değil dakikalar önemlidir: parola sıfırlama, oturum/token iptali, erişim gözden geçirme adımları önceden yazılı ve prova edilmiş olmalıdır.

## En İyi Pratikler

Savunmayı katmanlı ve birbirini destekleyen bir bütün olarak kurmak, tek bir sihirli çözüm aramaktan çok daha etkilidir. Öncelik sırasıyla:

1. **Phishing'e dayanıklı MFA'yı standart yapın.** Özellikle e-posta, VPN, kimlik sağlayıcı (identity provider) ve finansal sistemler için FIDO2/passkey. Bu tek başına en yüksek etkili kontroldür çünkü çalınan parolayı ve çoğu MFA atlatma tekniğini işe yaramaz kılar.

2. **E-posta kimlik doğrulamasını tam kurun ve zorlayın.** SPF, DKIM ve **`reject`'e ilerletilmiş** DMARC. Ek olarak benzer alan adlarını (lookalike domain) izleyin ve mümkünse defansif olarak kaydedin.

3. **Katmanlı e-posta ve endpoint kontrolü.** Sandboxing, time-of-click URL koruması, makro engelleme, EDR ve gelen e-postalarda net görsel uyarı (örneğin "bu e-posta dışarıdan geldi" bandı).

4. **Kritik süreçlere kanal dışı doğrulama ve çift onay gömün.** Özellikle ödeme bilgisi değişikliği ve eşik üstü transferler için. Bu, teknik değil süreçsel bir kontroldür ama BEC'e karşı en güçlü tek savunmadır.

5. **Zero trust ve least privilege uygulayın.** Ağ konumuna göre değil, kimlik ve cihaz sağlığına göre erişim verin; yatay hareketi sınırlamak için segmentasyon ve minimum yetki uygulayın. "Assume breach" zihniyetiyle tasarlayın.

6. **Sürekli, suçlamayan farkındalık ve kolay raporlama.** Simüle tatbikatları ölçüm için kullanın; başarı ölçütü olarak tıklama oranı kadar raporlama oranını da izleyin. Tek tıkla bildirim düğmesi sağlayın.

7. **Olay müdahalesini prova edin.** Kimlik bilgisi ifşası ve BEC senaryoları için önceden yazılmış, denenmiş playbook'lar; hızlı oturum/token iptali ve parola sıfırlama yetkinliği.

8. **Görünürlük ve geri besleme döngüsü.** Raporlanan phishing'leri analiz edin, tespit kurallarını güncelleyin ve öğrenilenleri hem teknik kontrollere hem de eğitime geri besleyin.

Sonuç olarak, phishing ve sosyal mühendisliğe karşı savunmanın özü tek bir fikirde toplanır: **İnsan hata yapacaktır — bu bir varsayım değil, bir kesinliktir.** İyi bir güvenlik mimarisi, tek bir insanın tek bir yanlış tıklamasının felaketle sonuçlanmayacağı şekilde tasarlanır. Teknik kontroller hata olasılığını düşürür, süreçsel kontroller ve katmanlı mimari ise hatanın maliyetini sınırlar. Bu ikisi birlikte çalıştığında, sosyal mühendislik ortadan kalkmaz ama yönetilebilir bir riske dönüşür.
