"""
6b. ADIM: Terminalde basit Turkce sohbet arayuzu.

Ne yapar:
  - Egitilmis modeli ve tokenizer'i yukler
  - Dongu: sen yaz -> model devam ettirsin -> cevabi yazdir
  - Kisa bir gecmis tutar (son konusmalar block_size'a sigacak sekilde kirpilir)

DURUST NOT: Bu model bir "soru-cevap asistani" olarak DEGIL, "metin devam
ettirici" olarak egitildi. Yani sorularini akilli sekilde yanitlamasini bekleme;
verdigin metni istatistiksel olarak surdurur. Gercek asistan davranisi icin
ileride kucuk bir talimat (instruction) veri setiyle ince ayar (fine-tune)
gerekir — bu, sonraki fazlarin isi.

Cikmak icin: 'cikis', 'quit' veya Ctrl+C.

Calistirma (proje kokunden):
    .venv\\Scripts\\python.exe src\\chat.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from tokenizers import Tokenizer

from config import BELGE_SONU, TOKENIZER_YOLU
from generate import model_yukle
from model import GPT  # noqa: F401  (model_yukle icinde kullaniliyor)


def ana():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = Tokenizer.from_file(str(TOKENIZER_YOLU))
    model, yol, adim = model_yukle(device, en_iyi=True)
    block_size = model.cfg.block_size
    amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    bs_id = tokenizer.token_to_id(BELGE_SONU)

    print("=" * 60)
    print(f"Jarvis-mini sohbet  [{yol.name}, {adim}. adim, {device}]")
    print("=" * 60)
    print("Not: Bu bir 'metin devam ettirici'. Cikmak icin: cikis / quit / Ctrl+C\n")

    # Sohbet gecmisini token id'leri olarak biriktiririz; boylece model
    # onceki konusmayi 'baglam' olarak gorur.
    gecmis_ids = []

    while True:
        try:
            girdi = input("Sen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGorusuruz!")
            break
        if girdi.lower() in ("cikis", "quit", "exit"):
            print("Gorusuruz!")
            break
        if not girdi:
            continue

        # Kullanici metnini gecmise ekle, sonuna bir bosluk koy ki model
        # cevabi ayri bir kelimeden baslasin
        gecmis_ids += tokenizer.encode(girdi + "\n").ids

        # Baglam sinirini asma: uretime yer birakmak icin sondan kirp
        uretilecek = 80
        azami_baglam = block_size - uretilecek
        if len(gecmis_ids) > azami_baglam:
            gecmis_ids = gecmis_ids[-azami_baglam:]

        x = torch.tensor(gecmis_ids, dtype=torch.long, device=device)[None, ...]
        with torch.amp.autocast("cuda", dtype=amp_dtype) if device == "cuda" \
                else _bos():
            y = model.generate(x, max_new_tokens=uretilecek, temperature=0.8,
                               top_k=50, repetition_penalty=1.3)

        # Sadece YENI uretilen kismi al (girdiden sonrasi)
        yeni_ids = y[0].tolist()[len(gecmis_ids):]
        # Model bir 'belgesonu' urettiyse cevabi orada kes (dogal duraklama)
        if bs_id in yeni_ids:
            yeni_ids = yeni_ids[:yeni_ids.index(bs_id)]
        cevap = tokenizer.decode(yeni_ids, skip_special_tokens=True).strip()

        print(f"Jarvis> {cevap}\n")
        # Uretilen cevabi da gecmise ekle (konusma akisi sursun)
        gecmis_ids += yeni_ids


class _bos:
    def __enter__(self): return self
    def __exit__(self, *a): return False


if __name__ == "__main__":
    ana()
