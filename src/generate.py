"""
6a. ADIM: Egitilmis modelle metin uretimi.

Ne yapar:
  - checkpoints/ altindaki modeli yukler (varsayilan: en iyi model)
  - Verilen baslangic metnini (istem) modele surdurttur
  - temperature ve top_k ile ureticiligi ayarlarsin

Calistirma ornekleri (proje kokunden):
    .venv\\Scripts\\python.exe src\\generate.py --istem "Turkiye'nin baskenti"
    .venv\\Scripts\\python.exe src\\generate.py --istem "def topla(a, b):" --token 120 --temp 0.7
"""

import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from tokenizers import Tokenizer

from config import CHECKPOINT_DIR, TOKENIZER_YOLU, ModelConfig
from model import GPT

CKPT_YOLU = CHECKPOINT_DIR / "jarvis_son.pt"
EN_IYI_YOLU = CHECKPOINT_DIR / "jarvis_en_iyi.pt"


def model_yukle(device: str, en_iyi: bool = True):
    """Checkpoint'i yukler ve degerlendirme moduna alir. Kaydedilmis
    model_config'i kullanir; boylece config.py sonradan degisse bile
    checkpoint dogru mimariyle yuklenir."""
    yol = EN_IYI_YOLU if en_iyi and EN_IYI_YOLU.exists() else CKPT_YOLU
    if not yol.exists():
        sys.exit("[HATA] Egitilmis model bulunamadi. Once train.py calistir.")
    ckpt = torch.load(yol, map_location=device)
    m_cfg = ModelConfig(**ckpt["model_config"]) if "model_config" in ckpt else ModelConfig()
    model = GPT(m_cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, yol, ckpt.get("adim", "?")


def uret(model, tokenizer, device, istem, token_sayisi, temp, top_k, tekrar_ceza):
    ids = tokenizer.encode(istem).ids
    if not ids:  # bos istem -> belgesonu tokeni ile basla
        ids = [tokenizer.token_to_id("<|belgesonu|>")]
    x = torch.tensor(ids, dtype=torch.long, device=device)[None, ...]
    amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    with torch.amp.autocast("cuda", dtype=amp_dtype) if device == "cuda" else _bos():
        y = model.generate(x, max_new_tokens=token_sayisi, temperature=temp,
                           top_k=top_k, repetition_penalty=tekrar_ceza)
    return tokenizer.decode(y[0].tolist(), skip_special_tokens=True)


class _bos:
    """CPU'da autocast yerine kullanilan bos baglam (context)."""
    def __enter__(self): return self
    def __exit__(self, *a): return False


def ana():
    p = argparse.ArgumentParser()
    p.add_argument("--istem", default="Turkiye", help="baslangic metni")
    p.add_argument("--token", type=int, default=100, help="uretilecek token sayisi")
    p.add_argument("--temp", type=float, default=0.8,
                   help="ureticilik: dusuk=emin/tekrarci, yuksek=rastgele")
    p.add_argument("--topk", type=int, default=50, help="sadece en olasi k token")
    p.add_argument("--ceza", type=float, default=1.3,
                   help="tekrar cezasi (1=kapali, 1.2-1.4 onerilir)")
    p.add_argument("--son", action="store_true",
                   help="en iyi yerine en son checkpoint'i kullan")
    args = p.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = Tokenizer.from_file(str(TOKENIZER_YOLU))
    model, yol, adim = model_yukle(device, en_iyi=not args.son)
    print(f"[model: {yol.name}, {adim}. adim, cihaz: {device}]\n")

    metin = uret(model, tokenizer, device, args.istem, args.token,
                 args.temp, args.topk, args.ceza)
    print(metin)


if __name__ == "__main__":
    ana()
