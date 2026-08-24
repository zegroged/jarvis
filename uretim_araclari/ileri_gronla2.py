"""İleri İngilizce güvenlik repolarindan 2. parti zengin dokuman cikarir (damitma kaynagi).

1. partide (ileri_gronla.py) her repodan sadece 20-90 dokuman alinmisti; repolar cok
daha buyuk. Bu script KALAN dokumanlari, YOL-BAZLI DETERMINISTIK id ile cikarir; boylece
idempotenttir (ayni dosya hep ayni id). Zaten damitilmis olanlari (guvenlik_<id>_damit.jsonl
VAR) atlar. Cikti PROJE ICINE: uretim_araclari/ileri_kaynak2.json

Repo onceligi savunma-dostu olanlardan basmar (Opus guvenlik-filtresini az tetikler).
"""
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
RAW = KOK / "data" / "raw" / "guvenlik"
QA_DIR = KOK / "data" / "processed" / "instruct_tr"
HEDEF = KOK / "uretim_araclari" / "ileri_kaynak2.json"

# (kisa_etiket, zip, azami_bu_parti) — savunma-dostu once, offensive sonra
# Teknik/pratisyen repolar ONCE (5/5 potansiyeli yuksek); surec/kultur repolari (devg/asvs) SONA.
# YENI yuksek-teknik kaynaklar eklendi (GTFOBins/LOLBAS/atomic/h4cker/hardware...).
SOURCES = [
    ("gtfobins", "GTFOBins__GTFOBins.github.io.zip", 200),
    ("lolbas", "LOLBAS-Project__LOLBAS.zip", 200),
    ("atomic", "redcanaryco__atomic-red-team.zip", 250),
    ("h4cker", "The-Art-of-Hacking__h4cker.zip", 120),
    ("hardware", "swisskyrepo__HardwareAllTheThings.zip", 80),
    ("bosk", "trimstray__the-book-of-secret-knowledge.zip", 40),
    ("nginx", "trimstray__nginx-admins-handbook.zip", 50),
    ("top10", "OWASP__Top10.zip", 40),
    ("payloads", "swisskyrepo__PayloadsAllTheThings.zip", 60),
    ("mastg", "OWASP__owasp-mastg.zip", 220),
    ("wstg", "OWASP__wstg.zip", 100),
    ("cheat", "OWASP__CheatSheetSeries.zip", 46),
    ("recipes", "The-Hacker-Recipes__The-Hacker-Recipes.zip", 120),
    ("internal", "swisskyrepo__InternalAllTheThings.zip", 98),
    ("hacktricks", "HackTricks-wiki__hacktricks.zip", 250),
    ("wcomm", "OWASP__www-community.zip", 130),
    ("apisec", "OWASP__API-Security.zip", 130),
    ("asvs", "OWASP__ASVS.zip", 60),
    ("devg", "OWASP__DevGuide.zip", 40),
]
MIN, MAX = 2200, 12000
KES = 5500

# Ceviri dil kodlari (en HARIC). OWASP/HackTricks repolari ayni icerigi ~15 dile ceviriyor;
# yalnizca Ingilizce kaynaktan damit — yoksa kaynak-dil kalintisi Turkce cikti'ya sizar.
DIL_KODLARI = {
    "es", "fr", "de", "el", "el-gr", "gr", "fa", "ar", "ru", "pt", "pt-pt", "pt-br",
    "zh", "zh-cn", "zh-tw", "ja", "ko", "id", "hi", "ml", "tr", "it", "pl", "uk",
    "vi", "he", "nl", "cs", "ro", "bg", "sr", "hr", "sk", "sl", "da", "sv", "no",
    "nb", "fi", "hu", "th", "bn", "ur", "ca", "az", "kk", "uz", "sw", "fil", "ta",
    "te", "mr", "gu", "pa", "fa-ir", "zh-hans", "zh-hant",
}


