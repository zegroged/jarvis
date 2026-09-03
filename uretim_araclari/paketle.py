"""bilgi_hazinesi/ altindaki tum .md dosyalarini korpus icin zip'ler."""
import sys, zipfile
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJ = KOK
KAYNAK = PROJ / "bilgi_hazinesi"
HEDEF_DIR = PROJ / "data" / "raw" / "uzman"
HEDEF_DIR.mkdir(parents=True, exist_ok=True)
HEDEF = HEDEF_DIR / "bilgi_hazinesi.zip"

n = 0
toplam = 0
with zipfile.ZipFile(HEDEF, "w", zipfile.ZIP_DEFLATED) as zf:
    for md in sorted(KAYNAK.rglob("*.md")):
        rel = md.relative_to(KAYNAK.parent).as_posix()  # ust segment = "bilgi_hazinesi"
        veri = md.read_bytes()
        zf.writestr(rel, veri)
        n += 1
        toplam += len(veri)

print(f"[OK] {HEDEF}")
print(f"  {n} makale, {toplam/1e6:.2f} MB ham metin, zip {HEDEF.stat().st_size/1e6:.2f} MB")
