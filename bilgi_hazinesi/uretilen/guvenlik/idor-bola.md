# IDOR / Broken Object Level Authorization (BOLA)

## Tanım

IDOR (Insecure Direct Object Reference), bir uygulamanın bir nesneye (kayıt,
dosya, hesap) erişirken kullanıcının verdiği bir referansı (genelde bir ID)
doğrudan kullanması ama o kullanıcının **o nesneye erişim yetkisi olup olmadığını
kontrol etmemesidir**. API dünyasında aynı kusurun daha genel adı **BOLA**'dır
(Broken Object Level Authorization) ve OWASP API Security Top 10 listesinin bir
numarasıdır. Pratikte gördüğümüz en yaygın ve en çok veri sızıntısına yol açan
zafiyet sınıflarından biridir — çünkü sömürüsü basit, tespiti araçlarla zordur ve
neredeyse her nesne-tabanlı uygulamada ortaya çıkabilir.

Klasik örnek: `GET /api/fatura/1043` isteği kendi faturanı getiriyor. Sayıyı
`1044` yapınca **başkasının** faturası geliyorsa, uygulamada IDOR vardır.

## Kök Neden: Kimlik Doğrulama ile Yetkilendirmenin Karıştırılması

IDOR'un temelinde, güvenliğin iki farklı katmanının birbirine karıştırılması
yatar:

- **Authentication (kimlik doğrulama):** "Sen kimsin?" — kullanıcı giriş yapmış,
  oturumu geçerli.
- **Authorization (yetkilendirme):** "Bu kaynağa erişmeye hakkın var mı?" — bu
  *belirli* nesnenin bu *belirli* kullanıcıya ait olup olmadığı.

IDOR'lu bir uygulamada authentication genelde doğrudur; kullanıcı gerçekten giriş
yapmıştır. Eksik olan, **nesne düzeyinde authorization**'dır. Sunucu, "istek yapan
kişi giriş yapmış, o hâlde istediği ID'yi getirebilir" varsayımına düşer. Oysa
giriş yapmış olmak, her nesneye erişim hakkı vermez. Bu ayrımı kaçırmak, IDOR'un
tek ve gerçek kök nedenidir.

İkinci bir kök neden, yetkilendirme kararının **yanlış katmanda** verilmesidir.
Birçok uygulama, kullanıcının yalnızca *kendi* nesnelerini gördüğü bir arayüz
(UI) sunar ve geliştirici "kullanıcı zaten başkasının ID'sini göremez ki"
düşüncesine kapılır. Ama API doğrudan çağrılabilir; saldırgan arayüzü değil,
altındaki endpoint'i konuşur. **İstemci tarafındaki kısıtlama güvenlik değildir.**

## Sömürü Mantığı

IDOR sömürüsü, diğer birçok zafiyetin aksine, karmaşık payload gerektirmez;
sadece **referansı değiştirmek** yeterlidir. Adımlar tipik olarak şöyledir:

1. **Referansı bul:** URL parametreleri (`?id=1043`), yol parçaları
   (`/user/1043`), istek gövdesi (JSON içindeki `"accountId": 1043`), gizli form
   alanları, cookie'ler veya API yanıtındaki ID'ler.
2. **Referansı değiştir:** Ardışık sayılarda bir-iki artır/azalt (`1044`, `1042`);
   UUID ise başka bir yanıtta gördüğün bir UUID'yi dene; iki farklı hesabı
   karşılaştır.
3. **Yetkisiz erişimi doğrula:** Başkasının verisi dönüyorsa okuma-IDOR; PUT/POST/
   DELETE ile değiştirebiliyorsan yazma-IDOR (çok daha ciddi).

Otomasyon burada işi büyütür: ardışık ID'lerde IDOR varsa, saldırgan bir betikle
`1`'den `100000`'e kadar dönüp **tüm veritabanını sıyırabilir** (mass data
exfiltration). Bu yüzden tek bir IDOR bile bir kullanıcının değil, tüm
kullanıcıların verisinin sızması demektir.

IDOR'un birkaç yaygın varyasyonu:

