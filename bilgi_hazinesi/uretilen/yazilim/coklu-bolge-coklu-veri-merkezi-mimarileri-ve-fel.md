# Çoklu Bölge / Çoklu Veri Merkezi Mimarileri ve Felaket Kurtarma

## Giriş ve Neden Önemli

Büyük ölçekli sistemlerin dayanıklılık (resilience) planlaması, tek bir veri merkezinin er ya da geç arızalanacağı varsayımı üzerine kuruludur. Elektrik kesintisi, ağ (network) bağlantısının kopması, doğal afet, insan hatası veya bir bulut sağlayıcının bölgesel (region) çökmesi kaçınılmazdır. **Multi-region** (çoklu bölge) ve **multi-datacenter** (çoklu veri merkezi) mimarileri, bir konumun tamamen kaybedilmesi durumunda bile hizmetin ayakta kalmasını hedefler.

Bu konu; kapasite planlaması, dayanıklılık, maliyet ve tutarlılık (consistency) arasındaki gerilimlerin tam merkezinde durur. Mühendisin verdiği her karar iki kritik metriğe indirgenir: sistem ne kadar veri kaybını göze alabilir (**RPO**) ve ne kadar süre kesinti kaldırabilir (**RTO**). Bu makale, bu kavramların çalışma mantığını, replikasyon gecikmesinin (replication lag) neden fizik yasalarıyla sınırlı olduğunu ve **active-active** ile **active-passive** stratejilerinin gerçekte ne anlama geldiğini derinlemesine ele alır.

## Temel Tanımlar

### Bölge (Region), Erişilebilirlik Alanı (Availability Zone) ve Veri Merkezi

Terimlerin karıştırılması, mimari hataların en yaygın kaynağıdır.

- **Veri merkezi (datacenter):** Fiziksel bir bina. Sunucular, güç kaynakları, soğutma ve ağ ekipmanı barındırır.
- **Availability Zone (AZ):** Birbirinden bağımsız güç, soğutma ve ağa sahip, ancak coğrafi olarak birbirine yakın (genellikle aynı metropol alanında, tipik olarak on kilometreler mesafede) bir veya birkaç veri merkezinden oluşan izole birim. AZ'ler arası gecikme (latency) genellikle bir milisaniyenin altında ile birkaç milisaniye arasındadır.
- **Region (bölge):** Coğrafi olarak ayrı bir alan (örneğin "Batı Avrupa", "Kuzey Amerika Doğu"). Birden fazla AZ içerir. Bölgeler arası gecikme onlarca hatta yüzlerce milisaniye olabilir.

Kritik ayrım şudur: **Bir AZ arızası ile bir bölge arızası farklı savunma stratejileri gerektirir.** Aynı bölgedeki farklı AZ'lere yayılmak, güç ve soğutma arızalarına karşı korur ama bir doğal afetin veya bölgesel kontrol düzlemi (control plane) çökmesinin tüm bölgeyi etkilemesine karşı korumaz. Gerçek felaket kurtarma (disaster recovery) için verinin farklı **bölgelere** kopyalanması gerekir.

### RPO (Recovery Point Objective)

**RPO**, bir felaket anında göze alınabilecek maksimum veri kaybı miktarıdır ve **zaman cinsinden** ölçülür. "RPO = 5 dakika" ifadesi, felaket sonrası en fazla son 5 dakikalık verinin kaybedilebileceği anlamına gelir.

RPO'yu belirleyen şey, verinin ne sıklıkla ikincil konuma kopyalandığıdır:
- Saatlik yedek (backup) alıyorsanız RPO'nuz en kötü durumda 1 saattir.
- Sürekli (asenkron) replikasyon yapıyorsanız RPO, replikasyon gecikmesi kadardır (saniyeler).
- Senkron replikasyon yapıyorsanız RPO teorik olarak sıfırdır.

### RTO (Recovery Time Objective)

**RTO**, bir felaket anından hizmetin yeniden çalışır hale geldiği ana kadar geçebilecek maksimum süredir. "RTO = 15 dakika" ifadesi, kesintiden 15 dakika sonra sistemin tekrar hizmet vermesi gerektiği anlamına gelir.

