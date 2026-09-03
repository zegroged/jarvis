"""Sadece soru+cevap DEGERLERI uzerinden Turkce oran (JSON yapisini haric tut)."""
import json, sys
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DIR = KOK / "data" / "processed" / "instruct_tr"
TR = set("çğıöşüÇĞİÖŞÜ")

bozuk = []
for jf in sorted(DIR.glob("*.jsonl")):
    metin_parca = []
    for satir in jf.read_text(encoding="utf-8", errors="replace").splitlines():
        satir = satir.strip()
        if not satir: continue
        try:
            o = json.loads(satir)
            metin_parca.append((o.get("soru","") or "") + " " + (o.get("cevap","") or ""))
        except Exception:
            pass
    t = " ".join(metin_parca)
    harf = sum(1 for c in t if c.isalpha())
    oran = (sum(1 for c in t if c in TR) / harf) if harf else 0
    if harf > 200 and oran < 0.02:
        bozuk.append((oran, jf.name))

print(f"DEGER-bazli ASCII-Turkce bozuk dosya: {len(bozuk)}")
for oran, ad in sorted(bozuk):
    print(f"  %{oran*100:.1f}  {ad}")
