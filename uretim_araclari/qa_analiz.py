"""Instruction dataset'i seviyeye gore analiz et (basit kavramsal vs ileri pratisyen)."""
import json, sys
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

F = KOK / "data" / "processed" / "jarvis_instruct_tr.jsonl"
kav, derin, tespit = [], [], []
for satir in F.read_text(encoding="utf-8", errors="replace").splitlines():
    satir = satir.strip()
    if not satir: continue
    try: o = json.loads(satir)
    except: continue
    k = o.get("kaynak", "")
    if k.endswith("_tespit"): tespit.append(o)
    elif k.endswith("_derin"): derin.append(o)
    else: kav.append(o)

top = len(kav)+len(derin)+len(tespit)
print(f"TOPLAM: {top} cift")
print(f"  KAVRAMSAL (temel, 'X nedir' tipi)  : {len(kav):>5}  (%{100*len(kav)/top:.0f})")
print(f"  DERIN-DALIS (gercek kod/CVE)        : {len(derin):>5}  (%{100*len(derin)/top:.0f})")
print(f"  TESPIT/YARGI (pratisyen)            : {len(tespit):>5}  (%{100*len(tespit)/top:.0f})")

def orn(liste, ad, n=2):
    print(f"\n--- ORNEK: {ad} ---")
    for o in liste[:n]:
        print("S:", o["soru"][:130])
        print("C:", o["cevap"][:160], "...\n")

orn(kav, "KAVRAMSAL (kullanicinin sikayet ettigi olabilir)")
orn(tespit, "TESPIT/YARGI (ileri)")