RTO; failover'ın (yük devretme) ne kadar otomatik olduğuna, DNS yayılma süresine, ikincil ortamın hazır (warm) mı yoksa sıfırdan mı ayağa kaldırılacağına (cold) bağlıdır.

> **Kavramsal netlik:** RPO geçmişe bakar (ne kadar veri kaybederim?), RTO geleceğe bakar (ne kadar sürede geri dönerim?). İkisi bağımsız hedeflerdir. RPO'su sıfır ama RTO'su saatlerce olan bir sistem tasarlanabilir ve tam tersi de mümkündür.

## RPO/RTO'yu İş Değerine Bağlamak

Bu iki metrik keyfî seçilmez; iş etkisinden türetilir. İki kavram burada devreye girer:

- **MTD (Maximum Tolerable Downtime):** İşin kabul edebileceği toplam maksimum kesinti. RTO, MTD'den küçük olmalıdır.
- Veri kaybının maliyeti: Bir finansal işlem sisteminde tek bir kayıp işlem yasal ve parasal sonuçlar doğurur, bu yüzden RPO sıfıra yaklaştırılır. Bir analitik loglama sisteminde birkaç dakikalık kayıp önemsizdir, RPO gevşek tutulup maliyet düşürülür.

Temel mühendislik gerçeği: **Daha düşük RPO/RTO üstel olarak daha pahalıdır.** RPO'yu 1 saatten 5 saniyeye çekmek, basit yedeklemeden sürekli replikasyona geçmek demektir; RTO'yu saatlerden saniyelere indirmek, atıl duran ikinci bir tam kapasite ortam çalıştırmak demektir. Her sistemi en katı hedefe göre tasarlamak yaygın ve pahalı bir hatadır.

## Replikasyon: Senkron ve Asenkron

Multi-region mimarinin kalbi, verinin bölgeler arasında nasıl kopyalandığıdır. İki temel model vardır ve aralarındaki seçim, doğrudan RPO ile gecikmeyi (dolayısıyla kullanıcı deneyimini) karşı karşıya getirir.

### Senkron Replikasyon (Synchronous)

Yazma işlemi (write), **hem birincil hem de ikincil konumda onaylandıktan sonra** istemciye başarı döner. Bu durumda ikincil konum daima birincil ile birebir aynıdır.

- **Avantaj:** RPO = 0. Birincil konum kaybedilse bile hiçbir onaylanmış veri kaybolmaz.
- **Maliyet:** Her yazma işlemi, iki konum arasındaki tur-gidiş süresini (round-trip time) beklemek zorundadır. AZ'ler arası bu mesafe kabul edilebilirken (birkaç ms), **kıtalar arası senkron replikasyon fiziksel olarak yıkıcıdır.** Işık hızı sabittir; İstanbul ile bir ABD bölgesi arasındaki tur-gidiş fiziksel alt sınırı bile onlarca milisaniyedir. Her yazmaya bu gecikmeyi eklemek, sistemi kullanılamaz hale getirir.

Bu yüzden senkron replikasyon pratikte **aynı bölge içindeki AZ'ler arasında** kullanılır.

### Asenkron Replikasyon (Asynchronous)

Yazma işlemi birincil konumda onaylanır onaylanmaz istemciye başarı döner; veri ikincil konuma **arka planda, sonradan** kopyalanır.

- **Avantaj:** Yazma gecikmesi düşük kalır; uzak bölgelere replikasyon mümkün olur.
- **Maliyet:** RPO > 0. Birincil konum, henüz kopyalanmamış veri varken çökerse, o veri kaybolur. Kaybedilen miktar **replikasyon gecikmesi** kadardır.

Bu, coğrafi olarak dağıtık felaket kurtarmanın standart modelidir. Kabul edilen gerçek şudur: Coğrafi dayanıklılık istiyorsanız, asenkron replikasyon ve dolayısıyla sıfır olmayan bir RPO ile yaşamayı öğrenmeniz gerekir.

### Replikasyon Gecikmesi (Replication Lag) — Kök Neden

Replikasyon gecikmesi, bir verinin birincilde yazılması ile ikincilde görünür olması arasındaki süredir. Bu gecikmenin kaynakları:

