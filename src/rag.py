"""
FAZ 3 / KADEME A - Modul 3: RAG bilgi tabani SORGULAMA (HIBRIT).

Iki sinyali birlestirir:
  - Anlamsal (embedding, e5): "parola saklama" -> "password storage" (dil koprusu)
  - Kelime (BM25): tam terim eslesmesi (SQL injection, XXE...)

Skorlar normalize edilip agirlikli toplanir; en iyi k parca dondurulur.
jarvis_agent.py bunu 'bilgi_ara' araci olarak kullanir.

Embedding modeli CPU'da calisir (7B GPU'dayken VRAM'i sismesin diye) — e5-small
kucuk oldugu icin tek sorgu ~50 ms surer.
"""

import os
import pickle
import re

from config import DATA_DIR

RAG_YOLU = DATA_DIR / "processed" / "guvenlik_rag.pkl"
EMBED_YOLU = DATA_DIR / "processed" / "guvenlik_rag_embed.npz"
E5_YOLU = (DATA_DIR.parent / "models" / "e5-base") \
    if (DATA_DIR.parent / "models" / "e5-base").exists() \
    else (DATA_DIR.parent / "models" / "e5-small")
RERANKER_YOLU = DATA_DIR.parent / "models" / "bge-reranker"

_idx = None       # BM25 + metinler + kaynaklar
_emb = None       # anlamsal embedding matrisi (N x d, fp16, normalize)
_e5 = None        # (tokenizer, model)
_reranker = None  # (tokenizer, cross-encoder model)


def kelimele(metin):
    return re.findall(r"[a-zA-Z0-9_]+", metin.lower())


def _yukle():
    global _idx, _emb
    if _idx is None:
        if not RAG_YOLU.exists():
            raise FileNotFoundError(f"Bilgi tabani yok: {RAG_YOLU}. Once: python src/rag_kur.py")
        with open(RAG_YOLU, "rb") as f:
            _idx = pickle.load(f)
    if _emb is None and EMBED_YOLU.exists():
        import numpy as np
        _emb = np.load(EMBED_YOLU)["embeddings"]  # N x d, fp16
    return _idx


def _e5_yukle():
    global _e5
    if _e5 is None:
        try:
            import torch
            os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
        except Exception:
            pass
        from transformers import AutoModel, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(str(E5_YOLU))
        model = AutoModel.from_pretrained(str(E5_YOLU)).eval()  # CPU
        _e5 = (tok, model)
    return _e5


def _embed_sorgu(soru):
    import torch
    import torch.nn.functional as F
    tok, model = _e5_yukle()
    b = tok("query: " + soru[:512], padding=True, truncation=True,
            max_length=256, return_tensors="pt")
    with torch.no_grad():
        o = model(**b)
    m = b["attention_mask"].unsqueeze(-1).float()
    e = (o.last_hidden_state * m).sum(1) / m.sum(1).clamp(min=1e-9)
    return F.normalize(e, dim=1)[0].numpy()


def _minmax(x):
    import numpy as np
    x = np.asarray(x, dtype="float32")
    lo, hi = x.min(), x.max()
    return (x - lo) / (hi - lo) if hi > lo else x * 0.0


def _reranker_yukle():
    global _reranker
    if _reranker is None:
        try:
            import torch
            os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
        except Exception:
            pass
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(str(RERANKER_YOLU))
        model = AutoModelForSequenceClassification.from_pretrained(str(RERANKER_YOLU)).eval()  # CPU
        _reranker = (tok, model)
    return _reranker


def _rerank(soru, adaylar, w_rr=0.35, w_hyb=0.65):
    """adaylar: [(hibrit_skor, kaynak, metin)] -> cross-encoder ilgililik puani ile
    hibrit puani HARMANLAYIP yeniden sirala. Saf reranker bazen guclu bir hibrit
    sonucunu (orn. dogru cheat sheet) yanlislikla geri itebiliyor; harman ikisinin
    de gucunu birlestirir."""
    import numpy as np
    import torch
    tok, model = _reranker_yukle()
    ciftler = [[soru, m[:512]] for _, _, m in adaylar]
    b = tok(ciftler, padding=True, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        rr = np.asarray(model(**b).logits.view(-1).float().tolist(), dtype="float32")
    hyb = np.asarray([a[0] for a in adaylar], dtype="float32")
    birlesik = w_rr * _minmax(rr) + w_hyb * _minmax(hyb)
    sira = np.argsort(birlesik)[::-1]
    return [(float(birlesik[i]), adaylar[i][1], adaylar[i][2]) for i in sira]


def ara(soru, k=5, w_sem=0.68, w_lex=0.32, aday=30):
    """Iki asamali arama:
      1) Hibrit (anlamsal e5 + kelime BM25) ile 'aday' kadar en iyi parcayi cek
      2) Reranker (cross-encoder) ile bu adaylari yeniden siralayip en iyi k'yi dondur
    Reranker yoksa hibrit ilk k'ye duser; embedding de yoksa BM25'e duser."""
    import numpy as np
    idx = _yukle()
    lex = np.asarray(idx["bm25"].get_scores(kelimele(soru)), dtype="float32")

    if _emb is not None and E5_YOLU.exists():
        try:
            qv = _embed_sorgu(soru).astype("float32")
            sem = (_emb.astype("float32") @ qv)  # kosinus (ikisi de normalize)
            skor = w_sem * _minmax(sem) + w_lex * _minmax(lex)
        except Exception:
            skor = lex
    else:
        skor = lex

    n_aday = max(k, aday if RERANKER_YOLU.exists() else k)
    en_iyi = np.argsort(skor)[::-1][:n_aday]
    adaylar = [(float(skor[i]), idx["kaynaklar"][i], idx["metinler"][i]) for i in en_iyi]

    if RERANKER_YOLU.exists():
        try:
            return _rerank(soru, adaylar)[:k]
        except Exception:
            pass
    return adaylar[:k]


def ara_metin(soru, k=5, parca_sinir=650):
    sonuc = ara(soru, k)
    if not sonuc:
        return "[bilgi tabaninda ilgili bir sey bulunamadi]"
    return "\n\n".join(f"### Kaynak: {kaynak}\n{metin[:parca_sinir].strip()}"
                       for _, kaynak, metin in sonuc)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    soru = " ".join(sys.argv[1:]) or "parolalari veritabaninda guvenli saklama"
    print(f"Soru: {soru}\n" + "=" * 60)
    print(ara_metin(soru, k=3))
