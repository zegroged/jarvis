# Infrastructure as Code (Altyapının Kod Olarak Yönetimi)

## Tanım

Infrastructure as Code (IaC), sunucuları, ağları, güvenlik kurallarını, yük dengeleyicileri, veritabanlarını ve bunların birbirleriyle olan ilişkilerini elle konsollara tıklayarak değil, makine tarafından okunabilir tanım dosyalarıyla oluşturma, değiştirme ve yönetme disiplinidir. Kısaca söylemek gerekirse: altyapının nasıl görünmesi gerektiğini bir metin dosyasına yazarsınız, bir araç da o dosyayı okuyup gerçek dünyayı o tanıma uygun hâle getirir.

Bu tanım basit görünür ama içinde derin bir fikir barındırır: altyapı artık bir *artifact* değil, bir *kaynak koddur*. Yani sürüm kontrolüne (Git) girer, code review'dan geçer, test edilir, otomatik olarak dağıtılır ve geri alınabilir (rollback). Bir sunucunun neden ve ne zaman şu boyuta geldiğini "kimin aklında kaldıysa" diye sormak yerine, `git log` ile öğrenirsiniz.

IaC dünyasında iki temel yaklaşım vardır ve bu ayrım makalenin geri kalanını anlamak için kritiktir:

- **Provisioning (sağlama) araçları** — Terraform, Pulumi, CloudFormation gibi. Bunlar altyapıyı *var eder*: "Bana üç sanal makine, bir yük dengeleyici ve bir veritabanı ver."
- **Configuration management (yapılandırma yönetimi) araçları** — Ansible, Puppet, Chef, SaltStack gibi. Bunlar var olan makinelerin *içini düzenler*: "Şu sunuculara nginx kur, şu config dosyasını yerleştir, servisi başlat."

Bu iki dünya sık sık karıştırılır. Terraform ile Ansible rakip değil, çoğunlukla ardışık çalışan tamamlayıcı araçlardır: Terraform makineyi doğurur, Ansible onu terbiye eder.

## Kök neden: neden IaC'ye ihtiyaç doğdu?

IaC'yi "modaya uymak" olarak görmek yaygın ama yanlış bir bakıştır. Bu disiplin somut bir acıya çözüm olarak ortaya çıktı. O acının adı **configuration drift** (yapılandırma kayması) ve **snowflake server** (kar tanesi sunucu) problemidir.

Elle yönetilen bir altyapıyı düşünün. Bir mühendis üretim (production) sunucusuna SSH ile bağlanıp acil bir sorunu çözmek için bir paketi elle günceller. Başka biri bir config satırını değiştirir. Zamanla her sunucu, tıpkı kar taneleri gibi birbirinden minik ama önemli farklarla ayrılan, kimsenin tam olarak bilmediği bir duruma gelir. Bu sunucu çökerse, onu birebir yeniden kurabilecek kimse yoktur çünkü mevcut hâli hiçbir yerde yazılı değildir. İşte bu, drift'tir: gerçek durum ile herhangi bir belgelenmiş beklenti arasındaki uçurumun sessizce büyümesi.

IaC bu problemi kökten çözer çünkü **tek gerçek kaynağı (single source of truth)** koda taşır. Sunucunun nasıl olması gerektiğinin tanımı artık birinin hafızasında değil, versiyon kontrolündeki bir dosyadadır. Bu şu üç temel faydayı getirir:

1. **Tekrarlanabilirlik (reproducibility):** Aynı kodu çalıştırırsanız aynı altyapıyı alırsınız. Test, staging ve production ortamlarını birebir aynı tanımdan üretebilirsiniz. "Bende çalışıyordu" bahanesi altyapı seviyesinde ölür.
2. **İzlenebilirlik (auditability):** Her değişiklik bir commit'tir. Kimin, neyi, ne zaman, neden değiştirdiği bellidir.
3. **Ölçeklenebilirlik:** Üç sunucuyu elle kurmak sıkıcıdır ama mümkündür. Üç yüz sunucuyu elle kurmak insani bir hatadır. Kod, sayının bir önemi olmadığı yerdir.

## İki temel kavram: Idempotency ve State

IaC'nin ruhunu anlamak için iki kavramı derinlemesine sindirmek gerekir. Bunlar birbirine bağlıdır ama farklı problemleri çözerler.

### Idempotency (değişmezlik / aynı sonuç güvencesi)

