"""
FAZ 3 / KADEME A - Modul 3: RAG bilgi tabani KURULUMU (GUVENLIK + YAZILIM).

Indirdigimiz otoriter dokumanlardan aranabilir bir bilgi tabani olusturur.
Boylece Jarvis bir soruda UYDURMAK yerine bu kaynaklardan ilgili parcalari
cekip okuyabilir. Bilgi boslugunu asil KAPATAN sey budur (fine-tune degil).

Kapsam:
  GUVENLIK: OWASP (CheatSheets, WSTG, ASVS, MASTG, Top10), PayloadsAllTheThings,
            InternalAllTheThings, HackTricks, h4cker, book-of-secret-knowledge,
            MITRE ATT&CK
  YAZILIM : Python resmi dokumanlari (cpython Doc/*.rst), FastAPI dokumanlari,
            Django dokumanlari, You-Dont-Know-JS, TheAlgorithms

Cikti: data/processed/guvenlik_rag.pkl  (BM25 index + metin parcalari + kaynaklar)
Sonra: rag_embed_kur.py ile anlamsal embedding eklenir.

Calistirma:
    .venv\\Scripts\\python.exe src\\rag_kur.py
"""

import json
import pickle
import random
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rank_bm25 import BM25Okapi
from tqdm import tqdm

from config import DATA_DIR

RAW = DATA_DIR / "raw"
RAG_YOLU = DATA_DIR / "processed" / "guvenlik_rag.pkl"

PARCA_MIN = 200
PARCA_MAX = 1400
AZAMI_PARCA = 80000

# Ingilizce-disi ceviri klasorleri (gurultu): Ingilizce kanonik surumu tutariz.
DIL_KODLARI = {
    "ar", "bn", "cs", "de", "el", "es", "fa", "fi", "fr", "he", "hi", "hu", "id",
    "it", "ja", "ko", "ml", "nl", "no", "pl", "pt", "pt-br", "ptbr", "ro", "ru",
    "sk", "sr", "sv", "th", "tr", "uk", "vi", "zh", "zh-cn", "zh-tw", "zh-hans",
    "zh-hant", "ca", "da", "hr", "bg", "az", "fa-ir",
}
# Dosya adi EKINDEKI dil kodu (README.tr-TR, foo-zh-Hans, bar_es): sondaki
# ayrac + dil kodu (+ istege bagli bolge eki) deseni.
_DIL_EKI = re.compile(
    r"[._-](" + "|".join(re.escape(c) for c in sorted(DIL_KODLARI, key=len, reverse=True))
    + r")([._-][a-zA-Z]+)?$", re.IGNORECASE)
# Genel dil-segmenti deseni: "fr", "pt-pt", "zh_cn" gibi 2 harf (+ istege bagli
# bolge) klasorleri. Ingilizce ve dil-disi kisa klasorler beyaz listede.
_DIL_SEGMENT = re.compile(r"^[a-z]{2}([-_][a-z]{2,4})?$")
_SEGMENT_BEYAZ = {"en", "js", "io", "ui", "os", "db", "go", "py", "md",
                  "rs", "sh", "cs", "vm", "ci", "ts", "cd", "qa"}


def _ceviri_mi(yol):
    for seg in yol.split("/"):
        s = seg.lower()
        if s in DIL_KODLARI:
            return True
        if s != "en" and s not in _SEGMENT_BEYAZ and _DIL_SEGMENT.match(s):
            return True
    ad = yol.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return bool(_DIL_EKI.search(ad))

