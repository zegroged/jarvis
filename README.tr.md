# Jarvis — Sıfırdan Kişisel Dil Modeli (Faz 1)

Hedef: Türkçe konuşan, yazılım dillerini ve siber güvenliği bilen kişisel bir asistan.
Bu depo o yolun **1. fazı**: tamamı elle, sıfırdan yazılmış ve bu laptopta eğitilen
küçük bir Transformer (GPT) dil modeli.

## Dürüst beklenti

- Model **~17M parametre** olacak. Kıyas için: GPT-2'nin en küçüğü 124M, Claude/GPT-4
  sınıfı modeller yüz milyarlarca parametre. 6 GB VRAM'in gerçekçi sınırı bu.
- İlk hedef "akıllılık" değil: **tutarlı Türkçe cümleler üretebilmesi** bile başarıdır.
- Asıl değer: her satırını bizim yazdığımız, ileride daha güçlü donanımda
  büyütülebilecek bir iskelet ve bu süreçte öğrenilenler.

## Donanım

RTX 3050 Laptop (6 GB VRAM) · i5-12450HX · 16 GB RAM · Windows 11 · Python 3.12

## Kurulum

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install numpy tqdm tokenizers requests
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python.exe src\test_kurulum.py   # her şey çalışıyor mu?
```

## Proje yapısı

```
src/
  config.py          → model + eğitim ayarları + talimat şablonu  [tek gerçek kaynak]
  model.py           → sıfırdan GPT: attention, MLP, bloklar      [ADIM 2 ✔]
  test_kurulum.py    → kurulum + GPU doğrulama testi              [ADIM 1 ✔]
  prepare_data.py    → veri toplama / temizleme                   [ADIM 3 ✔]
  train_tokenizer.py → Türkçe BPE tokenizer eğitimi               [ADIM 4 ✔]
  binlestir.py       → metni token id'lerine çevir (uint16 .bin)  [ADIM 5 ✔]
  train.py           → eğitim döngüsü (loss takibi, checkpoint)   [ADIM 5]
  generate.py        → eğitilmiş modelle metin üretimi            [ADIM 6 ✔]
  chat.py            → terminalde Türkçe metin sürdürme arayüzü   [ADIM 6 ✔]

  # --- FAZ 1.5: Talimat ince ayarı (soru-cevap davranışı) ---
  prepare_instruct.py → Türkçe talimat verisi indir/biçimle       [1.5-A ✔]
  finetune.py         → kayıp maskeli ince ayar (yalnız yanıttan) [1.5-B]
  chat_instruct.py    → asistan gibi soru-cevap sohbeti           [1.5-C ✔]
