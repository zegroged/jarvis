"""instruct_tr/*.jsonl birlestir, dogrula, Turkce kalite tara, tek veri seti yaz."""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\processed\instruct_tr")
HEDEF = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\processed\jarvis_instruct_tr.jsonl")
TR = set("çğıöşüÇĞİÖŞÜ")

toplam, gecersiz = 0, 0
ascii_dosya = []
ciftler = []
for jf in sorted(DIR.glob("*.jsonl")):
    ad = jf.stem                       # ornek: guvenlik_sql-injection
    dosya_alan = "guvenlik" if ad.startswith("guvenlik_") else "yazilim"
    dosya_kaynak = ad.split("_", 1)[1] if "_" in ad else ad
    metin = jf.read_text(encoding="utf-8", errors="replace")
    harf = sum(1 for c in metin if c.isalpha())
    oran = (sum(1 for c in metin if c in TR) / harf) if harf else 0
    if harf > 200 and oran < 0.02:
        ascii_dosya.append(jf.name)
    for satir in metin.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        try:
            o = json.loads(satir)
            if o.get("soru") and o.get("cevap"):
                o["alan"] = dosya_alan            # dosya adindan tutarli metadata
                o["kaynak"] = dosya_kaynak
                ciftler.append(o)
                toplam += 1
            else:
                gecersiz += 1
        except Exception:
            gecersiz += 1

# Yinelenen sorulari ele (normalize edilmis soru metnine gore)
import re as _re
gorulen_soru, tekil = set(), []
yinelenen = 0
for o in ciftler:
    anahtar = _re.sub(r"\s+", " ", o["soru"].strip().lower())
    if anahtar in gorulen_soru:
        yinelenen += 1
        continue
    gorulen_soru.add(anahtar)
    tekil.append(o)
ciftler = tekil

with HEDEF.open("w", encoding="utf-8") as f:
    for o in ciftler:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
print(f"Yinelenen soru elendi: {yinelenen}")

guv = sum(1 for o in ciftler if o.get("alan") == "guvenlik")
yaz = sum(1 for o in ciftler if o.get("alan") == "yazilim")
bayt = sum(len((o["soru"]+o["cevap"]).encode("utf-8")) for o in ciftler)
print(f"Dosya: {len(list(DIR.glob('*.jsonl')))}")
print(f"Gecerli cift: {toplam:,}  (guvenlik={guv}, yazilim={yaz})")
print(f"Gecersiz satir: {gecersiz}")
print(f"Metin: {bayt/1e6:.2f} MB")
print(f"ASCII-Turkce supheli dosya (<%2): {len(ascii_dosya)}")
for a in ascii_dosya[:40]:
    print("  ", a)
print(f"\n[OK] Birlesik veri seti: {HEDEF} ({HEDEF.stat().st_size/1e6:.2f} MB)")
print("\n--- ORNEK 2 CIFT ---")
for o in ciftler[:2]:
    print("S:", o["soru"])
    print("C:", o["cevap"][:200], "...")
    print()