# (alt_klasor, zip_adi, uzantilar, yol_filtresi)  — yol_filtresi None ise tumu
KAYNAKLAR = [
    # --- GUVENLIK ---
    ("guvenlik", "OWASP__CheatSheetSeries.zip", (".md",), None),
    ("guvenlik", "OWASP__wstg.zip", (".md",), None),
    ("guvenlik", "OWASP__ASVS.zip", (".md",), None),
    ("guvenlik", "OWASP__owasp-mastg.zip", (".md",), None),
    ("guvenlik", "OWASP__Top10.zip", (".md",), None),
    ("guvenlik", "swisskyrepo__PayloadsAllTheThings.zip", (".md",), None),
    ("guvenlik", "swisskyrepo__InternalAllTheThings.zip", (".md",), None),
    ("guvenlik", "HackTricks-wiki__hacktricks.zip", (".md",), None),
    ("guvenlik", "The-Art-of-Hacking__h4cker.zip", (".md",), None),
    ("guvenlik", "trimstray__the-book-of-secret-knowledge.zip", (".md",), None),
    ("guvenlik", "OWASP__API-Security.zip", (".md",), None),
    # --- YAZILIM ---
    ("yazilim", "donnemartin__system-design-primer.zip", (".md",), None),
    ("yazilim", "trekhleb__javascript-algorithms.zip", (".md",), None),
    ("yazilim", "rust-lang__book.zip", (".md",), None),                       # Rust
    ("yazilim", "golang__go.zip", (".md", ".rst"), lambda y: y.startswith("doc/")),  # Go
    ("yazilim", "dotnet__docs.zip", (".md",),                                 # C#/.NET
     lambda y: any(y.startswith("docs/" + s)
                   for s in ("csharp", "standard", "fundamentals", "core"))),
    ("guvenlik", "trimstray__nginx-admins-handbook.zip", (".md",), None),     # web sunucu guvenligi
    ("guvenlik", "kubernetes__website.zip", (".md",),                        # k8s/bulut
     lambda y: y.startswith("content/en/docs/")),
    # Python resmi referansi: cpython Doc/*.rst (whatsnew/ surum notlarini atla)
    ("kod", "python__cpython.zip", (".rst",),
     lambda y: y.startswith("Doc/") and not y.startswith("Doc/whatsnew")),
    ("kod", "fastapi__fastapi.zip", (".md",), lambda y: y.startswith("docs/en/")),
    ("kod", "django__django.zip", (".txt",), lambda y: y.startswith("docs/")),
    ("yazilim", "getify__You-Dont-Know-JS.zip", (".md",), None),
    ("yazilim", "TheAlgorithms__Python.zip", (".md",), None),
]
MITRE = ("guvenlik", "enterprise-attack.json")


def kelimele(metin):
    return re.findall(r"[a-zA-Z0-9_]+", metin.lower())


def md_temizle(metin):
    metin = re.sub(r"```.*?```", " [kod] ", metin, flags=re.S)
    metin = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", metin)
    metin = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", metin)
    metin = re.sub(r"<[^>]+>", "", metin)
    return metin


def rst_temizle(metin):
    """reStructuredText (.rst/.txt) artiklarini hafifce ayikla."""
    metin = re.sub(r"::\n", ":\n", metin)
    metin = re.sub(r":[a-z:]+:`~?([^`<]+?)(?:\s*<[^>]*>)?`", r"\1", metin)  # :func:`x` -> x
    metin = re.sub(r"\.\. [a-z-]+::.*", "", metin)  # yonerge satirlarini at
    metin = re.sub(r"^\s*\.\..*$", "", metin, flags=re.M)
    return metin


def parcala(metin, kaynak, ust="md"):
    metin = rst_temizle(metin) if ust in ("rst", "txt") else md_temizle(metin)
    bloklar = re.split(r"\n\s*\n", metin)
    parcalar, tampon = [], ""
    for b in bloklar:
        b = b.strip()
        if not b:
            continue
        if len(tampon) + len(b) < PARCA_MAX:
            tampon += ("\n\n" + b) if tampon else b
        else:
            if len(tampon) >= PARCA_MIN:
                parcalar.append((tampon, kaynak))
            tampon = b
    if len(tampon) >= PARCA_MIN:
        parcalar.append((tampon, kaynak))
    return parcalar


def zipten_parcalar(zip_yolu, uzantilar, yol_filtresi):
    parcalar = []
    etiket_kok = zip_yolu.stem.split("__")[-1]
    with zipfile.ZipFile(zip_yolu) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.endswith(tuple(uzantilar)):
                continue
            if not (200 <= info.file_size <= 400_000):
                continue
            yol = info.filename.split("/", 1)[-1]
            if _ceviri_mi(yol):   # Ingilizce-disi ceviri klasoru/dosyasi -> atla
                continue
            if yol_filtresi is not None and not yol_filtresi(yol):
                continue
            try:
                metin = zf.read(info).decode("utf-8", errors="ignore")
            except Exception:
                continue
            ust = yol.rsplit(".", 1)[-1]
            parcalar.extend(parcala(metin, f"{etiket_kok}:{yol}", ust))
    return parcalar