data/                → ham ve işlenmiş veri (git'e girmez)
checkpoints/         → model ağırlıkları (git'e girmez)
```

## Faz 1.5 — Talimat ince ayarı (neden ve nasıl)

Taban model "metin sürdürücü"dür: soru sorulunca cevap vermez, metni devam
ettirir. Faz 1.5, ~31.500 Türkçe `talimat → yanıt` örneğiyle kısa bir ek eğitim
yaparak **cevap verme formatını** öğretir. İki teknik önemli:

- **Kayıp maskeleme:** Model yalnızca *yanıt* tokenlarından öğrenir; soru
  tokenları maskelenir (`ignore_index=-1`). Böylece soruyu ezberlemez, "böyle
  bir soruya böyle cevap verilir" ilişkisini kurar.
- **Düşük öğrenme oranı:** Tabanın öğrendiklerini silmemek için (1e-4).

Çalıştırma sırası: `prepare_instruct.py` → (taban eğitimi bitince) `finetune.py`
→ `chat_instruct.py`. Dürüst beklenti: cevaplar kısa ve çoğu zaman hatalı olur;
başarı ölçütü "doğru bilgi" değil, "soruya uygun, düzgün Türkçe cevap formatı".

## Faz 2 — Yerel "üretim beyni" (Qwen2.5-Coder-7B)

Sıfırdan yazdığımız 17M model bir öğrenme çekirdeği; gerçekten çalışan kod ve
düzgün güvenlik tavsiyesi için **yerel açık-ağırlıklı bir kod modeli** kullanıyoruz.
Bu bir API **değil**: model dosyası `models/` altında, senin diskinde, internetsiz
çalışır, hiçbir veri dışarı gitmez.

- Model: `Qwen2.5-Coder-7B-Instruct` (GGUF, Q4_K_M, ~4.7 GB) — 6 GB VRAM'e
  kısmi GPU offload ile sığar.
- Çalıştırıcı: `llama-cpp-python` (CUDA wheel; modeli kendi projemizin içinde
  yükler — ayrı bir servis/uygulama yok).
- Arayüz: `src/jarvis_coder.py` — Türkçe konuşan, yazılım+güvenlik odaklı, savunma
  çerçeveli bir sistem istemiyle.

```powershell
.venv\Scripts\python.exe src\jarvis_coder.py                 # sohbet
.venv\Scripts\python.exe src\jarvis_coder.py --tekil "SQL injection nasıl önlenir?"
```

Sonraki adımlar: (Faz 2b) QLoRA ile Türkçe/güvenlik ince ayarı; (Faz 3) araç
kullanımı — komut çalıştırma, kod analizi, güvenlik taraması.

## Faz 3 — Jarvis "eyleme geçiyor" (araç kullanımı) ✔

Jarvis artık sadece konuşmaz; senin bilgisayarında **araç kullanarak iş yapar**.
`src/jarvis_agent.py` bir ajan döngüsü kurar: Jarvis "şu aracı çağır" der (JSON),
biz çalıştırıp sonucu geri veririz, o devam eder ya da nihai cevabı verir.

**18 araç, 4+ modül:**
- **Çekirdek:** `komut_calistir` (PowerShell) · `dosya_oku` · `dosya_yaz` ·
  `dizin_listele` · `dosya_ara` · `python_calistir`
- **Güvenlik:** `guvenlik_tara` (bandit statik analiz) · `bagimlilik_denetle`
  (pip-audit CVE) · `sir_ara` (koda sızmış anahtar/parola) · `port_tara` ·
  `hash_tanimla` · `base_coz` (base64/hex/url) · `http_baslik_denetle` (güvenlik
  başlıkları) · `ssl_denetle` (TLS) · `guvenli_parola_uret` · `dosya_hash`
- **Bilgi tabanı (RAG):** `bilgi_ara` — **56.322 parça, güvenlik + yazılım**.
  Güvenlik: OWASP (CheatSheets/WSTG/ASVS/MASTG/Top10/API), PayloadsAllTheThings,
  HackTricks, h4cker, MITRE ATT&CK, **CWE zafiyet katalogu**, nginx güvenliği,
  Kubernetes. Yazılım: Python (cpython Doc), **C#/.NET**, **Rust**, Django, FastAPI,
  JS (You-Dont-Know-JS), System Design, algoritmalar. Cevabı otoriter kaynağa dayandırır.
  (Go/Java/C++ resmi md dokümanı yayınlamadığından RAG'da zayıf — model genel bilgisi kullanılır.)
  **İki aşamalı arama:** (1) hibrit aday çekme — anlamsal (çok dilli e5-base
  embedding) + kelime (BM25); (2) **reranking** — cross-encoder (bge-reranker) ile
  adayları yeniden sıralama (hibrit-ağırlıklı harman). Türkçe soru İngilizce
  dokümanı bulur. Kur: `python src\rag_kur.py` sonra `python src\rag_embed_kur.py`.

**Daha büyük model takma:** `jarvis_agent.py` `models/` altındaki en büyük `.gguf`'ı
otomatik seçer; ya da `JARVIS_MODEL` ortam değişkeniyle yol ver. (14B indirirsen
6 GB'da yavaş çalışır — gerçek sıçrama için bulut/Kademe B gerekir.)
- **Mavi takım:** `log_analiz` — log dosyasında şüpheli desen/IOC taraması

**RAG kurulumu** (bir kez): `python src\rag_kur.py` → `data/processed/guvenlik_rag.pkl`.

```powershell
.venv\Scripts\python.exe src\jarvis_agent.py                    # sohbet
.venv\Scripts\python.exe src\jarvis_agent.py --tekil "src/rag.py'de güvenlik açığı var mı?"
.venv\Scripts\python.exe src\jarvis_agent.py --otonom           # onaysız (dikkatli)
```

**Emniyet kemeri:** yıkıcı komutlar (sil/format) ve mevcut dosya üzerine yazma
**onay** ister — modelin bir hatasından seni korur, `--otonom` ile kapatılabilir.

**Sağlamlık (7B'yi ajanda ehlileştirmek):** bağlam penceresi otomatik kırpılır,
döngü tespiti + araç bütçesi (aynı araç 3 / toplam 7 çağrıdan sonra cevap zorlanır),
esnek cevap ayrıştırma. Dürüst not: 7B bazen yanlış araç seçer ya da konudan sapar;
bu mekanizmalar yine de doğru cevaba yakınsamasını sağlar. Asıl akıl araçlarda ve
bilgi tabanında, modelde değil.

**Modül 5 (sonraki faz):** ses katmanı (Whisper STT + TTS) ve otonom izleme.
6 GB'da model + ses aynı anda sıkışık; ayrı bir çalışma gerektirir.

## Yol haritası

- **Faz 1 (bu depo):** küçük GPT + Türkçe tokenizer + eğitim + terminal sohbeti
- **Sonraki fazlar:** daha büyük veri ve model, fine-tune, araç kullanımı
  (komut çalıştırma, güvenlik taramaları), ses katmanı. Bunlar daha güçlü
  donanım/bütçe gerektirir — şimdilik kapsam dışı.
