import json, sys
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

out = KOK / ".cikti" / "wi1q23sq3.output"
j = json.loads(out.read_text(encoding="utf-8", errors="replace"))
if "result" in j:
    j = j["result"]
res = j["sonuclar"]

sayac = {"yuksek":0,"orta":0,"dusuk":0}
for d in res:
    for b in d.get("bosluklar",[]):
        sayac[b.get("oncelik","orta")] = sayac.get(b.get("oncelik","orta"),0)+1

print(f"Alan: {len(res)}, Toplam bosluk: {sum(sayac.values())}")
print(f"Oncelik: yuksek={sayac['yuksek']}, orta={sayac['orta']}, dusuk={sayac['dusuk']}\n")

for alan in ("guvenlik","yazilim"):
    print("#"*70)
    print(f"# {alan.upper()}")
    print("#"*70)
    for d in res:
        if d.get("alan") != alan: continue
        dom = d.get("domain","?")
        yuksek = [b for b in d["bosluklar"] if b["oncelik"]=="yuksek"]
        orta = [b for b in d["bosluklar"] if b["oncelik"]=="orta"]
        dusuk = [b for b in d["bosluklar"] if b["oncelik"]=="dusuk"]
        print(f"\n## {dom}  (Y:{len(yuksek)} O:{len(orta)} D:{len(dusuk)})")
        for b in yuksek:
            print(f"  [YUKSEK] {b['konu']}")
        for b in orta:
            print(f"  [orta]   {b['konu']}")
        for b in dusuk:
            print(f"  [dusuk]  {b['konu']}")
