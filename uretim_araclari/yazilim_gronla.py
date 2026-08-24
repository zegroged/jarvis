"""YAZILIM repolarindan (data/raw/{yazilim,kod,egitim,tr-teknik}) zengin dokuman cikarir.

Simdiye kadar sadece GUVENLIK damitildi; bu, YAZILIM pratisyen bilgisini (sistem tasarimi,
dil incelikleri, algoritma, best-practice, mimari) damitma kaynagi yapar. Dil + meta filtresi
uygulanir, yol-bazli deterministik id (yz- oneki), zaten damitilmis atlanir.

Cikti: uretim_araclari/yazilim_kaynak.json
"""
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
RAW = KOK / "data" / "raw"
QA_DIR = KOK / "data" / "processed" / "instruct_tr"
HEDEF = KOK / "uretim_araclari" / "yazilim_kaynak.json"

# (kisa_etiket, alt_klasor/zip, azami) — icerik-zengin teknik markdown repolari
SOURCES = [
    ("sysdesign", "yazilim/donnemartin__system-design-primer.zip", 120),
    ("sysdesign2", "yazilim/karanpratapsingh__system-design.zip", 80),
    ("ydkjs", "yazilim/getify__You-Dont-Know-JS.zip", 80),
    ("rustbook", "yazilim/rust-lang__book.zip", 120),
    ("rustnomicon", "yazilim/rust-lang__nomicon.zip", 50),
    ("rustref", "yazilim/rust-lang__reference.zip", 80),
    ("nodebest", "yazilim/goldbergyoni__nodebestpractices.zip", 80),
    ("profprog", "yazilim/charlax__professional-programming.zip", 60),
    ("epsk", "yazilim/mtdvio__every-programmer-should-know.zip", 60),
    ("scalability", "yazilim/binhnguyennus__awesome-scalability.zip", 40),
    ("dblearn", "yazilim/pingcap__awesome-database-learning.zip", 40),
    ("engpractices", "egitim/google__eng-practices.zip", 40),
    ("airbnbjs", "egitim/airbnb__javascript.zip", 40),
    ("mdn", "yazilim/mdn__content.zip", 200),
    ("docker", "yazilim/docker__docs.zip", 100),
    ("dotnet", "yazilim/dotnet__docs.zip", 120),
    ("devops", "yazilim/bregman-arie__devops-exercises.zip", 60),
    ("designpat", "yazilim/DovAmir__awesome-design-patterns.zip", 30),
    ("istihza", "tr-teknik/yazbel__python-istihza.zip", 60),
]
MIN, MAX = 2200, 14000
KES = 5500

DIL_KODLARI = {
    "es", "fr", "de", "el", "el-gr", "gr", "fa", "ar", "ru", "pt", "pt-pt", "pt-br",
    "zh", "zh-cn", "zh-tw", "ja", "ko", "id", "hi", "ml", "it", "pl", "uk",
    "vi", "he", "nl", "cs", "ro", "bg", "sr", "hr", "sk", "sl", "da", "sv", "no",
    "nb", "fi", "hu", "th", "bn", "ur", "ca", "az", "kk", "uz", "sw", "fil",
    # TAM-ISIM ceviri klasorleri (nodebest/rust vb. repolar dil-kodu yerine tam isim kullanir)
    "japanese", "french", "basque", "russian", "polish", "portuguese",
    "brazilian-portuguese", "german", "spanish", "chinese", "korean", "italian",
    "dutch", "arabic", "hebrew", "vietnamese", "ukrainian", "czech", "greek",
    "persian", "indonesian", "hindi", "thai", "romanian", "hungarian",
    "simplified-chinese", "traditional-chinese", "turkish-tr",
}
# NOT: 'tr' dil kodunu ELEME (Turkce icerik istihza gibi repolarda degerli olabilir)


