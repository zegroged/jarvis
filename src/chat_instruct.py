"""
FAZ 1.5 - ADIM C: Ince ayarli modelle Turkce asistan sohbeti.

chat.py'den farki: bu, her girdini talimat sablonuna ("### Talimat:\\n...\\n
### Yanit:\\n") sarar ve yaniti <|belgesonu|>'a kadar uretir. Yani "metin devam
ettirme" degil, "soruya cevap verme" davranisi hedeflenir.

DURUST NOT: Model 17M parametre; cevaplar cogu zaman kisa, bazen hatali ya da
uydurma olacak. Basari olcutu "dogru bilgi" degil, "soru sorulunca konuya
uygun, duzgun Turkce bir cevap FORMATI uretmesi".

Cikmak: cikis / quit / Ctrl+C.

Calistirma (finetune.py bittikten sonra):
    .venv\\Scripts\\python.exe src\\chat_instruct.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from tokenizers import Tokenizer

from config import BELGE_SONU, CHECKPOINT_DIR, TOKENIZER_YOLU, ModelConfig, istem_olustur
from model import GPT

MODEL_YOLU = CHECKPOINT_DIR / "jarvis_instruct.pt"


def ana():
    if not MODEL_YOLU.exists():
        sys.exit(f"[HATA] Ince ayarli model yok: {MODEL_YOLU}. Once finetune.py calistir.")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = Tokenizer.from_file(str(TOKENIZER_YOLU))
    bs_id = tokenizer.token_to_id(BELGE_SONU)

    ckpt = torch.load(MODEL_YOLU, map_location=device)
    m_cfg = ModelConfig(**ckpt["model_config"]) if "model_config" in ckpt else ModelConfig()
    model = GPT(m_cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    ctx = (torch.amp.autocast("cuda", dtype=amp_dtype) if device == "cuda"
           else _bos())

    print("=" * 60)
    print(f"Jarvis-mini (ince ayarli)  [{MODEL_YOLU.name}, {device}]")
    print("=" * 60)
    print("Soru sor, cevap vermeye calisir. Cikis: cikis / quit / Ctrl+C\n")

    while True:
        try:
            soru = input("Sen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGorusuruz!")
            break
        if soru.lower() in ("cikis", "quit", "exit"):
            print("Gorusuruz!")
            break
        if not soru:
            continue

        istem = istem_olustur(soru)
        ids = tokenizer.encode(istem).ids
        # Baglama sigma: uretime yer birak
        ids = ids[-(m_cfg.block_size - 120):]
        x = torch.tensor(ids, dtype=torch.long, device=device)[None, ...]
        with ctx:
            y = model.generate(x, max_new_tokens=120, temperature=0.7,
                               top_k=40, repetition_penalty=1.3)
        yeni = y[0].tolist()[len(ids):]
        if bs_id in yeni:
            yeni = yeni[:yeni.index(bs_id)]
        cevap = tokenizer.decode(yeni, skip_special_tokens=True).strip()
        print(f"Jarvis> {cevap}\n")


class _bos:
    def __enter__(self): return self
    def __exit__(self, *a): return False


if __name__ == "__main__":
    ana()