1. **Ağ mesafesi ve fizik:** Işık hızı üst sınırdır. Coğrafi mesafe arttıkça minimum gecikme artar.
2. **İkincil tarafın uygulama hızı:** İkincil, gelen değişiklikleri (örneğin bir veritabanının replikasyon akışını) uygulamakta yavaş kalabilir. Yazma yükü ani yükseldiğinde ikincil geride kalır ("lag spike").
3. **Tek iş parçacıklı uygulama:** Bazı veritabanlarında replikasyon uygulaması tek iş parçacıklıdır; birincilde paralel yürüyen yazmalar ikincilde seri uygulanır ve birikme oluşur.
4. **Uzun süren işlemler (long transactions):** Büyük bir transaction, ikincilde tümüyle uygulanana kadar sonraki değişiklikleri bloke edebilir.

Replikasyon gecikmesini **izlemek** kritiktir çünkü bu gecikme sizin gerçek RPO'nuzdur. Gecikme büyürken failover yapmak, tam da o büyümüş gecikme kadar veri kaybı demektir.

## Failover Stratejileri: Active-Passive ve Active-Active

### Active-Passive (Aktif-Pasif)

Bir bölge trafiği aktif olarak karşılar; diğer bölge(ler) yalnızca verinin kopyasını tutar ve normalde trafik almaz. Birincil çökünce trafik ikincile yönlendirilir (failover).

Pasif ortamın hazırlık seviyesine göre alt türler:
- **Cold standby (soğuk):** İkincil ortam kapalıdır; felaket anında sıfırdan ayağa kaldırılır. En ucuz, en yüksek RTO.
- **Warm standby (ılık):** İkincil ortam açık ve güncel veriye sahiptir ama küçük kapasitede çalışır; failover'da ölçeklenir. Orta maliyet, orta RTO.
- **Hot standby (sıcak):** İkincil tam kapasitede, hazır bekler; failover neredeyse anlıktır. En pahalı, en düşük RTO.

**Avantajları:** Basittir. Yazmalar tek bir bölgeye gittiği için **veri çakışması (write conflict) yoktur**. Tutarlılık kolay sağlanır.

**Dezavantajları:** İkincil kapasite (özellikle hot standby) çoğu zaman atıl durur; maliyet yüksektir. RTO, failover mekanizmasının hızıyla sınırlıdır.

### Active-Active (Aktif-Aktif)

Birden fazla bölge **aynı anda** okuma ve yazma trafiğini karşılar. Kullanıcılar en yakın bölgeye yönlendirilir (düşük gecikme avantajı), ve bir bölge çökerse trafiği kalan bölgeler emer.

**Avantajları:**
- Kaynaklar atıl durmaz; tüm bölgeler iş yapar.
- Kullanıcıya coğrafi yakınlık sayesinde düşük gecikme.
- Bir bölge kaybında failover neredeyse görünmez olabilir (çünkü diğerleri zaten çalışıyordu). Çok düşük RTO.

**Dezavantajları — ve burada asıl zorluk başlar:**
- **Yazma çakışmaları:** İki bölge aynı veriyi aynı anda değiştirdiğinde ne olur? Bu, dağıtık sistemlerin en zor problemidir.
- **Tutarlılık modeli karmaşıklaşır:** Güçlü tutarlılık (strong consistency) çoğu zaman feda edilip **nihai tutarlılık (eventual consistency)** benimsenir.

### Çakışma Çözümü (Conflict Resolution)

Active-active'de çakışmalar kaçınılmazdır. Yaygın yaklaşımlar:
- **Last-write-wins (LWW):** Zaman damgası en yeni olan kazanır. Basittir ama sessizce veri kaybettirir (kaybeden yazma yok olur) ve saat senkronizasyonuna (clock skew) bağımlıdır.
- **Bölgesel sahiplik (sharding by region):** Her veri parçasının "sahibi" olan tek bir bölge olur; o veriye yazmalar hep o bölgeye yönlenir. Çakışma önlenir ama gerçek anlamda "her yere yazma" ortadan kalkar.
- **CRDT'ler (Conflict-free Replicated Data Types):** Matematiksel olarak birleştirilebilir (merge) veri yapıları. Çakışmalar deterministik biçimde çözülür ama her veri tipine uymaz.
- **Uygulama düzeyinde birleştirme:** Çakışan sürümler uygulamaya sunulur, iş mantığı karar verir (örneğin alışveriş sepetinde iki listenin birleşimini almak).