# Tam-isim diller: yol'un HERHANGI yerinde substring olarak aranir (nodebest README.japanese.md
# gibi dosya-adi-eki ceviriler icin). Kisa kodlar (fr/ja) substring aranamaz (framework->fr yanlis pozitif).
TAM_ISIM_DIL = {
    "japanese", "french", "basque", "russian", "polish", "portuguese", "german",
    "spanish", "chinese", "korean", "italian", "dutch", "arabic", "hebrew",
    "vietnamese", "ukrainian", "czech", "greek", "persian", "indonesian", "hindi",
    "thai", "romanian", "hungarian", "brazilian", "simplified", "traditional",
    "indonesia", "espanol", "deutsch", "francais", "italiano", "nederlands",
}


def ceviri_mi(yol):
    y = yol.lower()
    segler = y.split("/")
    if "en" in segler or "en-us" in segler:
        return False
    if any(s in DIL_KODLARI for s in segler):
        return True
    return any(t in y for t in TAM_ISIM_DIL)


def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def slugla(yol):
    parcalar = [p for p in yol.split("/")[1:] if p]
    kuyruk = "-".join(parcalar[-3:])
    kuyruk = re.sub(r"\.(md|markdown|rst|mdx)$", "", kuyruk, flags=re.I)
    kuyruk = re.sub(r"[^a-zA-Z0-9]+", "-", kuyruk).strip("-").lower()
    return kuyruk[:60] or "doc"


def baslik(metin, yol):
    for satir in metin.splitlines():
        s = satir.strip().lstrip("#").strip()
        if s:
            return temizle(s[:120])
    return Path(yol).stem


def tamam(did):
    return (QA_DIR / f"yazilim_{did}_damit.jsonl").exists()


META = ("readme", "summary", "_sidebar", "changelog", "/.git", "contributing",
        "license", "code-of-conduct", "/index.md", "/toc", "glossary", "acknowledg",
        "foreword", "preface", "credits", "sponsor", "roadmap", "citation",
        "thanks", "translation", "-toc", "00-introduction", "chapter00", "/appendix",
        "code_of_conduct", "/.github/", "01-installation", "hello-cargo", "hello-world")


def main():
    sonuc = []
    gorulen_id = set()
    gorulen_hash = set()
    for etiket, zipyol, azami in SOURCES:
        zp = RAW / zipyol
        if not zp.exists():
            print(f"  YOK: {zipyol}")
            continue
        n = 0
        try:
            with zipfile.ZipFile(zp) as zf:
                for info in sorted(zf.infolist(), key=lambda i: -i.file_size):
                    if n >= azami:
                        break
                    ad = info.filename.lower()
                    if not (ad.endswith(".md") or ad.endswith(".markdown") or ad.endswith(".mdx") or ad.endswith(".rst")):
                        continue
                    if any(x in ad for x in META):
                        continue
                    if ceviri_mi(info.filename):
                        continue
                    if not (MIN <= info.file_size <= MAX):
                        continue
                    did = f"yz-{etiket}-{slugla(info.filename)}"
                    if did in gorulen_id:
                        did = f"{did}-{n}"
                    if did in gorulen_id or tamam(did):
                        continue
                    try:
                        metin = zf.read(info).decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    if "\x00" in metin[:2000]:
                        continue
                    metin = temizle(metin)[:KES]
                    if len(metin) < 600:
                        continue
                    h = hash(metin[:1000])
                    if h in gorulen_hash:
                        continue
                    gorulen_hash.add(h)
                    gorulen_id.add(did)
                    sonuc.append({
                        "id": did, "kaynak": etiket,
                        "baslik": baslik(metin, info.filename),
                        "yol": "/".join(info.filename.split("/")[1:]),
                        "metin": metin,
                    })
                    n += 1
        except zipfile.BadZipFile:
            continue
        print(f"  {etiket:<12} yeni:{n}")

    HEDEF.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nCikarilan YAZILIM dokuman: {len(sonuc)}")
    print(f"[OK] -> {HEDEF} ({HEDEF.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