def ceviri_mi(yol):
    """Yol segmentlerinde ceviri dil kodu (en haric) varsa True. 'en' segmenti varsa
    kesinlikle Ingilizce (False). Hic dil segmenti yoksa Ingilizce varsayilir (False)."""
    segler = [s.lower() for s in yol.split("/")]
    if "en" in segler:
        return False
    return any(s in DIL_KODLARI for s in segler)


def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def slugla(yol):
    # repo-kok sonrasi yol; son 3 parcayi al, slug yap
    parcalar = [p for p in yol.split("/")[1:] if p]
    kuyruk = "-".join(parcalar[-3:])
    kuyruk = re.sub(r"\.md$", "", kuyruk, flags=re.I)
    kuyruk = re.sub(r"[^a-zA-Z0-9]+", "-", kuyruk).strip("-").lower()
    return kuyruk[:60] or "doc"


def baslik(metin, yol):
    for satir in metin.splitlines():
        s = satir.strip().lstrip("#").strip()
        if s:
            return temizle(s[:120])
    return Path(yol).stem


def tamam(did):
    return (QA_DIR / f"guvenlik_{did}_damit.jsonl").exists()


def main():
    sonuc = []
    gorulen_id = set()
    gorulen_hash = set()
    zaten = 0
    for etiket, zn, azami in SOURCES:
        zp = RAW / zn
        if not zp.exists():
            print(f"  YOK: {zn}")
            continue
        n = 0
        try:
            with zipfile.ZipFile(zp) as zf:
                # cesitlilik icin buyukten kucuge
                for info in sorted(zf.infolist(), key=lambda i: -i.file_size):
                    if n >= azami:
                        break
                    ad = info.filename.lower()
                    if not ad.endswith(".md"):
                        continue
                    if any(x in ad for x in ("readme", "summary", "_sidebar", "changelog", "/.git", "/translated")):
                        continue
                    # meta/tanitim/surec dosyalari teknik-derin degil -> ele (ileri veri icin degersiz)
                    if any(x in ad for x in ("about", "introduction", "contributing", "release-note",
                            "next-dev", "foreword", "preface", "glossary", "license", "acknowledg",
                            "roadmap", "credits", "sponsor", "code-of-conduct", "citation",
                            "/index.md", "gsoc", "gsod", "/initiatives/", "/social/", "all-day-info",
                            "frontispiece", "overview", "taxonomy", "0x02a", "0x03-overview",
                            "/indexes/", "-index", "/index-", "matrix", "/_data/",
                            "code_of_conduct", "code-of-conduct", "/.github/",
                            "/aitech-", "workflow-optimization")):
                        continue
                    if ceviri_mi(info.filename):
                        continue
                    if not (MIN <= info.file_size <= MAX):
                        continue
                    did = f"{etiket}2-{slugla(info.filename)}"
                    if did in gorulen_id:
                        did = f"{did}-{n}"
                    if did in gorulen_id:
                        continue
                    if tamam(did):
                        zaten += 1
                        continue
                    try:
                        metin = zf.read(info).decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    if "\x00" in metin[:2000]:
                        continue
                    metin = temizle(metin)[:KES]
                    if len(metin) < 500:
                        continue
                    h = hash(metin[:1000])
                    if h in gorulen_hash:
                        continue
                    gorulen_hash.add(h)
                    gorulen_id.add(did)
                    sonuc.append({
                        "id": did,
                        "kaynak": etiket,
                        "baslik": baslik(metin, info.filename),
                        "yol": "/".join(info.filename.split("/")[1:]),
                        "metin": metin,
                    })
                    n += 1
        except zipfile.BadZipFile:
            continue
        print(f"  {etiket:<12} yeni:{n}")

    HEDEF.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nCikarilan 2.parti dokuman: {len(sonuc)}  (zaten damitilmis atlanan: {zaten})")
    print(f"[OK] -> {HEDEF} ({HEDEF.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
