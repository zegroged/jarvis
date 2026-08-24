"""Instruction dataset'i temel (kavramsal) ve ileri (derin+tespit) olarak ayir."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

D = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\processed")
F = D / "jarvis_instruct_tr.jsonl"
temel, ileri = [], []
for satir in F.read_text(encoding="utf-8", errors="replace").splitlines():
    satir = satir.strip()
    if not satir: continue
    try: o = json.loads(satir)
    except: continue
    k = o.get("kaynak", "")
    (ileri if (k.endswith("_tespit") or k.endswith("_derin") or k.endswith("_dfir") or k.endswith("_apro") or k.endswith("_damit")) else temel).append(o)

with (D / "jarvis_instruct_tr_temel.jsonl").open("w", encoding="utf-8") as f:
    for o in temel: f.write(json.dumps(o, ensure_ascii=False) + "\n")
with (D / "jarvis_instruct_tr_ileri.jsonl").open("w", encoding="utf-8") as f:
    for o in ileri: f.write(json.dumps(o, ensure_ascii=False) + "\n")

print(f"temel (kavramsal) : {len(temel):>5} cift -> jarvis_instruct_tr_temel.jsonl")
print(f"ileri (pratisyen) : {len(ileri):>5} cift -> jarvis_instruct_tr_ileri.jsonl")
