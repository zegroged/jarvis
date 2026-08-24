"""
CVE ISLEYICI — cvelistV5.zip (363k CVE Record Format 5.x kaydi) icindeki her
CVE'yi okunabilir bir metin blogu haline getirip korpusa yazar.

Cikti: data/corpus/korpus_cve_XXXX.jsonl.gz  (kendi onekiyle; korpus_kur.py'nin
korpus_XXXX ve hf_indir.py'nin korpus_hf_XXXX parcalarina DOKUNMAZ.)

Her kayittan cikarilan: CVE kimligi, durum, aciklama (EN), CWE, siddet/CVSS,
etkilenen urun/surum, birkac referans. REJECTED / aciklamasiz kayitlar atlanir.

Calistirma:
    .venv\\Scripts\\python.exe src\\cve_isle.py
"""

import gzip
import json
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import DATA_DIR

RAW = DATA_DIR / "raw"
KORPUS = DATA_DIR / "corpus"
ZIP_YOL = RAW / "guvenlik" / "cvelistV5.zip"
PARCA_DOK = 20000
CVE_RE = re.compile(r"/cves/.*/CVE-\d+-\d+\.json$", re.I)


def ilk_en(desc_list):
    if not isinstance(desc_list, list):
        return ""
    for d in desc_list:
        if isinstance(d, dict) and d.get("lang", "").lower().startswith("en"):
            return (d.get("value") or "").strip()
    for d in desc_list:
        if isinstance(d, dict) and d.get("value"):
            return d["value"].strip()
    return ""


def metin_uret(kayit):
    meta = kayit.get("cveMetadata", {})
    cid = meta.get("cveId", "")
    durum = meta.get("state", "")
    if durum == "REJECTED":
        return None

    cna = (kayit.get("containers", {}) or {}).get("cna", {}) or {}
    aciklama = ilk_en(cna.get("descriptions"))
    if len(aciklama) < 20:
        return None

    satirlar = [f"{cid} ({durum})", "", aciklama]

    # CWE
    cweler = []
    for pt in cna.get("problemTypes", []) or []:
        for d in pt.get("descriptions", []) or []:
            cw = d.get("cweId") or ""
            aciklama_cw = d.get("description") or ""
            etiket = " ".join(x for x in (cw, aciklama_cw) if x).strip()
            if etiket:
                cweler.append(etiket)
    if cweler:
        satirlar.append("Zafiyet turu (CWE): " + "; ".join(dict.fromkeys(cweler)))

    # CVSS / siddet
    for m in cna.get("metrics", []) or []:
        for anahtar, deger in m.items():
            if isinstance(deger, dict) and "baseScore" in deger:
                sev = deger.get("baseSeverity", "")
                satirlar.append(
                    f"CVSS ({anahtar}): {deger['baseScore']} {sev}".strip())
                break

    # Etkilenen urunler (ilk birkac)
    etk = []
    for a in (cna.get("affected", []) or [])[:5]:
        vendor = a.get("vendor", "") or ""
        urun = a.get("product", "") or ""
        ad = " ".join(x for x in (vendor, urun) if x and x != "n/a").strip()
        if ad:
            etk.append(ad)
    if etk:
        satirlar.append("Etkilenen: " + "; ".join(dict.fromkeys(etk)))

    # Referanslar (ilk birkac URL)
    refs = [r.get("url") for r in (cna.get("references", []) or [])
            if isinstance(r, dict) and r.get("url")]
    if refs:
        satirlar.append("Referanslar: " + " ".join(refs[:4]))

    return "\n".join(satirlar)


def sonraki_no():
    varlar = sorted(KORPUS.glob("korpus_cve_*.jsonl.gz"))
    if not varlar:
        return 1
    return int(varlar[-1].stem.split("_")[-1].split(".")[0]) + 1


def ana():
    if not ZIP_YOL.exists():
        sys.exit(f"[HATA] Bulunamadi: {ZIP_YOL}")
    print(f"CVE isleniyor: {ZIP_YOL} ({ZIP_YOL.stat().st_size/1e6:.0f} MB)")
    KORPUS.mkdir(parents=True, exist_ok=True)

    no = sonraki_no()
    f = gzip.open(KORPUS / f"korpus_cve_{no:04d}.jsonl.gz", "wt", encoding="utf-8")
    yazilan = shard_dok = atlanan = toplam_bayt = 0

    with zipfile.ZipFile(ZIP_YOL) as zf:
        adlar = [n for n in zf.namelist() if CVE_RE.search(n)]
        print(f"  {len(adlar):,} CVE kaydi bulundu, isleniyor...")
        for i, ad in enumerate(adlar):
            try:
                kayit = json.loads(zf.read(ad))
                metin = metin_uret(kayit)
            except Exception:
                metin = None
            if not metin:
                atlanan += 1
                continue
            f.write(json.dumps({"kaynak": "CVE:" + ad.rsplit("/", 1)[-1],
                                "metin": metin}, ensure_ascii=False) + "\n")
            toplam_bayt += len(metin.encode("utf-8"))
            yazilan += 1
            shard_dok += 1
            if shard_dok >= PARCA_DOK:
                f.close()
                no += 1
                shard_dok = 0
                f = gzip.open(KORPUS / f"korpus_cve_{no:04d}.jsonl.gz",
                              "wt", encoding="utf-8")
            if i % 20000 == 0 and i:
                print(f"\r  {i:,}/{len(adlar):,}  yazilan={yazilan:,}  "
                      f"{toplam_bayt/1e9:.2f} GB", flush=True)
    f.close()
    print("\n" + "=" * 60)
    print(f"[OK] CVE korpusa eklendi: yazilan={yazilan:,}, atlanan={atlanan:,}, "
          f"metin={toplam_bayt/1e9:.2f} GB")


if __name__ == "__main__":
    ana()