def mitre_parcalar(yol):
    parcalar = []
    veri = json.loads(yol.read_text(encoding="utf-8"))
    for nesne in veri.get("objects", []):
        if nesne.get("type") != "attack-pattern":
            continue
        ad = nesne.get("name", "")
        aciklama = nesne.get("description", "")
        if not ad or len(aciklama) < PARCA_MIN:
            continue
        metin = f"MITRE ATT&CK Teknigi: {ad}\n{md_temizle(aciklama)}"
        if nesne.get("x_mitre_detection"):
            metin += "\nTespit: " + md_temizle(nesne["x_mitre_detection"])
        parcalar.append((metin[:PARCA_MAX * 2], "MITRE:" + ad))
    return parcalar


def cwe_parcalar(zip_yolu):
    """CWE (Common Weakness Enumeration) XML'inden zafiyet siniflarini cikarir:
    her CWE'nin adi, aciklamasi ve azaltma yontemi. Guvenlik zafiyetlerinin
    kanonik katalogu."""
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(zip_yolu) as zf:
        xml_ad = next((n for n in zf.namelist() if n.endswith(".xml")), None)
        if not xml_ad:
            return []
        veri = zf.read(xml_ad)
    kok = ET.fromstring(veri)
    yerel = lambda e: e.tag.rsplit("}", 1)[-1]
    metin = lambda e: " ".join(t.strip() for t in e.itertext() if t and t.strip())
    parcalar = []
    for w in kok.iter():
        if yerel(w) != "Weakness":
            continue
        wid, ad = w.get("ID"), w.get("Name")
        if not wid or not ad:
            continue
        aciklama, azaltma = "", ""
        for c in w:
            ly = yerel(c)
            if ly in ("Description", "Extended_Description"):
                aciklama += " " + metin(c)
            elif ly == "Potential_Mitigations" and not azaltma:
                azaltma = metin(c)[:600]
        govde = f"CWE-{wid}: {ad}\n{aciklama.strip()[:1100]}"
        if azaltma:
            govde += "\nAzaltma: " + azaltma
        if len(govde) >= PARCA_MIN:
            parcalar.append((govde, f"CWE-{wid}:{ad}"))
    return parcalar


def ana():
    RAG_YOLU.parent.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("RAG bilgi tabani kuruluyor (GUVENLIK + YAZILIM)")
    print("=" * 60)

    tum = []
    for alt, zad, uz, filt in KAYNAKLAR:
        zp = RAW / alt / zad
        if not zp.exists():
            print(f"  [atla] {zad} yok")
            continue
        p = zipten_parcalar(zp, uz, filt)
        print(f"  {zad:<45} {len(p):>6} parca")
        tum.extend(p)

    mp = RAW / MITRE[0] / MITRE[1]
    if mp.exists():
        p = mitre_parcalar(mp)
        print(f"  {MITRE[1]:<45} {len(p):>6} parca")
        tum.extend(p)

    cwe_zip = RAW / "guvenlik" / "cwe.zip"
    if cwe_zip.exists():
        p = cwe_parcalar(cwe_zip)
        print(f"  {'cwe.zip (CWE zafiyet katalogu)':<45} {len(p):>6} parca")
        tum.extend(p)

    if len(tum) > AZAMI_PARCA:
        print(f"\n  {len(tum)} -> {AZAMI_PARCA}'e kirpiliyor")
        random.Random(42).shuffle(tum)
        tum = tum[:AZAMI_PARCA]

    print(f"\nToplam {len(tum)} parca tokenlaniyor ve BM25 index kuruluyor...")
    metinler = [m for m, _ in tum]
    kaynaklar = [k for _, k in tum]
    tokenli = [kelimele(m) for m in tqdm(metinler, desc="tokenleniyor")]
    bm25 = BM25Okapi(tokenli)

    print("Kaydediliyor...")
    with open(RAG_YOLU, "wb") as f:
        pickle.dump({"bm25": bm25, "metinler": metinler, "kaynaklar": kaynaklar}, f)
    print(f"[OK] Bilgi tabani hazir: {RAG_YOLU} "
          f"({RAG_YOLU.stat().st_size // 1024 // 1024} MB, {len(metinler)} parca)")
    print("Sonraki: python src/rag_embed_kur.py  (anlamsal embedding)")


if __name__ == "__main__":
    ana()