**Idempotency**, bir işlemi bir kez ya da yüz kez çalıştırmanın sonuçta aynı duruma yol açması özelliğidir. Matematikten gelen bir kavramdır: `f(f(x)) = f(x)`. Bir fonksiyonu tekrar tekrar uygulamak, ilk uygulamadan sonra durumu değiştirmiyorsa o fonksiyon idempotent'tir.

Neden bu kadar önemli? Çünkü IaC araçları çoğu zaman "her şeyi baştan kur" mantığıyla değil, "mevcut durumu istenen duruma yaklaştır" mantığıyla çalışır. Bir betiği (script) düşünün:

```bash
# Idempotent DEĞİL — imperatif düşünce
echo "10.0.0.5 db.internal" >> /etc/hosts
```

Bu satır her çalıştığında dosyaya bir satır daha ekler. Üç kez çalıştırırsanız üç kopya olur. Bu **imperative** (buyurgan) yaklaşımdır: "şunu yap" der, sonucun ne olduğuyla ilgilenmez.

IaC araçları bunun yerine **declarative** (bildirimsel) yaklaşımı benimser: "sonuç şu olsun" dersiniz, aracın kendisi mevcut durumu okuyup gerekli olup olmadığına karar verir.

```yaml
# Ansible — idempotent, declarative
- name: db.internal kaydı /etc/hosts icinde bulunsun
  ansible.builtin.lineinfile:
    path: /etc/hosts
    line: "10.0.0.5 db.internal"
    state: present
```

Bu görev ilk çalıştığında satırı ekler ("changed"). İkinci çalıştığında satırın zaten var olduğunu görür ve hiçbir şey yapmaz ("ok"). İşte idempotency budur: aracı defalarca çalıştırmak güvenlidir, yan etki üretmez.

**Kök neden olarak** idempotency neden zorunludur? Çünkü gerçek dünyada işlemler yarıda kalır. Ağ kopar, bir makine cevap vermez, bir uygulama zaman aşımına uğrar. İdempotent olmayan bir sistemde yarıda kalan bir işlemi yeniden çalıştırmak felakettir — çift kayıt, bozuk config, ikiye katlanan kaynaklar. İdempotent bir sistemde ise çözüm basittir: **tekrar çalıştır.** Araç kaldığı yerden değil, "istenen durum neyse oraya" doğru hareket eder. Bu, IaC'yi güvenilir kılan temel emniyet mekanizmasıdır.

Ansible'da idempotency büyük ölçüde *modüllerin* sorumluluğundadır. `lineinfile`, `copy`, `package`, `service` gibi yerleşik modüller idempotent tasarlanmıştır. Ama tehlike şuradadır: `command` ve `shell` modülleri ham komut çalıştırır ve **idempotent değildir**. `shell: "echo x >> file"` yazarsanız Ansible'ın idempotency güvencesini kendi elinizle bozarsınız. Bu yüzden ham kabuk komutları IaC'de bir son çare olmalıdır.

### State (durum) — özellikle Terraform'da

Terraform (ve genel olarak provisioning araçları) için asıl kalp kavram **state**'tir. State, Terraform'un "gerçek dünyada şu anda neyin var olduğuna dair inancını" tutan kayıttır. Genellikle `terraform.tfstate` adlı bir JSON dosyasında saklanır.

Neden state gerekir? Terraform üç şeyi karşılaştırmak zorundadır:

1. **Yapılandırma (config):** Sizin `.tf` dosyalarında yazdığınız, olması gereken durum.
2. **State:** Terraform'un en son bildiği durum.
3. **Gerçek altyapı:** Bulut sağlayıcısının API'sinde şu anda gerçekten var olan durum.

Terraform `plan` komutunu çalıştırdığınızda bu üçünü kıyaslar ve gerçeği config'e uydurmak için gereken minimum değişiklik setini üretir. State olmadan Terraform, bir kaynağı sizin config'inizle eşleştiremez. Örneğin config'te bir sunucunun adını değiştirirseniz, state olmadan Terraform bunun "var olan sunucunun yeniden adlandırılması mı yoksa yeni bir sunucu mu" olduğunu bilemez.

