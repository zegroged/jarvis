# Jarvis Bilgi Hazinesi

> Bu klasör, gelecekteki (güçlü donanımlı) Jarvis eğitimi için elle yazılmış,
> yoğunlaştırılmış Türkçe uzman bilgisidir. Amaç: siber güvenlik ve yazılım
> alanında, açık kaynakta bulunması zor olan **sentezlenmiş Türkçe uzman metni**
> biriktirmek. Genel kültür / bağlam anlama ucuzdur; asıl zor ve değerli olan
> derin alan bilgisidir — bu klasör tam olarak onu hedefler.

## Bu neden değerli (dürüst gerekçe)

- Açık kaynakta bol miktarda **İngilizce** güvenlik/yazılım metni var (OWASP,
  MITRE, HackTricks, döküman siteleri). Bunlar zaten `data/corpus/` içinde.
- Açık kaynakta **çok az** kaliteli, uzman seviyesi, bağlantıları kurulmuş
  **Türkçe** alan metni var. İşte bu boşluğu bu klasör doldurur.
- Bir modeli eğitirken en çok işine yarayan şey, bir konuyu *neden-nasıl*
  bağlamıyla anlatan, kavramları birbirine bağlayan yoğun metindir. Liste
  değil, akıl yürüten anlatı. Bu dosyalar öyle yazıldı.

## Dürüst sınırlar (unutma)

1. Bu metin bir modelin **ağırlıkları** değil, **eğitim hammaddesidir.** Tek
   başına bir model değil; onunla bir model eğitilir.
2. Bu bilgi bugünkü (2026 başı) anlayışıma dayanır. Güvenlikte ayrıntılar
   (CVE'ler, sürümler, araç bayrakları) hızla eskir; kavramlar yavaş eskir.
   Bu yüzden kavram ve yöntem ağırlıklı yazıldı, tek tek exploit değil.
3. "Her şey" burada yok — olamaz. Bu büyüyen bir hazine. Her oturumda bir
   cilt daha derinleşir.

## Eğitimde nasıl kullanılır

Bu dosyalar iki farklı eğitim biçimine de uygundur:

- **Continued pre-training / RAG (doğrudan):** Metinler temiz, başlıklı düzyazı.
  `data/raw/uzman/` altına zip'lenip `python src/korpus_kur.py` çalıştırılınca
  korpusa katılır; ya da RAG bilgi tabanına eklenir.
- **Instruction fine-tuning (dönüştürerek):** Her başlık/altbaşlık bir
  soru-cevap çiftine çevrilebilir (örn. "SSRF nedir ve nasıl savunulur?" →
  ilgili bölüm). Bu dönüşüm ileride bir betikle otomatikleştirilebilir.

Öneri: Yeni donanımda önce bu metinle **continued pre-training** (modelin dile
ve alana ısınması), sonra ondan türetilmiş **instruction çiftleriyle** ince
ayar. İkisi birlikte, tek başına ince ayardan çok daha iyi sonuç verir.

## İçindekiler

- `01_siber_guvenlik.md` — Siber güvenliğin bütünü: ilkeler, kriptografi,
  kimlik doğrulama, web güvenliği (OWASP derinlemesine), ağ güvenliği, yetki
  yükseltme, Active Directory, binary exploitation, tersine mühendislik,
  bulut/konteyner, mavi takım/tespit, pentest metodolojisi.
- `02_yazilim.md` — Yazılım mühendisliğinin bütünü: paradigmalar, veri
  yapıları/algoritmalar, bellek ve sistem programlama, eşzamanlılık, işletim
  sistemleri, ağlar, veritabanları, sistem tasarımı, mühendislik pratikleri,
  diller (Python/C/Rust/Go/JS/C#), güvenli kod yazımı.

## Sıradaki ciltler (planlanan — onayla, yazayım)

Her biri kendi başına derin bir dosya olabilir:
- `03_web_exploit_derin.md` — her OWASP sınıfı için sömürü + savunma laboratuvarı düzeyinde
- `04_binary_exploitation.md` — stack/heap/ROP/format string uçtan uca
- `05_active_directory.md` — Kerberos saldırıları, delegation, BloodHound yolları
- `06_mavi_takim_tespit.md` — detection engineering, SIEM kuralları, IR/forensics
- `07_kriptografi_derin.md` — protokoller, saldırılar, doğru kullanım kalıpları
- `08_sistem_tasarimi_derin.md` — büyük ölçekli mimari, dağıtık sistemler
- `09_guvenli_kod_dilbazli.md` — dil dil secure coding kalıpları

---
*Yazan: Claude (Jarvis projesi asistanı). Türkçe, teknik terimler İngilizce korunmuştur.*
