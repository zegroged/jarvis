"""Tum korpusun (korpus_*, korpus_cve_*, korpus_hf_*) gercek istatistigi."""
import gzip, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KORPUS = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\corpus")

def grup(dosya):
    ad = dosya.name
    if ad.startswith("korpus_cve_"): return "CVE (guvenlik zafiyet DB)"
    if ad.startswith("korpus_hf_"):  return "HF akis"
    return "Ana korpus (acik kaynak + uzman)"

istat = {}
for gz in sorted(KORPUS.glob("*.jsonl.gz")):
    g = grup(gz)
    d = istat.setdefault(g, {"dosya":0, "dok":0, "metin":0, "disk":0})
    d["dosya"] += 1
    d["disk"] += gz.stat().st_size
    with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as f:
        for satir in f:
            if not satir.strip(): continue
            try:
                obj = json.loads(satir)
            except Exception:
                continue
            d["dok"] += 1
            d["metin"] += len(obj.get("metin","").encode("utf-8"))

print("="*72)
print(f"{'GRUP':<38}{'DOK':>12}{'METIN(GB)':>11}{'DISK(GB)':>10}")
print("-"*72)
T = {"dok":0,"metin":0,"disk":0}
for g, d in sorted(istat.items()):
    print(f"{g:<38}{d['dok']:>12,}{d['metin']/1e9:>11.2f}{d['disk']/1e9:>10.2f}")
    for k in T: T[k]+=d[k]
print("-"*72)
print(f"{'TOPLAM':<38}{T['dok']:>12,}{T['metin']/1e9:>11.2f}{T['disk']/1e9:>10.2f}")
print("="*72)
