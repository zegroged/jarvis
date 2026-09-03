import json, sys
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

out = KOK / ".cikti" / "wi1q23sq3.output"
j = json.loads(out.read_text(encoding="utf-8", errors="replace"))
if "result" in j: j = j["result"]
res = j["sonuclar"]
ONC = {"yuksek":"🔴 YÜKSEK","orta":"🟡 orta","dusuk":"⚪ düşük"}
SIRA = {"yuksek":0,"orta":1,"dusuk":2}

lines = ["# Bilgi Hazinesi — Eksik Kapsama Yol Haritası",
    "",
    "> 18 alan uzmanı ajanının, mevcut 186 konuluk korpusu denetleyerek çıkardığı",
    "> kapsama boşlukları. Bu, önümüzdeki aylarda üretilecek uzman içeriğin",
    "> önceliklendirilmiş listesidir (genişleyen taksonomi). Toplam 194 boşluk.",
    ""]

for alan, baslik in (("guvenlik","## SİBER GÜVENLİK"),("yazilim","## YAZILIM")):
    lines.append(baslik); lines.append("")
    for d in res:
        if d.get("alan") != alan: continue
        lines.append(f"### {d['domain']}")
        for b in sorted(d["bosluklar"], key=lambda x: SIRA.get(x["oncelik"],1)):
            lines.append(f"- **[{ONC[b['oncelik']]}] {b['konu']}**  ")
            lines.append(f"  {b['neden']}")
        lines.append("")

hedef = KOK / "bilgi_hazinesi" / "YOL_HARITASI_eksikler.md"
hedef.write_text("\n".join(lines), encoding="utf-8")
print(f"[OK] {hedef} yazildi ({hedef.stat().st_size/1024:.0f} KB, {sum(len(d['bosluklar']) for d in res)} bosluk)")