## Tutarlılık ve CAP/PACELC

Multi-region tasarımının teorik zeminini **CAP teoremi** oluşturur: Ağ bölünmesi (network partition) yaşandığında, **tutarlılık (Consistency)** ile **erişilebilirlik (Availability)** arasında seçim yapmak zorunda kalırsınız.

- Bölgeler arası ağ koptuğunda **CP** sistem, tutarlılığı korumak için bazı isteklere hizmet vermeyi durdurur (reddeder).
- **AP** sistem, erişilebilirliği korumak için hizmet vermeyi sürdürür ama bölgeler geçici olarak farklı veri görebilir.

**PACELC**, CAP'i tamamlar: Bölünme (P) yoksa bile, **gecikme (Latency)** ile tutarlılık (C) arasında bir denge (else, E) vardır. Yani sistem sağlıklıyken bile güçlü tutarlılık istemek, bölgeler arası tur-gidişi beklemek yani ekstra gecikme demektir. Bu, active-active sistemlerin neden çoğunlukla nihai tutarlılığı seçtiğini açıklar.

## Failover Mekanizmasının Detayları

Failover'ı tetiklemek ve yönlendirmek başlı başına bir mühendislik alanıdır.

### Trafik Yönlendirme

- **DNS tabanlı failover:** DNS kayıtları, sağlık kontrolüne (health check) göre birincilden ikincile yönlendirilir. Basittir ama **DNS TTL** (yaşam süresi) ve istemci/çözümleyici önbelleklemesi nedeniyle yayılma dakikalar sürebilir; bu doğrudan RTO'ya eklenir. Düşük TTL kullanmak yardımcı olur ama sorunu tümüyle çözmez.
- **Anycast / global yük dengeleyici (global load balancer):** Aynı IP birden çok bölgeden yayınlanır; ağ, kullanıcıyı en yakın sağlıklı bölgeye yönlendirir. Failover çok daha hızlıdır çünkü DNS önbelleğine bağlı değildir.

### Sağlık Kontrolü ve Split-Brain Tehlikesi

Otomatik failover, birincilin gerçekten öldüğünü doğru tespit etmeye bağlıdır. En tehlikeli senaryo **split-brain**'dir: Birincil aslında çalışıyordur ama ağ bölünmesi yüzünden ikincil onu ölü sanır ve kendini birincil ilan eder. Şimdi **iki birincil** vardır, ikisi de yazma alır ve veri geri döndürülemez biçimde çatallanır.

Split-brain'e karşı korunma yöntemleri:
- **Quorum (çoğunluk):** Karar vermek için tek sayıda düğümün çoğunluğu gerekir; azınlıkta kalan taraf kendini pasifleştirir. Bu yüzden failover kararı çoğu zaman **üçüncü bir bölgedeki** hakem (arbiter/witness) düğümüyle verilir.
- **Fencing / STONITH:** Eski birincilin yazma yapması fiziksel/mantıksal olarak engellenir ("kafasına kurşun sık" mantığı).
- **Lease (kiralama):** Birincillik, süreli bir kira ile tutulur; kira yenilenmezse otomatik düşer.

## Doğru Kullanım ve Yaygın Tuzaklar

### Doğru Uygulamalar

- **Failover'ı düzenli test edin.** Test edilmemiş bir DR planı, plan değildir. **Game day** / kaos mühendisliği (chaos engineering) tatbikatlarıyla bölge kaybını kasıtlı olarak simüle edin. Netflix'in Chaos Monkey yaklaşımının felsefesi budur: Arızayı üretimde denetimli biçimde yaratıp sistemin dayanıklılığını kanıtlamak.
- **Geri dönüşü (failback) de planlayın.** Birincil geri geldiğinde trafiği geri almak, en az failover kadar risklidir; bu sırada iki ortam arasında biriken farkın uzlaştırılması gerekir.
- **RPO/RTO'yu ölçün, varsaymayın.** Replikasyon gecikmesini sürekli izleyin ve alarm kurun; gerçek RPO'nuz o gecikmedir.
- **Bağımlılıkları unutmayın.** Uygulama failover yapsa bile bağımlı olduğu bir servis (kimlik doğrulama, DNS, sır yönetimi) tek bölgede kaldıysa, tüm çaba boşa gider.

