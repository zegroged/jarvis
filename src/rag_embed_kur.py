"""
KADEME A - Parca 1: RAG'i ANLAMSAL aramaya yukselt (embedding index kur).

Mevcut BM25 index'i (guvenlik_rag.pkl) kelime eslestirir; Turkce soru + Ingilizce
dokuman durumunda zayif kalir. Cok dilli bir embedding modeli (multilingual-e5)
ile her parcayi ANLAM vektorune ceviririz; boylece "parola saklama" sorusu
"password storage" dokumanini bulur.

Bu betik: guvenlik_rag.pkl'deki parcalarin embedding'lerini hesaplar ve
guvenlik_rag_embed.npz olarak kaydeder. rag.py ikisini birlestirir (hibrit).

Calistirma (e5 modeli indikten sonra):
    .venv\\Scripts\\python.exe src\\rag_embed_kur.py
"""

import os
import pickle
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import torch
    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
except Exception:
    pass

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from config import DATA_DIR

KOK = DATA_DIR.parent
# Daha guclu e5-base varsa onu kullan, yoksa e5-small'a dus
E5_YOLU = (KOK / "models" / "e5-base") if (KOK / "models" / "e5-base").exists() \
    else (KOK / "models" / "e5-small")
RAG_YOLU = DATA_DIR / "processed" / "guvenlik_rag.pkl"
EMBED_YOLU = DATA_DIR / "processed" / "guvenlik_rag_embed.npz"


def mean_pool(son_gizli, maske):
    m = maske.unsqueeze(-1).float()
    return (son_gizli * m).sum(1) / m.sum(1).clamp(min=1e-9)


def embed_et(metinler, tok, model, device, on_ek, batch=64):
    """Metin listesini normalize edilmis embedding matrisine cevirir (e5 usulu)."""
    ciktilar = []
    for i in range(0, len(metinler), batch):
        parca = [on_ek + m[:512] for m in metinler[i:i + batch]]
        b = tok(parca, padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
        with torch.no_grad():
            o = model(**b)
        e = mean_pool(o.last_hidden_state, b["attention_mask"])
        ciktilar.append(F.normalize(e, dim=1).cpu().to(torch.float16))
        if (i // batch) % 20 == 0:
            print(f"\r  {min(i+batch,len(metinler))}/{len(metinler)}", end="", flush=True)
    return torch.cat(ciktilar).numpy()


def ana():
    if not E5_YOLU.exists():
        sys.exit(f"[HATA] Embedding modeli yok: {E5_YOLU}. Once e5-small indir.")
    if not RAG_YOLU.exists():
        sys.exit(f"[HATA] {RAG_YOLU} yok. Once rag_kur.py calistir.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Embedding modeli yukleniyor ({E5_YOLU.name}, {device})...")
    tok = AutoTokenizer.from_pretrained(str(E5_YOLU))
    model = AutoModel.from_pretrained(str(E5_YOLU)).to(device).eval()

    with open(RAG_YOLU, "rb") as f:
        idx = pickle.load(f)
    metinler = idx["metinler"]
    print(f"{len(metinler)} parca embed ediliyor...")

    t0 = time.time()
    # e5 dokumanlar icin "passage: " on eki ister
    emb = embed_et(metinler, tok, model, device, "passage: ")
    print(f"\n  bitti ({time.time()-t0:.0f} sn), boyut: {emb.shape}")

    np.savez_compressed(EMBED_YOLU, embeddings=emb)
    print(f"[OK] Anlamsal index kaydedildi: {EMBED_YOLU} "
          f"({EMBED_YOLU.stat().st_size // 1024 // 1024} MB)")


if __name__ == "__main__":
    ana()
