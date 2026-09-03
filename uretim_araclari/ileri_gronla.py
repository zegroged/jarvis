"""Gercek Ingilizce ileri guvenlik repolarindan zengin dokumanlari cikarir (damitma kaynagi)."""
import zipfile, sys, json, re
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAW = KOK / "data" / "raw" / "guvenlik"
HEDEF = KOK / ".cikti" / "ileri_kaynak.json"

# kaynak_etiket -> zip adi ; her kaynaktan azami dokuman (cesitlilik icin)
SOURCES = [
    ("HackTricks", "HackTricks-wiki__hacktricks.zip", 90),
    ("TheHackerRecipes", "The-Hacker-Recipes__The-Hacker-Recipes.zip", 60),
    ("MASTG", "OWASP__owasp-mastg.zip", 45),
    ("WSTG", "OWASP__wstg.zip", 40),
    ("ASVS", "OWASP__ASVS.zip", 20),
    ("OWASPCheatSheets", "OWASP__CheatSheetSeries.zip", 40),
    ("PayloadsAllTheThings", "swisskyrepo__PayloadsAllTheThings.zip", 35),
    ("InternalAllTheThings", "swisskyrepo__InternalAllTheThings.zip", 30),
]
MIN, MAX = 2200, 12000     # zengin ama devasa olmayan dokumanlar
KES = 5000                 # damitma icin ilk 5000 karakter yeter

def baslik(metin, yol):
    for satir in metin.splitlines():
        s = satir.strip().lstrip("#").strip()
        if s:
            return s[:120]
    return Path(yol).stem

sonuc = []
gorulen = set()
for etiket, zipad, azami in SOURCES:
    zp = RAW / zipad
    if not zp.exists():
        print(f"  YOK: {zipad}"); continue
    n = 0
    try:
        with zipfile.ZipFile(zp) as zf:
            for info in sorted(zf.infolist(), key=lambda i: -i.file_size):  # zenginler once
                if n >= azami: break
                ad = info.filename.lower()
                if not ad.endswith(".md"): continue
                if any(x in ad for x in ("readme", "summary", "_sidebar", "changelog", "/.git")): continue
                if not (MIN <= info.file_size <= MAX): continue
                try:
                    metin = zf.read(info).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                if "\x00" in metin[:2000]: continue
                h = hash(metin[:1000])
                if h in gorulen: continue
                gorulen.add(h)
                sonuc.append({"kaynak": etiket, "baslik": baslik(metin, info.filename),
                              "yol": info.filename.split("/", 1)[-1], "metin": metin[:KES]})
                n += 1
    except zipfile.BadZipFile:
        continue
    print(f"  {etiket:<22} {n} dokuman")

# id ata
for i, d in enumerate(sonuc):
    d["id"] = f"{d['kaynak'].lower()}-{i:04d}"
HEDEF.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
print(f"\n[OK] Toplam ileri kaynak dokuman: {len(sonuc)} -> {HEDEF}")