### Yaygın Hatalar

1. **Çoklu AZ ile çoklu bölgeyi karıştırmak.** Sadece AZ'lere yayılmak bölge çapındaki bir arızaya karşı koruma sağlamaz; ancak yanlış bir güvenlik hissi verir.
2. **Yedeğin geri yüklenebilirliğini test etmemek.** "Yedeğimiz var" demek yeterli değildir; sessizce bozulmuş, geri yüklenemeyen bir yedek RPO'yu sonsuza çıkarır.
3. **RPO/RTO'yu ayrıştırmamak.** Sadece "yüksek erişilebilirlik istiyoruz" demek ölçülebilir bir hedef değildir; iki metrik ayrı ayrı, sayısal olarak tanımlanmalıdır.
4. **Senkron replikasyonu uzak bölgeye kurmaya çalışmak.** Fiziksel gecikme yüzünden sistem kullanılamaz hale gelir. Uzak mesafe = asenkron.
5. **Split-brain'i göz ardı etmek.** Hakem/quorum olmadan kurulan otomatik failover, ağ bölünmesinde iki birincil üretip veriyi kalıcı olarak bozabilir.
6. **Failback'i unutmak.** Sadece failover'ı planlayıp geri dönüşü düşünmemek, birincil geri geldiğinde ikinci bir felakete yol açabilir.
7. **İkincil kapasiteyi yetersiz bırakmak.** Warm standby normalde küçük çalışıyorsa, tüm üretim yükünü emmek için failover anında ölçeklenmesi gerekir; ölçekleme başarısız olursa ikincil de çöker ("thundering herd").
8. **Bölgesel kotaları ve limitleri hesaba katmamak.** Felaket anında ikincil bölgede yeterli sunucu/kota ayrılmamışsa, tam da ihtiyaç anında kaynak bulunamaz.

## Somut Bir Örnek Üzerinden Karar

Bir e-ticaret ödeme sistemi düşünün:
- **Ödeme kayıtları:** Kayıp kabul edilemez → RPO ≈ 0 gerekir → aynı bölgedeki AZ'ler arası senkron replikasyon + uzak bölgeye asenkron kopya (kabul edilen küçük RPO ile felaket koruması).
- **Ürün kataloğu (çoğunlukla okuma):** Nadiren değişir, çakışma riski düşük → active-active ile her bölgede yerel okuma sunulabilir; düşük gecikme kazanılır.
- **Kullanıcı sepeti:** Nihai tutarlılık ve birleştirme mantığı (iki sepetin birleşimi) kabul edilebilir → active-active + uygulama düzeyinde çakışma çözümü.

Bu örnek şu ilkeyi gösterir: **Tek bir mimari tüm veriye uymaz.** Farklı veri sınıfları farklı tutarlılık, RPO ve RTO gereksinimlerine sahiptir; olgun sistemler her veri türü için ayrı strateji seçer.

## Özet

Çoklu bölge mimarisi, "tek konum eninde sonunda çöker" gerçeğine verilen mühendislik yanıtıdır. Tüm tasarım, iki ölçülebilir hedefe indirgenir: kabul edilebilir veri kaybı (**RPO**) ve kabul edilebilir kesinti (**RTO**). Bu hedeflere ulaşmanın yolu replikasyon seçiminden (senkron vs asenkron, ki bu doğrudan fizik ve gecikmeyle sınırlıdır), failover stratejisinden (active-passive'in basitliği vs active-active'in verimliliği ve çakışma karmaşıklığı) ve tutarlılık modelinden (CAP/PACELC dengeleri) geçer. En sık yapılan hatalar; AZ ile bölgeyi karıştırmak, planı test etmemek, split-brain'e karşı önlem almamak ve failback'i unutmaktır. Sağlam bir felaket kurtarma stratejisi, yazılmış bir belge değil, düzenli olarak kanıtlanmış (test edilmiş) bir davranıştır.
