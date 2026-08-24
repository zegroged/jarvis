import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

out = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\tasks\wi1q23sq3.output")
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

hedef = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\bilgi_hazinesi\YOL_HARITASI_eksikler.md")
hedef.write_text("\n".join(lines), encoding="utf-8")
print(f"[OK] {hedef} yazildi ({hedef.stat().st_size/1024:.0f} KB, {sum(len(d['bosluklar']) for d in res)} bosluk)")