**Kök neden:** Bulut API'lerinin çoğu, "ben bunu daha önce oluşturmuş muydum" sorusuna doğrudan cevap veremez. Terraform bir kaynak oluşturduğunda ona bir kimlik (ID) atanır ve bu ID ile sizin config'teki mantıksal isim (`aws_instance.web`) arasındaki eşleştirmeyi bir yerde tutmak zorundadır. İşte state bu eşleştirme defteridir. State'i silerseniz Terraform, gerçekte var olan kaynakların *kendisine ait olduğunu unutur* ve config'i tekrar uyguladığınızda hepsini yeniden oluşturmaya çalışır — bu da mevcut kaynaklarla çakışmalara veya beklenmedik silme/yeniden yaratma döngülerine yol açar.

State ayrıca **hassas veri** içerir. Veritabanı şifreleri, özel anahtarlar, IP adresleri state dosyasında düz metin olarak durabilir. Bu yüzden state dosyası asla Git'e commit'lenmemelidir.

## Somut örnek: Terraform ile bir web sunucusu

Aşağıdaki basitleştirilmiş örnek, declarative yaklaşımın nasıl göründüğünü gösterir:

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.micro"

  tags = {
    Name = "uretim-web-01"
  }
}
```

Bu bloğu ilk kez `terraform apply` ile uyguladığınızda Terraform bir makine oluşturur ve state'e "ben `aws_instance.web`'i oluşturdum, ID'si i-0xyz" diye yazar. İkinci kez `apply` çalıştırdığınızda plan boş çıkar: state ile config ve gerçek dünya birbirini tutar, yapılacak bir şey yoktur. İşte Terraform'un declarative + state kombinasyonundan doğan idempotent davranışı budur.

Şimdi `instance_type`'ı `t3.small` yaparsanız, `plan` size şunu söyler: bu değişiklik makinenin yeniden başlatılmasını (veya bazı durumlarda yok edilip yeniden yaratılmasını) gerektirir. Terraform hangi değişikliklerin *yerinde güncelleme (update in-place)*, hangilerinin *yok et ve yeniden yarat (destroy and recreate)* gerektirdiğini kaynak tipine göre bilir. Bu ayrımı görmeden `apply` yapmak, çoğu üretim kazasının kaynağıdır.

### Terraform ve Ansible birlikte

Tipik bir akış şöyle işler:

1. Terraform bulutta üç sanal makine, ağ ve güvenlik kurallarını oluşturur ve çıktı (output) olarak IP adreslerini verir.
2. Bu IP'ler Ansible'ın envanterine (inventory) aktarılır.
3. Ansible her makineye bağlanır, gerekli paketleri kurar, uygulama config'ini yerleştirir ve servisleri başlatır.

Buradaki iş bölümü mantıklıdır: Terraform *kutunun kendisiyle*, Ansible *kutunun içindekiyle* ilgilenir. Terraform'u bir makinenin içine paket kurmak için zorlamak (örneğin `remote-exec` provisioner'ları) genellikle bir anti-pattern kabul edilir, çünkü bu iş Terraform'un state ve idempotency modeline uymaz — provisioner'lar state'te güvenilir şekilde izlenmez ve idempotent değildir.

## Doğru kullanım ve tuzaklar

### State'i uzak ve kilitli tutun (remote state + locking)

Yerel `terraform.tfstate` dosyası tek kişilik projeler dışında bir tehlikedir. İki mühendis aynı anda `apply` çalıştırırsa state bozulur (state corruption). Çözüm **remote backend**'dir: state'i paylaşılan, sürümlenen ve kilitlenebilen bir yerde (örneğin bir object storage servisi + bir kilit mekanizması) tutmak.

**State locking** kritiktir: bir kişi `apply` çalıştırırken state kilitlenir, ikinci kişi beklemek zorunda kalır. Kilit olmadan iki eşzamanlı işlem — klasik bir **race condition** — state'i tutarsız hâle getirebilir. Bu, IaC'de kurtarması en zor arızalardan biridir.

### Elle müdahale etmeyin

IaC'nin en büyük ihlali, altyapıyı bir kez koda geçirdikten sonra konsola girip elle değişiklik yapmaktır. Bu, drift'i geri getirir. Terraform bir sonraki `plan`'da bu elle yapılan değişikliği görür ve onu "config'e uymayan bir sapma" olarak yorumlayıp geri almak (silmek) isteyebilir. Kural nettir: **kod ile yönetilen kaynağa elle dokunulmaz.** Değişiklik gerekiyorsa kod değişir.

### Küçük ve gözden geçirilebilir değişiklikler yapın

`terraform plan` çıktısı sizin en güçlü güvenlik ağınızdır. `apply`'dan önce planı *okumak* zorundasınız. "3 to add, 1 to change, 0 to destroy" satırındaki **destroy** sayısı sıfırdan farklıysa durup düşünün: neyi yok ediyorsunuz? O bir veritabanı mı? Plan'ı otomatik onaylayıp (`-auto-approve`) geçmek, üretimde bir veritabanını yanlışlıkla silmenin en hızlı yoludur.

## Gözden geçirme (review): IaC'nin en kritik ama en çok ihmal edilen adımı

IaC'nin gücü altyapıyı koda çevirmesidir; ama bu güç, kodun *gözden geçirilmesiyle* gerçek değere dönüşür. Uygulama kodunda bir bug en fazla bir özelliği bozar; altyapı kodunda bir bug tüm production'ı silebilir. Bu yüzden IaC review'ı, normal code review'dan daha yüksek bir titizlik gerektirir.

### Plan çıktısını review'ın merkezine koyun

En iyi ekipler, pull request'e sadece kod değişikliğini değil, o değişikliğin ürettiği `terraform plan` çıktısını da ekler (çoğu CI sistemi bunu otomatik olarak PR'a yorum olarak basar). Böylece gözden geçiren kişi soyut kodu değil, o kodun gerçek dünyada *ne yapacağını* görür. "Bu değişiklik neden 5 kaynağı yok ediyor?" sorusu, kod satırlarına bakarak değil, plan çıktısına bakarak sorulur.

### Review sırasında sorulması gereken sorular

- Bu değişiklik herhangi bir **stateful** kaynağı (veritabanı, disk, kalıcı depolama) yok edip yeniden yaratıyor mu? Bu, veri kaybı demektir.
- Değişiklik idempotent mi? Ansible tarafında `command`/`shell` kullanımı var mı, varsa gerçekten gerekli mi ve bir `creates`/`changed_when` koşuluyla korunuyor mu?
- Hassas veriler (secret'lar) koda gömülmüş (hardcoded) mü? Secret'lar koda değil, bir secret yönetim sistemine ait olmalıdır.
- Değişikliğin **blast radius**'u (etki yarıçapı) nedir? Tek bir servisi mi, yoksa paylaşılan bir ağ bileşenini mi etkiliyor?
- Bir geri alma (rollback) yolu var mı? Bu değişiklik ters giderse önceki commit'e dönmek güvenli mi?

### Otomatik denetim (policy as code)

İnsan gözü yorulur ve kaçırır. Bu yüzden olgun ekipler review'ı otomatikleştirir: **policy as code** araçları (örneğin plan çıktısını kurallara karşı denetleyen politika motorları), "hiçbir depolama alanı herkese açık olamaz" ya da "production veritabanı silinemez" gibi kuralları CI aşamasında zorunlu kılar. Ayrıca statik analiz araçları, IaC kodunu daha `apply` çalışmadan güvenlik yanlış yapılandırmaları (açık portlar, şifrelenmemiş diskler) için tarar. Bu araçlar insan review'ının yerini almaz, onu tabandan güçlendirir.

## Yaygın hatalar

**State dosyasını Git'e commit'lemek.** Hem güvenlik açığıdır (secret'lar sızar) hem de eşzamanlı çalışmada çakışma yaratır. State remote backend'de durmalıdır.

**Idempotency'yi `shell`/`command` ile bozmak.** Ansible'ın gücü modüllerin idempotency güvencesindedir. Her şeyi ham kabuk komutuyla yapmak, Ansible'ı pahalı bir SSH betiği çalıştırıcısına indirger.

**Plan'ı okumadan apply etmek.** `-auto-approve` bayrağını gözü kapalı kullanmak, review kültürünün olmadığı yerlerde en sık görülen felaket sebebidir. İnsan tarafından tetiklenen apply'larda plan mutlaka okunmalıdır; sadece CI/CD gibi kontrollü, testli boru hatlarında otomatik onay makul olabilir.

**Kopyala-yapıştır ile devasa monolitik konfigürasyonlar.** Her ortam için (dev, staging, prod) kodu kopyalamak, drift'i koda taşır. Bunun yerine **modüller** ve değişkenlerle parametreleştirme kullanılmalıdır: aynı modül, farklı değişken değerleriyle üç ortamı da üretir.

**Elle müdahale (out-of-band changes).** Koda geçirilmiş bir kaynağı konsoldan değiştirmek, drift'in ana kaynağıdır ve bir sonraki apply'da sürprizlere yol açar.

**Her şeyi tek bir dev state'te toplamak.** Tüm altyapıyı tek bir state dosyasında tutmak, her küçük değişiklikte tüm altyapıyı riske atar ve plan'ları yavaşlatır. Mantıksal olarak ayrılmış, birbirinden bağımsız state'ler (örneğin ağ katmanı ayrı, uygulama katmanı ayrı) blast radius'u küçültür.

**Sürüm sabitlememek (unpinned versions).** Ne provider, ne modül, ne de aracın kendi sürümünü sabitlememek, "dün çalışan bugün çalışmıyor" arızalarına yol açar. Sürümler açıkça sabitlenmeli (pin) ve kontrollü biçimde yükseltilmelidir.

## En iyi pratikler

**Her şeyi versiyon kontrolüne koyun ve doğrudan production'a apply etmeyin.** IaC kodu Git'te yaşar, değişiklikler PR üzerinden gider, review'dan geçer ve bir CI/CD boru hattı tarafından uygulanır. İnsanların kendi makinelerinden production'a `apply` yapması ortadan kaldırılmalıdır.

**Ortamları aynı koddan, farklı değişkenlerle üretin.** Dev, staging ve prod arasındaki tek fark değişken değerleri (boyut, sayı, isim) olmalı; kodun kendisi aynı kalmalıdır. Bu, "staging'de çalıştı ama prod'da patladı" sınıfı hataları büyük ölçüde ortadan kaldırır.

**Küçük, sık ve geri alınabilir değişiklikler yapın.** Yüz kaynağı değiştiren dev bir PR'ı gözden geçirmek imkânsızdır. Küçük değişiklikler hem review edilebilir hem de bir şey ters gittiğinde suçluyu bulmak kolaydır.

**Secret'ları koddan ayırın.** Şifreler ve anahtarlar asla `.tf` ya da `.yml` dosyalarına yazılmaz. Bunlar bir secret yönetim sistemine konur ve çalışma anında enjekte edilir. State'in de şifrelenmesi gerektiğini unutmayın.

**Idempotency'yi bir test kriteri olarak görün.** Ansible playbook'unuzu iki kez çalıştırın: ikinci çalıştırmada hiçbir görev "changed" dememelidir. Eğer diyorsa, bir yerde idempotent olmayan bir görev vardır ve bu gizli bir drift kaynağıdır. Bu basit "iki kez çalıştır" testi, IaC kalitesinin en ucuz göstergesidir.

**State'i kutsal sayın.** Remote, şifreli, kilitli, sürümlü ve yedekli tutun. State'i elle düzenlemek zorunda kaldığınızda (nadiren gerekir) araçların sunduğu güvenli komutları (import, move, remove gibi) kullanın, JSON'u editörle kurcalamayın.

**Plan'ı review'ın kanıtı yapın.** `apply`, sadece review edilmiş ve onaylanmış bir plan üzerinden çalışmalıdır. İnsan gözü + otomatik policy denetimi + statik güvenlik taraması: bu üçlü, IaC'yi hızlı olduğu kadar güvenli de kılar.

## Özet

Infrastructure as Code, altyapıyı belleklerden çıkarıp koda taşıyan bir disiplindir. İki temel araç ailesi vardır: altyapıyı var eden provisioning araçları (Terraform) ve makinelerin içini düzenleyen configuration management araçları (Ansible); bunlar rakip değil, ardışık çalışan ortaklardır. Bu disiplini güvenilir kılan iki kavram idempotency ve state'tir: idempotency, aynı işlemi defalarca çalıştırmayı güvenli kılarak arıza kurtarmayı basitleştirir; state ise Terraform'un gerçek dünya ile config arasındaki köprüsüdür ve bu yüzden korunması gereken en değerli varlıktır. Son olarak, IaC'nin gerçek değeri gözden geçirme kültüründe ortaya çıkar: plan çıktısını okumak, blast radius'u sorgulamak ve otomatik politikalarla insan gözünü desteklemek, bir metin dosyasını yanlışlıkla tüm production'ı silen bir silaha dönüşmekten alıkoyan şeydir.
