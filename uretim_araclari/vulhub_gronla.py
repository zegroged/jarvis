"""vulhub deposundaki gercek CVE zafiyet-lab README'lerini damitma kaynagi olarak cikarir.

vulhub__vulhub.zip icinde her klasor bir gercek CVE'nin calisan ortamidir; README.md
zafiyeti, etkilenen surumu, kurulumu ve tetikleme adimlarini anlatir. Bunlar "guncel
dunyada ise yarayan" spesifik, demirli ileri kaynaklardir.

Ciktisi PROJE ICINE yazilir (scratchpad'e degil): uretim_araclari/vulhub_kaynak.json
Boylece sonraki oturum yolu kaybetmez.
"""
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
ZIP = KOK / "data" / "raw" / "guvenlik" / "vulhub__vulhub.zip"
HEDEF = KOK / "uretim_araclari" / "vulhub_kaynak.json"

MIN, MAX = 1200, 12000   # anlamli ama devasa olmayan README'ler
KES = 5500               # damitma icin ilk ~5500 karakter yeter


def temizle(s):
    """Kontrol karakterlerini sur (Workflow/JSON guvenli)."""
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def slug(cve, urun):
    parca = f"{urun}-{cve}".lower()
    parca = re.sub(r"[^a-z0-9]+", "-", parca).strip("-")
    return f"vulhub-{parca}"


def baslik(metin, cve, urun):
    for satir in metin.splitlines():
        s = satir.strip().lstrip("#").strip()
        if s:
            return temizle(s[:120])
    return f"{urun} {cve}"


def main():
    if not ZIP.exists():
        sys.exit(f"[HATA] Zip yok: {ZIP}")

    sonuc = []
    gorulen_id = set()
    gorulen_hash = set()
    atlanan_kisa = atlanan_cince = 0

    with zipfile.ZipFile(ZIP) as zf:
        # Zenginden fakire: en dolgun README'ler once
        for info in sorted(zf.infolist(), key=lambda i: -i.file_size):
            ad = info.filename
            adl = ad.lower()
            if not adl.endswith("readme.md"):
                continue
            if ".zh-cn." in adl or ".zh-tw." in adl or "/ja/" in adl or ".ja." in adl:
                atlanan_cince += 1
                continue
            if not (MIN <= info.file_size <= MAX):
                atlanan_kisa += 1
                continue
            # yol: vulhub-<hash>/<urun>/<CVE-...>/README.md
            parcalar = ad.split("/")
            if len(parcalar) < 3:
                continue
            klasor = parcalar[-2]           # ornek: CVE-2021-3129  ya da  s2-061
            urun = parcalar[-3] if len(parcalar) >= 3 else "misc"
            cve_m = re.search(r"CVE-\d{4}-\d+", klasor, re.I)
            cve = cve_m.group(0).upper() if cve_m else klasor
            did = slug(cve, urun)
            if did in gorulen_id:
                continue
            try:
                metin = zf.read(info).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if "\x00" in metin[:2000]:
                continue
            metin = temizle(metin)[:KES]
            if len(metin) < 400:
                atlanan_kisa += 1
                continue
            h = hash(metin[:1000])
            if h in gorulen_hash:
                continue
            gorulen_hash.add(h)
            gorulen_id.add(did)
            sonuc.append({
                "id": did,
                "kaynak": "vulhub",
                "cve": cve,
                "urun": urun,
                "baslik": baslik(metin, cve, urun),
                "yol": "/".join(parcalar[1:]),
                "metin": metin,
            })

    HEDEF.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Cikarilan vulhub lab: {len(sonuc)}")
    print(f"Atlanan (kisa/uzun): {atlanan_kisa}, atlanan (Cince/JP): {atlanan_cince}")
    print(f"[OK] -> {HEDEF} ({HEDEF.stat().st_size/1024:.0f} KB)")
    # urun dagilimi
    dag = {}
    for d in sonuc:
        dag[d["urun"]] = dag.get(d["urun"], 0) + 1
    ust = sorted(dag.items(), key=lambda x: -x[1])[:15]
    print("Urun dagilimi (ilk 15):", ", ".join(f"{k}:{v}" for k, v in ust))


if __name__ == "__main__":
    main()