- **Yatay yetki ihlali (horizontal):** Aynı ayrıcalık düzeyindeki başka bir
  kullanıcının verisine erişmek (kullanıcı A, kullanıcı B'nin faturasını görür).
- **Dikey yetki ihlali (vertical):** Bir fonksiyona ait ID/parametreyi kullanarak
  daha yüksek ayrıcalıklı bir işleme erişmek (bu daha çok "Broken Function Level
  Authorization" ile örtüşür).
- **Dolaylı IDOR:** ID doğrudan görünmese de, tahmin edilebilir bir dosya adı,
  hash'lenmemiş bir sıra numarası veya öngörülebilir bir token ile erişim.

## Neden Tarayıcılarla Zor Yakalanır

Otomatik zafiyet tarayıcıları (DAST) IDOR'u genelde **kaçırır**, çünkü IDOR
teknik bir sözdizimi hatası değil, bir **iş mantığı / yetki** hatasıdır. Tarayıcı
`1043` ile `1044`'ün *ikisinin de* geçerli HTTP 200 döndürdüğünü görür ama
`1044`'ün o kullanıcıya *ait olmaması gerektiğini* bilmez — bunu bilmek uygulamanın
iş kurallarını anlamayı gerektirir. Bu yüzden IDOR tespiti büyük ölçüde **manuel
test** ve **iki hesapla karşılaştırma** işidir: bir hesapla oluştur, diğer hesapla
erişmeyi dene.

## Savunma

IDOR'a karşı tek gerçek savunma **her nesne erişiminde, sunucu tarafında, nesne
düzeyinde yetki kontrolü** yapmaktır. Somut ilkeler:

1. **Sahiplik/erişim kontrolünü her istekte doğrula.** Nesneyi çekmeden önce ya da
   çektikten hemen sonra sor: "Bu nesne, isteği yapan kullanıcıya mı ait / bu
   kullanıcının erişim hakkı var mı?" Örneğin sorguyu `WHERE id = :id AND
   sahip_id = :oturum_kullanici_id` biçiminde yaz; böylece başkasının ID'si
   satır döndürmez. Bu, kontrolü sorgunun kendisine gömer ve unutmayı zorlaştırır.

2. **Yetkilendirmeyi merkezî ve zorunlu kıl.** Her endpoint'te elle kontrol yazmak
   yerine, bir yetkilendirme katmanı/politika motoru (policy layer) kullan;
   böylece bir endpoint kontrolü *unutursa* varsayılan "reddet" olur (fail
   securely). "Her yeni endpoint güvenlik ekibine sorulsun" değil, "sistem
   varsayılan olarak kapalı" tasarla.

3. **Dolaylı referans kullan (indirect reference).** Kullanıcıya global veritabanı
   ID'si yerine, oturuma özel bir eşleme sun: kullanıcının kendi listesindeki
   `1, 2, 3` indeksleri sunucuda gerçek nesnelere eşlensin. Böylece kullanıcı
   başka bir nesneyi *adresleyemez* bile. Bu güçlü ama her mimaride pratik değildir.

4. **Tahmin edilemez tanımlayıcı (UUID) — yardımcıdır ama tek başına YETMEZ.**
   Ardışık ID yerine rastgele UUID kullanmak, kaba-kuvvetle numara denemeyi
   zorlaştırır. Ama bu bir **derinlemesine savunma katmanıdır, yetki kontrolünün
   yerine geçmez.** UUID'ler loglarda, `Referer` başlıklarında, paylaşılan
   bağlantılarda, başka API yanıtlarında sızabilir; sızan bir UUID ile yetki
   kontrolü yoksa erişim yine mümkündür. Yani UUID'ye tek başına bel bağlama; onu
   yalnızca ek bir engel olarak gör, tek savunma olarak değil.

5. **Yazma işlemlerine ayrı özen göster.** Okuma-IDOR veri sızdırır; yazma-IDOR
   (başkasının kaydını değiştirme/silme) bütünlüğü bozar ve çok daha ciddidir.
   PUT/PATCH/DELETE ve durum değiştiren POST'larda yetki kontrolünü asla atlama.

6. **Logla ve izle.** Bir kullanıcının kısa sürede çok sayıda farklı nesne ID'sine
   erişmeye çalışması (özellikle ardışık) bir IDOR taraması sinyalidir; bunu
   tespit et ve hız sınırla (rate limit).

## Yaygın Hatalar

- **"UI'da göstermiyoruz, o hâlde güvenli."** API doğrudan çağrılır; UI kısıtı
  güvenlik değildir.
- **Yetki kontrolünü sadece liste (list) endpoint'inde yapıp tekil (detail)
  endpoint'te unutmak.** `/faturalar` doğru filtreliyor ama `/fatura/{id}`
  filtrelemiyor — çok yaygın.
- **ID'yi UUID yaptık diye rahatlamak.** Yukarıda açıklandığı gibi tek başına
  yetmez.
- **Yetkiyi controller'ın başında bir kez kontrol edip, sonra farklı bir ID ile
  başka nesne çekmek.** Kontrol edilen ID ile kullanılan ID aynı olmalı.

## Özet

IDOR/BOLA, karmaşık bir exploit değil, **unutulmuş bir yetki kontrolüdür.** Kök
nedeni authentication'ı authorization sanmaktır. Panzehiri de tek cümledir: her
nesneye her erişimde, sunucu tarafında, "bu kaynak bu kullanıcıya mı ait?"
sorusunu sor ve yanıt hayırsa reddet. UUID, dolaylı referans ve loglama yardımcı
katmanlardır; ama merkezî, zorunlu, nesne düzeyinde yetkilendirme olmadan hiçbiri
yeterli değildir.
